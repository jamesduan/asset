# -*- coding: utf-8 -*-

from rest_framework import generics
from rest_framework import filters
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.parsers import MultiPartParser
from serializers import *
from accident.models import *
from util.timelib import str2stamp, stamp2str
from util.sendmail import sendmail_co
from django.template.loader import get_template
from django.template import Context
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from assetv2.settingsapi import GROUP_ID, DOMAIN_HEAD_ID, SUBMIT_MANTIS_URL, SUBMIT_MANTIS_POST
import time
from datetime import date
import json
import requests
from monitor.models import Event, EventDetail
from cmdb.models import Rota, RotaMan, RotaBackup, App, AppContact, Site, DdDomainV2, AppV2
import urllib


class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class AccidentTypeList(generics.ListAPIView):
    """
    事故根源类型查询.

    输入参数：
    * id                    -   PK
    * ptype_id              -   上级根源类型ID

    输出参数：

    * id                    -   PK
    * ptype_id              -   上级根源类型ID
    * ptype                 -   上级根源类型
    * name                  -   action内容

    """

    queryset = AccidentType.objects.using('accident').select_related().filter(enable=0).order_by('id')
    serializer_class = AccidentTypeSerializer
    filter_fields = ('ptype__id',)
    filter_backends = (filters.DjangoFilterBackend,)
    paginate_by = None


class AccidentList(generics.ListCreateAPIView):
    """
    事故列表页/创建事故.

    输入参数：
    * id                        -   PK
    * accidentid                -   事故编号
    * title                     -   事故名称
    * level                     -   事故等级
    * find_user_name            -   事故发现人
    * duty_manager_name         -   值班经理
    * happened_time             -   事故发生时间
    * finish_time              -    事故恢复时间
    * status                    -   事故状态
    * is_accident               -   是否事故

    输出参数：

    * id                        -   PK
    * accidentid                -   事故编号(int)
    * title                     -   事故名称(string)
    * level_name                -   事故等级(string)
    * find_user_id              -   事故发现人ID(int)
    * find_user_name            -   事故发现人(string)
    * duty_manager_id           -   值班经理ID(int)
    * duty_manager_name         -   值班经理(string)
    * happened_time             -   事故发生时间(int)
    * finish_time               -   事故恢复时间(int)
    * reason                    -   事故原因(text)
    * status_name               -   事故状态(string)
    * is_accident               -   是否事故(int) 0 是   1 否

    * comment                   -   事故备注(string)

    * duty_dept_names           -   责任部门(string) 多个，逗号分隔
    * duty_domain_names         -   责任Domain(string) 多个，逗号分隔
    * duty_users                -   责任报告人(string) 多个，逗号分隔
    * type_parent_name          -   事故根源类型(string)
    * type_name                 -   事故类型(string)
    * is_punish                 -   是否处罚(int) 0 不处罚  1 处罚

    """
    queryset = Accident.objects.using('accident').all().order_by('-accidentid')
    filter_fields = ('status__id', 'level', 'type__ptype__id', 'type__id', 'is_punish', 'is_accident')
    search_fields = ('accidentid', 'title', 'duty_manager_name', 'find_user_name', 'duty_users', 'mantis_id')
    filter_backends = (filters.SearchFilter,filters.DjangoFilterBackend)
    serializer_class = AccidentListSerializer

    def get_queryset(self):
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        duty_dept_id = self.request.QUERY_PARAMS.get('duty_dept_id', '')
        duty_domains = self.request.QUERY_PARAMS.get('duty_domains', '')
        status__id__in = self.request.QUERY_PARAMS.get('status__id__in', '')
        level__in = self.request.QUERY_PARAMS.get('level__in', '')
        type__ptype__id__in = self.request.QUERY_PARAMS.get('type__ptype__id__in', '')
        type__id__in = self.request.QUERY_PARAMS.get('type__id__in', '')
        filters = dict()
        if duty_domains:
            act_domains1 = AccidentDomain.objects.using('accident').filter(domainid__in = duty_domains.split(','))
            filters['accidentid__in'] = [ad1.accident_id for ad1 in act_domains1]
        elif duty_dept_id:
            dept2_ids = duty_dept_id.split(',')
            dept3_ids = [d.id for d in DdDepartmentNew.objects.using('default').filter(enable=0, pid__in=dept2_ids)]
            dm_ids = [dd.id for dd in DdDomainV2.objects.using('default').filter(enable=0, department_id__in = dept3_ids + dept2_ids)]
            other_ids = [od.id for od in AccidentOtherDomain.objects.filter(deptid__in=dept2_ids)]
            act_domains2 = AccidentDomain.objects.using('accident').filter(domainid__in=dm_ids + other_ids)
            filters['accidentid__in'] = [ad2.accident_id for ad2 in act_domains2]
        if status__id__in:
            filters['status__id__in'] = status__id__in.split(',')
        if level__in:
            filters['level__in'] = level__in.split(',')
        if type__ptype__id__in:
            filters['type__ptype__id__in'] = type__ptype__id__in.split(',')
        if type__id__in:
            filters['type__id__in'] = type__id__in.split(',')
        if start_date:
            filters['happened_time__gte'] = str2stamp(start_date, formt='%Y-%m-%d')

        if end_date:
            filters['happened_time__lt'] = str2stamp(end_date, formt='%Y-%m-%d') + 86400
        queryset = self.queryset.filter(**filters)
        return queryset

    def perform_create(self, serializer):
        action = self.request.DATA.get('action', '')
        happened_time = int(self.request.DATA.get('happened_time', int(time.time())))
        find_user_name = self.request.DATA.get('find_user_name', self.request.user.username)

        group_list = self.request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]

        if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_MONITOR'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name:
            raise YAPIException(u'只有Monitor、当日值班经理或超级管理员才有此权限！')

        id_num = stamp2str(happened_time, format('%Y%m%d'))
        exists = Accident.objects.using('accident').order_by('-accidentid').filter(accidentid__startswith=id_num)
        accident_id = exists[0].accidentid + 1 if exists else int(id_num + '01')

        if action == 'after_insert':  # 补录事故 默认状态为基本信息待补充
            try:
                DdUsers.objects.using('default').get(username=find_user_name, enable=0)
            except DdUsers.DoesNotExist:
                raise YAPIException('报告人不存在，请填写正确的域控账号！')
            serializer.save(accidentid=accident_id, status_id=2)
        else:   # 开启事故 默认状态为事故中
            if Accident.objects.using('accident').filter(is_accident=0, status_id=1).exists():
                raise YAPIException(u'当前已在事故中，请勿重复创建！')
            current_time = stamp2str(int(time.time()))
            try:
                cur_rota = Rota.objects.using('default').get(promotion=0, duty_domain=DOMAIN_HEAD_ID, duty_date_start__lt=current_time, duty_date_end__gte=current_time)
                duty_manager = cur_rota.duty_man.all().first()
                back_duty_manager = cur_rota.duty_backup.all().first()
                # duty_manager = RotaMan.objects.using('default').get(rota_id=cur_rota.id).man
                # back_duty_manager = RotaBackup.objects.using('default').get(rota_id=cur_rota.id).backup

                duty_manager_name = duty_manager.username
                cur_back_duty_manager_ch = back_duty_manager.username

                if back_duty_manager.display_name != '':
                    cur_back_duty_manager_ch = back_duty_manager.username_ch
                else:
                    cur_back_duty_manager_ch = '无'

            except Exception, e:
                duty_manager_name = ''
                cur_back_duty_manager_ch = ''
            accident = serializer.save(accidentid=accident_id, status_id=1, duty_manager_name=duty_manager_name)
            # 录入开启事故log
            AccidentLog.objects.using('accident').create(accident_id=accident.accidentid, source=0, username=find_user_name, level_id=1, message=u'事故发生', create_time=int(time.time()), happened_time=happened_time, from_accident=1)
            # 邮件通知值班经理
            t = get_template('mail/accident/open_accident.html')
            title = '【事故开启通知】%s' % str(accident.title)
            html_content = t.render(Context(locals()))
            try:
                sendmail_co(title, html_content, [self.request.user.username+'@yhd.com'], cc=[self.request.user.username+'@yhd.com'])
            except Exception, e:
                raise YAPIException(u'发送邮件失败：%s' % str(e))


