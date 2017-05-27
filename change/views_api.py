# -*- coding: utf-8 -*-
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
# from rest_framework.exceptions import YAPIException
from rest_framework.permissions import AllowAny
from django.http import HttpResponse
import uuid, logging
import time,datetime
from rest_framework import generics
from rest_framework import filters

from serializers import *
from cmdb.models import App
from cmdb.views_api import YAPIException
from models import *
from util.timelib import stamp2str
from django.core import serializers
from rest_framework.response import Response
from rest_framework import status
from change.filters import *
import json

class ChangeMain(generics.ListCreateAPIView):
    """
    变更数据创建/筛选接口.

    输入参数：

    * index       -   索引ID （可选，如无此参数则为所有LOG）
    * user        -   变更操作人
    * type        -   业务名称
    * action      -   业务动作
    * start_time  -   开始时间（大于等于）
    * end_time    -   结束时间（小于等于）
    * app_id      -   此条变更记录作用的pool

    输出参数：

    * id                    -   pk
    * user                  -   操作者
    * task_id               -   任务ID
    * type                  -   应用模块名称
    * action                -   应用模块动作
    * index                 -   索引值，装机脚本可采用虚拟机的IP
    * level                 -   预留字段，目前填写定值"change"
    * level_id              -   引起事故的等级
    * level_name            -   引起事故等级的名字 L1-L5
    * action_name           -   动作名
    * action_desc           -   动作描述
    * action_type_name      -   动作类型名
    * action_type_desc      -   动作类型描述
    * message               -   变更记录消息 
    * happen_time           -   变更记录发生时间
    * happen_time_str       -   变更记录发生时间字符串形式
    * created               -   记录创建时间 
    * app_id                -   关联的app_id
    * pool_name             -   关联的pool名
    """

    queryset = Main.objects.using('change')\
                           .exclude(type=settings.DISABLE_CHANGE_TYPES[0])\
                           .order_by("-happen_time")
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    serializer_class = ChangeMainSerializer

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):

        # define vars and get frontend objects
        filters = dict()
        app = None
        user = self.request.QUERY_PARAMS.get("user")
        type = self.request.QUERY_PARAMS.get("type")
        action = self.request.QUERY_PARAMS.get("action")
        index = self.request.QUERY_PARAMS.get("index")
        input_start_time = self.request.QUERY_PARAMS.get("start_time")
        input_end_time = self.request.QUERY_PARAMS.get("end_time")
        type_id = self.request.QUERY_PARAMS.get("type_id")
        action_id = self.request.QUERY_PARAMS.get("action_id")
        app_id = self.request.QUERY_PARAMS.get("app_id")
        level_id = self.request.QUERY_PARAMS.get("level_id")
        level_id__lt = self.request.QUERY_PARAMS.get("level_id__lt")
        change_id = self.request.QUERY_PARAMS.get("id")

        if type_id:
            try:
                type = Type.objects.get(id=int(type_id)).key
            except Type.DoesNotExist as e:
                raise YAPIException('error:type does not exists !')
            except ValueError,e:
                raise YAPIException('error:type_id not valid !')
            except Exception ,e:
                raise YAPIException('error:Server Error!')

        if app_id:
            try:
                app = App.objects.get(id=int(app_id))
            except App.DoesNotExist as e:
                raise YAPIException("app does not exists!")
            except ValueError, e:
                raise YAPIException("app_id not valid!")

        if level_id:
            try:
                acts = Action.objects.filter(level_id=int(level_id))
                act_ids = [act.id for act in acts]
                self.queryset = self.queryset.filter(action_id__in = act_ids)
            except ValueError, e:
                raise YAPIException("level_id not valid!")
            except Exception as e:
                raise YAPIException("error: can not find actions!")
        if level_id__lt:
            try:
                acts = Action.objects.filter(level_id__lt=int(level_id__lt))
                act_ids = [act.id for act in acts]
                self.queryset = self.queryset.filter(action_id__in = act_ids)
            except ValueError, e:
                raise YAPIException("level_id not valid!")
            except Exception as e:
                raise YAPIException("error: can not find actions!")

        if change_id:
            try:
                filters['id'] = int(change_id)
            except TypeError, e:
                raise YAPIException("id is not expect type !")
        if action_id:
            filters['action_id'] = action_id
        if app:
            filters['app'] = app
        if user:
            filters["user"] = user
        if type:
            filters["type"] = type
        if action:
            filters["action"] = action
        if index:
            filters["index__startswith"] = index

        # support unix time and general time format to search
        if input_start_time:
            try:
                start_time_unix = int(input_start_time)
                start_time = stamp2str(start_time_unix)
            except ValueError as e:
                start_time = input_start_time
            filters["happen_time__gte"] = start_time

        if input_end_time:
            try:
                end_time_unix = int(input_end_time)
                end_time = stamp2str(end_time_unix)
            except ValueError as e:
                end_time = input_end_time
            filters["happen_time__lte"] = end_time

        return self.queryset.filter(**filters)\
                           .exclude(type=settings.DISABLE_CHANGE_TYPES[0])\
                           .using('change')\
                           .order_by('-happen_time')

    def perform_create(self, serializer):
        # 验证type和action的合法性
        type = self.request.DATA.get('type')
        action = self.request.DATA.get('action')
        app_id = self.request.DATA.get('app_id')
        exists_type, exists_action, app = (None, None, None)

        try:
            exists_type = Type.objects.using('change').get(key=type)
        except Type.DoesNotExist as e:
            logging.warn("change.views_api.perform_create() "+\
                         "type does not exists!")

        if exists_type:
            type_id = exists_type.id
            try:
                exists_action = Action.objects.using('change').get(key=action, 
                                                              type_id=type_id)
            except Action.DoesNotExist as e:
                logging.warn("change.views_api.perform_create()" + \
                             "action does not exits! create failed!")
            if exists_action:
                try:
                    app = App.objects.get(id=app_id)
                except App.DoesNotExist as e:
                    logging.warn("app not exists! skip it")

                serializer.save(created=stamp2str(time.time()),
                                task_id=uuid.uuid4(),
                                action_id=exists_action.id, app=app)
            else:
                raise YAPIException("this action can not find!")
        else:
            raise YAPIException('type does not exists!')


