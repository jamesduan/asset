# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response, HttpResponse
from rest_framework.authtoken.models import Token
from assetv2.settingsmonitor import STATIC_URL, CMDBAPI_URL, ROOT_URL
from users.usercheck import login_required
from util import webmenu
from monitor.models import EventLevelMap, EventTypeMap, EventSourceMap
from cmdb.models import Site, App, DdDomain
from datetime import date, datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
import json
import time



class BasicInfo(object):
    """basic class which get the infomation such as domain、site、app ..."""
    @staticmethod
    def get_site_list():
        sites = Site.objects.filter(status=0)
        site_map = {}
        for i in sites:
            tmp_map = {}
            tmp_map['id'] = i.id
            tmp_map['name'] = i.name
            site_map[i.id] = tmp_map
        return site_map

    @staticmethod
    def get_app_list():
        apps = App.objects.filter(status=0)
        sites = Site.objects.filter(status=0)

        site_map = BasicInfo.get_site_list()
        app_list = []
        for j in apps:
            tmp_map = {}
            tmp_map['id'] = j.id
            tmp_map['name'] = j.name
            tmp_map['site'] = site_map[j.site_id] if j.site_id in site_map else {}

            app_list.append(tmp_map)

        return app_list
        # return json.dumps(app_list)


def hello(request):
    return HttpResponse("Hello world...")


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
def alarmlist(request):
    alarm_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_type_list = EventTypeMap.objects.all()
    event_level_list = EventLevelMap.objects.all()
    app_list = BasicInfo.get_app_list()
    # app_list = App.objects.all()
    start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    end_time = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")

    return my_render(request, 'monitor/alarmlist.html', locals())

@login_required
def eventlist(request):
    event_type_list = EventTypeMap.objects.all()
    event_source_list =EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    # site_list = Site.objects.all()
    # app_list = App.objects.all()
    site_list = BasicInfo.get_site_list()
    app_list = BasicInfo.get_app_list()

    start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    end_time = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
    return my_render(request, 'monitor/eventlist.html', locals())

@login_required
def undone_event(request):
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    # site_list = Site.objects.all()
    # app_list = App.objects.all()
    site_list = BasicInfo.get_site_list()
    app_list = BasicInfo.get_app_list()
    return my_render(request, 'monitor/undone_event.html', locals())


@login_required
def event_filter_keyword(request):
    start_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    # app_list = App.objects.all()
    app_list = BasicInfo.get_app_list()
    return my_render(request, 'monitor/eventfilter.html', locals())


@login_required
def event_convergence_rule(request):
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    app_list = BasicInfo.get_app_list()
    # app_list = App.objects.all()
    return my_render(request, 'monitor/event_convergence_rule.html', locals())


@login_required
def event_AI(request):
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    app_list = BasicInfo.get_app_list()
    return my_render(request, 'monitor/event_AI.html', locals())


@login_required
def source_detail(request):
    SOURCE_DOMAIN = {}
    source_id = request.GET.get('id', '')

    if not source_id:
        return HttpResponse("Source id not provided, please check.")

    try:
        src = EventSourceMap.objects.get(id=source_id)
        domain_id = src.domain_id
    except EventSourceMap.DoesNotExist:
        domain_id = None

    domain = None
    if domain_id:
        try:
            domain = DdDomain.objects.get(id=domain_id)
        except DdDomain.DoesNotExist:
            domain = None

    if domain:
        d_name = domain.domainname
        d_leader = domain.domainleaderaccount
        d_tel = domain.telephone.telephone
        SOURCE_DOMAIN = {'name': d_name, 'leader': d_leader, 'tel': d_tel}

    return my_render(request, 'monitor/sourcedetail.html', locals())


@login_required
def event_level_adjustment(request):
    start_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    app_list = BasicInfo.get_app_list()
    return my_render(request, 'monitor/event_level_adjustment.html', locals())


@login_required
def event_mask(request):
    start_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_type_list = EventTypeMap.objects.all()
    event_source_list = EventSourceMap.objects.exclude(domain_id=0)
    event_level_list = EventLevelMap.objects.all()
    app_list = BasicInfo.get_app_list()
    return my_render(request, 'monitor/event_mask.html', locals())


@login_required
def event_confirmation(request):
    return my_render(request, 'monitor/event_confirmation.html', locals())