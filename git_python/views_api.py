# -*- coding: utf-8 -*-
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, generics, filters, viewsets
from assetv2.settingsapi import *
from git import Repo
from git.exc import *
from git_python.utils.Utils import *
from git_python.serializers import *
from git_python.permissions import BootShPermission
from git_python.filters import *
from util.httplib import httpcall2
from urlparse import urlunparse
import json
import re
import redis
import shutil


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes((BootShPermission,))
def crud(request):
    working_tree_dir = request.REQUEST.get('working_tree_dir', request.data.get('working_tree_dir'))
    path = request.REQUEST.get('path', request.data.get('path'))
    content = request.REQUEST.get('content', request.data.get('content'))
    file_name = os.path.join(working_tree_dir, path)
    if request.method == 'GET':
        if os.path.isfile(file_name):
            with open(file_name) as f:
                content = f.read()
        return Response(status=status.HTTP_200_OK, data={'msg': content})
    elif request.method == 'POST':
        if not os.path.isfile(file_name):
            os.makedirs(os.path.dirname(file_name))
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '文件已经存在，不允许创建'})
        with open(file_name, 'w') as f:
            try:
                f.write(content)
            except IOError, e:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': e.args})
        repo = Repo(working_tree_dir)
        repo.git.add(path)
        return Response(status=status.HTTP_201_CREATED, data={'msg': '创建文件成功'})
    elif request.method == 'PUT':
        if not os.path.isfile(file_name):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '文件不存在，无法更新'})
        with open(file_name, 'w') as f:
            try:
                f.write(content)
            except IOError, e:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': e.args})
        repo = Repo(working_tree_dir)
        repo.git.add(path)
        return Response(status=status.HTTP_200_OK, data={'msg': '更新文件成功'})
    elif request.method == 'DELETE':
        if not os.path.isfile(file_name):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '文件不存在，无法删除'})
        repo = Repo(working_tree_dir)
        repo.git.rm('-f', path)
        # shutil.rmtree(os.path.dirname(path), True)
        return Response(status=status.HTTP_200_OK, data={'msg': '删除文件成功'})


@api_view(['GET'])
@permission_classes((AllowAny,))
def boot_sh_tree(request):
    working_tree_dir = request.GET['working_tree_dir']
    letter_list = request.GET['letter_list']
    default_args = ('--cached', '--abbrev=40', '--full-index', '--raw')
    # default_args = ('--abbrev=40', '--full-index', '--raw')
    repo = Repo(working_tree_dir)
    dirty_list = []
    dirty_dict = dict()
    for entry in repo.git.diff(*default_args).splitlines():
        entry_list = entry.split()
        letter, path = entry_list[4:6]
        if letter not in json.loads(letter_list):
            continue
        if path == 'boot.sh':
            dirty_list.append({
                'title': path,
                'path': path
            })
            continue
        try:
            site_name, app_name, file_name = path.split('/')
        except ValueError:
            continue
        if file_name != 'boot.sh':
            continue
        dirty_dict[site_name] = dirty_dict.get(site_name, dict())
        dirty_dict[site_name][app_name] = dirty_dict[site_name].get(app_name, [])
        dirty_dict[site_name][app_name].append({'path': path, 'title': file_name})
    for site_name in dirty_dict:
        site_dict = {'title': site_name, 'folder': True, 'expanded': True, 'children': []}
        for app_name in dirty_dict[site_name]:
            app_dict = {'title': app_name, 'folder': True, 'expanded': True, 'children': []}
            for file_dict in dirty_dict[site_name][app_name]:
                app_dict['children'].append({
                    'title': file_dict['title'],
                    'path': file_dict['path']
                })
            site_dict['children'].append(app_dict)
        dirty_list.append(site_dict)
    return Response(status=status.HTTP_200_OK, data=dirty_list)


