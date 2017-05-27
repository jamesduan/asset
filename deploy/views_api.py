# -*- coding: utf-8 -*-
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import generics, status, filters, viewsets
from serializers import *
from deploy.utils.CreateDeploy import CreateDeploy
from deploy.utils.DepFtp import DepFtp
from deploy.utils.Pika import Pika
from deploy.utils.DeployCommon import trident_callback, celery_report, ycc_rmvpublish
from deploy.models import *
from deploy.permissions import *
from deploy import filters as deploy_filters
from assetv2.settingsapi import *
from django.core.cache import get_cache
from django_redis import get_redis_connection
import time
import json
import random
from cmdb.models import DdUsersDomains, DdDomain, DdDepartmentNew, AppContact
import operator
from deploy.permissions import PathConfigAdminPermission
from datetime import datetime
from assetv2.settingsapi import DEPLOY_URL, DEPLOY_STG_DEFAULT_TIME, RELEASE_IPS, CODE_PATH, DEPLOY_QA_EXCLUDE_APP
from django.template import loader
from util.sendmail import sendmail_html, sendmail_v2
from rest_framework.exceptions import APIException
from util.utils import get_app_filter_by_request_user
from util.httplib import *
from django.db.models import Max
from django.conf import settings
import socket
import struct

class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code

@api_view(['GET', 'POST'])
@permission_classes((AllowAny, ))
def gitlab_push(request):
    if request.method == 'POST':
        file_object = open('thefile.txt', 'a')
        file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
        file_object.close()

        return Response({"message": "Got some data!", "data": request.data})

    return Response({"message": "This message just support GET!"})

@api_view(['GET', 'POST'])
@permission_classes((AllowAny, ))
def gitlab_request_merge_event(request):
    if request.method == 'POST':
        merge_status = request.data['object_attributes']['merge_status']
        state = request.data['object_attributes']['state']
        if merge_status == 'can_be_merged' and state == 'merged':
            branch_name = 'master'
            deploy_type = 'python'
            server_queryset = Server.objects.filter(app_id=1086, server_status_id=200, server_env_id=2)
            ip_list = [server_obj.ip for server_obj in server_queryset]
            amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[ip_list, CODE_PATH, branch_name, deploy_type])
            amqp.basic_publish()
        return Response({"message": "Got some data!", "data": request.data})
    return Response({"message": "This message just support GET!"})