class AccidentAll(generics.ListAPIView):
    """
    事故完整信息列表.

    输入参数：
    * id                        -   PK
    * accidentid                -   事故编号
    * title                     -   事故名称
    * level                     -   事故等级
    * find_user_name            -   事故发现人
    * duty_manager_name         -   值班经理
    * happened_time             -   事故发生时间
    * finish_time              -    事故恢复时间
    * status                    -   事故状态
    * is_accident               -   是否事故

    输出参数：

    * id                        -   PK
    * accidentid                -   事故编号(int)
    * title                     -   事故名称(string)
    * level_name                -   事故等级(string)
    * find_user_id              -   事故发现人ID(int)
    * find_user_name            -   事故发现人(string)
    * duty_manager_id           -   值班经理ID(int)
    * duty_manager_name         -   值班经理(string)
    * happened_time             -   事故发生时间(int)
    * finish_time               -   事故恢复时间(int)
    * reason                    -   事故原因(text)
    * status_name               -   事故状态(string)
    * is_accident               -   是否事故(int) 0 是   1 否

    * process                   -   事故经过(text)
    * comment                   -   事故备注(string)

    * duty_dept_names           -   责任部门(string) 多个，逗号分隔
    * duty_domain_names         -   责任Domain(string) 多个，逗号分隔
    * duty_users                -   责任报告人(string) 多个，逗号分隔
    * type_parent_name          -   事故根源类型(string)
    * type_name                 -   事故类型(string)
    * root_reason               -   事故根本原因(text)
    * affect                    -   影响(范围及程度、订单量、销售额）(text)
    * is_available              -   是否影响可用性(int) 0 不影响  1 影响
    * action                    -   事故改进措施(list)
    * mantis_id                 -   mantis编号(int) 默认为0，不提交mantis
    * is_punish                 -   是否处罚(int) 0 不处罚  1 处罚
    * punish_users              -   惩罚人(string) 多个，逗号分隔
    * punish_content            -   惩罚内容(text)
    * basic_sla                 -   基本信息填写SLA（精确到分钟）
    * detail_sla                -   详细信息填写SLA（精确到分钟）
    * is_accident               -   是否事故(int)   0 是 1 否

    """
    queryset = Accident.objects.using('accident').all().order_by('-accidentid')
    filter_fields = ('status__id', 'level', 'type__ptype__id', 'type__id', 'is_punish', 'is_accident')
    filter_backends = (filters.DjangoFilterBackend,)
    serializer_class = AccidentSerializer
    paginate_by = None
    permission_classes = (AllowAny,)

    def get_queryset(self):
        # queryset = Accident.objects.using('accident').order_by('-accidentid')
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        duty_dept_id = self.request.QUERY_PARAMS.get('duty_dept_id', '')
        duty_domains = self.request.QUERY_PARAMS.get('duty_domains', '')
        status__id__in = self.request.QUERY_PARAMS.get('status__id__in', '')
        level__in = self.request.QUERY_PARAMS.get('level__in', '')
        type__ptype__id__in = self.request.QUERY_PARAMS.get('type__ptype__id__in', '')
        type__id__in = self.request.QUERY_PARAMS.get('type__id__in', '')
        filters = dict()
        if duty_domains:
            act_domains1 = AccidentDomain.objects.using('accident').filter(domainid__in=duty_domains.split(','))
            filters['accidentid__in'] = [ad1.accident_id for ad1 in act_domains1]
        elif duty_dept_id:
            dept2_ids = duty_dept_id.split(',')
            dept3_ids = [d.id for d in DdDepartmentNew.objects.using('default').filter(enable=0, pid__in=dept2_ids)]
            dm_ids = [dd.id for dd in
                      DdDomainV2.objects.using('default').filter(enable=0, department_id__in=dept3_ids + dept2_ids)]
            other_ids = [od.id for od in AccidentOtherDomain.objects.filter(deptid__in=dept2_ids)]
            act_domains2 = AccidentDomain.objects.using('accident').filter(domainid__in=dm_ids+ other_ids)
            filters['accidentid__in'] = [ad2.accident_id for ad2 in act_domains2]
        if status__id__in:
            filters['status__id__in'] = status__id__in.split(',')
        if level__in:
            filters['level__in'] = level__in.split(',')
        if type__ptype__id__in:
            filters['type__ptype__id__in'] = type__ptype__id__in.split(',')
        if type__id__in:
            filters['type__id__in'] = type__id__in.split(',')
        if start_date:
            filters['happened_time__gte'] = str2stamp(start_date, formt='%Y-%m-%d')

        if end_date:
            filters['happened_time__lt'] = str2stamp(end_date, formt='%Y-%m-%d') + 86400
        queryset = self.queryset.filter(**filters)
        return queryset


