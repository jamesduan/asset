# -*- coding: utf-8 -*-
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, status
from rest_framework import filters
from rest_framework import permissions
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.decorators import api_view, permission_classes
from serializers import *
from django.db.models import Q

from deploy.utils.Pika import Pika
from monitor.models import *
from server.models import Server
from cmdb.models import App
from process.output import NotificationOutPut
from process.shield import NotificationShield
from permissions import *

import re
import time
from datetime import datetime, timedelta
from util.timelib import str2stamp, stamp2str, timelength_format
from django.shortcuts import HttpResponse
import logging
from process import event_preprocess
from monitor.process.output import SendTTS
from monitor.process.output import SendVoice
from monitor.common import event_global_var

logger = logging.getLogger('django')


class MyException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class Basic(object):
    """
    基础变量、方法类
    """
    pass


class EventList(Basic, generics.ListCreateAPIView):
    """
    告警推送接口.
    输入参数：
    :ip: string - 支持逗号分隔 - eg: '10.4.17.88,10.4.1.248' - 非必填
    :pool_id: int - 非必填
    （ip 或者 pool_id 必须填一个,如果填了ip，以ip为准）
    :level_id: int - 告警等级 - 必填
    :type_id: int - 告警类型 - 必填
    :sub_type: int - 是否根源报警 - 非必填(0-非根源，1-根源 默认0)
    :source_id: int - 告警来源 - 必填
    :title: string - 告警标题 - 必填
    :message: string - 告警内容 - 必填
    :send_to: string - 额外邮件发送人,支持逗号分隔(默认自动根据pool查找对应联系人，请参照等级文档) - 非必填
    :caller: string - 短信发送人,同上

    level-map
    100 - Critical TO: 值班经理,Monitor,IT Header,DL,Domain WAY: SMS, Email, Voice
    200 - High     TO: IT Header,Monitor,DL,Domian         WAY: SMS, Email, Voice
    300 - Normal   TO: Monitor,DL,Domian                   WAY: Email, Voice
    400 - Warning  TO: DL, Domain                          WAY: Email
    500 - Info     TO: /                                   WAY: /
    输出参数：
    http code 200 为成功 400 为失败 返回的json里的detail有说明信息
    """
    queryset = Event.objects.all().order_by('-get_time')
    search_fields = ('message', )
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    serializer_class = EventSerializer
    filter_fields = ('id', 'source__id', 'type__id', 'level__id', 'status', 'converge_id',)
    permission_classes = (EventPermission,)

    def get_queryset(self):
        queryset = Event.objects.all().order_by('-get_time')
        status_q = self.request.GET.get('status', '')
        level_id = self.request.GET.get('level_id', '')
        level__in = self.request.GET.get('level__in', '')
        source__in = self.request.GET.get('source__in', '')
        type__in = self.request.GET.get('type__in', '')
        site_id = self.request.GET.get('site_id', '')
        pool_id = self.request.GET.get('pool_id', '')
        start_time = self.request.GET.get('start_time', '')
        end_time = self.request.GET.get('end_time', '')
        source_id = self.request.GET.get('source_id', '')

        # for undone event
        if status_q:
            queryset = Event.objects.all().order_by('level__id', '-get_time')

        self_defined_filters = {}
        if level_id:
            self_defined_filters['level_id__lt'] = level_id

        if level__in:
            self_defined_filters['level__in'] = level__in.split(',')

        if source__in:
            self_defined_filters['source__in'] = source__in.split(',')

        if type__in:
            self_defined_filters['type__in'] = type__in.split(',')

        if site_id:
            sites = EventDetail.objects.filter(site__id=site_id)
            self_defined_filters['id__in'] = [site.event_id for site in sites]

        if pool_id:
            pools = EventDetail.objects.filter(pool__id=pool_id)
            self_defined_filters['id__in'] = [pool.event_id for pool in pools]

        if start_time:
            try:
                if start_time.count(':') == 1:
                    start_time += ':00'
                self_defined_filters['get_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise MyException(u'time format error')

        if end_time:
            try:
                if end_time.count(':') == 1:
                    end_time += ':00'
                self_defined_filters['get_time__lt'] = str2stamp(end_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise MyException(u'time format error')

        if source_id:
            self_defined_filters['source__id'] = source_id

        queryset = queryset.select_related("source", "type", "level")
        queryset = queryset.filter(**self_defined_filters)
        return queryset

    def perform_create(self, serializer):
        # updater = self.request.user.username
        pool_id = self.request.DATA.get('pool_id')
        level_id = self.request.DATA.get('level_id')
        if not level_id:
            raise MyException(u'level_id is wrong')
        if int(level_id) not in [100, 200, 300, 350, 400, 500]:
            raise MyException(u'level_id is not in the definded list')

        type_id = self.request.DATA.get('type_id')
        if not type_id:
            raise MyException(u'type_id is wrong')
        source_id = self.request.DATA.get('source_id')
        if not source_id:
            raise MyException(u'source_id is wrong')

        ip = self.request.DATA.get('ip')
        if ip:
            ip_list = ip.split(',')
            p = re.compile("^\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s*$")
            if ip_list:
                for i in ip_list:
                    if not p.match(i.strip()):
                        raise MyException(u'ip is not hefa')

        # 记录过来的请求时间
        # self.request.DATA['get_time'] = time.time()

        message = self.request.DATA.get('message')

        if not message:
            raise MyException(u'message can\'t empty')

        caller_message = self.request.DATA.get('caller_message')
        if caller_message and len(caller_message) > 400:
            raise MyException(u'call_message must < 400 bytes')


        # if (not ip) and (not pool_id):
        #     raise MyException(u'ip or pool_id mustn\'t empty')
        datas = {}  # self.request.DATA不支持修改
        for i in self.request.DATA:
            datas.setdefault(i, self.request.DATA[i])
        datas['get_time'] = time.time()

        # event preprocessing
        ret = event_preprocess.preprocess_entry(datas)
        if ret == event_preprocess.RET_NO_NEED_NEXT:
            raise MyException(u'push success', 200)

        amqp = Pika(task='monitor.tasks.run_notification', args=[json.dumps(datas)])
        task_id = amqp.basic_publish()


        # or 这种直接调封装的funciton
        # from monitor.process.process import process_notification
        # process_notification(json.dumps(datas))
        # task_id = 1

        if task_id:
            raise MyException(u'push success', 200)
        else:
            raise MyException(detail=u'failed to push the mq')
        # # filter
        # filter_instance = NotificationShield()
        # status = 2 if filter_instance.filter(ip=ip, message=message) else 0
        #
        # detail_list = []
        # if ip:
        #     ip_list = ip.split(',')
        #     servers = Server.objects.filter(ip__in=ip_list)
        #     if servers:
        #         app_ids = []
        #         parent_ips = []
        #         for i in servers:
        #             app_ids.append(i.app_id)
        #             parent_ips.append(i.parent_ip)
        #             obj = {}
        #             obj['ip'] = i.ip
        #             obj['pool_id'] = i.app_id
        #             obj['server_type'] = i.server_type_id
        #             obj['parent_ip'] = i.parent_ip if i.parent_ip else ''
        #             detail_list.append(obj)
        #
        #         apps = App.objects.filter(id__in=app_ids)
        #         app_map = {}
        #         if apps:
        #             for i in apps:
        #                 app_map[i.id] = i.site_id
        #
        #         switch_map = {}
        #         switch_servers = SwitchServer.objects.filter(server_ip__in=ip_list)
        #         if switch_servers:
        #             for i in switch_servers:
        #                 switch_map[i.server_ip] = i.switch_ip
        #
        #         for i in detail_list:
        #             i['site_id'] = app_map[i['pool_id']] if app_map.has_key(i['pool_id']) else 0
        #             i['switch_ip'] = switch_map[i['ip']] if switch_map.has_key(i['ip']) else ''
        # elif pool_id:
        #     if isinstance(pool_id, basestring):
        #         pool_list = pool_id.split(',')
        #     else:
        #         pool_list = [pool_id]
        #
        #     apps = App.objects.filter(id__in=pool_list)
        #     app_map = {}
        #     if apps:
        #         for i in apps:
        #             app_map[i.id] = i.site_id
        #     for i in pool_list:
        #         if i:
        #             obj = {}
        #             obj['ip'] = ''
        #             obj['pool_id'] = int(i)
        #             obj['site_id'] = app_map[int(i)]
        #             obj['server_type'] = 0
        #             obj['parent_ip'] = ''
        #             obj['switch_ip'] = ''
        #             detail_list.append(obj)
        #
        # try:
        #     instance = serializer.save(
        #         level_id=int(level_id),
        #         type_id=int(type_id),
        #         source_id=int(source_id),
        #         status=status,
        #         create_time=int(time.time())
        #     )
        #     _id = instance.id
        #     title = instance.title
        #     message = instance.message
        #     send_to = instance.send_to
        #     caller = instance.caller
        #     pool_ids = []
        #     tmp = []
        #     if detail_list:
        #         for i in detail_list:
        #             pool_ids.append(i['pool_id'])
        #             i['event_id'] = _id
        #             tmp.append(EventDetailCreate(**i))
        #
        #         EventDetailCreate.objects.bulk_create(tmp)
        #
        #     # 去重
        #     pool_ids = list(set(pool_ids))
        #     output = NotificationOutPut()
        #
        #     for p_id in pool_ids:
        #         # result = output.send(level_id, p_id, _id, {
        #         #     'caller': caller.split(',') if caller else [],
        #         #     'sender_to': send_to.split(',') if send_to else [],
        #         #     'subject': title,
        #         #     'content': message,
        #         #     'app_name': '-'
        #         # })
        #         result = output.send(200, 10, 1, {
        #             'caller': ['15800850671'],
        #             'sender_to': ['dingdan@yhd.com,zhangdingpeng@yhd.com,zhangyunyang@yhd.com'],
        #             'subject': title,
        #             'content': message,
        #             'app_name': '-'
        #         })
        #
        # except MyException, e:
        #     raise e


class EachEvent(Basic, generics.RetrieveUpdateDestroyAPIView):
    """
    Event单页接口.

    输入参数：无

    输出参数：
    """
    queryset = Event.objects.all().order_by('-get_time')
    serializer_class = EventSerializer

    def perform_update(self, serializer):
        event_id = self.request.DATA.get('id')
        new_status = self.request.DATA.get('status')
        if not new_status:
            new_status = 0
        else:
            new_status = int(new_status)

        origin_status = Event.objects.get(id=event_id).status
        origin_status = int(origin_status)

        if origin_status == 0 and new_status in (1, 2):
            now = time.time()
            serializer.save(cancel_time=now)
        else:
            serializer.save()


class AlarmList(Basic, generics.ListCreateAPIView):
    """
    alarm信息接口.

    输入参数：无

    输出参数：

    """
    queryset = Alarm.objects.all().order_by('-create_time')
    search_fields = ('event__message',)
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    serializer_class = AlarmSerializer
    filter_fields = ('id', 'event__source__id', 'status_id', 'method_id', 'event__type__id', 'event__level__id', 'status_id')
    permission_classes = (AlarmPermission,)

    def get_paginate_by(self):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):
        queryset = Alarm.objects.all().order_by('-create_time')
        start_time = self.request.GET.get('start_time', '')
        end_time = self.request.GET.get('end_time', '')
        pool_id = self.request.GET.get('pool_id', '')
        exclude_source_id = self.request.GET.get('exclude_source_id', 0)
        level__in = self.request.GET.get('level__in', '')
        source__in = self.request.GET.get('source__in', '')
        type__in = self.request.GET.get('type__in', '')
        source_id = self.request.GET.get('source_id', '')

        self_defined_exclude = {}
        self_defined_filters = {}
        if start_time:
            try:
                self_defined_filters['create_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M')
            except ValueError:
                raise MyException(u'time format error')

        if end_time:
            try:
                self_defined_filters['create_time__lt'] = str2stamp(end_time, '%Y-%m-%d %H:%M')
            except ValueError:
                raise MyException(u'time format error')

        if pool_id:
            pools = EventDetail.objects.filter(pool__id=pool_id)
            self_defined_filters['event__id__in'] = [pool.event_id for pool in pools]

        if exclude_source_id:
            self_defined_exclude['event__source_id'] = exclude_source_id

        if level__in:
            self_defined_filters['event__level__in'] = level__in.split(',')

        if source__in:
            self_defined_filters['event__source__in'] = source__in.split(',')

        if type__in:
            self_defined_filters['event__type__in'] = type__in.split(',')

        if source_id:
            self_defined_filters['event__source_id'] = source_id

        queryset = queryset.filter(**self_defined_filters).exclude(**self_defined_exclude)
        return queryset


class EventFilterList(Basic, generics.ListCreateAPIView):
    """
    event filter keyword信息接口.

    输入参数：无

    输出参数：

    """
    queryset = EventFilter.objects.all().order_by('-start_time')
    serializer_class = EventFilterSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('keyword',)

    def get_queryset(self):
        queryset = EventFilter.objects.all().order_by('-start_time')
        start_time = self.request.GET.get('start_time', '')
        end_time = self.request.GET.get('end_time', '')

        self_defined_filters = {}
        if start_time:
            self_defined_filters['start_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M:%S')

        if end_time:
            self_defined_filters['start_time__lte'] = str2stamp(end_time, '%Y-%m-%d %H:%M:%S')

        queryset = queryset.filter(**self_defined_filters)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user.username
        now = time.time()
        serializer.save(create_time=now, user=user)


class EachEventFilter(Basic, generics.RetrieveUpdateDestroyAPIView):
    """
    EventFilter单页接口.

    输入参数：无

    输出参数：
    """
    queryset = EventFilter.objects.all().order_by('-start_time')
    serializer_class = EventFilterSerializer

    def perform_update(self, serializer):
        user = self.request.user.username
        serializer.save(user=user)


class EventConvergenceRuleList(Basic, generics.ListCreateAPIView):
    """
    EventConvergenceRule信息接口.

    输入参数：无

    输出参数：

    """
    queryset = EventConvergenceRule.objects.all().order_by('-id')
    serializer_class = EventConvergenceRuleSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('key',)
    filter_fields = ('source__id', 'type__id',)

    def perform_create(self, serializer):
        user = self.request.user.username
        serializer.save(user=user)


class EachEventConvergenceRule(Basic, generics.RetrieveUpdateDestroyAPIView):
    """
    EventConvergenceRule单页接口.

    输入参数：无

    输出参数：
    """
    queryset = EventConvergenceRule.objects.all()
    serializer_class = EventConvergenceRuleSerializer

    def perform_update(self, serializer):
        user = self.request.user.username
        serializer.save(user=user)


class SourceList(Basic, generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    queryset = EventSourceMap.objects.all()
    serializer_class = SourceListSerializer
    paginate_by = None


class TypeList(Basic, generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    queryset = EventTypeMap.objects.all()
    serializer_class = TypeListSerializer
    paginate_by = None


class LevelList(Basic, generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    queryset = EventLevelMap.objects.all()
    serializer_class = TypeListSerializer
    paginate_by = None

    def get_queryset(self):
        id__lt = self.request.GET.get('id__lt', '')
        if id__lt:
            return self.queryset.filter(id__lt=id__lt)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def alarm_callback(request):
    pid = request.DATA.get('pid', 0)
    errorcode = request.DATA.get('errorcode', 0)
    error = request.DATA.get('error', '')
    senttimes = request.DATA.get('senttimes', 0)
    badreceivers = request.DATA.get('badreceivers', '')
    callback = request.DATA.get('callback', '')
    is_stg = request.DATA.get('is_stg', 0)
    result = 'ok'
    if is_stg:
        try:
            T.objects.create(value=json.dumps(request.DATA))
        except Exception, e:
            pass
        r = HttpResponse(json.dumps({'params': request.POST}), content_type="application/json")
        r.status_code = 201
        return r

    # voice phone
    if callback:
        callback = json.loads(callback)
        state = callback.get('CallState', '')

        if state != '正常':
            now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            msg = u"有一条语音电话状态为%s，请及时跟进。%s" %(state, now)

            sv = SendVoice()
            sv.send(msg)

    # 如果提交失败并且是BI的就重播一条
    if errorcode == -417:
        tts = SendTTS()
        alarm = Alarm.objects.filter(id=pid)
        event_id = alarm[0].event_id
        receiver = alarm[0].receiver
        method_id = alarm[0].method_id

        event = Event.objects.filter(id=event_id)
        source_id = event[0].source_id
        level_id = event[0].level_id
        content = ''
        if source_id == 5 and level_id == 300 and method_id == 4:
            content = "你有一条BI报警，请及时处理"

        if content:
            tmp = {
                'pid': pid,
                'receiver_list': receiver,
                'content': content,
                'app_id': 0,
                'app_name': '-'
            }
            result = tts.send(**tmp)

    try:
        res = Alarm.objects.filter(id=pid).update(
            errorcode=errorcode,
            result=callback,
            error=error,
            senttimes=senttimes,
            badreceivers=badreceivers
        )
    except Exception, e:
        result = e.message

    r = HttpResponse(json.dumps({'success': request.POST}), content_type="application/json")
    r.status_code = 201
    return r


@api_view(['POST'])
@permission_classes((AllowAny, ))
def event_preprocess_callback(request):
    pid = request.DATA.get('pid', 0)
    errorcode = request.DATA.get('errorcode', 0)
    error = request.DATA.get('error', '')
    senttimes = request.DATA.get('senttimes', 0)
    badreceivers = request.DATA.get('badreceivers', '')
    callback = request.DATA.get('callback', '')
    is_stg = request.DATA.get('is_stg', 0)
    result = 'ok'
    if is_stg:
        try:
            T.objects.create(value=json.dumps(request.DATA))
        except Exception, e:
            pass
        r = HttpResponse(json.dumps({'params': request.POST}), content_type="application/json")
        r.status_code = 201
        return r

    try:
        res = EventPreprocess.objects.filter(id=pid).update(
            errorcode=errorcode,
            result=callback,
            error=error,
            senttimes=senttimes,
            badreceivers=badreceivers
        )
    except Exception, e:
        result = e.message

    r = HttpResponse(json.dumps({'success': request.POST}), content_type="application/json")
    r.status_code = 201
    return r


class Test(Basic, generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    serializer_class = TestSerializer

    def get_queryset(self):
            a = NotificationOutPut()
            result = a.send(200, 10, 1, {
                'caller': [15800850671],
                'sender_to': ['dingdan@yhd.com'],
                'subject': 'ddtest234',
                'content': 'ddtest234',
                'app_id': 10,
                'app_name': 'qusi'
            })
            return T.objects.all()


@api_view(['POST'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def eventupdateall(request):
    ids = request.POST.get('ids').split(',')
    user = request.user.username
    cancel_type = request.POST.get('cancel_type', '0')
    comment = request.POST.get('comment', '')

    update_data = {'status':1,'cancel_user':user,'cancel_time':time.time(),'cancel_type':cancel_type}
    if comment:
        update_data['comment'] = comment

    response_data = {}
    try:
        res = Event.objects.filter(id__in=ids).update(**update_data)
    except Exception as e:
        logger.warning("Exception:%s", e.message)
        response_data['result'] = -1
        response_data['detail'] = e.message
        return HttpResponse(json.dumps(response_data), content_type="application/json")

    if not res:
        msg = "Invalid event id, please check."
        logger.warning("Exception:%s", msg)
        response_data['result'] = -1
        response_data['detail'] = msg
    else:
        response_data['result'] = 0

    return HttpResponse(json.dumps(response_data), content_type="application/json")


# process the request from the web front right click
@api_view(['POST'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def front_right_operate(request):
    type = request.POST.get('type', '')
    ip = request.POST.get('ip', '')

    response_data = {}
    retcode = -1
    if type == '' or ip == '':
        retcode = -1
    else:
        retcode = exe_shell_command(type, ip)

    response_data['retcode'] = retcode
    return HttpResponse(json.dumps(response_data), content_type="application/json")


def convert_to_dicts(objs):
    obj_arr = []
    for o in objs:
        dict = {}
        dict.update(o.__dict__)
        dict.pop("_state", None)
        obj_arr.append(dict)

    return obj_arr

@api_view(['GET'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def showAI(request):
    # a4 = time.time()
    start = request.GET.get('start_time')
    if start.count(':') == 1:
        start += ':00'
    end = request.GET.get('end_time')
    if end.count(':') == 1:
        end += ':00'
    start = time.mktime(time.strptime(start, '%Y-%m-%d %H:%M:%S'))
    end = time.mktime(time.strptime(end, '%Y-%m-%d %H:%M:%S'))
    shoulian = int(request.GET.get('shoulian', 1))  # 1-收敛 0-不收敛
    limit = int(request.GET.get('limit', 30))
    offset = int(request.GET.get('offset', 0))
    ll = None  # 总条数，后面赋值
    level_id = request.GET.get('level_id')
    type_id = request.GET.get('type_id')
    source_id = request.GET.get('source_id')
    search = request.GET.get('search')
    pool_id = int(request.GET.get('pool_id', 0))

    pool_event_ids = []
    if pool_id:
        eventdetail_res = EventDetail.objects.filter(pool_id=pool_id)
        if eventdetail_res:
            for i in eventdetail_res:
                pool_event_ids.append(i.event_id)

    self_defined_filters = {}
    self_defined_filters["get_time__gte"] = start
    self_defined_filters["get_time__lte"] = end
    self_defined_filters["converge_id"] = 0
    if pool_event_ids:
        self_defined_filters["id__in"] = pool_event_ids
    if level_id:
        self_defined_filters['level_id__in'] = level_id.split(',')
    if type_id:
        self_defined_filters['type_id__in'] = type_id.split(',')
    if source_id:
        self_defined_filters['source_id__in'] = source_id.split(',')
    if search:
        self_defined_filters['message__contains'] = search

    if shoulian == 1:
        res = Event.objects.filter(**self_defined_filters).order_by('-create_time').values()
    else:
        ll = Event.objects.filter(**self_defined_filters).count()
        if offset + limit > ll:
            limit = ll
        res = Event.objects.filter(**self_defined_filters).order_by('-create_time')[offset: offset+limit+1].values()

    source_res = EventSourceMap.objects.all()
    source_map = {}
    for i in source_res:
        source_map.setdefault(i.id, i.name)

    level_res = EventLevelMap.objects.all()
    level_map = {}
    for i in level_res:
        level_map.setdefault(i.id, i.name)

    type_res = EventTypeMap.objects.all()
    type_map = {}
    for i in type_res:
        type_map.setdefault(i.id, i.name)

    data_list = res
    # data_list = convert_to_dicts(res)

    event_ids = []
    for i in data_list:
        event_ids.append(i['id'])

    # print time.time() - a4
    event_detail_res = EventDetail.objects.filter(event_id__in=event_ids)
    event_details_map = {}
    pool_ids = []
    for i in event_detail_res:
        pool_ids.append(i.pool_id)
        if i.event_id not in event_details_map:
            event_details_map[i.event_id] = {'ip': [i.ip], 'pool_id': i.pool_id}
        else:
            event_details_map[i.event_id]['ip'].append(i.ip)

    app_res = App.objects.filter(status=0, id__in=pool_ids)
    app_map = {}
    for i in app_res:
        app_map.setdefault(i.id, i.name)

    if shoulian == 1:
        # 开始收敛
        tag_map = {}
        process_list = []
        other_list = []

        for i in data_list:
            i['get_time_format'] = time.strftime('%m-%d %H:%M:%S', time.localtime(i['get_time']))
            k = event_details_map.get(i['id'], {})
            i.setdefault('ip', k.get('ip', []))
            i.setdefault('pool_id', k.get('pool_id', 0))
            i.setdefault('pool_name', [app_map.get(k.get('pool_id', 0), '')])
            i.setdefault('details', [])
            i.setdefault('level_name', level_map.get(i['level_id'], ''))
            i.setdefault('source_name', source_map.get(i['source_id'], ''))
            i.setdefault('type_name', type_map.get(i['type_id'], ''))

            tag = i['tag']
            if tag:
                if tag not in tag_map:
                    tag_map[tag] = [i]
                else:
                    if i['ip']:
                        tag_map[tag][0]['ip'] += i['ip']
                    if i['pool_name']:
                        tag_map[tag][0]['pool_name'] += i['pool_name']
                    tag_map[tag][0]['details'].append(i)
            else:
                other_list.append(i)

        new_data_list = []
        for key in tag_map:
            new_data_list = tag_map[key] + new_data_list
        data_list = new_data_list + other_list

        for i in data_list:
            ip_list2 = []
            pool_name_list2 = []
            for ip in i['ip']:
                if ip and ip not in ip_list2:
                    ip_list2.append(ip)

            for p_n in i['pool_name']:
                if p_n and p_n not in pool_name_list2:
                    pool_name_list2.append(p_n)

            i['ip'] = ','.join(ip_list2)
            i['pool_name'] = ','.join(pool_name_list2)

        ll = len(data_list)
        if offset + limit > ll:
            limit = ll
        data_list = data_list[offset: offset+limit+1]
    else:
        # =_= 这段代码复制了2遍，应该提出来
        for i in data_list:
            i['get_time_format'] = time.strftime('%m-%d %H:%M:%S', time.localtime(i['get_time']))
            k = event_details_map.get(i['id'], {})
            i.setdefault('ip', k.get('ip', []))
            i.setdefault('pool_id', k.get('pool_id', 0))
            i.setdefault('pool_name', [app_map.get(k.get('pool_id', 0), '')])
            i.setdefault('details', [])
            i.setdefault('level_name', level_map.get(i['level_id'], ''))
            i.setdefault('source_name', source_map.get(i['source_id'], ''))
            i.setdefault('type_name', type_map.get(i['type_id'], ''))
        data_list = data_list[:]  # queryset转为list

    return HttpResponse(json.dumps({'count': ll, 'data': data_list}), content_type="application/json")



# 0: success
# -1: failure
def exe_shell_command(type, ip):
    import os
    ret = -1
    type = int(type)
    cmd = ''
    if type == 1:
        # ping
        cmd = 'ping -c 3 ' + ip
    elif type == 2:
        # telnet 8080
        cmd = 'nc -w 1 -v ' + ip + ' 8080'
    elif type == 3:
        # telnet 10050
        cmd = 'nc -w 1 -v ' + ip + ' 10050'
    elif type == 4:
        # traceroute
        cmd = 'traceroute -w 3 ' + ip
    else:
        logger.warning("Unexpected type:%s", type)
        return ret

    ret = os.system(cmd)
    if ret != 0:
        ret = -1

    return ret


class EventLevelAdjustmentList(generics.ListCreateAPIView):
    """
    事件等级调整API

    输入参数：无

    输出参数：

    """
    queryset = EventLevelAdjustment.objects.all().order_by('-create_time')
    serializer_class = EventLevelAdjustmentSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('ip', 'operator',)
    filter_fields = ('id', 'status', )
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        queryset = EventLevelAdjustment.objects.all().order_by('-create_time')
        start_time = self.request.GET.get('start_time', '')
        end_time = self.request.GET.get('end_time', '')

        self_defined_filters = {}
        if start_time:
            self_defined_filters['start_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M:%S')

        if end_time:
            self_defined_filters['start_time__lte'] = str2stamp(end_time, '%Y-%m-%d %H:%M:%S')

        queryset = queryset.filter(**self_defined_filters)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user.username
        now = time.time()
        serializer.save(create_time=now, operator=user)


class EachEventLevelAdjustment(Basic, generics.RetrieveUpdateDestroyAPIView):
    """
    事件等级调整单页接口.

    输入参数：无

    输出参数：
    """
    queryset = EventLevelAdjustment.objects.all().order_by('-create_time')
    serializer_class = EventLevelAdjustmentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def perform_update(self, serializer):
        user = self.request.user.username
        serializer.save(operator=user, hit_time=0)

    def perform_destroy(self, instance):
        # instance is EventLevelAdjustment object
        # logical deletion
        EventLevelAdjustment.objects.filter(id=instance.id).update(status=1)


class EventMaskList(generics.ListCreateAPIView):
    """
    事件屏蔽API

    输入参数：无

    输出参数：

    """
    queryset = EventMask.objects.all().order_by('-create_time')
    serializer_class = EventMaskSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('ip', 'operator',)
    filter_fields = ('id', 'status', )
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        queryset = EventMask.objects.all().order_by('-create_time')
        start_time = self.request.GET.get('start_time', '')
        end_time = self.request.GET.get('end_time', '')

        self_defined_filters = {}
        if start_time:
            self_defined_filters['start_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M:%S')

        if end_time:
            self_defined_filters['start_time__lte'] = str2stamp(end_time, '%Y-%m-%d %H:%M:%S')

        queryset = queryset.filter(**self_defined_filters)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user.username
        now = time.time()
        serializer.save(create_time=now, operator=user)


class EachEventMask(Basic, generics.RetrieveUpdateDestroyAPIView):
    """
    事件屏蔽单页接口.

    输入参数：无

    输出参数：
    """
    queryset = EventMask.objects.all().order_by('-create_time')
    serializer_class = EventMaskSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def perform_update(self, serializer):
        user = self.request.user.username
        serializer.save(operator=user, hit_time=0)

    def perform_destroy(self, instance):
        # instance is EventMask object
        # logical deletion
        EventMask.objects.filter(id=instance.id).update(status=1)


# event api version 2
@api_view(['GET'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def get_eventlistv2(request):
    id_q = request.GET.get('id', '')
    source__id = request.GET.get('source__id', '')
    type__id = request.GET.get('type__id', '')
    level__id = request.GET.get('level__id', '')
    status_q = request.GET.get('status', '')
    converge_id = request.GET.get('converge_id', '')
    # 小于level_id
    level_id = request.GET.get('level_id', '')
    level__in = request.GET.get('level__in', '')
    source__in = request.GET.get('source__in', '')
    type__in = request.GET.get('type__in', '')
    site_id = request.GET.get('site_id', '')
    pool_id = request.GET.get('pool_id', '')

    start_time = request.GET.get('start_time', '')
    end_time = request.GET.get('end_time', '')
    search = request.GET.get('search')

    order_by_list = ['-get_time']
    self_defined_filters = {}
    undone_event_flag = False

    if id_q:
        self_defined_filters['id'] = id_q

    if source__id:
        self_defined_filters['source__id'] = source__id

    if type__id:
        self_defined_filters['type__id'] = type__id

    if level__id:
        self_defined_filters['level__id'] = level__id

    if status_q:
        try:
            status_q = int(status_q)
        except ValueError:
            raise MyException(u'the parameter \'status\' incorrect')

        self_defined_filters['status'] = status_q
        # for undone event
        if status_q == 0:
            order_by_list.insert(0, 'level__id')
            undone_event_flag = True

    if converge_id:
        self_defined_filters['converge_id'] = converge_id

    # 小于level_id
    if level_id:
        self_defined_filters['level_id__lt'] = level_id

    if level__in:
        self_defined_filters['level__in'] = level__in.split(',')

    if source__in:
        self_defined_filters['source__in'] = source__in.split(',')

    if type__in:
        self_defined_filters['type__in'] = type__in.split(',')

    if site_id:
        event_detail = EventDetail.objects.filter(site__id=site_id)
        self_defined_filters['id__in'] = [one.event_id for one in event_detail]

    if pool_id:
        event_detail = EventDetail.objects.filter(pool_id=pool_id).values('event_id')
        event_ids = [one['event_id'] for one in event_detail]
        self_defined_filters['id__in'] = event_ids

    if start_time:
        try:
            if start_time.count(':') == 1:
                start_time += ':00'
            self_defined_filters['get_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise MyException(u'time format error')
    else:
        # 如果没有指定id，则设置默认时间
        if not id_q:
            # start_time 默认为过去的24h
            start_time_default = int(time.time()) - 24*3600
            self_defined_filters['get_time__gte'] = start_time_default

    if end_time:
        try:
            if end_time.count(':') == 1:
                end_time += ':00'
            self_defined_filters['get_time__lt'] = str2stamp(end_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise MyException(u'time format error')
    else:
        # 如果没有指定id，则设置默认时间
        if not id_q:
            # end_time 默认为现在
            end_time_default = int(time.time()) + 60
            self_defined_filters['get_time__lt'] = end_time_default

    if search:
        self_defined_filters['message__contains'] = search

    # page information
    limit = int(request.GET.get('page_size', 30))
    offset = (int(request.GET.get('page', 1)) - 1)*limit

    # the count of the result
    # the count use about 600ms(local test)
    count = Event.objects.filter(**self_defined_filters).count()

    # if 0, return directly
    if count == 0:
        return HttpResponse(json.dumps({'count': 0, 'results': []}), content_type="application/json")

    if offset + limit > count:
        limit = count - offset + 1

    # the result set
    columns_list = ['id', 'level_id', 'level_adjustment_id', 'type_id',
                    'source_id', 'title', 'message', 'get_time', 'create_time',
                    'cancel_time', 'cancel_user', 'comment', 'status', 'cancel_type']

    # use about 600ms(local test)
    result_set = Event.objects.filter(**self_defined_filters).order_by(*order_by_list)[offset: offset+limit].values(*columns_list)

    # event id in result
    eventid_list = []
    for event in result_set:
        eventid_list.append(event['id'])

    # event detail.eg.ip and pool
    ed_columns = ['event_id', 'ip', 'pool_id']
    event_detail_res = EventDetail.objects.filter(event_id__in=eventid_list).values(*ed_columns)
    event_detail_map = {}
    pool_id_list = []
    for ed in event_detail_res:
        pool_id_list.append(ed['pool_id'])
        if ed['event_id'] not in event_detail_map:
            event_detail_map[ed['event_id']] = {'ip': [ed['ip']], 'pool_id': ed['pool_id']}
        else:
            event_detail_map[ed['event_id']]['ip'].append(ed['ip'])

    # preload app info
    event_global_var.update_app_info(pool_id_list)

    # add extra info
    for row in result_set:
        # 未处理事件持续时间
        if undone_event_flag:
            row['during_time'] = timelength_format(row['get_time'], int(time.time()))

        # time format
        row['get_time'] = stamp2str(row['get_time'])
        row['create_time'] = stamp2str(row['create_time'])
        if row['cancel_time'] == 0:
            row['cancel_time'] = ""
        else:
            row['cancel_time'] = stamp2str(row['cancel_time'])

        detail = event_detail_map.get(row['id'], {})
        row.setdefault('ip', detail.get('ip', []))

        pack_pool_id = detail.get('pool_id', 0)
        row.setdefault('pool_id', pack_pool_id)
        app_info = event_global_var.get_app_info(pack_pool_id)
        if app_info:
            site_pool_name = app_info[0] + "/" + app_info[1]
        else:
            site_pool_name = ''
        row.setdefault('pool_name', site_pool_name)

        row.setdefault('source_name', event_global_var.get_source_info(row['source_id']))
        row.setdefault('level_name', event_global_var.get_level_info(row['level_id']))
        row.setdefault('type_name', event_global_var.get_type_info(row['type_id']))

        # status name
        row['status'] = event_global_var.get_event_status_name(row['status'])

    # queryset转为list
    result_set = result_set[:]
    return HttpResponse(json.dumps({'count': count, 'results': result_set}), content_type="application/json")


# alarm api version 2
@api_view(['GET'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def get_alarmlistv2(request):
    # event parameter
    pool_id = request.GET.get('pool_id', '')
    exclude_source_id = request.GET.get('exclude_source_id', 0)

    source__in = request.GET.get('source__in', '')
    type__in = request.GET.get('type__in', '')
    level__in = request.GET.get('level__in', '')

    # compatible
    source_id = request.GET.get('event__source__id', '')
    type_id = request.GET.get('event__type__id', '')
    level_id = request.GET.get('event__level__id', '')

    search = request.GET.get('search', '')

    event_defined_filters = {}
    event_defined_exclude = {}

    if pool_id:
        event_detail = EventDetail.objects.filter(pool_id=pool_id).values('event_id')
        event_ids = [one['event_id'] for one in event_detail]
        event_defined_filters['id__in'] = event_ids

    if exclude_source_id:
        event_defined_exclude['source_id'] = exclude_source_id

    if source__in:
        event_defined_filters['source_id__in'] = source__in.split(',')

    if type__in:
        event_defined_filters['type_id__in'] = type__in.split(',')

    if level__in:
        event_defined_filters['level_id__in'] = level__in.split(',')

    if source_id:
        event_defined_filters['source_id'] = source_id

    if type_id:
        event_defined_filters['type_id'] = type_id

    if level_id:
        event_defined_filters['level_id'] = level_id

    if search:
        event_defined_filters['message__contains'] = search

    # alarm parameter
    id_q = request.GET.get('id', '')
    status_id = request.GET.get('status_id', '')
    method_id = request.GET.get('method_id', '')

    start_time = request.GET.get('start_time', '')
    end_time = request.GET.get('end_time', '')

    order_by_list = ['-create_time']
    alarm_defined_filters = {}

    if id_q:
        alarm_defined_filters['id'] = id_q

    if status_id:
        alarm_defined_filters['status_id'] = status_id

    if method_id:
        alarm_defined_filters['method_id'] = method_id

    if start_time:
        try:
            alarm_defined_filters['create_time__gte'] = str2stamp(start_time, '%Y-%m-%d %H:%M')
        except ValueError:
            raise MyException('time format error')
    else:
        # 如果没有指定id，则设置默认时间
        if not id_q:
            # start_time 默认为过去的24h
            start_time_default = int(time.time()) - 24*3600
            alarm_defined_filters['create_time__gte'] = start_time_default

    if end_time:
        try:
            alarm_defined_filters['create_time__lt'] = str2stamp(end_time, '%Y-%m-%d %H:%M')
        except ValueError:
            raise MyException('time format error')
    else:
        # 如果没有指定id，则设置默认时间
        if not id_q:
            # end_time 默认为现在
            end_time_default = int(time.time()) + 60
            alarm_defined_filters['create_time__lt'] = end_time_default

    event_id_list = []
    # 是否要过滤
    if event_defined_filters or event_defined_exclude:
        # 过滤1：alarm
        alarm_count = Alarm.objects.filter(**alarm_defined_filters).count()
        if alarm_count == 0:
            return HttpResponse(json.dumps({'count': 0, 'results': []}), content_type="application/json")

        alarm_columns = ['event_id']
        alarm_result_set = Alarm.objects.filter(**alarm_defined_filters).values(*alarm_columns)

        event_id_list = []
        for one in alarm_result_set:
            event_id_list.append(one['event_id'])

        old_event_ids = event_defined_filters.get('id__in', [])
        if old_event_ids:
            # 交集
            event_id_merge = list(set(event_id_list).intersection(set(old_event_ids)))
            event_defined_filters['id__in'] = event_id_merge
        else:
            event_defined_filters['id__in'] = event_id_list

        # 过滤2: event
        event_count = Event.objects.filter(**event_defined_filters).exclude(**event_defined_exclude).count()
        if event_count == 0:
            return HttpResponse(json.dumps({'count': 0, 'results': []}), content_type="application/json")

        event_columns = ['id']
        event_result_set = Event.objects.filter(**event_defined_filters).exclude(**event_defined_exclude).values(*event_columns)
        event_id_list = []
        for one in event_result_set:
            event_id_list.append(one['id'])

    # page information
    limit = int(request.GET.get('page_size', 30))
    offset = (int(request.GET.get('page', 1)) - 1)*limit

    # query alarm info
    if event_id_list:
        alarm_defined_filters['event_id__in'] = event_id_list
    alarm_count = Alarm.objects.filter(**alarm_defined_filters).count()
    if alarm_count == 0:
        return HttpResponse(json.dumps({'count': 0, 'results': []}), content_type="application/json")

    count = alarm_count
    if offset + limit > count:
        limit = count - offset + 1

    columns_list = ['id', 'event_id', 'method_id', 'result', 'create_time', 'receiver', 'error']
    alarm_result_set = Alarm.objects.filter(**alarm_defined_filters).order_by(*order_by_list)[offset:offset+limit].values(*columns_list)

    event_id_list = []
    for one in alarm_result_set:
        event_id_list.append(one['event_id'])

    # query event info
    event_defined_filters = {'id__in': event_id_list}
    event_columns = ['id', 'source_id', 'type_id', 'level_id', 'title', 'message', 'level_adjustment_id']
    event_result_set = Event.objects.filter(**event_defined_filters).values(*event_columns)

    event_map = {}
    for one in event_result_set:
        event_map.setdefault(one['id'], one)

    # event detail.eg.ip and pool
    ed_columns = ['event_id', 'ip', 'pool_id']
    event_detail_res = EventDetail.objects.filter(event_id__in=event_id_list).values(*ed_columns)
    event_detail_map = {}
    pool_id_list = []
    for ed in event_detail_res:
        pool_id_list.append(ed['pool_id'])
        if ed['event_id'] not in event_detail_map:
            event_detail_map[ed['event_id']] = {'ip': [ed['ip']], 'pool_id': ed['pool_id']}
        else:
            event_detail_map[ed['event_id']]['ip'].append(ed['ip'])

    # preload app info
    event_global_var.update_app_info(pool_id_list)

    # add extra info
    # method_name, receiver_name, source_name, type_name, level_name
    for row in alarm_result_set:
        # alarm
        row['method_name'] = event_global_var.get_alarm_method_name(row['method_id'])
        row['create_time'] = stamp2str(row['create_time'])

        # event
        event_id = row['event_id']
        one_event = event_map.get(event_id, {})
        for event_field in one_event:
            if event_field != 'id':
                row[event_field] = one_event[event_field]

        row['source_name'] = event_global_var.get_source_info(one_event.get('source_id', 0))
        row['type_name'] = event_global_var.get_type_info(one_event.get('type_id', 0))
        row['level_name'] = event_global_var.get_level_info(one_event.get('level_id', 0))

        # event_detail
        one_event_detail = event_detail_map.get(event_id, {})
        row['ip'] = one_event_detail.get('ip', [])
        pack_pool_id = one_event_detail.get('pool_id', 0)
        row['pool_id'] = pack_pool_id

        # pool name
        app_info = event_global_var.get_app_info(pack_pool_id)
        if app_info:
            site_pool_name = app_info[0] + "/" + app_info[1]
        else:
            site_pool_name = ''
        row.setdefault('pool_name', site_pool_name)

        # receiver_name
        row['receiver'] = event_global_var.get_alarm_receiver_name(row['method_id'], row['receiver'])

    alarm_result_set = alarm_result_set[:]
    return HttpResponse(json.dumps({'count': count, 'results': alarm_result_set}), content_type="application/json")


# 事件误报确认
@api_view(['POST'])
@permission_classes((IsAuthenticatedOrReadOnly, ))
def confirm_event_accuracy(request):
    id_q = request.POST.get('id', 0)
    update_data = {'cancel_type':1}
    response_data = {}

    try:
        res = Event.objects.filter(id=id_q).update(**update_data)
    except Exception as e:
        logger.warning("Exception:%s", e.message)
        response_data['result'] = -1
        response_data['detail'] = e.message
        return HttpResponse(json.dumps(response_data), content_type="application/json")

    if not res:
        msg = "Invalid event id, please check."
        logger.warning("Exception:%s", msg)
        response_data['result'] = -1
        response_data['detail'] = msg
    else:
        response_data['result'] = 0

    return HttpResponse(json.dumps(response_data), content_type="application/json")
