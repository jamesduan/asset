# -*- coding: utf-8 -*-
import time

from django.shortcuts import render_to_response
from rest_framework.authtoken.models import Token
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, LOGIN_URL, LOGOUT_URL
from users.usercheck import login_required
from util.timelib import *
from cmdb.models import News
from util import webmenu
from models import DnsZoneEnv, DnsZone
from cmdb.models import DdUsers, DdUsersDomains


def my_render(request, template, context={}):
    tokenobj = Token.objects.get(user_id=request.user.id)
    token = tokenobj.key if tokenobj is not None else None
    expire_date = stamp2datestr(int(time.time()) - 7*24*3600)
    news = News.objects.filter(created__gte=expire_date, status=1).order_by('-id')[:1]
    for item in news:
        context['GLOBAL_NEWS'] = item
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)


def is_valid_and_is_dba(user_name):
    # 78  --- SA
    # 108 --- DBA
    # 171 --- devOps
    valid_obj = DdUsersDomains.objects.filter(dddomain__id__in=[78, 108, 171])
    valid_ids = [x.ddusers_id for x in valid_obj]
    dba_ids = [x.ddusers_id for x in valid_obj if x.dddomain_id == 108]

    try:
        user_id = DdUsers.objects.get(username=user_name).id
    except DdUsers.DoesNotExist:
        user_id = -1

    return user_id in valid_ids, user_id in dba_ids


@login_required
def zone(request):
    dns_zone_env = DnsZoneEnv.objects.all()

    user_name = request.user.username
    is_valid, is_dba = is_valid_and_is_dba(user_name)
    is_dba = int(is_dba)
    # is_dba = 1  # debug_fxc

    if is_valid:
    # if True:  # debug_fxc
        return my_render(request, 'dns/zone.html', locals())
    else:
        return my_render(request, 'dns/dns_403.html', locals())


@login_required
def record(request):
    dns_zone_id = request.GET.get('zone_id')
    dns_zone = DnsZone.objects.get(id=dns_zone_id)
    ttl = dns_zone.ttl

    user_name = request.user.username
    is_valid, is_dba = is_valid_and_is_dba(user_name)
    is_dba = int(is_dba)
    # is_dba = 1  # debug_fxc

    if is_valid:
    # if True:  # debug_fxc
        return my_render(request, 'dns/record.html', locals())
    else:
        return my_render(request, 'dns/dns_403.html', locals())
