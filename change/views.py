# -*- coding: utf-8 -*-

from rest_framework.authtoken.models import Token
from django.shortcuts import render_to_response
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, LOGOUT_URL, LOGIN_URL
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from users.usercheck import login_required
from models import *
from django.db import connections
from django.core.paginator import PageNotAnInteger, Paginator, InvalidPage, EmptyPage
from datetime import  date,timedelta
import datetime
from cmdb.models import News,DdDomain,DdUsers
from django.http import HttpResponse
from util import sendmail
from util.timelib import *
from util import webmenu, breadcrumbs
from util.utils import get_domains_by_request_user

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
@csrf_exempt
def changelist(request):
    ycc_type_id = Type.objects.using('change').get(key=settings.DISABLE_CHANGE_TYPES[0]).id
    type_list = Type.objects.using('change').exclude(id=ycc_type_id)
    action_list = Action.objects.using('change').exclude(type_id=ycc_type_id)
    # type_list = Main.objects.all().using('change').values('type').distinct()
    # action_list = Main.objects.all().using('change').values('action').distinct()
    change_id = request.GET.get('id', None)
    return my_render(request, 'cmdbv2/change/changelist.html', locals())

@login_required
@csrf_exempt
def exception_report(request):
    return my_render(request, 'cmdbv2/change/exception_report.html', locals())

@login_required
@csrf_exempt
def exception_trend(request, id):
    before =  time.mktime((datetime.datetime.now() - datetime.timedelta(days=14)).timetuple())
    start = int(before - (before % 86400))
    endDate = date.today().strftime("%Y-%m-%d")
    startDate = (date.today()-timedelta(14)).strftime("%Y-%m-%d")
    exception_report = ExceptionReport.objects.get(id=id)
    exception_daily = ExceptionReportDaily.objects.filter(report_id = id, create_time__gte = start)
    return my_render(request, 'cmdbv2/change/exception_trend.html', locals())

@login_required
@csrf_exempt
def exception_detail(request, id):
    page1_get = int(request.GET.get("page1", 1))
    page2_get = int(request.GET.get("page2", 1))
    page1_size = 10
    page2_size = 5
    after_range_num = 5
    befor_range_num = 4

    try:
        exception_report = ExceptionReport.objects.get(id=id)
    except Exception, e:
        return  HttpResponse("该异常不存在")
    cursor = connections[exception_report.use_db].cursor()
    cursor.execute(exception_report.cmdbsql)
    results = cursor.fetchall()

    fields = exception_report.fileds.split(",")
    fields_count = len(fields)
    is_superuser=request.user.is_superuser
    mail_list = str(exception_report.db_mail).split(',')
    #排除备注数据已恢复正常的情况
    indexs_ids = [rs[0] for rs in results]
    comments = ExceptionDetailComment.objects.filter(exception_id = id)
    comments_id = [c.index for c in comments]
    for comment in comments:
        if comment.index not in indexs_ids:
            sendmail.sendmail_html(subject='CMDB异常报表存在备注数据已恢复正常',
               html_content='<h1>Hi:</h1><br><h3>异常报表存在备注数据恢复正常，备注信息已删除，原始记录如下</h3>' +
                            '<br>&nbsp;&nbsp;异常名称：<strong>'+ exception_report.cname +
                            '</strong><br>&nbsp;&nbsp;查询日期：<strong>'+ stamp2str(time.time()) +
                            '</strong><br>&nbsp;&nbsp;索引值：<strong>'+ comment.index +
                            '</strong><br>&nbsp;&nbsp;备注信息：<strong>'+ comment.comment +
                            '</strong><br>&nbsp;&nbsp;详细信息请查看以下页面： ' +
                            '<br>&nbsp;&nbsp;&nbsp;&nbsp;http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/' + str(exception_report.id) +
                            '/ <br>&nbsp;&nbsp;请核实被删除备注信息是否恢复正常！<br>&nbsp;&nbsp;谢谢！',
               recipient_list = mail_list)
            comment.delete()

    new_exceptions = []
    for new in results:
        if new[0] not in comments_id:
            new_exceptions.append(new)

    #将异常数据添加备注信息，并分类传送给前台
    data_danger = []
    data_success = []

    domains=get_domains_by_request_user(request)
    domains_name=[item.domainname for item in domains]

    for rs in results:
        if not request.user.is_superuser and not exception_report.owner_domain:
            mark=0
            for i in range(len(fields)):
                if rs[i] in domains_name:
                    mark=1
                    break
            if not mark:
                continue
        comment = ExceptionDetailComment.objects.filter(exception_id = id, index = rs[0]).first()
        if comment:
            rs = list(rs)
            rs.insert(0, comment.id)
            rs.append(comment.comment)
            data_success.append(rs)
        else:
            data_danger.append(rs)

    danger_count = len(data_danger)
    success_count = len(data_success)

    old_count = exception_report.exception_count
    # new_count = len(results) - success_count
    new_count = len(results) - len(ExceptionDetailComment.objects.filter(exception_id = id))
    #更新异常数据数量至exception_report和exception_report_daily表
    current_time = int(time.time())

    time_str = date.today().strftime("%Y-%m-%d")+ ' 00:00:00'
    update_time = int(time.mktime(time.strptime(time_str, '%Y-%m-%d %H:%M:%S')))

    exception_report.exception_count = new_count
    exception_report.last_update = current_time

    #与前一天的异常数做对比，出现新的异常则报警发送邮件
    # if new_count > old_count:
    #     new_exp = ''
    #     for new1 in new_exceptions:
    #         new_exp += str(new1[0]) + '&nbsp;&nbsp;'
    #     sendmail.sendmail_html(subject='CMDB异常报表出现' + str(new_count - old_count) + '条新的异常数据',
    #            html_content='<h1>Hi:</h1><br><h3>异常报表新增' + str(new_count - old_count) + '条异常数据</h3>' +
    #                         '<br>&nbsp;&nbsp;异常名称：<strong>'+ exception_report.cname +
    #                         '</strong><br>&nbsp;&nbsp;出现日期：<strong>'+ stamp2str(time.time()) +
    #                         '</strong><br>&nbsp;&nbsp;异常数据：<strong>'+ new_exp +
    #                         '</strong><br>&nbsp;&nbsp;详细信息请查看以下页面： ' +
    #                         '<br>&nbsp;&nbsp;&nbsp;&nbsp;http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/' + str(exception_report.id) +
    #                         '/ <br>&nbsp;&nbsp;请尽快排查数据数据出现的原因并做处理！<br>&nbsp;&nbsp;谢谢！',
    #            recipient_list = mail_list)

    daily, created = ExceptionReportDaily.objects.get_or_create(report_id=exception_report.id, create_time=update_time,defaults={
        'exception_count': new_count,
    })
    if not created:
        daily.exception_count = new_count
        daily.save()

    exception_report.save()


    try:
        page1 = page1_get
        if page1 < 1:
            page1 = 1
    except ValueError:
        page1 = 1
    paginator1 = Paginator(data_danger, page1_size)
    try:
        data_danger = paginator1.page(page1)
    except(EmptyPage, InvalidPage, PageNotAnInteger):
        data_danger = paginator1.page(paginator1.num_pages)
    if page1 >= after_range_num:
        page1_range = paginator1.page_range[page1-after_range_num:page1+befor_range_num]
    else:
        page1_range = paginator1.page_range[0:int(page1)+befor_range_num]

    try:
        page2 = page2_get
        if page2 < 1:
            page2 = 1
    except ValueError:
        page2 = 1
    paginator2 = Paginator(data_success, page2_size)
    try:
        data_success = paginator2.page(page2)
    except(EmptyPage, InvalidPage, PageNotAnInteger):
        data_success = paginator2.page(paginator2.num_pages)
    if page2 >= after_range_num:
        page2_range = paginator2.page_range[page2-after_range_num:page2+befor_range_num]
    else:
        page2_range = paginator2.page_range[0:int(page2)+befor_range_num]
    return my_render(request, 'cmdbv2/change/exception_detail.html', locals())