# 编辑保存后更新事故状态
def updateAccidentStatus(accident):
    if accident.status_id != 1:
        if accident.level == 0 or accident.finish_time == 0 or len(accident.duty_domains) == 0:
            accident.status_id = 2
        elif accident.reason == '' or accident.reason is None:
            accident.status_id = 3
        elif accident.level in [3, 4]:
            accident.status_id = 200
        else:
            if accident.action:
                action_status = [c_act.status for c_act in accident.action]
                if 2 in action_status:
                    accident.status_id = 6
                elif 1 in action_status:
                    accident.status_id = 5
                else:
                    accident.status_id = 200
            else:
                accident.status_id = 4
        accident.save()


# 更新事故发生和恢复时间至事故log
def updateLogByAccident(old_accident, request, accident):
    happened_time = int(request.DATA.get('happened_time', 0))
    finish_time = int(request.DATA.get('finish_time', 0))
    if happened_time != 0 and happened_time != old_accident.happened_time:
        AccidentLog.objects.filter(accident_id=accident.accidentid, source=0, from_accident=1).update(
            happened_time=accident.happened_time)
    if finish_time != 0 and finish_time != old_accident.finish_time:
        AccidentLog.objects.filter(accident_id=accident.accidentid, source=0, from_accident=2).update(
            happened_time=accident.finish_time)


