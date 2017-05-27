# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response, HttpResponse, HttpResponseRedirect
from rest_framework.authtoken.models import Token
from assetv2.settingsaccident import STATIC_URL, CMDBAPI_URL, ROOT_URL, CMDBV2_URL, MONITOR_URL, MEDIA_URL, OMS_HOST, DOMAIN_HEAD_ID, GROUP_ID
from users.usercheck import login_required
from accident.models import AccidentParentType, AccidentType, AccidentStatus, Accident, AccidentLog, AccidentOtherDomain
from cmdb.models import DdDepartmentNew, DdDomain, DdDomainV2, DdUsers, Rota, RotaMan, RotaBackup, WebMenu, AppV2
from monitor.models import EventSourceMap, EventTypeMap, EventLevelMap
from change.models import Type, Action
from datetime import date, timedelta, datetime
import calendar
from util.timelib import stamp2str, str2stamp
import requests
import xlwt
import StringIO
from util import webmenu, breadcrumbs
import time
from assetv2.settingsaccident import GROUP_ID


def my_render(request, template, context={}):
    token_obj = Token.objects.get(user_id=request.user.id)
    token = token_obj.key if token_obj else None
    context['API_TOKEN'] = token
    context['UID'] = request.user.id if request.user.id else 0
    context['USER'] = request.user
    context['ROOT_URL'] = ROOT_URL
    context['STATIC_URL'] = STATIC_URL
    context['MEDIA_URL'] = MEDIA_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread

    return render_to_response(template, context)


@login_required
def accident_center(request):
    try:
        accident = Accident.objects.using('accident').get(is_accident=0, status_id=1)
    except Accident.DoesNotExist:
        accident = None
    if accident:
        user_list = DdUsers.objects.using('default').filter(enable=0)
        cmdbv2_url = CMDBV2_URL
        monitor_url = MONITOR_URL
        media_url_reg = 'http://' + OMS_HOST + MEDIA_URL
        current_time = stamp2str(int(time.time()))
        try:
            cur_rota = Rota.objects.using('default').get(promotion=0, duty_domain=DOMAIN_HEAD_ID,
                                                         duty_date_start__lt=current_time,
                                                         duty_date_end__gte=current_time)
            duty_manager = cur_rota.duty_man.all().first()
            back_duty_manager = cur_rota.duty_backup.all().first()
        except (Rota.DoesNotExist, Rota.MultipleObjectsReturned):
            duty_manager = None
            back_duty_manager = None
        return my_render(request, 'accident/center_accident.html', locals())
    else:
        return my_render(request, 'accident/center_normal.html', locals())



@login_required
def pool_influence(request):
    try:
        accident = Accident.objects.using('accident').get(is_accident=0, status_id=1)
    except Accident.DoesNotExist:
        accident = None
    return my_render(request, 'accident/pool_influence.html', locals())