class ChangeType(generics.ListAPIView):
    queryset = Type.objects.all().order_by('-id')
    serializer_class = ChangeTypeSerializer

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):
        filters = dict()
        level_id__in = self.request.QUERY_PARAMS.get("level_id__in", '')

        if level_id__in:
            actions = Action.objects.filter(level_id__in = level_id__in.split(','))
            type_ids = list(set([a.type_id for a in actions]))
            if type_ids:
                filters['id__in'] = type_ids
            else:
                return []
        return self.queryset.filter(**filters).order_by('-id')


class ChangeAction(generics.ListCreateAPIView):
    """docstring for ChangeActionList"""
    queryset = Action.objects.all().order_by('-id')
    serializer_class = ChangeActionSerializer

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):

        type = None

        filters = dict()
        type_id = self.request.QUERY_PARAMS.get("type_id")
        level_id__in = self.request.QUERY_PARAMS.get("level_id__in", '')

        if type_id:
            try:
                type = Type.objects.get(id=int(type_id))
                filters['type'] = type
            except ValueError as e:
                raise YAPIException("type_id is not valid!")
            except Type.DoesNotExist, e:
                raise YAPIException("type({id}) does not exists".format(id=type_id))
        if level_id__in:
            filters['level_id__in'] = level_id__in.split(',')
        return self.queryset.filter(**filters).order_by('-id')


class ExceptionReportList(generics.ListCreateAPIView):
    """
    异常数据列表接口.

    输入参数：page_size  每页展示数量

    输出参数：

    * id        -   pk
    * cname     -   异常描述
    * owner     -   维护团队
    * exception_count   -   异常数量
    * last_update   -   更新时间
    """
    queryset = ExceptionReport.objects.filter(status=1)
    serializer_class = ExceptionReportSerializer
    filter_backends = (filters.SearchFilter,filters.DjangoFilterBackend,ExceptionReportFilterBackend)
    search_fields = ('cname', 'owner','owner_domain__domainname')
    filter_fields = ('type',)

@api_view(['POST'])
@permission_classes((AllowAny, ))
def exception_trend(request):
    report_id = request.POST['report_id']
    start = request.POST['start']
    end = request.POST['end']
    start = int(time.mktime(datetime.datetime.strptime(start,'%Y-%m-%d').timetuple()))
    end = int(time.mktime(datetime.datetime.strptime(end,'%Y-%m-%d').timetuple())) + 86400
    exception_trend = ExceptionReportDaily.objects.filter(report_id =report_id, create_time__range = (start, end))
    result = serializers.serialize('json', exception_trend)
    return HttpResponse(result)

@api_view(['GET'])
@permission_classes((AllowAny, ))
def change_action_by_type(request):
    type = request.GET.get('type')
    action_list = Main.objects.filter(type = type).using('change').values('action').distinct()
    return Response(status=status.HTTP_200_OK, data=action_list)