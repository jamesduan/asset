# -*- coding: utf-8 -*-
import json
from rest_framework.authtoken.models import Token
from django.shortcuts import render_to_response, HttpResponse, redirect
from assetv2.settingsdeploy import YCC_ENV, CMDBAPI_URL, STATIC_URL, ROOT_URL, LOGOUT_URL, LOGIN_URL, YCC_DOCS
from django.views.decorators.csrf import csrf_exempt
from users.usercheck import login_required
from cmdb.models import Site, ConfigDbInstance, News, ConfigDbKvDefault
from assetv2.settingsapi import YCC_GROUP_ID, GROUP_ID, IDC_SHOW, YCC_CMP_ENV
from models import *
from util.timelib import *
from ycc.permissions import permission
from util.utils import *
from util import webmenu, breadcrumbs
from asset.models import Room


# Create your views here.
def my_render(request, template, context={}):
    tokenobj = Token.objects.get(user_id=request.user.id)
    token = tokenobj.key if tokenobj is not None else None
    expire_date = stamp2datestr(int(time.time()) - 7 * 24 * 3600)
    news = News.objects.filter(created__gte=expire_date, status=1).order_by('-id')[:1]
    for item in news:
        context['GLOBAL_NEWS'] = item

    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['YCC_ENV'] = YCC_ENV
    context['YCC_CMP_ENV'] = YCC_CMP_ENV
    context['ROOT_URL'] = ROOT_URL
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL
    context['HELP_URL'] = "http://oms.yihaodian.com.cn/docs/?p=637"
    context['FEEDBACK_URL'] = "http://oms.yihaodian.com.cn/docs/?p=684"

    # dynamic web menu and breadcrumb
    # the second parameter is depreciated
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)


@login_required
@csrf_exempt
def grouplist(request):
    env = ConfigEnv.objects.exclude(name='both')
    group_list = request.user.groups.values()
    if GROUP_ID['YCC_ADMIN'] in [group['id'] for group in group_list] and not request.user.is_superuser:
        app_id_list = [app.id for app in App.objects.all()]
    else:
        app_id_list = get_app_id_filter_by_request_user(request)
    group = ConfigGroup.objects.filter(status=1, app_id__in=app_id_list)
    # group = ConfigGroup.objects.filter(status=1)
    room = Room.objects.filter(name__in=IDC_SHOW)
    site = Site.objects.all()
    is_admin = True if permission(request, ['YCC_ADMIN']) else False
    is_commit = True if permission(request, ['COMMIT', 'YCC_ADMIN']) else False
    # if isSaPermission(request) and YCC_ENV == 'production':
    # if YCC_ENV == 'production':
    # if isSaPermission(request):
    #     canEdit = True
    # if isCommitPermission(request):
    #     canCommit = True
    # if YCC_ENV == 'production':
    #     return my_render(request, 'ycc/prod_group.html', locals())
    # elif YCC_ENV == 'test':
    #     return my_render(request, 'ycc/prod_group.html', locals())
    domains = get_domains_by_request_user(request)
    if is_configinfo_v3_domains(request):
        return redirect('/deploy/yccv2/group/v3/')
    return my_render(request, 'ycc/prod_group.html', locals())


@login_required
def copyGroupData(request):
    groups = ConfigGroup.objects.filter(status=1)
    envs = ConfigEnv.objects.exclude(name='both')
    return my_render(request, 'ycc/copy_pool_data.html', locals())


# def isSaPermission(request):
#     if request.user is None:
#         return False
#     group_list = request.user.groups.values()
#     group_id_list = [group['id'] for group in group_list]
#     return True if YCC_GROUP_ID in group_id_list else False
#
#
# def isCommitPermission(request):
#     if request.user is None:
#         return False
#     group_list = request.user.groups.values()
#     group_id_list = [group['id'] for group in group_list]
#     return True if GROUP_ID['COMMIT'] in group_id_list else False


def isDBHisPermission(request):
    if request.user is None:
        return False
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    return True if GROUP_ID['DB_HIS'] in group_id_list else False


@login_required
@csrf_exempt
def proconfiginfov2list(request):
    # group_list = request.user.groups.values()
    # if GROUP_ID['YCC_ADMIN'] in [group['id'] for group in group_list]:
    #     app_queryset = App.objects.all()
    # else:
    #     app_queryset = get_app_filter_by_request_user(request)
    # group = ConfigGroup.objects.filter(idc=1, status=1, app_id__in=[app.id for app in app_queryset])
    group = ConfigGroup.objects.filter(idc=1, status=1)
    allgroupstatus = ConfigGroupStatus.objects.all()
    idc = Room.objects.filter(name__in=IDC_SHOW)
    configinfourl = 'proconfiginfo'
    status_list = [status_tuple for status_tuple in ConfigGroupStatus.STATUS if status_tuple[0] in [0, 1, 2, 4, 5, 6]]
    env = ConfigEnv.objects.exclude(name='both')
    # if isSaPermission(request):
    #     configinfourl = 'configinfo'
    domains = get_domains_by_request_user(request)
    return my_render(request, 'ycc/pro_configinfo.html', locals())