@api_view(['POST'])
@permission_classes((BootShPermission,))
def commit(request):
    working_tree_dir = request.POST['working_tree_dir']
    msg = request.POST['msg']
    repo = Repo(working_tree_dir)
    if not repo.is_dirty(index=True, working_tree=False, untracked_files=False):
        return Response(status=status.HTTP_200_OK, data={'msg': '没有需要提交的内容'})
    if repo.index.unmerged_blobs():
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '存在冲突的文件，禁止提交'})
    repo.git.stash('save')
    # repo.remotes.origin.pull()
    repo.git.pull()
    try:
        repo.git.stash('pop')
    except GitCommandError:
        repo.git.stash('clear')
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '生成冲突的文件，禁止提交'})
    for blob in changes_to_be_committed(repo):
        if os.path.isfile(os.path.join(working_tree_dir, blob)):
            repo.git.add(blob)
        else:
            repo.git.rm('--cached', blob)
    # dirty_dict = changes_to_be_committed(repo)
    # for letter in dirty_dict:
    #     if letter in ['A', 'M']:
    #         for path in dirty_dict[letter]:
    #             repo.git.add(path)
    #     elif letter in ['D']:
    #         for path in dirty_dict[letter]:
    #             repo.git.rm('--cached', path)
    repo.index.commit(msg)
    # repo.remotes.origin.push()
    try:
        repo.git.push()
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '提交失败'})
    return Response(status=status.HTTP_201_CREATED, data={'msg': '提交成功'})


# @api_view(['POST'])
# @permission_classes((AllowAny, ))
# def log(request):
#     working_tree_dir = request.POST['working_tree_dir']
#     number = request.POST['number']
#     blob = request.POST.get('blob')
#     repo = Repo(working_tree_dir)
#     origin_log_list = repo.heads.master.log()[-1 * int(number):]
#     origin_log_list.reverse()
#     formatted_log_list = [
#         {
#             'hash': entry.newhexsha,
#             'author': entry.actor.name,
#             'message': entry.message,
#             'date_time': stamp2str(entry.time[0])
#         } for entry in origin_log_list]
#     return Response(status=status.HTTP_200_OK, data=formatted_log_list)


@api_view(['GET'])
@permission_classes((AllowAny,))
def log(request):
    working_tree_dir = request.GET['working_tree_dir']
    path = request.GET.get('path')
    page = int(request.GET.get('page'))
    page_size = int(request.GET.get('page_size'))
    repo = Repo(working_tree_dir)
    default_args = ['--date=iso', '--pretty=format:%H %an %ad %s']
    if path:
        default_args.append(path)
    origin_log_list = repo.git.log(*default_args).splitlines()
    formatted_log_list = []
    for origin_log in origin_log_list[(page - 1) * page_size: (page - 1) * page_size + page_size]:
        try:
            hash, author, date, time, timezone, message = re.split('\s', origin_log, 5)
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=origin_log)
        formatted_log_list.append({
            'path': path,
            'hash': hash,
            'author': author,
            'message': message,
            'date': '{0} {1}'.format(date, time)
        })
    return Response(status=status.HTTP_200_OK, data={'count': len(origin_log_list), 'results': formatted_log_list})


@api_view(['GET'])
@permission_classes((AllowAny,))
def unmerged_blobs(request):
    working_tree_dir = request.REQUEST.get('working_tree_dir')
    path = request.REQUEST.get('path')
    repo = Repo(working_tree_dir)
    unmerged_blobs_list = repo.index.unmerged_blobs().get(path)
    unmerged_blobs_dict = dict()
    for stage, blob in unmerged_blobs_list:
        unmerged_blobs_dict[stage] = blob.data_stream.read()
    return Response(status=status.HTTP_200_OK, data=unmerged_blobs_dict)


@api_view(['PUT'])
@permission_classes((BootShPermission,))
def checkout(request):
    stage_dict = {'2': '--ours', '3': '--theirs'}
    working_tree_dir = request.data.get('working_tree_dir')
    path = request.data.get('path')
    stage = request.data.get('stage')
    repo = Repo(working_tree_dir)
    try:
        repo.git.checkout(stage_dict[stage], path)
        repo.git.add(path)
        return Response(status=status.HTTP_200_OK, data={'msg': '解决冲突成功'})
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '解决冲突失败'})