class AccidentDetail(generics.RetrieveUpdateAPIView):
    """
    更新事故详细信息

    输入参数：
    * id                        -   PK

    输出参数：

    * id                        -   PK
    * accidentid                -   事故编号(int)
    * title                     -   事故名称(string)
    * level_name                -   事故等级(string)
    * find_user_id              -   事故发现人ID(int)
    * find_user_name            -   事故发现人(string)
    * duty_manager_id           -   值班经理ID(int)
    * duty_manager_name         -   值班经理(string)
    * happened_time             -   事故发生时间(int)
    * finish_time               -   事故恢复时间(int)
    * reason                    -   事故原因(text)
    * status_name               -   事故状态(string)
    * is_accident               -   是否事故(int) 0 是   1 否

    * process                   -   事故经过(text)
    * comment                   -   事故备注(string)

    * duty_dept_names           -   责任部门(string) 多个，逗号分隔
    * duty_domain_names         -   责任Domain(string) 多个，逗号分隔
    * duty_domains              -   责任Domain（json）
    * duty_users                -   责任报告人(string) 多个，逗号分隔
    * type_parent_name          -   事故根源类型(string)
    * type_name                 -   事故类型(string)
    * root_reason               -   事故根本原因(text)
    * affect                    -   影响(范围及程度、订单量、销售额）(text)
    * is_available              -   是否影响可用性(int) 0 不影响  1 影响
    * action                    -   事故改进措施(list)
    * mantis_id                 -   mantis编号(int) 默认为0，不提交mantis
    * is_punish                 -   是否处罚(int) 0 不处罚  1 处罚
    * punish_users              -   惩罚人(string) 多个，逗号分隔
    * punish_content            -   惩罚内容(text)
    * basic_sla                 -   基本信息填写SLA（精确到分钟）
    * detail_sla                -   详细信息填写SLA（精确到分钟）
    * is_accident               -   是否事故(int)   0 是 1 否
    """
    queryset = Accident.objects.using('accident').all().order_by('-accidentid')
    serializer_class = AccidentSerializer
    permission_classes = (AllowAny, )

    def perform_update(self, serializer):
        action = self.request.DATA.get('action', '')
        group_list = self.request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        if action == 'close':   # 关闭事故
            finish_time = int(self.request.DATA.get('finish_time', int(time.time())))
            print(finish_time)
            receive = self.request.DATA.get('receive', '')
            cc = self.request.DATA.get('cc', '')
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_MONITOR'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name:
                raise YAPIException(u'只有Monitor、当日值班经理或超级管理员才有此权限！')
            if receive:
                receive = receive.split(',')
            else:
                raise YAPIException('关闭事故的同时系统会发送通知邮件，收件人不能为空！')
            if cc:
                cc = cc.split(',')
            accident = serializer.save(status_id=2)
            if accident.finish_time == 0:
                accident.finish_time = finish_time
                accident.save()
            # 编辑保存后更新事故状态
            updateAccidentStatus(accident)
            # 关闭事故写log
            AccidentLog.objects.using('accident').create(accident_id=accident.accidentid, level_id=3, username=self.request.user.username, message='事故已恢复', create_time=int(time.time()), happened_time = finish_time, from_accident=2)
            # 处理经过同步写到事故详情
            if accident.process == '' or accident.process is None:
                accident.process = '\n'.join([(stamp2str(log.happened_time, formt='%m/%d %H:%M:%S') + '  ' + log.username + '  ' + log.message) for log in accident.logs_happened])
                accident.save()
            # 邮件通知值班经理
            t = get_template('mail/accident/close_accident.html')
            title = '【事故恢复通知】%s' % str(accident.title)
            html_content = t.render(Context(locals()))
            try:
                sendmail_co(title, html_content, receive, cc=cc)
            except Exception, e:
                raise YAPIException(u'send mail error: %s ###' % str(e))
        elif action == 'delete':    # 删除事故(逻辑)
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name:
                raise YAPIException(u'只有事故当日的值班经理或超级管理员才有此权限！')
            serializer.save(is_accident=1)
        elif action == 'mantis':    # 提交Mantis
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_SUPPORT'] not in group_id_list:
                raise YAPIException(u'只有技术支持或超级管理员才有此权限！')
            cur_accident = self.get_object()
            duty_user = cur_accident.duty_users.split(',')[0] if cur_accident.duty_users else 'QA'
            SUBMIT_MANTIS_POST['summary'] = SUBMIT_MANTIS_POST['summary'] % cur_accident.title
            SUBMIT_MANTIS_POST['description'] = SUBMIT_MANTIS_POST['description'] % (cur_accident.affect, cur_accident.process, cur_accident.reason)
            SUBMIT_MANTIS_POST['handler'] = SUBMIT_MANTIS_POST['handler'] % duty_user
            try:    # 调用Mantis系统
                response = requests.post(SUBMIT_MANTIS_URL, data=SUBMIT_MANTIS_POST)
                if response.status_code == 200:
                    res = response.json()['bug_id']
                    if res:
                        res = serializer.save(mantis_id=int(res))
                    else:
                        raise YAPIException(u'提交mantis返回结果为空')
            except Exception,e:
                raise YAPIException(u'提交mantis出错：%s' % str(e))
        elif action == 'basic_monitor':     # monitor修改基本信息
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_MONITOR'] not in group_id_list:
                raise YAPIException(u'只有Monitor或超级管理员才有此权限！')
            try:
                DdUsers.objects.get(username=self.request.DATA.get('duty_manager_name'), enable=0)
            except DdUsers.DoesNotExist:
                raise YAPIException(u'值班经理不存在，请填写正确的域控账号,仍有问题可联系liuyating1校验用户信息。')
            try:
                DdUsers.objects.get(username=self.request.DATA.get('find_user_name'), enable=0)
            except DdUsers.DoesNotExist:
                raise YAPIException(u'报告人不存在，请填写正确的域控账号,仍有问题可联系liuyating1校验用户信息。')
            old_accident = self.get_object()
            accident = serializer.save()
            # 更新事故发生和恢复时间至事故log
            updateLogByAccident(old_accident, self.request, accident)
        elif action == 'basic':     # 值班经理修改基本信息
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name:
                raise YAPIException(u'只有事故当日的值班经理或超级管理员才有此权限！')
            duty_dept_id = self.request.DATA.get('duty_dept_id', '')
            duty_domain_ids = self.request.DATA.get('duty_domain_ids', '')
            try:
                DdUsers.objects.get(username=self.request.DATA.get('duty_manager_name'), enable=0)
            except DdUsers.DoesNotExist:
                raise YAPIException(u'值班经理不存在，请填写正确的域控账号,仍有问题可联系liuyating1校验用户信息。')
            try:
                DdUsers.objects.get(username=self.request.DATA.get('find_user_name'), enable=0)
            except DdUsers.DoesNotExist:
                raise YAPIException(u'报告人不存在，请填写正确的域控账号,仍有问题可联系liuyating1校验用户信息。')
            if duty_dept_id and duty_domain_ids == '':
                raise YAPIException(u'责任部门和Domain修改错误，请保证落实责任到Domain！')
            old_accident = self.get_object()
            instance = serializer.save()
            if instance.basicinfo_time == 0 or instance.basicinfo_time is None:
                instance.basicinfo_time = int(time.time())
                instance.save()

            # 更新事故发生和恢复时间至事故log
            updateLogByAccident(old_accident, self.request, instance)

            AccidentDomain.objects.using('accident').filter(accident_id=instance.accidentid).delete()
            if duty_domain_ids:
                for dm_id in duty_domain_ids.split(','):
                    try:
                        departmentid = DdDomainV2.objects.get(id=int(dm_id)).department_level2.id
                    except Exception:
                        try:
                            departmentid = AccidentOtherDomain.objects.get(id=int(dm_id)).deptid
                        except AccidentOtherDomain.DoesNotExist:
                            raise YAPIException(u'输入的Domain不存在，ID为%d' % int(dm_id))
                    AccidentDomain.objects.using('accident').create(accident_id=instance.accidentid, domainid=int(dm_id), departmentid=departmentid)
            # 编辑保存后更新事故状态
            updateAccidentStatus(instance)
        elif action == 'detail':     # 修改详细信息
            duty_users = self.get_object().duty_users.split(',')
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name and self.request.user.username not in duty_users:
                raise YAPIException(u'只有责任人、事故当日的值班经理或超级管理员才有此权限！')
            instance = serializer.save(type_id=self.request.DATA.get('type_id'))

            if instance.detailinfo_time == 0 or instance.detailinfo_time == None:
                instance.detailinfo_time = int(time.time())
                instance.save()

            updateAccidentStatus(instance)

        elif action == 'punish':     # 修改处罚信息
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_QA'] not in group_id_list:
                raise YAPIException(u'只有QA或超级管理员才有此权限！')
            serializer.save()
        elif action == 'title':     # 修改事故名称信息
            if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and GROUP_ID['ACCIDENT_MONITOR'] not in group_id_list and self.request.user.username != self.get_object().duty_manager_name:
                raise YAPIException(u'只有Monitor、当日值班经理或超级管理员才有此权限！')
            serializer.save()
        else:
            raise YAPIException(u'错误的请求，缺少action参数！')