@login_required
def accident_list(request):
    accident_status = AccidentStatus.objects.using('accident').all()
    accident_parent_type = AccidentParentType.objects.using('accident').filter(enable=0)
    accident_type = AccidentType.objects.using('accident').filter(enable=0)
    dept_level2 = DdDepartmentNew.objects.filter(deptlevel=2, enable=0)
    domain_list = DdDomainV2.objects.filter(enable = 0).exclude(id=DOMAIN_HEAD_ID)
    today = date.today()
    start_date = (today - timedelta(7)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    user_list = DdUsers.objects.filter(enable=0)
    current_time = stamp2str(int(time.time()))
    try:
        cur_rota = Rota.objects.using('default').get(promotion=0, duty_domain=DOMAIN_HEAD_ID, duty_date_start__lt=current_time, duty_date_end__gte=current_time)
        duty_manager = cur_rota.duty_man.all().first()
        back_duty_manager = cur_rota.duty_backup.all().first()
    except (Rota.DoesNotExist, Rota.MultipleObjectsReturned):
        duty_manager = None
        back_duty_manager = None

    edit_visible = False
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    if request.user.is_superuser or GROUP_ID['ACCIDENT_MASTER'] in group_id_list or GROUP_ID['ACCIDENT_MONITOR'] in group_id_list:
        edit_visible = True
    other_domain_list = AccidentOtherDomain.objects.all()
    return my_render(request, 'accident/accident_list.html', locals())


@login_required
def load_accident(request):
    api_url = '%saccident/accident/all/?%s' % (CMDBAPI_URL, ('&'.join([k+'='+v for k,v in zip(request.GET.keys(), request.GET.values())])))
    headers = {'Authorization':'Basic YWNjaWRlbnQ6ODVCKFVQcFkyM00pKl5ibl4='}
    res = requests.get(api_url, headers=headers)
    if res.status_code != 200:
        return HttpResponse(u'获取导出数据出现错误，请联系平台研发刘亚婷')
    data = res.json()
    # 设置excel表格头样式
    head_style = xlwt.XFStyle()

    # 设置对齐方式
    head_alignment = xlwt.Alignment()
    head_alignment.horz = xlwt.Alignment.HORZ_CENTER
    head_alignment.vert = xlwt.Alignment.VERT_CENTER
    head_style.alignment = head_alignment

    # 设置excel表格内容样式
    content_style = xlwt.XFStyle()
    # 设置对齐方式
    alignment = xlwt.Alignment()
    alignment.horz = xlwt.Alignment.HORZ_LEFT
    alignment.vert = xlwt.Alignment.VERT_CENTER
    content_style.alignment = alignment

    file = xlwt.Workbook(encoding='utf-8')
    table = file.add_sheet(u"历史事故列表", cell_overwrite_ok=True)
    table.row(0).set_style(xlwt.easyxf('font:height 380;'))

    # 写入excel表格头
    head = [u'编号', u'值班经理', u'值班经理账号', u'事故编号', u'事故等级',  u'事故名称', u'发生时间', u'影响范围',  u'影响时长', u'是否影响可用性', u'事故原因', u'责任部门', u'处理经过',
            u'责任Domain', u'责任人', u'事故类型', u'根源分类',
            u'是否处罚', u'处罚人', u'处罚信息', u'Mantis编号', u'事故状态',  u'恢复时间', u'基本信息填写SLA', u'详细信息填写SLA', u'备注', u'是否电商系统', u'调校系数' ]

    for col in range(0,len(head)):
        if col ==0:
            table.col(col).width = 1400
        else:
            table.col(col).width = 4000
        table.write(0, col, head[col], head_style)
    # 循环写入表格数据
    row = 1     # 表格当前行
    for id, item in enumerate(data):
        value = [id+1,item['duty_manager_name_ch'], item['duty_manager_name'], item['accidentid'],  item['level_name'], item['title'], stamp2str(item['happened_time'], '%Y-%m-%d %H:%M'),
                item['affect'], item['time_length'], '是' if item['is_available'] else '否', item['reason'], item['duty_dept_names'],  item['process'],
                item['duty_domain_names'], item['duty_users'], item['type_parent_name'],
                item['type_name'],  '是' if item['is_punish'] else '否', item['punish_users'], item['punish_content'], item['mantis_id'],
                item['status_name'], stamp2str(item['finish_time'], '%Y-%m-%d %H:%M'), item['basic_sla'], item['detail_sla'], item['comment'], item['is_online_str'], item['health']]
        table.write(row, 0, value[0], head_style)
        for col1 in range(1,len(head)):
            table.write(row, col1, value[col1], content_style)
        table.row(row).set_style(xlwt.easyxf('font:height 300;'))
        row += 1

    sio = StringIO.StringIO()
    file.save(sio)
    response = HttpResponse(sio.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=accident_list@%s.xls' % date.today().strftime("%Y%m%d")
    response.write(sio.getvalue())
    return response


@login_required
def load_accident_all(request):
    api_url = '%saccident/accident/all/?%s' % (CMDBAPI_URL, ('&'.join([k+'='+v for k,v in zip(request.GET.keys(), request.GET.values())])))
    headers = {'Authorization':'Basic YWNjaWRlbnQ6ODVCKFVQcFkyM00pKl5ibl4='}
    res = requests.get(api_url, headers=headers)
    if res.status_code != 200:
        return HttpResponse(u'获取导出数据出现错误，请联系平台研发刘亚婷')
    data = res.json()
    # 设置excel表格头样式
    head_style = xlwt.XFStyle()

    # 设置对齐方式
    head_alignment = xlwt.Alignment()
    head_alignment.horz = xlwt.Alignment.HORZ_CENTER
    head_alignment.vert = xlwt.Alignment.VERT_CENTER
    head_style.alignment = head_alignment

    # 设置excel表格内容样式
    content_style = xlwt.XFStyle()
    # 设置对齐方式
    alignment = xlwt.Alignment()
    alignment.horz = xlwt.Alignment.HORZ_LEFT
    alignment.vert = xlwt.Alignment.VERT_CENTER
    content_style.alignment = alignment

    file = xlwt.Workbook(encoding='utf-8')
    table = file.add_sheet(u"历史事故列表(附Action)", cell_overwrite_ok=True)
    table.row(0).set_style(xlwt.easyxf('font:height 380;'))

    # 写入excel表格头
    head = [u'编号', u'值班经理', u'值班经理账号', u'事故编号', u'事故等级',  u'事故名称', u'发生时间', u'影响范围',  u'影响时长', u'是否影响可用性', u'事故原因', u'责任部门', u'处理经过',
            u'改进措施', u'责任Domain', u'责任人', u'事故类型', u'根源分类',  u'措施负责部门', u'措施负责人', u'改进措施预计完成时间',
            u'改进措施状态', u'是否处罚', u'处罚人', u'处罚信息', u'Mantis编号', u'事故状态',  u'恢复时间', u'基本信息填写SLA', u'详细信息填写SLA', u'备注',u'是否电商系统', u'调校系数']

    for col in range(0,len(head)):
        if col ==0:
            table.col(col).width = 1400
        else:
            table.col(col).width = 4000
        table.write(0, col, head[col], head_style)
    # 循环写入表格数据
    row = 1     # 表格当前行
    for id, item in enumerate(data):
        actions = item['action']
        cur_row = row
        if actions is not None and len(actions) > 0:
            for action in actions:
                try:
                    value = [id+1, item['duty_manager_name_ch'], item['duty_manager_name'], item['accidentid'],  item['level_name'], item['title'], stamp2str(item['happened_time'], '%Y-%m-%d %H:%M'),
                            item['affect'], item['time_length'], '是' if item['is_available'] else '否', item['reason'], item['duty_dept_names'],  item['process'],
                            action['action'], item['duty_domain_names'], item['duty_users'], item['type_parent_name'],
                            item['type_name'],  action['dutydept_name'], action['duty_users'], stamp2str(action['expect_time'], '%Y-%m-%d'), action['status_name'],
                            '是' if item['is_punish'] else '否', item['punish_users'], item['punish_content'], item['mantis_id'],
                            item['status_name'], stamp2str(item['finish_time'], '%Y-%m-%d %H:%M'), item['basic_sla'], item['detail_sla'], item['comment'], item['is_online_str'], item['health']]
                    table.write(row, 0, value[0], head_style)
                    for col1 in range(1,len(head)):
                        table.write(row, col1, value[col1], content_style)
                    table.row(row).set_style(xlwt.easyxf('font:height 300;'))
                    row += 1
                except Exception,e:
                    return HttpResponse(u"事故%s改进措施数据格式非法,action_id=%s,请联系平台研发刘亚婷" % (str(item['accidentid']), str(action['id'])))
            table.write_merge(cur_row, row-1, 0, 0, value[0], head_style)
        else:
            value = [id+1, item['duty_manager_name_ch'], item['duty_manager_name'], item['accidentid'], item['level_name'], item['title'], stamp2str(item['happened_time'], '%Y-%m-%d %H:%M'),
                    item['affect'], item['time_length'], '是' if item['is_available'] else '否', item['reason'], item['duty_dept_names'], item['process'],
                    u'', item['duty_domain_names'], item['duty_users'], item['type_parent_name'],
                    item['type_name'],  u'', u'', u'',
                    u'', '是' if item['is_punish'] else '否', item['punish_users'], item['punish_content'], item['mantis_id'],
                    item['status_name'], stamp2str(item['finish_time'], '%Y-%m-%d %H:%M'), item['basic_sla'], item['detail_sla'], item['comment'], item['is_online_str'], item['health']]
            table.write(row, 0, value[0], head_style)
            for col3 in range(1,len(head)):
                table.write(row, col3, value[col3], content_style)
            table.row(row).set_style(xlwt.easyxf('font:height 300;'))
            row += 1

    sio = StringIO.StringIO()
    file.save(sio)
    response = HttpResponse(sio.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=accident_list@%s.xls' % date.today().strftime("%Y%m%d")
    response.write(sio.getvalue())
    return response


@login_required
def accident_detail(request):
    accidentid = request.GET.get('id')
    accident_parent_type = AccidentParentType.objects.using('accident').filter(enable=0)
    accident_type = AccidentType.objects.using('accident').filter(enable=0)
    dept_level2 = DdDepartmentNew.objects.filter(deptlevel=2, enable=0)
    domain_list = DdDomainV2.objects.filter(enable=0).exclude(id=DOMAIN_HEAD_ID)
    try:
        accident = Accident.objects.using('accident').get(accidentid=accidentid)
    except Accident.DoesNotExist:
        accident = None
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    username = request.user.username
    is_edit_action = True if request.user.is_superuser or GROUP_ID['ACCIDENT_MASTER'] in group_id_list or username == accident.duty_manager_name or username in accident.duty_users else False
    # duty_domain_count = accident.duty_domains.count()
    other_domain_list = AccidentOtherDomain.objects.all()
    return my_render(request, 'accident/accident_detail.html', locals())


@login_required
def accident_process(request):
    accidentid = request.GET.get('id')
    try:
        accident = Accident.objects.using('accident').get(accidentid=accidentid)
        if accident.status_id == 1 and accident.is_accident == 0:
            return HttpResponseRedirect('/accident/center/')
    except Accident.DoesNotExist:
        accident = None
    return my_render(request, 'accident/accident_process.html', locals())


@login_required
def sla_domain(request):
    today = date.today()
    year = today.year
    month = today.month
    last_month = month - 1
    if month == 1:
        last_month = 12
        year -= 1
    start_date = datetime(year, last_month, 1).strftime("%Y-%m-%d")
    end_date = (date(year, month, 1) - timedelta(1)).strftime("%Y-%m-%d")
    # end_date = (datetime(year, month, 1) + timedelta(days=last_month_day)).strftime("%Y-%m-%d")
    dept_level2 = DdDepartmentNew.objects.filter(deptlevel=2, enable=0)
    dept_list = DdDepartmentNew.objects.filter(deptlevel=3, enable=0)
    domain_list = DdDomainV2.objects.filter(enable=0).exclude(id=DOMAIN_HEAD_ID)
    other_domain_list = AccidentOtherDomain.objects.all()
    return my_render(request, 'accident/sla_domain.html', locals())