@api_view(['PUT'])
@permission_classes((BootShPermission,))
def reset(request):
    working_tree_dir = request.data.get('working_tree_dir')
    path = request.data.get('path')
    repo = Repo(working_tree_dir)
    try:
        repo.git.reset('HEAD', path)
    except GitCommandError:
        pass
    try:
        repo.git.checkout('--', path)
        return Response(status=status.HTTP_200_OK, data={'msg': '还原成功'})
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '还原失败'})


@api_view(['GET'])
@permission_classes((AllowAny,))
def diff(request):
    working_tree_dir = request.GET.get('working_tree_dir')
    path = request.GET.get('path')
    revision = request.GET.get('revision')
    repo = Repo(working_tree_dir)
    commit = repo.commit(revision)
    git_blob = git_blob_from_commit(commit, path)
    parents = commit.parents
    if len(parents) == 0:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '该文件没有历史修改记录，不作比较'})
    elif len(parents) > 1:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '该文件通过合并而成，不作比较'})
    else:
        last_git_blob = git_blob_from_commit(parents[0], path)
        return Response(status=status.HTTP_200_OK, data={
            'commit': git_blob.data_stream.read() if git_blob else None,
            'last_commit': last_git_blob.data_stream.read() if last_git_blob else None
        })


@api_view(['GET'])
@permission_classes((AllowAny,))
def diff_cached(request):
    working_tree_dir = request.GET.get('working_tree_dir')
    path = request.GET.get('path')
    repo = Repo(working_tree_dir)
    index_git_blob = git_blob_from_index(repo.index, path)
    commit_git_blob = git_blob_from_commit(repo.commit('HEAD'), path)
    return Response(status=status.HTTP_200_OK, data={
        'index': index_git_blob.data_stream.read() if index_git_blob else None,
        'commit': commit_git_blob.data_stream.read() if commit_git_blob else None
    })


@api_view(['GET'])
@permission_classes((AllowAny,))
def boot_sh_puppet(request):
    puppet_dict = {0: 'boot.sh'}
    for git_boot_sh_app in GitBootShApp.objects.all():
        app = git_boot_sh_app.app
        puppet_dict[app.id] = os.path.join(app.site.name, app.name, 'boot.sh')
    return Response(status=status.HTTP_200_OK, data=puppet_dict)


@api_view(['POST'])
@permission_classes((AllowAny,))
def boot_sh_web_hook_puppet(request):
    web_hook_dict = request.data
    for puppet_master in GIT['BOOT_SH']['PUPPET_MASTER_LIST']:
        code, response = httpcall2('http://%s%s' % (puppet_master, GIT['BOOT_SH']['PUPPET_URL']), method='POST')
        web_hook_dict['puppet'] = web_hook_dict.get('puppet', dict())
        web_hook_dict['puppet'][puppet_master] = json.loads(response) if code is not None and code < 400 else dict()
        web_hook_dict['puppet'][puppet_master]['code'] = code
    r = redis.Redis(host=REDIS["HOST"], port=REDIS["PORT"], db=3)
    r.set(web_hook_dict['after'], json.dumps(web_hook_dict))
    return Response(status=status.HTTP_200_OK, data=True)


@api_view(['GET'])
@permission_classes((AllowAny,))
def boot_sh_puppet_result(request):
    hash = request.GET.get('hash')
    r = redis.Redis(host=REDIS["HOST"], port=REDIS["PORT"], db=3)
    data = r.get(hash)
    if data:
        return Response(status=status.HTTP_200_OK, data=json.loads(data))
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '未查到相关信息'})


