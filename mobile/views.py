# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from rest_framework.authtoken.models import Token
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import logout
from assetv2.settings_mobile import ROOT_URL, STATIC_URL
from models import AuthUser
from cmdb.models import DdUsers, RotaActivity, DdDomainV2, DdDepartmentNew
import json

def my_render(request, template, context={}):
    #user_id = 1025
    user_id = request.user.id

    #权限判断
    authuser_obj = AuthUser.objects.get(pk=user_id)
    if not authuser_obj.is_app:
        logout(request)
        return render_to_response('mobile/register.html', context)

    token_obj = Token.objects.get(user_id=user_id)
    token = token_obj.key if token_obj else None
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL
    context['STATIC_URL'] = STATIC_URL
    return render_to_response(template, context)


#def login(request):
#    return my_render(request,'mobile/login.html',locals())

def register(request):
    return render_to_response('mobile/register.html',locals())

@login_required
def loginout(request):
    logout(request, ROOT_URL + 'login/')
    return HttpResponseRedirect(ROOT_URL + 'login/')

@login_required
def home(request):
    return my_render(request,'mobile/home.html',locals())

@login_required
def personal(request):
    try:
        user = DdUsers.objects.using('default').get(username=request.user.username, enable=0)
        dept = user.dept_level2
    except DdUsers.DoesNotExist:
        user = None
        dept = None
    domain_list = user.domains.all()
    domain = None
    if domain_list.count() == 1:
        domain = domain_list.first()
    return my_render(request,'mobile/personal/center.html',locals())


@login_required
def orderchart(request):
    return my_render(request,'mobile/monitor/orderchart.html',locals())


@login_required
def personal_info(request):
    return my_render(request,'mobile/personal/info.html',locals())


@login_required
def yellow_find_user(request):
    return my_render(request,'mobile/yellowpages/find_user.html',locals())


@login_required
def yellow_find_user_result(request):
    username = request.GET.get('username')
    return my_render(request,'mobile/yellowpages/find_user_result.html',locals())


@login_required
def yellow_duty_list(request):
    return my_render(request,'mobile/yellowpages/duty_list.html',locals())


@login_required
def yellow_duty_detail(request):
    activity_id = request.GET.get('activity_id', '')
    if activity_id:
        try:
            activity = RotaActivity.objects.using('default').get(id=int(activity_id))
        except RotaActivity.DoesNotExist:
            activity = None
        if activity:
            start_time = activity.start_time.strftime('%m/%d %H:%M')
            end_time = activity.start_time.strftime('%m/%d %H:%M')
    return my_render(request,'mobile/yellowpages/duty_detail.html',locals())


@login_required
def base(request):
    return my_render(request,'mobile/base/home.html',locals())


@login_required
def base_monitor(request):
    return my_render(request,'mobile/base/monitor.html',locals())


@login_required
def base_yellowpage(request):
    return my_render(request,'mobile/base/yellowpage.html',locals())


@login_required
def base_mime(request):
    return my_render(request,'mobile/base/mime.html',locals())

# @login_required
# def test(request):
#     return my_render(request,'mobile/test.html',locals())