class CurrentAccidentList(generics.ListAPIView):
    """
    当前事故列表.

    输入参数：
    * id                        -   PK
    * accidentid                -   事故编号
    * title                     -   事故名称
    * level                     -   事故等级
    * find_user_name            -   事故发现人
    * duty_manager_name         -   值班经理
    * happened_time             -   事故发生时间
    * finish_time              -    事故恢复时间
    * status                    -   事故状态
    * is_accident               -   是否事故

    输出参数：

    * id                        -   PK
    * accidentid                -   事故编号(int)
    * title                     -   事故名称(string)
    * level_name                -   事故等级(string)
    * find_user_id              -   事故发现人ID(int)
    * find_user_name            -   事故发现人(string)
    * duty_manager_id           -   值班经理ID(int)
    * duty_manager_name         -   值班经理(string)
    * happened_time             -   事故发生时间(int)
    * finish_time               -   事故恢复时间(int)
    * reason                    -   事故原因(text)
    * status_name               -   事故状态(string)
    * is_accident               -   是否事故(int) 0 是   1 否

    * comment                   -   事故备注(string)

    * duty_dept_names           -   责任部门(string) 多个，逗号分隔
    * duty_domain_names         -   责任Domain(string) 多个，逗号分隔
    * duty_users                -   责任报告人(string) 多个，逗号分隔
    * type_parent_name          -   事故根源类型(string)
    * type_name                 -   事故类型(string)
    * is_punish                 -   是否处罚(int) 0 不处罚  1 处罚

    """
    queryset = Accident.objects.using('accident').filter(is_accident=0, status=1).order_by('-accidentid')
    serializer_class = AccidentListSerializer


class AccidentActionList(generics.ListCreateAPIView):
    """
    事故改进措施列表/新增事故改进措施.

    输入参数：
    * id                    -   PK
    * accident_id           -   事故ID
    * action                -   action内容
    * duty_users            -   action负责人
    * create_time           -   Log时间
    * finish_time           -   预计完成时间
    * trident_id            -   tridentID（预期完成时间超过两周的action需关联）
    * status                -   action状态

    输出参数：

    * id                    -   PK
    * accident_id           -   事故ID
    * action                -   action内容
    * dutydept_level2       -   action负责部门
    * duty_users            -   action负责人
    * create_time           -   创建时间
    * finish_time           -   预计完成时间
    * trident_id            -   tridentID（预期完成时间超过两周的action需关联）
    * status_name           -   action状态

    """

    queryset = AccidentAction.objects.using('accident').all().order_by('id')
    serializer_class = AccidentActionSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('accident__accidentid', )
    permission_classes = (AllowAny, )

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def perform_create(self, serializer):
        accident_id = int(self.request.DATA.get('accident_id'))
        try:
            accident = Accident.objects.get(accidentid=accident_id)
        except Accident.DoesNotExist:
            raise YAPIException(u'事故编号找不到事故记录，请重新检查！')
        if accident.status_id == 1:
            raise YAPIException(u'事故仍为恢复，不允许编辑改进措施信息！')
        group_list = self.request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and self.request.user.username != accident.duty_manager_name and self.request.user.username not in accident.duty_users.split(','):
            raise YAPIException(u'只有责任人、事故当日的值班经理或超级管理员才有此权限！')
        today = str2stamp(date.today().strftime("%Y-%m-%d"), formt='%Y-%m-%d')
        serializer.save(create_time=today, accident_id=accident_id)
        updateAccidentStatus(accident)


class AccidentActionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccidentAction.objects.using('accident').select_related().all().order_by('-accidentid')
    serializer_class = AccidentActionSerializer
    permission_classes = (AllowAny, )

    def perform_update(self, serializer):
        accident = self.get_object().accident
        if accident.status_id == 1:
            raise YAPIException(u'事故仍为恢复，不允许编辑改进措施信息！')
        group_list = self.request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        username = self.request.user.username
        if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and username != accident.duty_manager_name and  username not in accident.duty_users.split(',') and username not in self.get_object().duty_users.split(','):
            raise YAPIException(u'只有责任人、事故当日的值班经理、action负责人或超级管理员才有此权限！')
        instance = serializer.save()
        # 根据action状态更新事故状态
        updateAccidentStatus(accident)

    def perform_destroy(self, instance):
        accident = self.get_object().accident
        if accident.status_id == 1:
            raise YAPIException(u'事故仍为恢复，不允许删除改进措施信息！')
        group_list = self.request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        username = self.request.user.username
        if not self.request.user.is_superuser and GROUP_ID['ACCIDENT_MASTER'] not in group_id_list and username != accident.duty_manager_name and  username not in accident.duty_users.split(',') and username not in self.get_object().duty_users.split(','):
            raise YAPIException(u'只有责任人、事故当日的值班经理、action负责人或超级管理员才有此权限！')
        instance.delete()
        updateAccidentStatus(accident)


class AccidentDomainList(generics.ListCreateAPIView):
    """
    事故责任Domain列表

    """

    queryset = AccidentDomain.objects.using('accident').select_related().all().order_by('id')
    serializer_class = AccidentDomainSerializer

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None


class AccidentPoolList(generics.ListCreateAPIView):

    queryset = AccidentPool.objects.using('accident').filter(enable=0).order_by('create_time')
    serializer_class = AccidentPoolSerializer
    permission_classes = (AllowAny, )
    filter_fields = ('accident_id', )
    filter_backends = (filters.DjangoFilterBackend,)

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def perform_create(self, serializer):
        app_id = int(self.request.DATA.get('app_id', 0))
        accident_id = int(self.request.DATA.get('accident_id', 0))

        if accident_id == 0:
            if Accident.objects.filter(is_accident=0, status=1).exists():
                raise YAPIException(u'当前无事故,录入或推送log失败！')
        if app_id == 0:
            raise YAPIException(u'疑似pool的id不能为0！')
        try:
            app = AppV2.objects.get(id=app_id)
        except AppV2.DoesNotExist:
            raise YAPIException('该pool不存在')
        if AccidentPool.objects.filter(accident_id=accident_id, enable=0, app_id=app_id).exists():
            raise YAPIException(u'已添加至疑似pool，无需重复添加！')
        serializer.save()
        # 记录添加疑似pool动作至事故log
        msg = '标记%s/%s为疑似pool' % (app.site.name, app.name)
        AccidentLog.objects.create(accident_id=accident_id, username=self.request.user.username, app_id=app_id, level_id=3,
                                   message=msg, create_time=int(time.time()), happened_time=int(time.time()))