@login_required
@csrf_exempt
def configinfov2list(request):
    # env = ConfigEnv.objects.all()
    env = ConfigEnv.objects.all().order_by('-id')
    queryenvfilter = env.exclude(name='both')
    if request.GET.get('env_id') is None:
        a_list = ['<a href="/deploy/yccv2/configinfo/v2/?env_id=%s">配置文件管理 (%s)</a>' % (env.id, env.name) for env in queryenvfilter]
        return HttpResponse('<br>'.join(a_list))
    env_obj = ConfigEnv.objects.filter(id=request.GET.get('env_id')).first()
    if env_obj:
        docs_id = YCC_DOCS.get(env_obj.id)
    # if YCC_ENV == 'production':
    #     env = env.filter(name='both')
    # else:
    #     env = env.exclude(name='both')
    group_list = request.user.groups.values()
    app_id = request.GET.get('app_id', None)
    if GROUP_ID['YCC_ADMIN'] in [group['id'] for group in group_list] and not request.user.is_superuser:
        app_id_list = [app.id for app in App.objects.all()]
    else:
        app_id_list = get_app_id_filter_by_request_user(request)
    group = ConfigGroup.objects.filter(idc=1, status=1, app_id__in=app_id_list)
    # group = ConfigGroup.objects.filter(idc=1, status=1)
    idc = Room.objects.filter(name__in=IDC_SHOW)
    db_instances = ConfigDbInstance.objects.all()
    user_for_upload_tmp = request.user
    # is_commit = True if permission(request, ['COMMIT', 'YCC_ADMIN']) else False
    is_commit = True
    # if YCC_ENV == 'production' and not isSaPermission(request):
    #     canEdit = False
    domains = get_domains_by_request_user(request)
    is_domain = is_configinfo_v3_domains(request)
    config_types = ConfigType.objects.all()

    return redirect('/deploy/yccv2/configinfo/v3/')

    # if is_domain:
    #     return redirect('/deploy/yccv2/configinfo/v3/')
    # else:
    #     return my_render(request, 'ycc/configinfo.html', locals())


@login_required
def cmpconfiginfos(request):
    groups = ConfigGroup.objects.filter(status=1)
    envs = ConfigEnv.objects.exclude(name='both')
    return my_render(request, 'ycc/cmpconfiginfo.html', locals())


@login_required
@csrf_exempt
def dbupdatelist(request):
    env = ConfigEnv.objects.all()
    queryenvfilter = env.exclude(name='both')
    if YCC_ENV == 'production':
        env = env.filter(name='both')
    else:
        env = env.exclude(name='both')
    syn_user = request.user
    group = ConfigGroup.objects.filter(idc=1, status=1)
    idc = Room.objects.all()
    db_instances = ConfigDbInstance.objects.all()
    canDBHis = False
    canEdit = True if permission(request, ['YCC_ADMIN']) else False
    if YCC_ENV == 'production':
        if isDBHisPermission(request):
            canDBHis = True
        # if isSaPermission(request):
        #     canEdit = True
    db_default_instances = ConfigDbKvDefault.objects.exclude(jdbctype=0).order_by('dbtype')
    return my_render(request, 'ycc/dbupdate.html', locals())

@login_required
@csrf_exempt
def config_subscribe_list(request):
    statuscode_list = ConfigSubscribeLog.objects.values('status_code').distinct()
    updatetime = ConfigSubscribeLog.objects.values('update_time').distinct()
    updatetime_list = []
    for ut in updatetime:
        time = str(ut['update_time'])
        updatetime_list.append({
            'id': ut['update_time'],
            'value': time[0:4] + '-' + time[4:6] + '-' + time[6:8]
        })
    return my_render(request, 'ycc/config_subscribe_list.html', locals())

@login_required
@csrf_exempt
def config_maingroup(request):
    return my_render(request, 'ycc/config_main_group.html', locals())


@login_required
@csrf_exempt
def gray_release_blackip(request):
    return my_render(request, 'ycc/gray_release_blackip.html', locals())