@api_view(['GET', 'POST'])
@permission_classes((AllowAny, ))
def gitlab_push_event(request):
    if request.method == 'POST':
        project_id = request.data['project_id']
        branch = request.data['ref']
        if project_id == 32:  # assetv2 触发消息队列
            if branch == 'refs/heads/master':
                file_object = open('thefile.txt', 'a')
                file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
                file_object.close()
                release_ips = ['10.4.31.31', '10.17.32.88', '10.4.31.159', '10.17.26.4']
                code_path = '/data/assetv2'
                branch_name = 'master'
                deploy_type = 'python'
                amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
                amqp.basic_publish()
        if project_id == 127: # docs触发
            if branch == 'refs/heads/master':
                file_object = open('thefile.txt', 'a')
                file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
                file_object.close()
                release_ips = ['10.4.31.159', ]
                code_path = '/data/manual/_source/docs'
                branch_name = 'master'
                deploy_type = 'manual-docs'
                amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
                amqp.basic_publish()
        if project_id == 128: # docs-office触发
            if branch == 'refs/heads/master':
                file_object = open('thefile.txt', 'a')
                file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
                file_object.close()
                release_ips = ['10.4.31.159', ]
                code_path = '/data/manual/_source/docs-office'
                branch_name = 'master'
                deploy_type = 'manual-docs-office'
                amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
                amqp.basic_publish()
            # if branch == 'refs/heads/cmdbv2':
            #     release_ips = ['10.4.31.31', '10.17.32.88']
            #     code_path = '/data/assetv2'
            #     branch_name = 'cmdbv2'
            #     deploy_type = 'python'
            #     amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
            #     amqp.basic_publish()
            # if branch == 'refs/heads/cmdbapi':
            #     release_ips = ['10.4.31.31', '10.17.32.88']
            #     code_path = '/data/assetv2'
            #     branch_name = 'cmdbapi'
            #     deploy_type = 'python'
            #     amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
            #     amqp.basic_publish()
            # if branch == 'refs/heads/deploy':
            #     release_ips = ['10.4.31.159', '10.17.26.4', '10.4.31.31', '10.17.32.88']
            #     code_path = '/data/assetv2'
            #     branch_name = 'cmdbapi'
            #     deploy_type = 'python'
            #     amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
            #     amqp.basic_publish()
        elif project_id == 14:  # 测试发消息
            file_object = open('thefile.txt', 'a')
            file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
            file_object.close()
            release_ips = ['10.4.31.31', '10.17.32.88']
            code_path = '/home/deploy/test'
            branch_name = 'master'
            deploy_type = 'test'
            amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
            amqp.basic_publish()
        elif project_id == 56:
            file_object = open('thefile.txt', 'a')
            file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
            file_object.close()
        elif project_id == 186:  # 乐道APP最终编译版
            if branch == 'refs/heads/master':
                file_object = open('thefile.txt', 'a')
                file_object.write(json.dumps(request.data, ensure_ascii=False) + "\n")
                file_object.close()
                release_ips = ['10.4.31.31',]
                code_path = '/data/ledao_app_build'
                branch_name = 'master'
                deploy_type = 'ledao_app'
                amqp = Pika(task='deploy.tasks.deploy_by_gitlab', args=[release_ips, code_path, branch_name, deploy_type])
                amqp.basic_publish()
        return Response({"message": "Got some data!", "data": request.data})

    return Response({"message": "This message just support GET2!"})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def muti_save_deploy_v2(request):
    """
    发布系统-新建发布任务接口.(静态改造过的脚本)

    输入参数：

    * data - json格式   [{发布任务1},{发布任务2}]
    * 每个json的格式
    ** app_id   POOL ID号
    ** deptype  发布类型  1为stgtoprod 2为ftptoprod
    ** ftpath   发布全路径
    ** comment  备注信息
    ** jiraid   trident编号
    ** packtype 发布包类型  0为webapps  3为static, 4为hadoop
    ** publishDateTimeFrom 发布起始时间
    ** publishDateTimeTo 发布结束时间
    ** restart 是否重启

    输出参数：

    * http status 201    创建成功    ['depid1','depid2']
    * http status 400    创建出错
    """
    data = request.POST.get("data") if request.POST.get("data") else request.POST.get("_content")
    if data is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='input params can\'t be empty.')
    try:
        data = json.loads(data)
    except Exception:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='input params is not json.')
    trident = CreateDeploy(data)
    deploy_list = trident.get_deploy_list()
    # 预发布
    for deploy in deploy_list:
        if deploy['pubtype'] == 1 and deploy['status'] == 1:
            amqp = Pika(task='deploy.tasks.auto_pre_deploy', args=[deploy['depid']])
            amqp.basic_publish()
    return Response(status=status.HTTP_201_CREATED, data=deploy_list)


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def rollback(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    interval = request.POST.get('interval', DEPLOY_INTERVAL)
    parallel = json.loads(request.POST.get('parallel', 'false'))
    amqp = Pika(task='deploy.tasks.rollback', args=[depid, interval, parallel])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def auto_publish(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    interval = request.POST.get('interval', DEPLOY_INTERVAL)
    amqp = Pika(task='deploy.tasks.auto_publish', args=[depid, interval])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def auto_pre_deploy(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    amqp = Pika(task='deploy.tasks.auto_pre_deploy', args=[depid])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def auto_single_deploy(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    ip = request.POST.get('ip')
    is_one_click = request.POST.get('is_one_click')
    init_tomcat = request.POST.get('init_tomcat')
    amqp = Pika(task='deploy.tasks.auto_single_deploy', args=[ip, is_one_click, init_tomcat])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['GET'])
@permission_classes((AllowAny, ))
def permitted(request):
    """

    输入参数：

    * depid    -   发布号
    * pubtype  -   类型

    输出参数：

    * True or False
    """
    depid = request.GET.get('depid')
    pubtype = request.GET.get('pubtype')
    if not (depid and pubtype):
        return Response(status=status.HTTP_400_BAD_REQUEST)
    deploy_list = [DeployMainConfig, DeployMain]
    deploy = deploy_list[int(pubtype)].objects.get(depid=depid)
    publishdatetimefrom = deploy.publishdatetimefrom
    publishdatetimeto = deploy.publishdatetimeto
    is_permitted = True if publishdatetimefrom <= int(time.time()) <= publishdatetimeto or publishdatetimefrom == 0 else False
    return Response(status=status.HTTP_200_OK, data=is_permitted)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def log(request):
    """

    输入参数：

    * depid    -   发布号

    输出参数：

    * host          -   主机
    * create_time   -   创建时间
    * log           -   日志
    * error         -   错误
    """
    depid = request.GET.get('depid')
    cache = get_cache('deploy')
    log_list = cache.get(depid, [])
    if not log_list:
        con = get_redis_connection("deploy")
        for log in con.lrange(depid, 0 ,-1):
            log_list.append(json.loads(log))
    return Response(status=status.HTTP_200_OK, data=log_list)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def log2(request):
    """

    输入参数：

    * task_id    -   任务号

    输出参数：

    * host          -   主机
    * create_time   -   创建时间
    * log           -   日志
    * error         -   错误
    """
    task_id = request.GET.get('task_id')
    data = celery_report(task_id)
    if task_id.count('*'):
        data['ready'] = True
        data['status'] = 'No status.'
        data['result'] = 'You may need to refresh the page manually.'
    return Response(status=status.HTTP_200_OK, data=data)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def log_reboot(request):
    """

    输入参数：

    * ticket_id    -   任务号

    输出参数：

    """
    ticket_id = request.GET.get('ticket_id')
    try:
        deploy_ticket_celery = DeployTicketCelery.objects.get(ticket_id=ticket_id)
        return Response(status=status.HTTP_200_OK, data=celery_report(deploy_ticket_celery.celery_task_id))
    except DeployTicketCelery.DoesNotExist:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def ftp_list(request):
    """

    输入参数：

    * app_id    -   应用ID
    * packtype  -   包类型
    * date      -   日期

    输出参数：

    * http status 201    创建成功    ['pack1','pack2']
    """
    pack_list = ['fullpackage-war', 'hotfix-tar', 'hotfix-war', 'static', 'hadoop']
    app_id = request.REQUEST.get('app_id')
    packtype = request.REQUEST.get('packtype')
    deploy_ftp_obj = None
    if not (app_id and packtype):
        return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
    date = request.REQUEST.get('date', stamp2str(time.time(), '%Y%m%d'))
    try:
        deploy_ftp_obj = DeployFtp.objects.get(app_id=app_id)
    except DeployFtp.DoesNotExist:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    jon_str = '/'
    path = jon_str.join([deploy_ftp_obj.path, pack_list[int(packtype)], date])
    try:
        ftp = DepFtp(host=deploy_ftp_obj.ftp, user=deploy_ftp_obj.user, passwd=deploy_ftp_obj.passwd)
        lists = ftp.lists(path)
        ftp.close()
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_200_OK, data=lists)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def catalina(request):
    """

    输入参数：

    * ip    -   IP地址

    输出参数：

    * List
    """
    ip = request.GET.get('ip')
    output = ssh('tail -n100 /usr/local/tomcat6/logs/catalina.out', ip)[2]
    return Response(status=status.HTTP_200_OK, data=output.splitlines())


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def config_rollback(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    interval = request.POST.get('interval', DEPLOY_INTERVAL)
    amqp = Pika(task='deploy.tasks.config_rollback', args=[depid, interval])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def config_auto_publish(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    amqp = Pika(task='deploy.tasks.config_auto_publish', args=[depid])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((AllowAny, ))
def online_report(request):
    task_dict = request.POST.get('task_dict')
    task_dict = json.loads(task_dict)
    action = request.POST.get('action')
    username = request.POST.get('username')
    server_change_content = request.POST.get('server_change_content')
    email = request.POST.get('email')
    email = json.loads(email)
    poolname = request.POST.get('poolname')
    sitename = request.POST.get('sitename')
    amqp = Pika(task='deploy.tasks.online_report', args=[REDIS['HOST'], REDIS['PORT'], task_dict, action, username, server_change_content, email, poolname, sitename])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((RebootPermission, ))
def auto_reboot(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    data = json.loads(request.POST.get('data'))[0]
    if data.get('publishDateTimeFrom', 0) == 0:
        amqp = Pika(task='deploy.tasks.auto_reboot', args=[data])
        task_id = amqp.basic_publish()
        return Response(status=status.HTTP_200_OK, data={'task_id': task_id})
    else:
        deploy_reboot = DeployReboot(reboot_time=data['publishDateTimeFrom'], data=json.dumps(data))
        deploy_reboot.save()
        return Response(status=status.HTTP_200_OK, data={'task_id': None})


@api_view(['GET', 'DELETE'])
@permission_classes((AllowAny, ))
def redis_python(request, category):
    key = request.REQUEST.get('key', request.DATA.get('key'))
    many = request.REQUEST.get('many', request.DATA.get('many'))
    if key is None:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    cache = get_cache(category)
    if request.method == 'DELETE':
        keys = cache.keys(key)
        cache.delete_many(keys)
        return Response(status=status.HTTP_200_OK, data=keys)
    elif request.method == 'GET':
        if many is not None:
            return Response(status=status.HTTP_200_OK, data=cache.get_many(cache.keys(key)))
        return Response(status=status.HTTP_200_OK, data=cache.get(key))


class DeployVersionAppList(generics.ListAPIView):
    """
    版本列表.

    输入参数：

    * app_id    -   应用ID(可选，无此参数为所有app_id)
    * app_env_id   -   pk(可选，无此参数为所有app_env)

    输出参数：

    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_name  -   应用名称
    * app_env   -   环境   1 - stagging    2 - production
    * ftpath    -   ftp路径
    * app_version   -   app版本
    * created_time  -   记录创建时间
    * updated_time  -   记录更新时间
    """

    queryset = DeployVersionApp.objects.all()
    serializer_class = DeployVersionAppSerializer
    paginate_by = None

    def get_queryset(self):
        filters = dict()
        app_id = self.request.QUERY_PARAMS.get("app_id")
        if app_id:
            filters["app_id"] = app_id
        app_env_id = self.request.QUERY_PARAMS.get("app_env_id")
        if app_env_id:
            filters["app_env_id"] = app_env_id
        return DeployVersionApp.objects.filter(**filters)


class DeployVersionAppDetail(generics.RetrieveUpdateAPIView):
    """
    版本列表.

    输入参数：无

    输出参数：

    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_name  -   应用名称
    * app_env   -   环境   1 - stagging    2 - production
    * ftpath    -   ftp路径
    * app_version   -   app版本
    * created_time  -   记录创建时间
    * updated_time  -   记录更新时间
    """

    queryset = DeployVersionApp.objects.all()
    serializer_class = DeployVersionAppSerializer
    paginate_by = None

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.app_env_id == 2:
            instance.ftp_path = Deployv3StgMain.objects.filter(app_id=instance.app_id, status=2, deploy_type=instance.pack_type).order_by('-id')[0].source_path
            instance.save()


class DeployMainList(generics.ListAPIView):
    """
    发布申请单列表.

    输入参数：

    * app_id    -   应用ID(可选，无此参数为所有app_id)
    * deptype   -   发布类型    1 - Stag2Product    2 - Ftp2Product
    * depid     -   发布号
    * status    -   状态  123 - 待发布   4 发布成功  5 已回滚   6 发布中   7 已作废
    * uid    -   用户ID
    * packtype  -   包类型
    * is_trident    - 是否trident发布 523是   非523否
    * is_gray_release   -   是否灰度
    * start_date   -   大于等于最后操作时间
    * end_date   -   小于最后操作时间

    输出参数：

    * depid     -   发布号
    * jiraid    -   Trident-ID
    * username  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * deptype_name    -   发布类型
    * packtype_name   -   包类型
    * restart  -   是否重启
    * last_modified  -   最后操作时间
    * publishdatetimefrom   -   发布开始时间
    * publishdatetimeto -   发布结束时间
    * status_name   -   状态

    """

    queryset = DeployMain.objects.all()
    serializer_class = DeployMainSerializer
    paginate_by = 20

    def get_queryset(self):
        filters = dict()
        excludes = dict()
        app_id = self.request.QUERY_PARAMS.get("app_id")
        if app_id:
            filters["app_id"] = app_id
        deptype = self.request.QUERY_PARAMS.get("deptype")
        if deptype:
            filters["deptype"] = deptype
        depid = self.request.QUERY_PARAMS.get("depid")
        if depid:
            filters["depid"] = depid
        status = self.request.QUERY_PARAMS.get("status")
        status_list = status.split(',') if status else None
        if status_list:
            filters["status__in"] = status_list
        uid = self.request.QUERY_PARAMS.get("uid")
        if uid:
            filters["uid"] = uid
        packtype = self.request.QUERY_PARAMS.get("packtype", '')
        if packtype != '':
            filters["packtype"] = packtype
        is_gray_release = self.request.QUERY_PARAMS.get("is_gray_release")
        if is_gray_release:
            filters["is_gray_release"] = is_gray_release
        is_trident = self.request.QUERY_PARAMS.get("is_trident")
        if is_trident:
            if is_trident == '523':
                filters['uid'] = 523
            else:
                excludes['uid'] = 523
        start_date = self.request.QUERY_PARAMS.get("start_date")
        if start_date:
            filters["last_modified__gte"] = start_date
        end_date = self.request.QUERY_PARAMS.get("end_date")
        if end_date:
            filters["last_modified__lt"] = end_date
        return DeployMain.objects.filter(**filters).exclude(**excludes).order_by('-id')


class DeployDetailList(generics.ListAPIView):
    """
    发布详细列表.

    输入参数：

    * depid     -   发布号
    * is_source -   是否是源服务器

    输出参数：

    * host  -   服务器IP
    * is_source -   是否是源服务器
    * has_real  -   是否已经发布
    * real_time -   发布时间
    * has_rollback  -   是否已经回滚
    * rollback_time -   回滚时间
    * has_error -   是否有错
    * complete  =   是否完成
    """

    queryset = DeployDetail.objects.all()
    serializer_class = DeployDetailSerializer
    paginate_by = None

    def get_queryset(self):
        filters = dict()
        depid = self.request.QUERY_PARAMS.get("depid")
        if depid:
            filters["depid"] = depid
        is_source = self.request.QUERY_PARAMS.get("is_source")
        if is_source:
            filters["is_source"] = is_source
        return DeployDetail.objects.filter(**filters).order_by('-id')


class DeployRollbackReasonList(generics.ListCreateAPIView):
    """
    发布系统回滚理由.

    输入参数：（POST）
    * uid       -   用户ID
    * depid     -   发布号
    * verifier  -   确认人
    * reason    -   原因

    输出参数：

    * uid       -   用户ID
    * depid     -   发布号
    * verifier  -   确认人
    * reason    -   原因
    * created   -   创建时间
    """
    queryset = DeployRollbackReason.objects.all().order_by('-created')
    serializer_class = DeployRollbackReasonSerializer
    permission_classes = (DeployPermission, )
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter)
    filter_fields = ('depid',)
    lookup_field = 'depid'


class Status(generics.RetrieveUpdateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * status    -       状态值（状态值为0、1、2、3可废弃，4、5、6状态无法废弃）

    输出参数：

    * status        -   当前状态值
    """
    queryset = DeployMain.objects.all()
    serializer_class = DeployMainSerializer
    permission_classes = (DeployPermission, )
    lookup_field = 'depid'

    # def perform_update(self, serializer):
    #     instance = serializer.save()
    #     if instance.uid == 523:
    #         trident_callback(instance, instance.status)


class StatusConfig(generics.RetrieveUpdateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * status    -       状态值（状态值为0、1、2、3可废弃，4、5、6状态无法废弃）

    输出参数：

    * status        -   当前状态值
    """
    queryset = DeployMainConfig.objects.all()
    serializer_class = DeployMainConfigSerializer
    permission_classes = (DeployPermission, )
    lookup_field = 'depid'

    def perform_update(self, serializer):
        instance = serializer.save()
        # if instance.uid == 523:
        #     trident_callback(instance, instance.status)
        if instance.status == 7:
            ycc_rmvpublish(instance)


class DeployMainConfigList(generics.ListAPIView):
    """
    发布申请单列表.

    输入参数：

    * app_id    -   应用ID(可选，无此参数为所有app_id)
    * depid     -   发布号
    * status    -   状态  123 - 待发布   4 发布成功  5 已回滚   6 发布中   7 已作废
    * uid    -   用户ID

    输出参数：

    * depid     -   发布号
    * jiraid    -   Trident-ID
    * username  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * idc_name    -   机房名称
    * restart  -   是否重启
    * last_modified  -   最后操作时间
    * publishdatetimefrom   -   发布开始时间
    * publishdatetimeto -   发布结束时间
    * status_name   -   状态
    * app_id   -   应用ID
    """

    queryset = DeployMainConfig.objects.all()
    serializer_class = DeployMainConfigSerializer
    paginate_by = 20

    def get_queryset(self):
        filters = dict()
        app_id = self.request.QUERY_PARAMS.get("app_id")
        if app_id:
            filters["app_id"] = app_id
        depid = self.request.QUERY_PARAMS.get("depid")
        if depid:
            filters["depid"] = depid
        status = self.request.QUERY_PARAMS.get("status")
        status_list = status.split(',') if status else None
        if status_list:
            filters["status__in"] = status_list
        uid = self.request.QUERY_PARAMS.get("uid")
        if uid:
            filters["uid"] = uid
        return DeployMainConfig.objects.filter(**filters).order_by('-id')


class DeployMainConfigListV2(generics.ListAPIView):
    """
    发布申请单列表V2.

    输入参数：

    * app_id    -   应用ID(可选，无此参数为所有app_id)
    * depid     -   发布号
    * status    -   状态  123 - 待发布   4 发布成功  5 已回滚   6 发布中   7 已作废
    * uid    -   用户ID

    输出参数：

    * depid     -   发布号
    * jiraid    -   Trident-ID
    * username  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * idc_name    -   机房名称
    * restart  -   是否重启
    * gray_release_info - 灰度发布信息
    * last_modified  -   最后操作时间
    * publishdatetimefrom   -   发布开始时间
    * publishdatetimeto -   发布结束时间
    * status_name   -   状态
    * app_id   -   应用ID
    """

    queryset = DeployMainConfig.objects.all().order_by('-id')
    serializer_class = DeployMainConfigSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('depid', 'jiraid')
    filter_class = deploy_filters.DeployMainConfigDateTimeFilter
    paginate_by = 20


class DeployDetailConfigList(generics.ListAPIView):
    """
    发布详细列表.

    输入参数：

    * depid     -   发布号

    输出参数：

    * host  -   服务器IP
    * real_time -   发布时间
    * rollback_time -   回滚时间
    """

    queryset = DeployDetailConfig.objects.all()
    serializer_class = DeployDetailConfigSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('depid',)
    paginate_by = None


class InProgress(generics.RetrieveUpdateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * in_progress    -       状态值（状态值为0、1）

    输出参数：

    * in_progress        -   当前状态值
    """
    queryset = DeployMain.objects.all()
    serializer_class = DeployMainSerializer
    permission_classes = (DeployPermission, )
    lookup_field = 'depid'


class InProgressConfig(generics.RetrieveUpdateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * in_progress    -       状态值（状态值为0、1）

    输出参数：

    * in_progress        -   当前状态值
    """
    queryset = DeployMainConfig.objects.all()
    serializer_class = DeployMainConfigSerializer
    permission_classes = (DeployPermission, )
    lookup_field = 'depid'


class DeployTicketCeleryDetail(generics.RetrieveAPIView):
    """
    发布申请单状态.

    输入参数：

    * ticket_id     -       ticketID

    输出参数：

    * percent        -   当前状态值
    """
    queryset = DeployTicketCelery.objects.all()
    serializer_class = DeployTicketCelerySerializer
    permission_classes = (AllowAny, )
    lookup_field = 'ticket_id'

class Deployv3StgMainFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        app_queryset = get_app_filter_by_request_user(request)
        return queryset.filter(app_id__in=[app.id for app in app_queryset])

class Deployv3StgMainList(generics.ListCreateAPIView):
    """
    Stg发布列表/创建发布单

    创建输入参数：
    * site_name         -  站点名
    * app_name          -  Pool名
    * depid             -  发布号（可选，默认自动创建）
    * deploy_type       -  发布包的类型  0 webapps    3 static
    * source_path       -  发布源码包路径
    * is_restart        -  是否重启  0 否    1 是
    * uid               -  用户ID
    * is_need_deploy    - 是否发布 0 不发布  1 发布
    * bz                -  备注（可选）

    查询输入参数：
    * site_id       -   站点ID
    * app_id        -   应用ID
    * depid         -   发布号
    * status        -   状态  1 待发布   2 已发布  3 已回滚   4 发布异常   5 已作废
    * deploy_type   -   发布包的类型
    * uid           -   用户ID
    * start_date    -   大于等于发布完成时间
    * end_date      -   小于发布完成时间

    输出参数：
    * id                -   ID
    * depid             -   发布号
    * uid               -   操作者
    * site_name         -   站点名称
    * app_name          -   应用名称
    * is_restart        -   是否重启
    * created_time      -   发布单创建时间
    * success_update    -   发布完成时间
    * rollback_time     -   回滚时间
    * status_name       -   发布状态
    * deploy_type       -   发布包的类型
    """

    queryset = Deployv3StgMain.objects.all().order_by('-depid')
    serializer_class = Deployv3StgMainSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter, Deployv3StgMainFilterBackend)
    filter_fields = ('site_id', 'app_id', 'uid', 'deploy_type', 'status', 'depid')
    search_fields = ('depid', 'uid')
    permission_classes = (StgListCreatePermission,)

    def get_queryset(self):
        filters = dict()
        excludes = dict()
        site_id = self.request.QUERY_PARAMS.get("site_id")
        if site_id:
            filters["site_id"] = site_id
        app_id = self.request.QUERY_PARAMS.get("app_id")
        if app_id:
            filters["app_id"] = app_id
        uid = self.request.QUERY_PARAMS.get("uid")
        if uid:
            filters["uid"] = uid
        deploy_type = self.request.QUERY_PARAMS.get("deploy_type", '')
        if deploy_type != '':
            filters["deploy_type"] = deploy_type
        status = self.request.QUERY_PARAMS.get("status")
        if status:
            filters["status"] = status
        depid = self.request.QUERY_PARAMS.get("depid")
        if depid:
            filters["depid"] = depid
        start_date = self.request.QUERY_PARAMS.get("start_date")
        if start_date:
            filters["success_update__gte"] = start_date
        end_date = self.request.QUERY_PARAMS.get("end_date")
        if end_date:
            filters["success_update__lt"] = end_date
        return Deployv3StgMain.objects.filter(**filters).exclude(**excludes).order_by('-depid')

    def perform_create(self, serializer):
        site_name = self.request.DATA.get('site_name', '')
        app_name = self.request.DATA.get('app_name', '')
        app_id = int(self.request.DATA.get('app_id', 0))
        depid = self.request.DATA.get('depid', '')
        uid = self.request.DATA.get('uid', '')
        source_path = self.request.DATA.get('source_path', '')
        deploy_type = int(self.request.DATA.get('deploy_type', 0))
        is_need_deploy = int(self.request.DATA.get('is_need_deploy', 0))
        server_ids = self.request.DATA.get('server_ids', '')

        try:
            if app_name and site_name:
                site = Site.objects.exclude(status=1).get(name=site_name)
                app = App.objects.exclude(status=1).get(name=app_name, site_id=site.id)
            else:
                app = App.objects.exclude(status=1).get(id=app_id)
                site = Site.objects.exclude(status=1).get(id=app.site_id)
        except (Site.DoesNotExist, App.DoesNotExist):
                raise YAPIException('失败：站点或Pool不存在！')
        if deploy_type not in [0, 3]:
            raise YAPIException('失败：输入参数缺乏deploy_type（发布类型）字段。')

        if source_path == '':
            raise YAPIException('失败：输入参数缺乏source_path（发布包路径）字段。')

        if deploy_type == 0:
            deploy_type_name = 'webapps'
        else:
            deploy_type_name = 'static'
        now = datetime.now()
        min = datetime(now.year,now.month,now.day,0,0,0)
        min_time = int(time.mktime(min.timetuple()))
        max_time = min_time + 86400
        cur_deploy_num = Deployv3StgMain.objects.filter(app_id = app.id, deploy_type=deploy_type, created__gte = min_time, created__lt = max_time).count()
        try:
            max_deploy_num = Deployv3StgMaxtime.objects.get(app_id = app.id, deploy_type = deploy_type).deploy_maxtime
        except:
            max_deploy_num = DEPLOY_STG_DEFAULT_TIME
        if max_deploy_num != 0:
            if cur_deploy_num >= max_deploy_num:
                raise YAPIException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='失败：当前Pool今天%s的发布次数已达%s次上限，无法再创建发布申请。' % (deploy_type_name, max_deploy_num))

        if uid == '':
            uid = self.request.user.username

        if depid == '':
            depid = stamp2str(int(time.time()), '%Y%m%d%H%M%S') + str(random.randint(100000,999999))

        app_id = app.id
        if deploy_type == 3:    #静态POOL发布，需要强行将app_id指向静态POOL
            app_id = DEPLOY_STATIC_APP_ID

        if server_ids != '':
            server_ids = server_ids.split(',')
            if len(server_ids) != Server.objects.filter(id__in = server_ids, server_status_id = 200).count():
                raise YAPIException('失败：输入的IP中，有一个或多个不属于该POOL。')
            # target_hosts = Server.objects.exclude(server_type_id = 3).filter(id__in = server_ids, server_status_id = 200)
            target_hosts = Server.objects.filter(id__in=server_ids, server_status_id=200)
        else:
            # target_hosts = Server.objects.exclude(server_type_id = 3).filter(app_id=app_id, server_env_id=1, server_status_id = 200)
            target_hosts = Server.objects.exclude(server_type_id=3).filter(app_id=app_id, server_env_id=1,
                                                                           server_status_id=200)
        if target_hosts.count() ==0:
            raise YAPIException('失败：该pool没有使用中的机器(docker测试中，暂时屏蔽)，不允许创建发布申请！')

        is_autocreated = 0
        if is_need_deploy == 1:
            is_autocreated = 1
        instance = serializer.save(site_id = site.id, app_id = app.id, depid=depid, uid=uid, status=1, is_autocreated=is_autocreated, created=int(time.time()))

        for item in target_hosts:
            asset = item.asset if item.server_type_id == 1 else item.parent_asset
            room = asset.rack.room
            try:
                idc = DeployIDC.objects.get(id=room.area_id)
            except DeployIDC.DoesNotExist:
                raise YAPIException('失败：发布机不存在！')
            Deployv3Detail.objects.create(depid=depid, target_host=item.ip, deploy_host=idc.host)

        if instance.is_autocreated == 1:
            instance.is_process = 1
            instance.save()
            amqp = Pika(task='deploy.tasks.stg_deploy', args=[depid,])
            amqp.basic_publish()
        else:
            mailto = [uid + '@yhd.com']
            try:
                contact = AppContact.objects.get(pool_id=app.id)
                if contact.domain_email:
                    mailto.append(contact.domain_email)
            except AppContact.DoesNotExist:
                pass
            content = {
                'depid':  depid,
                'url':   DEPLOY_URL + 'stg/detail/?depid=%s' % instance.depid,
            }
            title = u'【全自动发布系统提醒】%s/%s的stg发布单%s成功创建。' % (site.name, app.name, depid)
            html_content = loader.render_to_string('mail/auto_stg_create_notify.html', content)
            # sendmail_html(title, html_content, mailto)
            sendmail_v2(title, html_content, mailto, app)

class Deployv3StgMainDetail(generics.RetrieveUpdateAPIView):
    """
    Stg发布更新

    输入参数：
    * depid     -   发布号
    * success_time  -   发布完成时间
    * rollback_time  -   回滚时间
    * status   -   发布状态
    * is_process - 是否正在发布
    * process - 发布进度

    输出参数：

    * depid     -   发布号
    * uid  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * is_restart  -   是否重启
    * created_time   -   发布单创建时间
    * success_time  -   发布完成时间
    * rollback_time  -   回滚时间
    * status_name   -   发布状态
    * deploy_type - 发布包的类型
    * deploy_type_name - 发布包的类型(中文)
    * is_process - 是否正在发布
    * process - 发布进度
    """

    queryset = Deployv3StgMain.objects.all().order_by('-depid')
    serializer_class = Deployv3StgMainSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('depid',)
    lookup_field = 'depid'


class Deployv3StgDetail(generics.ListAPIView):
    """
    Stg发布详情（附LOG）

    输入参数：
    * depid     -   发布号

    输出参数：

    * depid     -   发布号
    * uid  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * is_restart  -   是否重启
    * created_time   -   发布单创建时间
    * success_time  -   发布完成时间
    * rollback_time  -   回滚时间
    * status_name   -   发布状态
    * deploy_type - 发布包的类型
    * detail - 发布的host详情
    * logs   - 发布的日志
    """

    queryset = Deployv3StgMain.objects.all().order_by('-depid')
    serializer_class = Deployv3StgDetailSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('depid',)
    lookup_field = 'depid'
    permission_classes = (AllowAny,)

@api_view(['POST'])
@permission_classes((AllowAny, ))
def stg_deploy_event(request):
    """
    Stg发布操作

    输入参数：
    * depid     -   发布号
    * action    -   动作  deploy发布   rollback回滚  cancel作废
    """

    depid = request.POST.get('depid', '')
    action = request.POST.get('action', '')
    if depid == '':
        return Response(status=status.HTTP_400_BAD_REQUEST, data="输入参数错误，请检查URL")
    try:
        stg = Deployv3StgMain.objects.get(depid = depid)
    except Deployv3StgMain.DoesNotExist:
        return Response(status=status.HTTP_400_BAD_REQUEST, data="发布申请单不存在!")

    try:
        cur_domain = App.objects.get(status=0, id=stg.app_id).domainid
    except:
        return Response(status=status.HTTP_400_BAD_REQUEST, data="该pool不存在！")
    user_domains = DdUsersDomains.objects.filter(ddusers__username = stg.uid)
    domains_ids = [dm.dddomain_id for dm in user_domains]
    if not request.user.is_superuser:
        if (cur_domain not in domains_ids) :
            return Response(status=status.HTTP_401_UNAUTHORIZED, data="你所属Domain对该pool没有操作权限！")
    if stg.is_process == 1:
        return Response(status=status.HTTP_400_BAD_REQUEST, data="发布正在进行中，请勿重复提交!")

    if action == 'deploy':
        stg.is_process = 1
        stg.save()
        amqp = Pika(task='deploy.tasks.stg_deploy', args=[depid,])
        amqp.basic_publish()
    if action == 'cancel':
        stg.status = 5
        stg.save()
    if action == 'rollback':
        stg.is_process = 1
        stg.save()
        amqp = Pika(task='deploy.tasks.stg_rollback', args=[depid,])
        amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data="success")

@api_view(['GET', 'POST'])
@permission_classes((AllowAny, ))
def publish_count(request):
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    dept_level2_id = request.GET.get('department_id', 0)
    domain_id = request.GET.get('domain_id', 0)
    app_id = request.GET.get('app_id', 0)
    is_stagging = int(request.GET.get('is_stagging', 2))
    is_gray_release = request.GET.get('is_gray_release', '')
    is_trident = request.GET.get('is_trident', '')
    package_type = request.GET.get('package_type','')
    show_all_or_pool = request.GET.get('show_all_or_pool', '0')

    pro_filters = dict()
    stg_filters = dict()
    pro_excludes = dict()
    stg_excludes = dict()

    if start_date:
        start_date = str2stamp(start_date, formt='%Y-%m-%d')
        stg_filters['success_update__gte'] = start_date
        pro_filters['last_modified__gte'] = start_date

    if end_date:
        end_date = str2stamp(end_date, formt='%Y-%m-%d') + 86400
        stg_filters['success_update__lt'] = end_date
        pro_filters['last_modified__lt'] = end_date

    cycle_days = (end_date - start_date) / 86400

    if is_gray_release != '':
        pro_filters['is_gray_release'] = int(is_gray_release)

    if package_type != '':
        stg_filters['deploy_type'] = int(package_type)
        pro_filters['packtype'] = int(package_type)

    if is_trident != '':
        if is_trident == '523':
            pro_filters['uid'] = 523
        else:
            pro_excludes['uid'] = 523

    pro_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP
    stg_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP

    applist = App.objects.filter(status=0)
    domainlist = DdDomain.objects.filter(enable =0)

    if app_id:
        applist = applist.filter(id=int(app_id))
    elif domain_id:
        domainlist = domainlist.filter(enable = 0, id = int(domain_id))
        applist = applist.filter(domainid = int(domain_id))
    elif dept_level2_id:
        dept_level3 = DdDepartmentNew.objects.filter(enable = 0, pid = dept_level2_id)
        domain_all = DdDomain.objects.filter(enable = 0)
        domainlist = []
        if dept_level3:
            for dept in dept_level3:
                for dm in domain_all:
                    if dm.departmentid == dept.id:
                        domainlist.append(dm)
        else:
            for dm in domain_all:
                if dm.departmentid == dept_level2_id:
                    domainlist.append(dm)
        domain_id_list = [d.id for d in domainlist]
        applist = applist.filter(domainid__in = domain_id_list)

    app_id_list = [a.id for a in applist]
    pro_filters['app_id__in'] = app_id_list
    stg_filters['app_id__in'] = app_id_list

    pro_deploy_list = []
    stg_deploy_list = []
    if is_stagging != 1:
        pro_deploy_list = DeployMain.objects.filter(**pro_filters).exclude(**pro_excludes)

    if is_stagging != 0:
        stg_deploy_list = Deployv3StgMain.objects.filter(**stg_filters)
    resultlist = []
    if show_all_or_pool == '0':
        success_count = 0
        rollback_count = 0
        unfinished_count = 0
        scrap_count = 0
        all_count = 0
        success_rate = 0
        rollback_rate = 0
        for app in applist:
            if pro_deploy_list:
                for pro in pro_deploy_list:
                    if pro.app_id == app.id:
                        all_count += 1
                        if pro.status == 4:
                            success_count += 1
                        elif pro.status == 5:
                            rollback_count += 1
                        elif pro.status in [0,1,2,3,6,8,9,10,11,12]:
                            unfinished_count += 1
                        elif pro.status == 7:
                            scrap_count += 1
            if stg_deploy_list:
                for stg in stg_deploy_list:
                    if stg.app_id == app.id:
                        all_count += 1
                        if stg.status == 2:
                            success_count += 1
                        elif stg.status == 3:
                            rollback_count +=1
                        elif stg.status == 1:
                            unfinished_count += 1
                        elif stg.status == 5:
                            scrap_count +=1

        if (success_count + rollback_count):
            success_rate = round(success_count * 100 / float(success_count + rollback_count), 2)
            rollback_rate = round(rollback_count * 100 / float(success_count + rollback_count), 2)
        resultlist.append({
            'id': '-',
            'site': '-',
            'pool': '-',
            'department': '-',
            'domain': '-',
            'domainid': '-',
            'all_count': all_count,
            'success_count': success_count,
            'rollback_count': rollback_count,
            'failure_count': unfinished_count,
            'scrap_count': scrap_count,
            'success_rate': success_rate,
            'rollback_rate': rollback_rate,
            'publish_cycle': round(cycle_days/float(success_count),2) if success_count != 0 else '0'
        })
    elif show_all_or_pool == '1':
        for app in applist:
            pro_count = 0
            stg_count = 0
            pro_success = 0
            pro_rollback = 0
            pro_unfinished = 0
            pro_scrap = 0
            stg_success = 0
            stg_rollback = 0
            stg_unfinished = 0
            stg_scrap = 0
            success_rate = 0
            rollback_rate = 0
            if pro_deploy_list:
                for pro in pro_deploy_list:
                    if pro.app_id == app.id:
                        pro_count = pro_count + 1
                        if pro.status == 4:
                            pro_success =  pro_success + 1
                        elif pro.status == 5:
                            pro_rollback = pro_rollback + 1
                        elif pro.status in [0,1,2,3,6,8,9,10,11,12]:
                            pro_unfinished = pro_unfinished + 1
                        elif pro.status == 7:
                            pro_scrap = pro_scrap + 1
            if stg_deploy_list:
                for stg in stg_deploy_list:
                    if stg.app_id == app.id:
                        stg_count = stg_count + 1
                        if stg.status == 2:
                            stg_success += 1
                        elif stg.status == 3:
                            stg_rollback +=1
                        elif stg.status == 1:
                            stg_unfinished += 1
                        elif stg.status == 5:
                            stg_scrap +=1
            success_count = pro_success + stg_success
            rollback_count = pro_rollback + stg_rollback
            unfinished_count = pro_unfinished + stg_unfinished
            scrap_count = pro_scrap + stg_scrap
            all_count = pro_count + stg_count
            if (success_count + rollback_count):
                success_rate = round(success_count * 100 / float(success_count + rollback_count), 2)
                rollback_rate = round(rollback_count * 100 / float(success_count + rollback_count), 2)
            resultlist.append({
                'id': app.id,
                'site': app.site.name if app.site else '',
                'pool': app.name,
                'department': app.domain.department.deptname if (app.domain and app.domain.department) else '',
                'domain': app.domain.domainname if app.domain else '',
                'domainid': app.domainid,
                'all_count': all_count,
                'success_count': success_count,
                'rollback_count': rollback_count,
                'failure_count': unfinished_count,
                'scrap_count': scrap_count,
                'success_rate': success_rate,
                'rollback_rate': rollback_rate,
                'publish_cycle': round(cycle_days/float(success_count),2) if success_count != 0 else '0'
            })
    else:
        for dm in domainlist:
            pro_count = 0
            stg_count = 0
            pro_success = 0
            pro_rollback = 0
            pro_unfinished = 0
            pro_scrap = 0
            stg_success = 0
            stg_rollback = 0
            stg_unfinished = 0
            stg_scrap = 0
            success_rate = 0
            rollback_rate = 0
            pool_cycle = 0.0
            pool_count = 0
            for app in applist:
                if app.domainid == dm.id:
                    cycle_pool_success = 0
                    if pro_deploy_list:
                        for pro in pro_deploy_list:
                            if pro.app_id == app.id:
                                pro_count +=1
                                if pro.status == 4:
                                    pro_success += 1
                                    cycle_pool_success += 1
                                elif pro.status == 5:
                                    pro_rollback +=1
                                elif pro.status in [0,1,2,3,6,8,9,10,11,12]:
                                    pro_unfinished += 1
                                elif pro.status == 7:
                                    pro_scrap +=1
                    if stg_deploy_list:
                        for stg in stg_deploy_list:
                            if stg.app_id == app.id:
                                stg_count += 1
                                if stg.status == 2:
                                    stg_success += 1
                                    cycle_pool_success += 1
                                elif stg.status == 3:
                                    stg_rollback +=1
                                elif stg.status == 1:
                                    stg_unfinished += 1
                                elif stg.status == 5:
                                    stg_scrap +=1
                    if cycle_pool_success:
                        pool_cycle += round(cycle_days/(float)(cycle_pool_success), 2)
                        pool_count += 1
            success_count = pro_success + stg_success
            rollback_count = pro_rollback + stg_rollback
            unfinished_count = pro_unfinished + stg_unfinished
            scrap_count = pro_scrap + stg_scrap
            all_count = pro_count + stg_count
            if (success_count + rollback_count):
                success_rate = round(success_count * 100 / float(success_count + rollback_count), 2)
                rollback_rate = round(rollback_count * 100 / float(success_count + rollback_count), 2)

            dept_v2_name = ''
            dept_level2 = DdDepartmentNew.objects.filter(enable = 0, deptlevel = 2)
            dept_level2_ids = [level2.id for level2 in dept_level2]
            if dm.departmentid in dept_level2_ids:
                dept_v2_name =  dm.department.deptname
            elif dm.department.pid in dept_level2_ids:
                try:
                    dept_v2_name = DdDepartmentNew.objects.get(id = dm.department.pid).deptname + '-' + dm.department.deptname
                except DdDepartmentNew.DoesNotExist:
                    dept_v2_name = ''

            resultlist.append({
                'id': '-',
                'site': '-',
                'pool': '-',
                'department': dept_v2_name,
                'domain': dm.domainname,
                'domainid': dm.id,
                'all_count': all_count,
                'success_count': success_count,
                'rollback_count': rollback_count,
                'failure_count': unfinished_count,
                'scrap_count': scrap_count,
                'success_rate': success_rate,
                'rollback_rate': rollback_rate,
                'publish_cycle': round(pool_cycle/float(pool_count), 2) if pool_count != 0 else '0'
            })
    return Response(resultlist)

@api_view(['GET'])
@permission_classes((AllowAny, ))
def publish_trend(request):
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    package_type = request.GET.get('package_type','')
    is_stagging = int(request.GET.get('is_stagging', 2))
    is_gray_release = request.GET.get('is_gray_release', '')
    is_trident = request.GET.get('is_trident', '')

    pro_filters = dict()
    stg_filters = dict()
    pro_excludes = dict()
    stg_excludes = dict()

    app_valid_ids = [a.id for a in App.objects.filter(status=0)]
    if app_valid_ids:
        stg_filters['app_id__in'] = app_valid_ids
        pro_filters['app_id__in'] = app_valid_ids

    if start_date:
        start_date = str2stamp(start_date, formt='%Y-%m-%d')
        stg_filters['success_update__gte'] = start_date
        pro_filters['last_modified__gte'] = start_date

    if end_date:
        end_date = str2stamp(end_date, formt='%Y-%m-%d') + 86400
        stg_filters['success_update__lt'] = end_date
        pro_filters['last_modified__lt'] = end_date

    if package_type != '':
        stg_filters['deploy_type'] = int(package_type)
        pro_filters['packtype'] = int(package_type)

    if is_gray_release != '':
        pro_filters['is_gray_release'] = int(is_gray_release)

    if is_trident != '':
        if is_trident == '523':
            pro_filters['uid'] = 523
        else:
            pro_excludes['uid'] = 523

    pro_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP
    stg_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP

    pro_deploy_list = []
    stg_deploy_list = []

    if is_stagging != 1:
        pro_deploy_list = DeployMain.objects.filter(**pro_filters).exclude(**pro_excludes)
    if is_stagging != 0:
        stg_deploy_list = Deployv3StgMain.objects.filter(**stg_filters)
    xAxis = []
    all_count = []
    success_count = []
    rollback_count = []
    unfinished_count = []
    scrap_count = []
    next_data = start_date + 86400
    while start_date and  next_data <= end_date:
        pro_success = 0
        pro_rollback = 0
        pro_unfinished = 0
        pro_scrap = 0
        stg_success = 0
        stg_rollback = 0
        stg_unfinished = 0
        stg_scrap = 0

        pro_count = 0
        stg_count = 0
        if pro_deploy_list:
            for pro in pro_deploy_list:
                if pro.last_modified >= start_date and pro.last_modified < next_data:
                    pro_count += 1
                    if pro.status == 4:
                        pro_success += 1
                    elif pro.status == 5:
                        pro_rollback +=1
                    elif pro.status in [0,1,2,3,6,8,9,10,11,12]:
                        pro_unfinished += 1
                    elif pro.status == 7:
                        pro_scrap +=1
        if stg_deploy_list:
            for stg in stg_deploy_list:
                if stg.success_update >= start_date and stg.success_update < next_data:
                    stg_count += 1
                    if stg.status == 2:
                        stg_success += 1
                    elif stg.status == 3:
                        stg_rollback +=1
                    elif stg.status == 1:
                        stg_unfinished += 1
                    elif stg.status == 5:
                        stg_scrap +=1
        xAxis.append(stamp2datestr(start_date, formt='%Y-%m-%d'))
        all_count.append(pro_count + stg_count)
        success_count.append(pro_success + stg_success)
        rollback_count.append(pro_rollback + stg_rollback)
        unfinished_count.append(pro_unfinished + stg_unfinished)
        scrap_count.append(pro_scrap + stg_scrap)

        start_date = next_data
        next_data += 86400

    series = {
        'all_count': all_count,
        'success_count': success_count,
        'rollback_count': rollback_count,
        'unfinished_count': unfinished_count,
        'scrap_count': scrap_count
    }
    return Response(status=status.HTTP_200_OK, data={'xAxis':xAxis, 'series':series})

@api_view(['GET'])
@permission_classes((AllowAny, ))
def publish_compare(request):
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    is_stagging = request.GET.get('is_stagging', 2)
    is_gray_release = request.GET.get('is_gray_release', '')
    is_trident = request.GET.get('is_trident', '')

    pro_filters = dict()
    stg_filters = dict()
    pro_excludes = dict()
    stg_excludes = dict()
    app_valid_ids = [a.id for a in App.objects.filter(status=0)]
    if app_valid_ids:
        stg_filters['app_id__in'] = app_valid_ids
        pro_filters['app_id__in'] = app_valid_ids
    if start_date != '':
        start_date = str2stamp(start_date, formt='%Y-%m-%d')
        stg_filters['success_update__gte'] = start_date
        pro_filters['last_modified__gte'] = start_date

    if end_date != '':
        end_date = str2stamp(end_date, formt='%Y-%m-%d') + 86400
        stg_filters['success_update__lt'] = end_date
        pro_filters['last_modified__lt'] = end_date

    if is_gray_release != '':
        pro_filters['is_gray_release'] = int(is_gray_release)

    if is_trident != '':
        if is_trident == '523':
            pro_filters['uid'] = 523
        else:
            pro_excludes['uid'] = 523

    pro_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP
    stg_excludes['app_id__in'] = DEPLOY_QA_EXCLUDE_APP

    pro_deploy_list = []
    stg_deploy_list = []

    if is_stagging != '1':
        pro_deploy_list = DeployMain.objects.filter(**pro_filters).exclude(**pro_excludes)

    if is_stagging != '0':
        stg_deploy_list = Deployv3StgMain.objects.filter(**stg_filters)

    department_list = DdDepartmentNew.objects.filter(enable = 0, deptlevel = 2)

    all_count = []
    success_count = []
    rollback_count = []
    unfinished_count = []
    scrap_count = []

    yAxis = []
    for dept_v2 in department_list:
        domains = DdDomain.objects.filter(enable = 0, departmentid = dept_v2.id)
        domain_list = [d for d in domains]
        dept_level3 = DdDepartmentNew.objects.filter(enable=0, pid=dept_v2.id)
        if dept_level3:
            domain_all = DdDomain.objects.filter(enable=0)
            for dept in dept_level3:
                for dm2 in domain_all:
                    if dm2.departmentid == dept.id:
                        domain_list.append(dm2)
        domains_ids = [dm.id for dm in domain_list]
        apps = App.objects.filter(status=0, domainid__in = domains_ids)

        pro_deploys = pro_deploy_list.filter(app_id__in = [a.id for a in apps]) if pro_deploy_list else []
        stg_deploys = stg_deploy_list.filter(app_id__in = [a.id for a in apps]) if stg_deploy_list else []

        pro_success = 0
        pro_rollback = 0
        pro_unfinished = 0
        pro_scrap = 0
        stg_success = 0
        stg_rollback = 0
        stg_unfinished = 0
        stg_scrap = 0

        pro_count = 0
        stg_count = 0
        for pro in pro_deploys:
            pro_count += 1
            if pro.status == 4:
                pro_success += 1
            elif pro.status == 5:
                pro_rollback +=1
            elif pro.status in [0,1,2,3,6,8,9,10,11,12]:
                pro_unfinished += 1
            elif pro.status == 7:
                pro_scrap +=1

        for stg in stg_deploys:
            stg_count += 1
            if stg.status == 2:
                stg_success += 1
            elif stg.status == 3:
                stg_rollback +=1
            elif stg.status == 1:
                stg_unfinished += 1
            elif stg.status == 5:
                stg_scrap +=1
        all_count.append(pro_count + stg_count)
        success_count.append(pro_success + stg_success)
        rollback_count.append(pro_rollback + stg_rollback)
        unfinished_count.append(pro_unfinished + stg_unfinished)
        scrap_count.append(pro_scrap + stg_scrap)
        yAxis.append(dept_v2.deptname)
    series = {
        'all_count': all_count,
        'success_count': success_count,
        'rollback_count': rollback_count,
        'unfinished_count': unfinished_count,
        'scrap_count': scrap_count
    }
    return Response(status=status.HTTP_200_OK, data={'yAxis':yAxis, 'series':series})


@api_view(['GET'])
@permission_classes((AllowAny, ))
def dashboard_pool(request):
    app_id = request.GET.get('app_id', '')
    select_num = request.GET.get('select_num', 10)
    is_gray_release = request.GET.get('is_gray_release', 0)
    package_type = request.GET.get('package_type', 0)

    filters = dict()
    if app_id != '':
        filters['app_id'] = app_id
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='必须选择pool查询！')
    if is_gray_release != '':
        filters['is_gray_release'] = is_gray_release
    if package_type != '':
        filters['packtype'] = package_type

    mainlist = DeployMain.objects.filter(status=4).filter(**filters).order_by('-last_modified')[:select_num][::-1]
    xAxis = []
    keep_time = []
    for deploy in mainlist:
        xAxis.append(stamp2str(deploy.last_modified))
        detaillist = DeployDetail.objects.exclude(is_source = 1).filter(depid = deploy.depid)
        times = [d.real_time for d in detaillist]
        times.sort()
        if times:
            keep_time.append(times[-1] - times[0])
    series = {
        'keep_time': keep_time
    }
    return Response(status=status.HTTP_200_OK, data={'xAxis':xAxis, 'series':series})


@api_view(['GET'])
@permission_classes((AllowAny, ))
def jenkins_job(request):
    app_dict = dict()
    app_queryset = get_app_filter_by_request_user(request)
    for app_obj in app_queryset:
        app_dict['/'.join([app_obj.site.name, app_obj.name])] = [obj.url for obj in DeployJenkinsJob.objects.filter(app=app_obj)]
    return Response(status=status.HTTP_200_OK, data=app_dict)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def config_info(request):
    app_dict = dict()
    app_queryset = get_app_filter_by_request_user(request, ignore_superuser=True)
    for app_obj in app_queryset:
        if app_obj.status != 0:
            continue
        app_dict[app_obj.id] = dict()
        app_dict[app_obj.id]['pool_name'] = '/'.join([app_obj.site.name, app_obj.name])
        deploy_ftp = DeployFtp.objects.filter(app_id=app_obj.id).first()
        app_dict[app_obj.id]['ftp_path'] = deploy_ftp.path if deploy_ftp else None
        deploy_path = DeployPath.objects.filter(app_id=app_obj.id).first()
        app_dict[app_obj.id]['deploy_path'] = deploy_path.path if deploy_path else None
        hudson_job = HudsonJob.objects.filter(app_id=app_obj.id, jobtype=1).first()
        app_dict[app_obj.id]['staging_jenkins'] = hudson_job.url if hudson_job else None
        hudson_job = HudsonJob.objects.filter(app_id=app_obj.id, jobtype=2).first()
        app_dict[app_obj.id]['production_jenkins'] = hudson_job.url if hudson_job else None
        app_dict[app_obj.id]['healthcheck'] = True if \
            NeednotCheck.objects.using('db_opsadmin').filter(pool_id=app_obj.id).first() else (True if
            CheckUrl.objects.using('db_opsadmin').filter(pool_id=app_obj.id, status=1).first() else False)
    return Response(status=status.HTTP_200_OK, data=app_dict)

@api_view(['GET'])
@permission_classes((AllowAny, ))
def publish_screen(request):
    now = int(time.time())
    start_day =  now - (now % 86400) - 28800
    end_day = start_day + 86400
    publish_list = DeployMain.objects.filter(publishdatetimefrom__gte= start_day, publishdatetimeto__lt = end_day).order_by('publishdatetimefrom')
    publish_config_list = DeployMainConfig.objects.filter(publishdatetimefrom__gte= start_day, publishdatetimeto__lt = end_day).order_by('publishdatetimefrom')
    publish_all = []
    for pub in publish_list:
        detail = DeployDetail.objects.exclude(is_source = 1).filter(depid = pub.depid)
        finish_num = 0
        for d in detail:
            if 1 == d.has_real:
                finish_num = finish_num + 1
        finish_num = round(float(finish_num) / len(detail) * 100, 2) if len(detail) else 0
        publish_all.append({
            'trident': pub.jiraid,
            'depid': pub.depid,
            'pool': pub.app.site.name + '/' + pub.app.name,
            'package_type': pub.packtype_name,
            'is_gray_release': '是' if pub.is_gray_release else '否',
            'progress': finish_num,
            'is_progress': '是' if pub.in_progress else '否',
            'status': pub.status_name,
            'last_modified': stamp2str(pub.last_modified, formt='%Y-%m-%d %H:%M:%S')
        })
    for pub_config in publish_config_list:
        finish_c = 0
        if pub_config.restart:
            detail = DeployDetailConfig.objects.filter(depid = pub.depid)
            for d in detail:
                if d.real_time:
                    finish_c = finish_c + 1
            finish_c = round(float(finish_c) / len(detail) * 100, 2) if len(detail) else 0
        publish_all.append({
            'trident': pub_config.jiraid,
            'depid': pub_config.depid,
            'pool': pub_config.app.site.name + '/' + pub_config.app.name,
            'package_type': '配置',
            'is_gray_release': '-',
            'progress': finish_c,
            'is_progress': '是' if pub_config.in_progress else '否',
            'status': pub_config.status_name,
            'last_modified': stamp2str(pub_config.last_modified, formt='%Y-%m-%d %H:%M:%S')
        })
    results = sorted(publish_all, key=operator.itemgetter('last_modified'))

    return Response(results)


class JenkinsJobList(generics.ListAPIView):
    """
    JenkinsJobList

    输入参数：
    * app    -   应用ID(可选，无此参数为所有app_id)

    输出参数：

    * app     -   应用ID
    * url  -   JenkinsJobUrl
    """

    queryset = DeployJenkinsJob.objects.all()
    serializer_class = JenkinsJobListSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('app',)
    paginate_by = None


class DeployPathViewSet(viewsets.ModelViewSet):
    permission_classes = (PathConfigAdminPermission,)
    queryset = DeployPath.objects.all()
    serializer_class = DeployPathSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    filter_fields = ('app_id',)
    search_fields = ('name',)


class DeployFtpViewSet(viewsets.ModelViewSet):
    permission_classes = (PathConfigAdminPermission,)
    queryset = DeployFtp.objects.all()
    serializer_class = DeployFtpSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('app_id',)


class HudsonJobViewSet(viewsets.ModelViewSet):
    permission_classes = (HudsonJobAdminPermission,)
    queryset = HudsonJob.objects.all()
    serializer_class = HudsonJobSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('app_id',)

class DeployProcessPatternViewSet(viewsets.ModelViewSet):
    # permission_classes = (DeployProcessPatternAdminPermission,)
    queryset = DeployProcessPattern.objects.all()
    serializer_class = DeployProcessPatternSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('app',)


class Deployv3StgMaxtimeList(generics.ListCreateAPIView):
    """
    Stg发布次数白名单列表

    输入参数：
    * app_id    -   应用ID
    * deploy_type       -   发布包类型
    * deploy_maxtime     -   每次最大发布次数

    输出参数：
    * id        -  ID
    * app_id    -   应用ID
    * deploy_maxtime     -   每次最大发布次数
    """

    queryset = Deployv3StgMaxtime.objects.all()
    serializer_class = Deployv3StgMaxtimeSerializer
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter)
    filter_fields = ('app__id', 'deploy_type')
    search_fields = ('app__name', 'deploy_maxtime')
    permission_classes = (StgDeployPermission,)

    def perform_create(self, serializer):
        app_id = self.request.DATA.get('app_id')
        deploy_type = self.request.DATA.get('deploy_type')
        if Deployv3StgMaxtime.objects.filter(app_id = app_id, deploy_type = deploy_type).count():
            raise YAPIException('error: this record is already exists!')
        else:
            serializer.save(app_id = app_id)

class Deployv3StgMaxtimeDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Stg发布次数白名单详情

    输入参数：
    * id        -  ID
    * app_id    -   应用ID
    * deploy_maxtime     -   每次最大发布次数

    输出参数：
    * id        -  ID
    * app_id    -   应用ID
    * deploy_maxtime     -   每次最大发布次数
    """

    queryset = Deployv3StgMaxtime.objects.all()
    serializer_class = Deployv3StgMaxtimeSerializer
    permission_classes = (StgDeployPermission,)


class DeployMainListV2(generics.ListAPIView):
    """
    发布申请单列表.

    输入参数：

    * app_id    -   应用ID(可选，无此参数为所有app_id)
    * deptype   -   发布类型    1 - Stag2Product    2 - Ftp2Product
    * depid     -   发布号
    * status    -   状态  123 - 待发布   4 发布成功  5 已回滚   6 发布中   7 已作废
    * uid    -   用户ID
    * packtype  -   包类型
    * is_trident    - 是否trident发布 523是   非523否
    * is_gray_release   -   是否灰度
    * start_date   -   大于等于最后操作时间
    * end_date   -   小于最后操作时间

    输出参数：

    * depid     -   发布号
    * jiraid    -   Trident-ID
    * username  -   操作者
    * site_name -   站点名称
    * app_name   -   应用名称
    * deptype_name    -   发布类型
    * packtype_name   -   包类型
    * restart  -   是否重启
    * last_modified  -   最后操作时间
    * publishdatetimefrom   -   发布开始时间
    * publishdatetimeto -   发布结束时间
    * status_name   -   状态

    """

    queryset = DeployMain.objects.all().order_by('-id')
    serializer_class = DeployMainSerializer
    # filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, deploy_filters.DeployMainBackend)
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    search_fields = ('depid', 'jiraid')
    filter_class = deploy_filters.DeployMainDateTimeFilter


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def auto_publish_v2(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    from_scratch = request.POST.get('from_scratch', 'true')
    amqp = Pika(task='deploy.tasks.auto_publish_v2', args=[depid, json.loads(from_scratch)])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def rollback_v2(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    depid = request.POST.get('depid')
    rollback_type = request.POST.get('rollback_type')
    amqp = Pika(task='deploy.tasks.rollback_v2', args=[depid, json.loads(rollback_type)])
    task_id = amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data={'task_id': task_id})


class DeployMainDetailV2(generics.RetrieveUpdateAPIView):
    """
    发布申请单状态.

    输入参数：

    * depid     -       发布单号
    * in_progress    -       状态值（状态值为0、1）

    输出参数：

    * in_progress        -   当前状态值
    """
    queryset = DeployMain.objects.all()
    serializer_class = DeployMainSerializer
    permission_classes = (DeployPermission, )
    lookup_field = 'depid'


@api_view(['GET'])
@permission_classes((AllowAny, ))
def sre_pandora(request):
    """
    输入参数：


    输出参数：

    * task_id
    """
    progress_dict = dict()
    id_list = [obj['id__max'] for obj in DeployMain.objects.filter(packtype=0).order_by('id').values('app_id').annotate(Max('id'))]
    for deploy_main_obj in DeployMain.objects.filter(id__in=id_list):
        app_obj = deploy_main_obj.app
        if app_obj is None or app_obj.site is None:
            continue
        progress_dict['/'.join([app_obj.site.name, app_obj.name])] = deploy_main_obj.in_progress or deploy_main_obj.status in [9, 11]
    return Response(status=status.HTTP_200_OK, data=progress_dict)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def bulk_list(request):
    from deploy.serializers import DeployMainSerializer, DeployMainConfigSerializer
    publishdatetimefrom = request.GET.get('publishdatetimefrom')
    main_list = []
    for deploy_main_obj in DeployMain.objects.filter(publishdatetimefrom__gte=publishdatetimefrom):
        deploy_main_dict = dict(DeployMainSerializer(deploy_main_obj).data)
        deploy_main_dict['packtype'] = deploy_main_obj.packtype
        deploy_main_dict['group_id'] = json.dumps({'jiraid': deploy_main_obj.jiraid, 'app_id': deploy_main_obj.app_id})
        main_list.append(deploy_main_dict)
    for deploy_main_config_obj in DeployMainConfig.objects.filter(publishdatetimefrom__gte=publishdatetimefrom):
        deploy_main_config_dict = dict(DeployMainConfigSerializer(deploy_main_config_obj).data)
        deploy_main_config_dict['is_gray_release'] = 1 if deploy_main_config_obj.gray_release_info is not None else 0
        deploy_main_config_dict['packtype_name'] = 'config'
        deploy_main_config_dict['packtype'] = 4
        deploy_main_config_dict['group_id'] = json.dumps({'jiraid': deploy_main_config_obj.jiraid, 'app_id': deploy_main_config_obj.app_id})
        main_list.append(deploy_main_config_dict)
    return Response(status=status.HTTP_200_OK, data=main_list)


@api_view(['POST'])
@permission_classes((DeployPermission, ))
def bulk_rollback(request):
    """
    输入参数：

    * depid     -   发布号

    输出参数：

    * task_id
    """
    group_id_list = request.POST.get('group_id_list')
    if group_id_list is None:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    app_id_dict = dict()
    for group_id in json.loads(group_id_list):
        group_id = json.loads(group_id)
        app_id = group_id['app_id']
        app_id_dict[app_id] = app_id_dict.get(app_id, [])
        app_id_dict[app_id].append(group_id['jiraid'])
    for app_id in app_id_dict:
        amqp = Pika(task='deploy.tasks.bulk_rollback', args=[app_id, app_id_dict[app_id]])
        amqp.basic_publish()
    return Response(status=status.HTTP_200_OK, data=app_id_dict)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def sre_pandora_v2(request):
    """
    输入参数：


    输出参数：

    * task_id
    """
    app_obj_dict = dict()
    app_dict = dict()
    for app_obj in App.objects.filter(status=0, type=0):
        app_obj_dict[app_obj] = 0
    for disable_ip_obj in DisableIp.objects.using('db_opsadmin').all():
        ip = socket.inet_ntoa(struct.pack('I',socket.htonl(disable_ip_obj.ip)))
        server_obj = Server.objects.exclude(server_status_id=400).filter(ip=ip).first()
        if server_obj is not None and server_obj.app in app_obj_dict:
            app_obj_dict[server_obj.app] += 1
    for app_obj in app_obj_dict:
        app_dict['/'.join([app_obj.site.name, app_obj.name])] = True if app_obj_dict[app_obj] > 5 else False
    return Response(status=status.HTTP_200_OK, data=app_dict)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def test_http_500(request):
    raise Exception('test')