class AccidentPoolDetail(generics.RetrieveUpdateAPIView):

    queryset = AccidentPool.objects.using('accident').filter(enable=0).order_by('create_time')
    serializer_class = AccidentPoolSerializer
    permission_classes = (AllowAny, )

    def perform_update(self, serializer):
        app_id = int(self.request.DATA.get('app_id', 0))
        accident_id = int(self.request.DATA.get('accident_id', 0))
        if accident_id == 0:
            if Accident.objects.filter(is_accident=0, status=1).exists():
                raise YAPIException(u'当前无事故,录入或推送log失败！')
        if app_id == 0:
            raise YAPIException(u'疑似pool的id不能为0！')
        try:
            app = AppV2.objects.get(id=app_id)
        except AppV2.DoesNotExist:
            raise YAPIException('该pool不存在')
        serializer.save(enable=1)
        # 记录取消疑似pool动作至事故log
        msg = '取消标记%s/%s为疑似pool' % (app.site.name, app.name)
        AccidentLog.objects.create(accident_id=accident_id, username=self.request.user.username, app_id=app_id,
                                   level_id=3, message=msg, create_time=int(time.time()), happened_time=int(time.time()))


class AccidentLogList(generics.ListCreateAPIView):
    """
    事故处理Log/新增事故log.

    输入参数：

    方式1——人工录入：
    * source=0              -   来自人工录入
    * username              -   录入员工
    * message               -   log内容
    方式2——推送配置变更：
    * source=1              -   来自配置变更
    * username              -   录入员工
    * from_id               -   配置变更表记录ID
    * app_id                -   受影响应用ID(可选)
    * ip                    -   IP(可选)
    * change_user           -   配置变更操作人
    * source_id             -   来源
    * type_id               -   类型
    * level_id              -   log重要性等级
    * message               -   log内容
    * happened_time         -   变更发生时间
    方式3——推送告警事件：
    * source=2              -   来自告警事件
    * username              -   录入员工
    * from_id               -   告警事件表记录ID
    * app_id                -   受影响应用ID
    * ip                    -   IP(可选)
    * source_id             -   来源
    * type_id               -   类型
    * level_id              -   log重要性等级
    * message               -   log内容
    * happened_time         -   告警发生时间

    输出参数：

    * id                    -   PK
    * accident_id           -   事故ID
    * username              -   录入员工
    * source                -   系统来源ID
    * system_name           -   系统来源
    * from_id               -   系统来源表ID
    * app_id                -   受影响应用ID
    * app_name              -   受影响应用名
    * ip                    -   IP
    * level_id              -   log重要性等级
    * message               -   log内容
    * create_time           -   log写入时间
    * is_process            -   是否同步至事故处理经过  0 不同步  1 同步
    * enable                -   是否已废弃  0 可用  1 废弃

    """

    # queryset = AccidentLog.objects.using('accident').all()
    serializer_class = AccidentLogSerializer
    permission_classes = (AllowAny, )
    filter_fields = ('accident_id', 'source', 'username')
    ordering_fields = ('create_time','-create_time', 'happened_time', '-happened_time')
    ordering = ('-create_time',)
    filter_backends = (filters.DjangoFilterBackend,filters.OrderingFilter,)

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):
        queryset = AccidentLog.objects.using('accident').all()
        create_time_start = self.request.GET.get('create_time_start', 0)
        create_time_end = self.request.GET.get('create_time_end', 0)
        happened_time_start = self.request.GET.get('happened_time_start', 0)
        happened_time_end = self.request.GET.get('happened_time_end', 0)
        filters = dict()
        if create_time_start:
            filters['create_time__gt'] = create_time_start
        if create_time_end:
            filters['create_time__lte'] = create_time_end
        if happened_time_start:
            filters['happened_time__gt'] = happened_time_start
        if happened_time_end:
            filters['happened_time__lte'] = happened_time_end
        return queryset.filter(**filters)

    def perform_create(self, serializer):
        source = int(self.request.DATA.get('source', 0))
        from_id = int(self.request.DATA.get('from_id', 0))
        app_id = int(self.request.DATA.get('app_id', 0))
        # ip = self.request.DATA.get('ip', 0)
        level_id = int(self.request.DATA.get('level_id', 0))
        accident_id = int(self.request.DATA.get('accident_id', 0))

        if accident_id == 0:
            try:
                accident = Accident.objects.get(is_accident=0, status=1)
            except Accident.DoesNotExist:
                raise YAPIException(u'当前无事故,录入或推送log失败！')
            accident_id = accident.id

        if source == 0:
            image_urls = urllib.unquote(self.request.DATA.get('image_urls', '').encode('utf-8'))
            instance = serializer.save(accident_id=accident_id, create_time=int(time.time()))
            if image_urls:
                url_list = image_urls.split(',')
                for url in url_list:
                    try:
                        image = AccidentLogImage.objects.get(image=url)
                    except AccidentLogImage.DoesNotExist, AccidentLogImage.MultipleObjectsReturned:
                        instance.delete()
                        raise YAPIException('找不到图片保存路径，log录入失败！')
                    image.accident_log_id = instance.id
                    image.save()
        else:
            if from_id == 0:
                raise YAPIException(u'推送记录到事故Log必须传参from_id(配置变更或告警事件的表ID)！')
            if level_id == 0:
                raise YAPIException(u'推送记录到事故Log必须传参level_id(log重要性等级)！')
            if source == 1:
                if AccidentLog.objects.filter(accident_id=accident_id, source=1, from_id=from_id):
                    raise YAPIException(u'该条配置变更记录已推送至事故Log,无需重复推送！')
                serializer.save(accident_id=accident_id, create_time=int(time.time()))
            elif source == 2:
                if AccidentLog.objects.filter(accident_id=accident_id, source=2, from_id=from_id):
                    raise YAPIException(u'该条告警事件记录已推送至事故Log,无需重复推送！')
                serializer.save(accident_id=accident_id, create_time=int(time.time()))
            else:
                raise YAPIException(u'参数source非法，只允许输入：0代表人工录入、1代表来自配置变更系统、2代表来自告警事件系统！')


