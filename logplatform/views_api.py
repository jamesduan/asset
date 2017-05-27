# -*- coding: utf-8 -*-
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, status
from rest_framework import filters
from rest_framework import permissions
from serializers import *
from change.utiltask import *
from logplatform.models import *
from util.sendmail import *
from management.commands.reg_running_threading import test_my_reg
import time
import json


def get_date(shijianchuo=0):
    if not shijianchuo:
        shijianchuo = time.time()
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(shijianchuo))


class MyException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class Basic(object):
    """
    基础变量、方法类
    """
    DB_ALIA = 'logplatform'


class RegList(Basic, generics.ListCreateAPIView):
    """
    防ccurl信息接口.

    输入参数：无

    输出参数：

    """
    queryset = Reg.objects.using(Basic.DB_ALIA).filter(type=1).order_by('query')
    search_fields = ('query','updater','remark',)
    filter_fields = ('enable',)
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    serializer_class = RegSerializer

    def perform_create(self, serializer):
        updater = self.request.user.username
        instance = serializer.save(updater=updater, update_time=get_date())

        changeAndEmail(instance, '新增')


class RegDetail(Basic, generics.RetrieveUpdateDestroyAPIView):
    queryset = Reg.objects.using(Basic.DB_ALIA).all()
    serializer_class = RegSerializer

    def perform_update(self, serializer):
        id = self.get_object().id
        reg_instance = Reg.objects.using(Basic.DB_ALIA).get(id=id)

        updater = self.request.user.username
        instance = serializer.save(updater=updater, update_time=get_date())

        changeAndEmail(instance, '修改', reg_instance)


class TestReg(Basic, APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, pk):
        result = test_my_reg(pk)
        result['request'] = json.dumps(result['request'], indent=4)
        result['response'] = json.dumps(result['response'], indent=4)
        return Response(result)

def changeAndEmail(instance, opration, reg=None):
    # 发邮件
    subject = '防CC规则变更提醒邮件'
    html_content = '操作：' + opration
    html_content += '<br>操作人：' + instance.updater

    html_content += '<br>ID：' + str(instance.id)

    html_content += '<br>规则：'
    if reg:
        html_content += str(reg.query) + ' -> '
    html_content += instance.query

    interval_value = {60: '1分钟', 3600: '1小时'}
    html_content += '<br>单位：'
    if reg:
        html_content += interval_value[reg.interval_value] + ' -> '
    html_content += interval_value[instance.interval_value]

    html_content += '<br>阀值：'
    if reg:
        html_content += str(reg.count) + ' -> '
    html_content += str(instance.count)

    is_influence = {0: '不影响', 1: '影响'}
    html_content += '<br>下单：'
    if reg:
        html_content += is_influence[reg.is_influence] + ' -> '
    html_content += is_influence[instance.is_influence]

    enable = {0: '启用', 1: '关闭'}
    html_content += '<br>状态：'
    if reg:
        html_content += enable[reg.enable] + ' -> '
    html_content += enable[instance.enable]

    html_content += '<br>备注：'
    if reg:
        html_content += str(reg.remark) + ' -> '
    html_content += instance.remark

    recipient_list = 'IT_Security@yhd.com'
    receive = recipient_list.split(',')
    sendmail_html(subject, html_content, receive)

    # 变更记录
    key = 'cc_' + str(instance.id)
    block_cc_create(instance.updater, key, html_content)
