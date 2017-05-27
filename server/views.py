# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response
from rest_framework.authtoken.models import Token
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, NVWA_PHYSICS_INSTALL_API, LOGOUT_URL, LOGIN_URL
from users.usercheck import login_required
from server.models import ServerOsTemplate, ServerAppTemplate, ServerEnv, ServerStatus, ServerType
from asset.models import Room
from cmdb.models import News, Site, App
from util.timelib import *
from util import webmenu, breadcrumbs
from server.models import Server,LogMain
from django.conf import settings

def my_render(request, template, context={}):
    tokenobj = Token.objects.get(user_id=request.user.id)
    token = tokenobj.key if tokenobj is not None else None
    expire_date = stamp2datestr(int(time.time()) - 7*24*3600)
    news = News.objects.filter(created__gte=expire_date, status=1).order_by('-id')[:1]
    for item in news:
        context['GLOBAL_NEWS'] = item
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)

@login_required
def serverinstalllist(request):
    search = request.GET.get('search', '')
    server_os_template = ServerOsTemplate.objects.filter(status=1)
    server_app_template = ServerAppTemplate.objects.filter(status=1)
    server_status = ServerStatus.objects.exclude(id=400)
    server_type = ServerType.objects.all()
    physics_api = NVWA_PHYSICS_INSTALL_API
    return my_render(request, 'cmdbv2/server/serverinstalllist.html', locals())


@login_required
def servervirtuallist(request):
    vm_install_configuration = settings.VM_INSTALL_CONFIGURATION
    vm_host_app_id_list = ','.join([str(app_id) for app_id in settings.VM_HOST_APP_ID_LIST])
    return my_render(request, 'cmdbv2/server/servervirtuallist.html', locals())


@login_required
def serverlist(request):
    server_status = ServerStatus.objects.exclude(id=400)
    server_env = ServerEnv.objects.all()
    server_type = ServerType.objects.all()
    room = Room.objects.all()
    site = Site.objects.all()
    app = App.objects.filter(status=0)
    return my_render(request, 'cmdbv2/server/serverlist.html', locals())


@login_required
def lb_group(request):
    app_queryset = App.objects.filter(status=0)
    return my_render(request, 'cmdbv2/server/server_lb_group.html', locals())


@login_required
def server_detail(request):
    id = request.GET.get('id')
    if id:
        try:
            server = Server.objects.exclude(server_status_id=400).get(id = id)
        except:
            server = None
    return my_render(request, 'globalsearch/server/serverdetail.html', locals())

@login_required
def server_log(request):
    type=request.GET.get('type')
    action=request.GET.get('action')
    index=request.GET.get('index')
    filters = {}
    if type:
        filters['type'] = type
    if action:
        filters['action'] = action
    if index:
        filters['index'] = index

    details = LogMain.objects.filter(**filters).order_by('-happen_time')
    return my_render(request, 'cmdbv2/server/server_log.html', locals())