class AccidentLogImageList(generics.ListCreateAPIView):
    """
    事故处理Log的附图列表/新增事故log附图.

    输入参数：

    * image         -   image文件

    输出参数：

    * id                    -   PK
    * accident_log          -   事故logID
    * image                 -   图片

    """

    queryset = AccidentLogImage.objects.using('accident')
    serializer_class = AccidentLogImageSerializer
    parser_classes = (MultiPartParser,)
    permission_classes = (AllowAny, )
    # filter_fields = ('accident_id', 'source')
    # filter_backends = (filters.DjangoFilterBackend,)

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def perform_create(self, serializer):
        serializer.save(create_time=int(time.time()))


@api_view(['POST'])
@permission_classes((AllowAny, ))
def send_accident_log(request):
    """
    事故期间发送邮件通知

    输入参数：
    * receive        -   邮件接收人
    * cc             -   邮件抄送人
    输出参数：
    * success        -   true/false
    """

    receive = request.POST.get("receive", '')
    cc = request.POST.get("cc")

    try:
        accident = Accident.objects.using('accident').get(is_accident=0, status_id=1)
    except Accident.DoesNotExist:
        raise YAPIException('往前未发生事故！')
    if receive == '':
        raise YAPIException('发送事故进度邮件，收件人不能为空！')
    receive = receive.split(',')
    if cc:
        cc = cc.split(',')

    # 邮件通知
    t = get_template('mail/accident/send_accident_process.html')
    title = '【事故处理进度通知】%s' % str(accident.title)
    html_content = t.render(Context(locals()))
    try:
        sendmail_co(title, html_content, receive, cc=cc)
    except Exception, e:
        raise YAPIException('发送邮件失败，原因：%s' % str(e))
    return Response(json.dumps({'success': True}))


@api_view(['GET'])
@permission_classes((AllowAny, ))
def pool_influence(request):
    events = Event.objects.using('monitor').filter(source=6, create_time__gte=int(time.time())-3600, create_time__lt=int(time.time()), status=0)
    eventdetails = EventDetail.objects.using('monitor').filter(event_id__in=[ev.id for ev in events])

    dept_level2 = DdDepartmentNew.objects.filter(enable=0, deptlevel=2)
    dept_level3 = DdDepartmentNew.objects.filter(enable=0, deptlevel=3)
    domain_all = DdDomainV2.objects.filter(enable=0)
    app_all = App.objects.using('default').filter(status=0)
    app_contacts = AppContact.objects.using('default').filter(pool_status=0)
    sites = Site.objects.using('default').filter(status=0)
    # app获取站点名
    site_list = {}
    for site in sites:
        site_list[int(site.id)] = site.name
    # 获取二级部门名称
    dept_list = {}
    for dept in dept_level2:
        dept_list[int(dept.id)] = dept.deptname
    # 根据Domain获取二级部门
    domain_dept = {}
    for dm in domain_all:
        for dept3 in dept_level3:
            if dept3.id == dm.department.id and dept_list.has_key(int(dept3.pid)):
                domain_dept[int(dm.id)] = {
                    'deptid': int(dept3.pid),
                    'dept_name': dept_list[int(dept3.pid)]
                }
        if not domain_dept.has_key(int(dm.id)):
            for dept2 in dept_level2:
                if dept2.id == dm.department.id and dept_list.has_key(int(dept2.id)):
                    domain_dept[int(dm.id)] = {
                    'deptid': int(dept2.id),
                    'dept_name': dept_list[int(dept2.id)]
                }
    # 根据pool获取pool联系人信息
    app_contact = {}
    for ac in app_contacts:
        app_contact[int(ac.pool_id)] = {
            'domain_name': ac.domain_name,
            'domain_leader': ac.p_user,
            'leader_phone': ac.p_no,
            'domain_backup_leader': ac.b_user,
            'backup_leader_phone': ac.b_no
        }
    # 获取事件详情
    event = {}
    for ee in events:
        event[ee.id] = {
            'title': ee.title,
            'message': ee.message
        }
    # 将事故详情按pool归类
    app_event = {}
    for ed in eventdetails:
        if event.has_key(int(ed.event_id)):
            if app_event.has_key(int(ed.pool_id)):
                app_event[int(ed.pool_id)].append(event[int(ed.event_id)])
            else:
                app_event[int(ed.pool_id)] = [event[int(ed.event_id)]]
    # 将所有pool的事件详情按二级部门归类
    dept_app = {}
    for app in app_all:
        if app.domainid != 0:
            if domain_dept.has_key(int(app.domainid)):
                deptid = domain_dept[int(app.domainid)]['deptid']
                if dept_app.has_key(deptid) and dept_app[deptid].has_key('apps'):
                    dept_app[deptid]['apps'].append({
                        'pool_id': int(app.id),
                        'site_name': site_list.setdefault(int(app.site_id), ''),
                        'app_name': app.name,
                        'contact': app_contact.setdefault(int(app.id), {}),
                        'events': app_event.setdefault(int(app.id), [])
                    })
                else:
                    dept_app[deptid] = {
                        'dept_name': domain_dept[int(app.domainid)]['dept_name'],
                        'apps': [{
                            'pool_id': int(app.id),
                            'site_name': site_list.setdefault(int(app.site_id), ''),
                            'app_name': app.name,
                            'contact': app_contact.setdefault(int(app.id), {}),
                            'events': app_event.setdefault(int(app.id), [])
                        }]
                    }
        else:
            if dept_app.has_key(0) and dept_app[0].has_key('apps'):
                dept_app[0]['apps'].append({
                    'pool_id': int(app.id),
                    'site_name': site_list.setdefault(int(app.site_id), ''),
                    'app_name': app.name,
                    'contact': app_contact.setdefault(int(app.id), {}),
                    'events': app_event.setdefault(int(app.id), [])
                })
            else:
                dept_app[0] = {
                    'dept_name': '基础服务Pool',
                    'apps': [{
                        'pool_id': int(app.id),
                        'site_name': site_list.setdefault(int(app.site_id), ''),
                        'app_name': app.name,
                        'contact': app_contact.setdefault(int(app.id), {}),
                        'events': app_event.setdefault(int(app.id), [])
                    }]
                }
    return Response(json.dumps(dept_app))


