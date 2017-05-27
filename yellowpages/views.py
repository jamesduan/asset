from django.shortcuts import render
from rest_framework.authtoken.models import Token
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, LOGOUT_URL, LOGIN_URL
from django.shortcuts import render_to_response, HttpResponse
from users.usercheck import login_required
from util import webmenu
from cmdb.models import App
from ycc.models import ConfigGroup
# Create your views here.

def my_render(request, template, context={}):
    try:
        tokenobj = Token.objects.get(user_id=request.user.id)
    except Token.DoesNotExist:
        return HttpResponse(content='Token matching query does not exist',status=400)
    token = tokenobj.key if tokenobj is not None else None
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL
    context['HELP_URL'] = "http://oms.yihaodian.com.cn/docs/?p=637"
    context['FEEDBACK_URL'] = "http://oms.yihaodian.com.cn/docs/?p=684"

    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)

@login_required
def pool_dependence(request):
    apps=App.objects.filter(status=0)
    configgroup= ConfigGroup.objects.filter(status=1).values('group_id').distinct()
    return my_render(request,'yellowpages/pool_dependence.html',locals())