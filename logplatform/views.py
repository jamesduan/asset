# -*- coding: utf-8 -*-
import time
from util.timelib import *
from django.shortcuts import render_to_response
from rest_framework.authtoken.models import Token
from assetv2.settingslogplatform import STATIC_URL, CMDBAPI_URL, ROOT_URL, CMDBAPI_USER, CMDBAPI_PASS, LOGIN_URL, LOGOUT_URL
from util.timelib import stamp2str
from users.usercheck import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import csv
from cmdb.models import News
from datetime import datetime
from django.core.paginator import PageNotAnInteger, Paginator, InvalidPage, EmptyPage
from util import webmenu

from logplatform.models import Reg

DB_ALIA = 'logplatform'


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


@login_required
def regmain(request):
    reg = Reg.objects.using(DB_ALIA).all()

    return my_render(request, 'logplatform/reg/reg.html', locals())


@login_required
def rule(request):
    reg = Reg.objects.using(DB_ALIA).all()

    return my_render(request, 'logplatform/reg/rule.html', locals())
