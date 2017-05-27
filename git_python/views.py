# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response
from rest_framework.authtoken.models import Token
from assetv2.settingsdeploy import STATIC_URL, GIT
from users.usercheck import login_required
from git import Repo
from git.exc import *
from git_python.utils.Utils import changes_to_be_committed
from cmdb.models import App, Room
from git_python.models import GitApp, GitFileType
import shutil
import os
from util import webmenu


def my_render(request, template, context={}):
    token_obj = Token.objects.get(user_id=request.user.id)
    token = token_obj.key if token_obj else None
    context['API_TOKEN'] = token
    context['UID'] = request.user.id if request.user.id else 0
    context['USER'] = request.user
    context['STATIC_URL'] = STATIC_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)


@login_required
def boot_sh(request):
    username = request.user.username
    working_tree_dir = os.path.join(GIT['BOOT_SH']['LOCAL_DIR'], username)
    error = False
    try:
        repo = Repo(working_tree_dir)
    except NoSuchPathError:
        error = True
    except InvalidGitRepositoryError:
        shutil.rmtree(working_tree_dir, True)
        error = True
    if error:
        repo = Repo.clone_from(GIT['BOOT_SH']['REMOTE_URL'], working_tree_dir)
        cw = repo.config_writer()
        cw.set_value('user', 'name', username)
        cw.set_value('user', 'email', username + '@yhd.com')
    if repo.is_dirty(index=True, working_tree=False, untracked_files=False):
        if not repo.index.unmerged_blobs():
            repo.git.stash('save')
            repo.git.pull()
            try:
                repo.git.stash('pop')
            except GitCommandError:
                repo.git.stash('clear')
            for blob in changes_to_be_committed(repo):
                if os.path.isfile((os.path.join(working_tree_dir, blob))):
                    repo.git.add(blob)
                else:
                    repo.git.rm('--cached', blob)
    else:
        repo.git.pull()
    context = {'WORKING_TREE_DIR': working_tree_dir, 'USERNAME': username}
    return my_render(request, 'git/boot_sh.html', context)


@login_required
def git_app(request):
    username = request.user.username
    working_tree_dir = os.path.join(GIT['COMMON']['LOCAL_DIR'], username)
    error = False
    try:
        repo = Repo(working_tree_dir)
    except NoSuchPathError:
        error = True
    except InvalidGitRepositoryError:
        shutil.rmtree(working_tree_dir, True)
        error = True
    if error:
        repo = Repo.clone_from(GIT['COMMON']['REMOTE_URL'], working_tree_dir)
        cw = repo.config_writer()
        cw.set_value('user', 'name', username)
        cw.set_value('user', 'email', username + '@yhd.com')
    if repo.is_dirty(index=True, working_tree=True, untracked_files=False):
        if not repo.index.unmerged_blobs():
            repo.git.stash('save')
            repo.git.pull()
            try:
                repo.git.stash('pop', '--index')
            except GitCommandError:
                repo.git.stash('clear')
    else:
        repo.git.pull()
    app_queryset = App.objects.filter(status=0, type=0)
    type_list = GitFileType.objects.all()
    room_queryset = Room.objects.filter(name__in=['DCB', 'DCD'])
    return my_render(request, 'git/git_app.html', locals())