@login_required
@csrf_exempt
def exception_comment_insert(request):
    exception_id = request.POST['exception_id']
    index = request.POST['index']
    comment = request.POST['comment']
    new_comment = ExceptionDetailComment.objects.create(exception_id = exception_id, index = index, comment = comment)
    new_comment.save()
    return HttpResponse('success')

@login_required
@csrf_exempt
def exception_comment_update(request):
    id = request.POST['id']
    comment = request.POST['comment']
    old_comment = ExceptionDetailComment.objects.get(id = id)
    old_comment.comment = comment
    old_comment.save()
    return HttpResponse('success')

@login_required
@csrf_exempt
def exception_comment_delete(request):
    id = request.POST['id']
    old_comment = ExceptionDetailComment.objects.get(id = id)
    old_comment.delete()
    return HttpResponse('success')

@login_required
@csrf_exempt
def exception_detail_api(request):
    exception_report_id=request.GET.get('exception_report_id')
    # limit=request.GET.get('limit')
    try:
        exception_report=ExceptionReport.objects.get(id=exception_report_id,type=1)
    except Exception,e:
        return  HttpResponse("该页面不存在")
    titles = exception_report.fileds.strip().replace('，',',').encode('utf8').split(',')
    api_fields=exception_report.api_fields.strip().replace('，',',').encode('utf8').split(',')
    if api_fields[-1] =='':
        api_fields=api_fields[:-1]
    field_titles={}
    for i in range(0,len(api_fields)):
        field_titles[api_fields[i]]=titles[i]
    api_url=exception_report.api_url.strip()

    username=request.user.username
    # if limit=='0':
    domain_all=DdDomain.objects.filter(enable=0)
    app_all=App.objects.filter(status=0)
    # else:
    domain=DdUsers.objects.get(username=username,enable=0).domains.all()
    app=App.objects.filter(status=0,domainid__in=[obj.id for obj in domain])
    return my_render(request, 'cmdbv2/change/exception_detail_api.html', locals())