class GitBootShAppList(generics.ListCreateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * status    -       状态值（状态值为0、1、2、3可废弃，4、5、6状态无法废弃）

    输出参数：

    * status        -   当前状态值
    """
    queryset = GitBootShApp.objects.all()
    serializer_class = GitBootShAppSerializer
    permission_classes = (AllowAny, )


class GitBootShAppDetail(generics.RetrieveDestroyAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * status    -       状态值（状态值为0、1、2、3可废弃，4、5、6状态无法废弃）

    输出参数：

    * status        -   当前状态值
    """
    queryset = GitBootShApp.objects.all()
    serializer_class = GitBootShAppSerializer
    permission_classes = (BootShPermission,)
    lookup_field = 'app_id'


class GitAppViewSet(viewsets.ModelViewSet):
    permission_classes = (BootShPermission,)
    queryset = GitApp.objects.all()
    serializer_class = GitAppSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    filter_class = GitAppFilter
    search_fields = ('app__name',)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        content = self.request.DATA.get('content')
        if content is None:
            return
        working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], self.request.user.username)
        file_name = (instance.room.name + '_' if instance.room else '') + instance.type.name
        git_path = '/'.join([instance.app.site.name, instance.app.name, file_name]) if instance.app else file_name
        file_path = os.path.join(working_tree_dir, git_path)
        try:
            if not os.path.isfile(file_path):
                file_dir = os.path.dirname(file_path)
                if not os.path.isdir(file_dir):
                    os.makedirs(file_dir)
            else:
                raise Exception(u'文件已经存在，不允许创建')
            with open(file_path, 'w') as f:
                f.write(content)
            repo = Repo(working_tree_dir)
            repo.git.add(git_path)
        except Exception, e:
            instance.delete()
            raise Exception(e.args[0])

    def perform_destroy(self, instance):
        instance.delete()
        working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], self.request.user.username)
        file_name = (instance.room.name + '_' if instance.room else '') + instance.type.name
        git_path = '/'.join([instance.app.site.name, instance.app.name, file_name]) if instance.app else file_name
        file_path = os.path.join(working_tree_dir, git_path)
        if not os.path.isfile(file_path):
            raise Exception(u'文件不存在，无法删除')
        repo = Repo(working_tree_dir)
        repo.git.rm('-f', git_path)


@api_view(['GET', 'PUT'])
@permission_classes((BootShPermission,))
def git_app_file(request, pk):
    git_app_obj = GitApp.objects.get(id=pk)
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    file_name = (git_app_obj.room.name + '_' if git_app_obj.room else '') + git_app_obj.type.name
    git_path = '/'.join([git_app_obj.app.site.name, git_app_obj.app.name, file_name]) if git_app_obj.app else file_name
    content = request.DATA.get('content')
    file_path = os.path.join(working_tree_dir, git_path)
    if request.method == 'GET':
        if os.path.isfile(file_path):
            with open(file_path) as f:
                content = f.read()
        return Response(status=status.HTTP_200_OK, data={'detail': content})
    elif request.method == 'PUT':
        if not os.path.isfile(file_path):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '文件不存在，无法更新'})
        with open(file_path, 'w') as f:
            try:
                f.write(content)
            except IOError, e:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': e.args[0]})
        repo = Repo(working_tree_dir)
        repo.git.add(git_path)
        return Response(status=status.HTTP_200_OK, data={'detail': '更新文件成功'})


