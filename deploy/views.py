# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response, HttpResponse, redirect
from rest_framework.authtoken.models import Token
from assetv2.settingsdeploy import STATIC_URL, DEPLOY_INTERVAL, CMDBAPI_URL, ROOT_URL
from users.usercheck import login_required
from cmdb.models import DdDepartmentNew, DdDomain, App, DdUsers, Site
from asset.models import Room
from deploy.models import Deployv3StgMain, DeployCenterMenu, HudsonJob, DeployMain, DeployRollbackReason,DeployMainConfig
from deploy.utils.DeployCommon import get_recursive_node_dict
from datetime import date, timedelta
from util.httplib import httpcall2
from util.utils import *
import json
from assetv2.settingsdeploy import GROUP_ID, DEPLOY_STATIC_APP_ID, STAGING_NETWORK_SEGMENT
from django.conf import settings
from util import webmenu, breadcrumbs


def my_render(request, template, context={}):
    token_obj = Token.objects.get(user_id=request.user.id)
    token = token_obj.key if token_obj else None
    context['API_TOKEN'] = token
    context['UID'] = request.user.id if request.user.id else 0
    context['USER'] = request.user
    context['ROOT_URL'] = ROOT_URL
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)

@login_required
def normal_list(request):
    return my_render(request, 'deploy/normal_list.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL, 'STAGING_NETWORK_SEGMENT': STAGING_NETWORK_SEGMENT})

@login_required
def normal_detail(request):
    depid = request.GET.get('depid')
    return redirect('/deploy/prod/detail/?depid=' + depid)
    # return my_render(request, 'deploy/normal_detail.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL})

@login_required
def gray_list(request):
    return my_render(request, 'deploy/gray_list.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL, 'STAGING_NETWORK_SEGMENT': STAGING_NETWORK_SEGMENT})

@login_required
def gray_detail(request):
    depid = request.GET.get('depid')
    return redirect('/deploy/prod/detail/?depid=' + depid)
    # return my_render(request, 'deploy/gray_detail.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL})

@login_required
def ycc_list(request):
    return my_render(request, 'deploy/ycc_list.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL})


@login_required
def ycc_list_v2(request):
    app_queryset = App.objects.filter(status=0, type=0)
    zone_queryset = Room.objects.filter(ycc_display=True)
    return my_render(request, 'deploy/ycc_list_v2.html', locals())


@login_required
def ycc_detail(request):
    return my_render(request, 'deploy/ycc_detail.html', context={'DEPLOY_INTERVAL': DEPLOY_INTERVAL})


@login_required
def ycc_detail_v2(request):
    dd_users_queryset = DdUsers.objects.filter(enable=0)
    rollback_category_list = list(DeployRollbackReason.CATEGORY)
    return my_render(request, 'deploy/ycc_detail_v2.html', locals())


@login_required
def single_detail(request):
    return my_render(request, 'deploy/single_detail.html')

@login_required
def reboot_detail(request):
    return my_render(request, 'deploy/reboot_detail.html')

@login_required
def redis(request):
    return my_render(request, 'deploy/redis.html')

@login_required
def stg_list(request):
    static_app_id = DEPLOY_STATIC_APP_ID
    group_id_list = [group['id'] for group in request.user.groups.values()]
    is_admin = False
    if request.user.is_superuser or GROUP_ID['DEPLOY'] in group_id_list:
        is_admin = True
    own_domains = get_domains_by_request_user(request)
    applist = get_app_filter_by_request_user(request).filter(status=0).order_by('name')
    site_ids = [a.site_id for a in applist]
    sitelist = Site.objects.filter(status=0, id__in=list(set(site_ids))).order_by('name')
    return my_render(request, 'deploy/stg_list.html', locals())


@login_required
def stg_detail(request):
    return my_render(request, 'deploy/stg_detail.html', locals())


@login_required
def publish_count(request):
    app_list = App.objects.filter(status=0)
    domain_list = DdDomain.objects.filter(enable=0)
    department_list = DdDepartmentNew.objects.filter(enable=0, deptlevel=2)
    start_date = (date.today() - timedelta(7)).strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")
    return my_render(request, 'deploy/publish_count.html', locals())


@login_required
def publish_trend(request):
    start_date = (date.today() - timedelta(7)).strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")
    return my_render(request, 'deploy/publish_trend.html', locals())


@login_required
def center(request):
    # node_dict = json.dumps(get_recursive_node_dict(DeployCenterMenu.objects.filter(parent__isnull=True).first()), skipkeys=True)
    return my_render(request, 'deploy/center2.html', locals())


# @login_required
# def center_my(request):
#     node_dict = json.dumps(get_recursive_node_dict(DeployCenterMenu.objects.filter(name='我的发布').first()), skipkeys=True)
#     return my_render(request, 'deploy/center.html', locals())

@login_required
def dashboard_pool(request):
    applist = []
    error = ''
    try:
        user = DdUsers.objects.get(username=request.user.username, enable=0)
    except DdUsers.DoesNotExist:
        error = '错误: 请联系HR确保你的用户信息存在且正确!'
        return my_render(request, 'deploy/dashboard_pool.html', locals())
    for d in user.domains.all():
        app = App.objects.filter(domainid=d.id).order_by('name')
        for a in app:
            applist.append(a)
    return my_render(request, 'deploy/dashboard_pool.html', locals())


@login_required
def jenkins(request):
    domains = get_domains_by_request_user(request)
    return my_render(request, 'deploy/jenkins.html', locals())


@login_required
def publish_screen(request):
    today = (date.today()).strftime("%Y-%m-%d")
    return my_render(request, 'deploy/publish_screen.html', locals())


@login_required
def publish_largescreen(request):
    today = (date.today()).strftime("%Y-%m-%d")
    return my_render(request, 'deploy/publish_largescreen.html', locals())


@login_required
def path_config(request):
    app_queryset = App.objects.filter(status=0, type=0)
    return my_render(request, 'deploy/path_config.html', locals())


@login_required
def publish_compare(request):
    start_date = (date.today() - timedelta(7)).strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")
    return my_render(request, 'deploy/publish_compare.html', locals())


@login_required
def hudson_job(request):
    app_queryset = App.objects.filter(status=0, type=0)
    job_type_list = list(HudsonJob.JOB_TYPE)
    return my_render(request, 'deploy/hudson_job.html', locals())

@login_required
def process_pattern(request):
    app_queryset = App.objects.filter(status=0,type=0)
    return my_render(request,'deploy/process_pattern.html',locals())

@login_required
def stg_deploy_limit(request):
    applist = App.objects.filter(status=0)
    return my_render(request, 'deploy/stg_deploy_limit.html', locals())


@login_required
def prod_list(request):
    deploy_interval = DEPLOY_INTERVAL
    trident_prefix = settings.TRIDENT['PREFIX']
    static_app_id = settings.DEPLOY_STATIC_APP_ID
    app_queryset = App.objects.filter(status=0, type=0)
    status_list = list(DeployMain.STATUS)
    pack_type_list = list(DeployMain.PACK_TYPE)
    deploy_type_list = list(DeployMain.DEPLOY_TYPE)
    gray_rollback_type_list = list(DeployMain.GRAY_ROLL_TYPE)
    staging_network_segment = settings.STAGING_NETWORK_SEGMENT
    app_id_list = settings.APP_ID_LIST
    return my_render(request, 'deploy/prod_list.html', locals())


@login_required
def prod_detail(request):
    deploy_interval = DEPLOY_INTERVAL
    dd_users_queryset = DdUsers.objects.filter(enable=0)
    rollback_category_list = list(DeployRollbackReason.CATEGORY)
    return my_render(request, 'deploy/prod_detail.html', locals())


@login_required
def bulk_list(request):
    trident_prefix = settings.TRIDENT['PREFIX']
    return my_render(request, 'deploy/bulk_list.html', locals())


@login_required
def rollback_reason(request):
    return my_render(request,'deploy/rollback_reason.html',locals())