@api_view(['GET'])
@permission_classes((AllowAny, ))
def sla_domain(request):
    start_date = int(request.GET.get('start_date', 0))
    end_date = int(request.GET.get('end_date', 0))
    dept_id_in = request.GET.get('dept_id_in', '')
    dept2_id_in = request.GET.get('dept2_id_in', '')
    domain_id_in = request.GET.get('domain_id_in', '')
    if start_date == 0:
        raise YAPIException(u'统计的开始日期不能为空！')
    if end_date == 0:
        raise YAPIException(u'统计的结束日期不能为空！')
    if start_date > end_date:
        raise YAPIException(u'统计的开始日期不能大于结束日期！')
    # start_date_str = int(stamp2str(start_date, formt='%Y%m%d') + '00')
    # end_date_str = int(stamp2str(end_date + 86400, formt='%Y%m%d') + '00')
    act_dms = AccidentDomain.objects.using('accident').filter(accident__happened_time__gte=start_date, accident__happened_time__lt=end_date + 86400, accident__is_accident=0)
    dept_level2 = DdDepartmentNew.objects.filter(enable=0, deptlevel=2)
    dept_level3 = DdDepartmentNew.objects.filter(enable=0, deptlevel=3)
    all_domains = DdDomainV2.objects.using('default').filter(enable=0).exclude(id=DOMAIN_HEAD_ID)
    # 获取二级部门名称
    dept2_list = {}
    for dept in dept_level2:
        dept2_list[int(dept.id)] = dept.deptname
    # 获取三级部门名称
    dept_list = {}
    for dept in dept_level3:
        dept_list[int(dept.id)] = dept.deptname
    # 根据Domain获取二级部门
    domain_dept = {}
    for dm in all_domains:
        for dept3 in dept_level3:
            if dept3.id == dm.department.id and dept2_list.has_key(int(dept3.pid)):
                domain_dept[int(dm.id)] = {
                    'dept2_id': int(dept3.pid),
                    'dept2_name': dept2_list[int(dept3.pid)]
                }
        if not domain_dept.has_key(int(dm.id)):
            for dept2 in dept_level2:
                if dept2.id == dm.department.id and dept2_list.has_key(int(dept2.id)):
                    domain_dept[int(dm.id)] = {
                        'dept2_id': int(dept2.id),
                        'dept2_name': dept2_list[int(dept2.id)]
                    }
    dm_filters = {}
    other_filters = {}
    if domain_id_in:
        domain_ids = domain_id_in.split(',')
        dm_filters['id__in'] = domain_ids
        other_filters['id__in'] = domain_ids
    elif dept_id_in:
        dept_ids = dept_id_in.split(',')
        dm_ids = [dm.id for dm in all_domains.filter(department__id__in=dept_ids)]
        dm_filters['id__in'] = dm_ids
        other_filters['deptid__in'] = dept_ids
    elif dept2_id_in:
        dept2_ids = dept2_id_in.split(',')
        dm_ids = [dm.id for dm in all_domains.filter(department__pid__in=dept2_ids)]
        dm2_ids = [dm2.id for dm2 in all_domains.filter(department__id__in=dept2_ids)]
        dm_filters['id__in'] = dm_ids + dm2_ids
        other_filters['deptid__in'] = dept2_ids

    dm_filters['enable'] = 0
    domains = all_domains.filter(**dm_filters)
    other_domains = AccidentOtherDomain.objects.filter(**other_filters)
    all_hours = round(float(end_date + 86400 - start_date) / 3600.0, 2)
    domain_results = []
    act_dm_dict = {}
    for ad in act_dms:
        try:
            accident = ad.accident
            # domain = ad.domain
        except (Accident.DoesNotExist, DdDomainV2.DoesNotExist), e:
            continue
        if act_dm_dict.has_key(int(ad.domainid)):
            act_dm_dict[ad.domainid].append({
                'accidentid': accident.accidentid,
                'repair_time': accident.finish_time - accident.happened_time,
                'health': accident.health
            })
        else:
            act_dm_dict[ad.domainid] = [{
                'accidentid': accident.accidentid,
                'repair_time': accident.finish_time - accident.happened_time,
                'health': accident.health
            }]
    for dm in domains:
        repair_time, health_repair_time, count = 0, 0, 0
        if act_dm_dict.has_key(dm.id):
            for ad in act_dm_dict[dm.id]:
                repair_time += ad['repair_time']
                health_repair_time += ad['repair_time'] * ad['health']
                count += 1
        repair_hours = repair_time / 3600.0
        health_repair_hours = health_repair_time / 3600.0
        domain_results.append({
            'id': dm.id,
            'dept2_name': domain_dept[int(dm.id)]['dept2_name'] if domain_dept.has_key(int(dm.id)) else '',
            'deptname': dept_list[dm.department_id] if dept_list.has_key(dm.department_id) else '',
            'domainname': dm.domainname,
            'domainleader': dm.domainleaderaccount,
            'repair_hour': "%.3f" % repair_hours,
            'health_repair_hours': "%.3f" % health_repair_hours,
            'accident_count': count,
            'availability': '%.3f' % ((all_hours - health_repair_hours) / all_hours * 100)
        })
    for other in other_domains:
        repair_time, health_repair_time, count = 0, 0, 0
        for ad in act_dms:
            try:
                accident = ad.accident
                # domain = ad.domain
            except Accident.DoesNotExist:
                continue
            # if domain.enable == 1:
            #     continue
            if ad.domainid == other.id:
                time_length = accident.finish_time - accident.happened_time
                repair_time += time_length
                health_repair_time += time_length * accident.health
                count += 1
        repair_hours = repair_time / 3600.0
        health_repair_hours = health_repair_time / 3600.0
        domain_results.append({
            'id': other.id,
            'dept2_name': other.deptname,
            'deptname': other.deptname,
            'domainname': other.domainname,
            'domainleader': '',
            'repair_hour': "%.3f" % repair_hours,
            'health_repair_hours': "%.3f" % health_repair_hours,
            'accident_count': count,
            'availability': '%.3f' % ((all_hours - health_repair_hours) / all_hours * 100)
        })
    return Response(domain_results)