@api_view(['GET'])
@permission_classes((AllowAny,))
def git_app_tree(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    letter = request.GET.get('letter')
    default_args = ('--cached', '--abbrev=40', '--full-index', '--raw')
    repo = Repo(working_tree_dir)
    # 将所有文件转换为一个字典
    dirty_dict = dict()
    for entry in repo.git.diff(*default_args).splitlines():
        entry_list = entry.split()
        real_letter, path = entry_list[4:6]
        if real_letter != letter:
            continue
        my_dirty_dict = dirty_dict
        while True:
            path_list = path.split('/', 1)
            if len(path_list) > 1:
                p1, p2 = path_list
                my_dirty_dict[p1] = my_dirty_dict.get(p1, dict())
                path = p2
                my_dirty_dict = my_dirty_dict[p1]
            else:
                my_dirty_dict[path_list[0]] = None
                break
    # 将字典转换为tree控件识别的格式
    dirty_list = [get_recursive_node_dict(title, dirty_dict[title]) for title in dirty_dict]
    return Response(status=status.HTTP_200_OK, data=dirty_list)


@api_view(['POST'])
@permission_classes((BootShPermission,))
def commit_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    msg = request.POST['msg']
    repo = Repo(working_tree_dir)
    if not repo.is_dirty(index=True, working_tree=True, untracked_files=False):
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '没有需要提交的内容'})
    if repo.index.unmerged_blobs():
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '存在冲突的文件，禁止提交'})
    repo.git.stash('save')
    repo.git.pull()
    try:
        repo.git.stash('pop')
    except GitCommandError:
        repo.git.stash('clear')
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '生成冲突的文件，禁止提交'})
    default_args = ('--abbrev=40', '--full-index', '--raw')
    dirty_list = [entry.split()[-1] for entry in repo.git.diff(*default_args).splitlines()]
    for blob in dirty_list:
        if os.path.isfile(os.path.join(working_tree_dir, blob)):
            repo.git.add(blob)
        else:
            repo.git.rm('--cached', blob)
    repo.index.commit(msg)
    try:
        repo.git.push()
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '提交失败'})
    GitApp.objects.filter(created_by=request.user, valid=False).update(valid=True)
    return Response(status=status.HTTP_201_CREATED, data={'detail': '提交成功'})


@api_view(['PUT'])
@permission_classes((BootShPermission,))
def checkout_v2(request):
    stage_dict = {
        '2': '--ours',
        '3': '--theirs'
    }
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.data.get('path')
    stage = request.data.get('stage')
    repo = Repo(working_tree_dir)
    try:
        repo.git.checkout(stage_dict[stage], path)
        repo.git.add(path)
        return Response(status=status.HTTP_200_OK, data={'detail': '解决冲突成功'})
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '解决冲突失败'})


@api_view(['GET'])
@permission_classes((AllowAny,))
def unmerged_blobs_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.REQUEST.get('path')
    repo = Repo(working_tree_dir)
    unmerged_blobs_list = repo.index.unmerged_blobs().get(path)
    unmerged_blobs_dict = dict()
    for stage, blob in unmerged_blobs_list:
        unmerged_blobs_dict[stage] = blob.data_stream.read()
    return Response(status=status.HTTP_200_OK, data=unmerged_blobs_dict)


@api_view(['GET'])
@permission_classes((AllowAny,))
def log_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.GET.get('path')
    page = int(request.GET.get('page'))
    page_size = int(request.GET.get('page_size'))
    repo = Repo(working_tree_dir)
    default_args = ['--date=iso', '--pretty=format:%H%n%an%n%ad%n%s']
    if path:
        default_args.append(path)
    origin_log_list = repo.git.log(*default_args).splitlines()
    formatted_log_list = []
    formatted_log_dict = dict()
    item_dict = {
        0: 'hash',
        1: 'author',
        2: 'date',
        3: 'message'
    }
    i = 0
    for origin_log in origin_log_list:
        formatted_log_dict[item_dict[i]] = origin_log
        i += 1
        if i > len(item_dict) - 1:
            formatted_log_dict['path'] = path
            formatted_log_list.append(formatted_log_dict)
            formatted_log_dict = dict()
            i = 0
    return Response(status=status.HTTP_200_OK, data={'count': len(formatted_log_list), 'results': formatted_log_list[(page - 1) * page_size: (page - 1) * page_size + page_size]})


@api_view(['GET'])
@permission_classes((AllowAny,))
def diff_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.GET.get('path')
    revision = request.GET.get('revision')
    repo = Repo(working_tree_dir)
    default_args = ['--pretty=format:%H', path]
    revision_list = repo.git.log(*default_args).splitlines()
    revision_position = revision_list.index(revision)
    last_revision = None if revision_position == len(revision_list)-1 else revision_list[revision_position+1]
    git_blob = git_blob_from_commit(repo.commit(revision), path)
    last_git_blob = git_blob_from_commit(repo.commit(last_revision), path) if last_revision else None
    return Response(status=status.HTTP_200_OK, data={
        'commit': git_blob.data_stream.read() if git_blob else '',
        'last_commit': last_git_blob.data_stream.read() if last_git_blob else ''
    })


