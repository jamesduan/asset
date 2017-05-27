# -*- coding: utf-8 -*-
from rest_framework.authtoken.models import Token
from django.shortcuts import render_to_response, HttpResponse
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, LOGOUT_URL, LOGIN_URL, HYBRID_CDS_REQUIRE_TASK
from django.views.decorators.csrf import csrf_exempt
from users.usercheck import login_required
from models import *
from asset.models import Room
from cmdb.models import News
from util.timelib import *

# Create your views here.
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
    return render_to_response(template, context)


@login_required
@csrf_exempt
def requirementlist(request):
    hybrid_url = HYBRID_CDS_REQUIRE_TASK
    return my_render(request, 'cmdbv2/hybrid/requirementlist.html', locals())


@login_required
@csrf_exempt
def requirementdetaillist(request):
    requirement = HybridRequirement.objects.all().order_by("-id")
    return my_render(request, 'cmdbv2/hybrid/requirementdetaillist.html', locals())