@login_required
@csrf_exempt
def db_association(request):
    group = ConfigGroup.objects.filter(status=1)
    idc = Room.objects.filter(name__in=IDC_SHOW)
    db_insts = ConfigDbInstance.objects.all()
    return my_render(request, 'ycc/db_association.html', locals())


@login_required
@csrf_exempt
def configinfov3list(request):
    # env = ConfigEnv.objects.all()
    env = ConfigEnv.objects.exclude(name='both').order_by('-id')
    queryenvfilter = env.exclude(name='both')
    select_idc_name = []
    select_env_name = []
    group_list = request.user.groups.values()
    app_id = request.GET.get('app_id', None)
    if GROUP_ID['YCC_ADMIN'] in [group['id'] for group in group_list] and not request.user.is_superuser:
        app_id_list = [app.id for app in App.objects.all()]
    else:
        app_id_list = get_app_id_filter_by_request_user(request)

    group_show_list = []
    group = ConfigGroup.objects.filter(idc=1, status=1, app_id__in=app_id_list)
    for g in group:
        group_status_id_tmp = ConfigGroupStatus.objects.get(group=g.id, status=0).id
        group_show_list.append({
            'id': g.id,
            'group_status_id': group_status_id_tmp,
            'group_id': g.group_id
        })
    idc = Room.objects.filter(name__in=IDC_SHOW)
    for i in idc:
        select_idc_name.append(i.name_ch)
    select_idc_name = '&'.join(select_idc_name)
    for e in env:
        select_env_name.append(e.name)
    select_env_name = '&'.join(select_env_name)
    db_instances = ConfigDbInstance.objects.all()
    config_types = ConfigType.objects.all()
    user_for_upload_tmp = request.user
    # is_commit = True if permission(request, ['COMMIT', 'YCC_ADMIN']) else False
    is_commit = True
    # if YCC_ENV == 'production' and not isSaPermission(request):
    #     canEdit = False
    domains = get_domains_by_request_user(request)
    return my_render(request, 'ycc/configinfov3.html', locals())


@login_required
@csrf_exempt
def group_v3(request):
    group_list = request.user.groups.values()
    if GROUP_ID['YCC_ADMIN'] in [group['id'] for group in group_list] and not request.user.is_superuser:
        app_id_list = [app.id for app in App.objects.all()]
    else:
        app_id_list = get_app_id_filter_by_request_user(request)
    is_admin = True if permission(request, ['YCC_ADMIN']) else False
    is_commit = True if permission(request, ['COMMIT', 'YCC_ADMIN']) else False
    config_group_queryset = ConfigGroup.objects.filter(status=1, app_id__in=app_id_list, idc=1)
    config_env_queryset = ConfigEnv.objects.exclude(name='both')
    user = request.user
    return my_render(request, 'ycc/group_v3.html', locals())

@login_required
@csrf_exempt
def room_apps(request):
    rooms=Room.objects.all()
    roomapps={}
    for item in rooms:
        roomapps[item.id]=RoomApps.objects.filter(room=item.id)
    return my_render(request, 'ycc/room_apps.html', locals())


@login_required
@csrf_exempt
def soa_service(request):
    env = ConfigEnv.objects.exclude(name='both').order_by('-id')
    queryenvfilter = env.exclude(name='both')
    select_idc_name = []
    select_env_name = []
    group_list = request.user.groups.values()

    app_show_list = []
    apps = App.objects.filter(status=0)
    for app in apps:
        if SoaService.objects.filter(app__id=app.id).exists():
            app_show_list.append({
                'id': app.id,
                'site_name': app.site.name,
                'app_name': app.name,
                'site_app_name': app.site.name + '_' + app.name
            })
    idc = Room.objects.filter(status=1)
    for i in idc:
        select_idc_name.append(i.name_ch)
    select_idc_name = '&'.join(select_idc_name)
    soa_env = SoaEnv.objects.all()
    for e in env:
        select_env_name.append(e.name)
    select_env_name = '&'.join(select_env_name)
    db_instances = ConfigDbInstance.objects.all()
    user_for_upload_tmp = request.user
    # is_commit = True if permission(request, ['COMMIT', 'YCC_ADMIN']) else False
    is_commit = True
    # if YCC_ENV == 'production' and not isSaPermission(request):
    #     canEdit = False
    domains = get_domains_by_request_user(request)
    user_group_infos = request.user.groups.values_list()
    is_soa_group = False
    for info in user_group_infos:
        if info[0] == 29:
            is_soa_group = True
    # soa_permission = True if request.user.is_superuser or is_soa_group else False
    soa_permission = True if is_soa_group else False
    return my_render(request, 'ycc/soa_service.html', locals())