@api_view(['POST'])
@permission_classes((AllowAny,))
def web_hook_puppet(request):
    web_hook_dict = request.data
    puppet_dict = dict()
    for git_app_obj in GitApp.objects.filter(valid=True):
        app = git_app_obj.app
        type = git_app_obj.type
        room = git_app_obj.room
        app_id = app.id if app else 0
        if type.room_property:
            type_name = '_'.join([room.name, type.name])
            git_path = '/'.join([app.site.name, app.name, type_name]) if app else type_name
            puppet_dict[type.name] = puppet_dict.get(type.name, dict())
            puppet_dict[type.name][app_id] = puppet_dict[type.name].get(app_id, dict())
            puppet_dict[type.name][app_id][room.name] = git_path
        else:
            git_path = '/'.join([app.site.name, app.name, type.name]) if app else type.name
            puppet_dict[type.name] = puppet_dict.get(type.name, dict())
            puppet_dict[type.name][app_id] = git_path
    for puppet_master in GIT['COMMON']['PUPPET_MASTER_LIST']:
        url = urlunparse(('http', puppet_master, GIT['COMMON']['PUPPET_URL'], '', '', ''))
        code, response = httpcall2(url, method='POST', body={'data': json.dumps(puppet_dict)})
        web_hook_dict['puppet'] = web_hook_dict.get('puppet', dict())
        web_hook_dict['puppet'][puppet_master] = json.loads(response) if code is not None and code < 400 else dict()
        web_hook_dict['puppet'][puppet_master]['code'] = code
    r = redis.Redis(host=REDIS["HOST"], port=REDIS["PORT"], db=3)
    r.set(web_hook_dict['after'], json.dumps(web_hook_dict))
    return Response(status=status.HTTP_200_OK, data=web_hook_dict)


@api_view(['GET'])
@permission_classes((AllowAny,))
def diff_cached_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.GET.get('path')
    repo = Repo(working_tree_dir)
    index_git_blob = git_blob_from_index(repo.index, path)
    commit_git_blob = git_blob_from_commit(repo.commit('HEAD'), path)
    return Response(status=status.HTTP_200_OK, data={
        'index': index_git_blob.data_stream.read() if index_git_blob else None,
        'commit': commit_git_blob.data_stream.read() if commit_git_blob else None
    })


@api_view(['PUT'])
@permission_classes((BootShPermission,))
def reset_v2(request):
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], request.user.username)
    path = request.data.get('path')
    git_app = request.data.get('git_app')
    repo = Repo(working_tree_dir)
    try:
        repo.git.reset('HEAD', path)
    except GitCommandError:
        pass
    try:
        repo.git.checkout('--', path)
    except GitCommandError:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '还原失败'})
    if git_app is not None:
        try:
            site_name, app_name, file_name = path.split('/')
        except Exception, e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '路径%s无法解析' % path})
        app_obj = None
        for app in App.objects.filter(name=app_name):
            if app.site.name == site_name:
                app_obj = app
                break
        if app_obj is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '路径%s找不到对应的Pool' % path})
        file_name_list = file_name.split('_', 1)
        if len(file_name_list) == 1:
            file_type = file_name
            room_obj = None
        else:
            room_name, file_type = file_name_list
            room_queryset = Room.objects.filter(name=room_name)
            if room_queryset is None:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '机房名称%s无法识别' % room_name})
            else:
                room_obj = room_queryset.first()
        file_type_queryset = GitFileType.objects.filter(name=file_type)
        if file_type_queryset is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': '文件类型%s无法识别' % file_type})
        else:
            file_type_obj = file_type_queryset.first()
        GitApp.objects.create(app=app_obj, type=file_type_obj, room=room_obj)
    return Response(status=status.HTTP_200_OK, data={'detail': '还原成功'})
