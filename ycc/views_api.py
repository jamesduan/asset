# -*- coding: utf-8 -*-
import time, datetime
from django.utils.datastructures import MultiValueDictKeyError
from asset.models import IpTotal
from asset.models import Asset
from util.timelib import stamp2str
import json
import os
import tempfile
import zipfile
import shutil
import chardet
import random
import urllib
import urllib2
from rest_framework import generics
from django.core.cache import cache
from redis.exceptions import ConnectionError, TimeoutError
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.exceptions import APIException
from django.shortcuts import HttpResponse
from rest_framework.response import Response
from django.core.servers.basehttp import FileWrapper
from django.db.models import Max
from change.tasks import collect
from django.db.models import Q
from change.utiltask import *
from ycc.models import ConfigGroup
from datetime import date
from serializers import *
from cmdb.models import Site, App, ConfigDbKvCustom, ConfigDbInstance, ConfigDbKvDefault, DdDomain, DdUsers, \
    DdUsersDomains
from assetv2.settingsdeploy import YCC_ENV
from assetv2.settingsapi import YCC_GROUP_ID, jdbc_url_key_name, jdbc_username_key_name, jdbc_password_key_name, \
    YCC_CMP_ENV
from ycc.management.commands import ycc_sync_app_and_group
from assetv2.settingsapi import CATCH_REDIS, DB_SUPPORT
import operator
from django.utils import six
from ycc import filters as ycc_filters
from ycc.permissions import *
from deploy.utils.Pika import Pika
from server.models import Server
from assetv2.settingsdeploy import SOA_SERVER
import binascii


def md5(str):
    import hashlib
    m = hashlib.md5()
    m.update(str)
    return m.hexdigest()


def get_configinfos_v3(group_id='', data_id=''):
    configinfo_v3 = ConfigInfoV3.objects.filter(group_status__status=0, group_status__group__status=1)
    if group_id:
        configinfo_v3 = configinfo_v3.filter(group_status__group__group_id=group_id)
    if data_id:
        configinfo_v3 = configinfo_v3.filter(data_id=data_id)
    return configinfo_v3


def configinfov3_insert_cmp(group_id, data_id, content_md5):
    configinfo_cmp = ConfiginfoCmp.objects.filter(group_id=group_id, data_id=data_id)
    flag = True
    if len(configinfo_cmp):
        if len(configinfo_cmp) == 1:
            if configinfo_cmp[0].cmp:
                configinfo_v3 = get_configinfos_v3(group_id, data_id)
                if configinfo_v3:
                    for config in configinfo_v3:
                        if not content_md5 == config.content_md5:
                            flag = False
                            break
        else:
            flag = True
    return {
        'result': flag,
        'message': '该配置文件为一致性配置文件，插入内容必须相同！'
    }


def get_room_idc(group_name):
    idcs_envs = {}
    rooms = Room.objects.filter(status=1)
    envs = ConfigEnv.objects.exclude(name='both')
    for rm in rooms:
        # try:
        #     group_statuss = ConfigGroup.objects.get(group_id=group_name, idc=rm.id).group_status
        # except ConfigGroup.DoesNotExist:
        #     raise YAPIException('ConfigGroup DoesNotExist!')
        # except ConfigGroup.MultipleObjectsReturned:
        #     raise YAPIException('ConfigGroup MultipleObjectsReturned!')
        group_statuss = ConfigGroup.objects.filter(group_id=group_name, idc=rm.id)
        if group_statuss:
            if not idcs_envs.get(rm.id):
                idcs_envs[rm.id] = {}
            tmp_en = []
            for en in envs:
                tmp_en.append(en)
            idcs_envs[rm.id]['group_status'] = group_statuss[0].group_status
            idcs_envs[rm.id]['room'] = tmp_en
            idcs_envs[rm.id]['idc_name'] = rm.name_ch
    return idcs_envs


def create_or_update_configinfocmp(flag_tmp, group_id, data_id):
    configinfo_cmp = ConfiginfoCmp.objects.filter(group_id=group_id, data_id=data_id)
    if len(configinfo_cmp) == 1:
        configinfo_cmp.update(cmp=flag_tmp)
    elif len(configinfo_cmp) == 0:
        configinfo_cmp.create(group_id=group_id, data_id=data_id, cmp=flag_tmp)
    else:
        raise YAPIException('ConfiginfoCmp MultipleObjectsReturned!')


def get_cmp_result(cond_id, cmp_md5_list):
    md5_tmp = ''
    flag_tmp = 1
    if cond_id is not None:
        flag_tmp = 0
    else:
        for cm in cmp_md5_list:
            if not md5_tmp:
                md5_tmp = cm
            else:
                if not cm == md5_tmp:
                    flag_tmp = 0
                    break
    return flag_tmp


class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class GroupList(generics.ListCreateAPIView):
    """
    YCC配置组列表/新增.

    输入参数：

    输出参数：

    * id                    -   PK
    * site_id               -   站点ID
    * site_name             -   站点名称
    * app_id                -   应用ID
    * app_name              -   应用名称
    * group_id              -   配置组名称
    * type                  -   1-app类配置  2-公共组件类（jar）
    * old_pool              -   兼容老YCC字段，未来会废弃
    * idc                   -   IDC标识符  SH-南汇  JQ-金桥
    * created               -   创建时间
    * updated               -   修改时间
    """
    queryset = ConfigGroup.objects.filter(status=1).order_by('-id')
    serializer_class = GroupSerializer
    filter_backends = (filters.SearchFilter, ycc_filters.ConfigGroupFilterBackend)
    # filter_backends = (filters.SearchFilter,)
    search_fields = ('site_name', 'app_name', 'group_id', 'idc__name_ch')
    permission_classes = (YccAdminPermission,)

    def perform_create(self, serializer):
        group_id = serializer.validated_data.get('group_id')
        idc = serializer.validated_data.get('idc')
        if ConfigGroup.objects.filter(group_id=group_id, idc=idc, status=1).exists():
            raise YAPIException('同名同IDC配置组已经存在。')
        type = serializer.validated_data.get('type')
        siteid = 0
        appid = 0
        sitename = ''
        appname = ''
        if type == 1:
            site_id = self.request.DATA.get('site_id', None)
            app_id = self.request.DATA.get('app_id', None)
            site = Site.objects.get(pk=site_id)
            app = App.objects.get(pk=app_id)
            siteid = site.id
            appid = app.id
            sitename = site.name
            appname = app.name
        current_time = int(time.time())
        group = serializer.save(site_id=siteid, site_name=sitename, app_id=appid, app_name=appname,
                                created=current_time, updated=current_time)
        ConfigGroupStatus.objects.create(group=group, version=0, status=0, pre_version=0)
        # 变更系统
        collect_type = '应用类' if group.type == 1 else '公共组建类'
        collect_index = '%s/%s/%s' % (
            group.group_id, Room.objects.get(
                name=group.idc).name_ch, collect_type)
        collect(
            {'type': "group", 'action': 'add', 'index': collect_index, 'level': 'normal',
             'message': '成功创建配置组：%s' % group.group_id,
             'user': self.request.user.username,
             'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})

    def get_queryset(self):
        # queryset = ConfigGroup.objects.filter(status=1)
        return self.queryset


class GroupDetail(generics.RetrieveUpdateAPIView):
    queryset = ConfigGroup.objects.filter(status=1)
    serializer_class = GroupSerializer
    permission_classes = (YccAdminPermission,)

    def perform_update(self, serializer):
        group_id = self.request.DATA.get('group_id', None)
        idc = self.request.DATA.get('idc', None)
        id = self.request.DATA.get('id', None)
        rmid = self.request.DATA.get('rmid', None)
        if rmid:
            instance = ConfigGroup.objects.filter(id=rmid)
            status = self.request.DATA.get('status', None)
            instance.update(status=status)
            collect_action = 'delete'
        else:
            instance = ConfigGroup.objects.filter(id=id)
            instance.update(group_id=group_id, idc=idc)
            collect_action = 'edit'
        collect_type = '应用类' if instance[0].type == 1 else '公共组建类'
        collect_idc_name = Room.objects.get(name=instance[0].idc).name_ch
        collect_index = '%s/%s/%s' % (
            instance[0].group_id, collect_idc_name, collect_type)
        collect(
            {'type': "group", 'action': collect_action, 'index': collect_index, 'level': 'normal',
             'message': '成功%s配置组{idc:%s;group_name:%s}' % (collect_action, collect_idc_name, instance[0].group_id),
             'user': self.request.user.username,
             'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})


@api_view(['POST'])
@permission_classes((AllowAny,))
def uploadMetaInfo(request):
    response = HttpResponse()
    response['Content-Type'] = 'text/html;charset=UTF-8'
    response.status_code = 200
    return response


# 同步APP
@api_view(['GET'])
@permission_classes((AllowAny,))
def syn_groupcontact(request):
    response1 = ycc_sync_app_and_group.retmsg()
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


# 历史DB配置管理判断DB标识符是否存在
@api_view(['GET'])
@permission_classes((AllowAny,))
def dburl_exists(request):
    dburl = request.QUERY_PARAMS['dburl'] if request.QUERY_PARAMS['dburl'] else ''
    username = request.QUERY_PARAMS['username'] if request.QUERY_PARAMS['username'] else ''
    error_msg = ''
    """
    Standard:
        For Oracle: jdbc:oracle:thin:@//<host>:<port>/ServiceName NOT OR jdbc:oracle:thin:@<host>:<port>:<SID>
        For Mysql: jdbc:mysql://<host>:<port>/<database_name>

    Example:
        jdbc:oracle:thin:@//prod-db-pri01.int.yihaodian.com:1521/item
        jdbc:mysql://mysql-frontweb.int.yihaodian.com:3306/yhd_frontweb_sys
        jdbc:mysql://mysql-sem.int.yihaodian.com:3307/market?autoReconnect=true&autoReconnectForPools=true
    """
    dbtype = get_dbname(dburl)
    if dbtype:
        if dbtype == 'mysql':
            if dburl.split('//', 1)[0] != 'jdbc:mysql:':
                dburl = ''
            error_msg = "标识符未存在，参照：jdbc:mysql://[host]:[port]/[database_name]并且username应于标识符匹配"
        elif dbtype == 'oracle':
            if dburl.split('//', 1)[0] != 'jdbc:oracle:thin:@':
                dburl = ''
            error_msg = "标识符未存在，参照：jdbc:oracle:thin:@//[host]:[port]/[ServiceName]并且username应于标识符匹配"
        else:
            error_msg = "标识符不存在，请检查！"
    if '(' in dburl or ')' in dburl or 'mongo' in dburl:
        dburl = ''
    elif '//' in dburl:
        dburl = dburl.split('//', 1)[1]
    # elif '@' in dburl and '//' not in dburl:
    #     dburl_tmp = dburl.split('@', 1)[1]
    #     if ':' in dburl_tmp:
    #         try:
    #             dburl = "%s:%s/%s" % (dburl_tmp.split(':')[0], dburl_tmp.split(':')[1], dburl_tmp.split(':')[2])
    #         except:
    #             raise YAPIException('URL格式不对！')
    else:
        dburl = ''
    if '?' in dburl:
        dburl = dburl.split('?', 1)[0]
    if dburl:
        dburl = "%s//%s" % (dburl.strip(), username.strip())
    con_db_int = ConfigDbInstance.objects.filter(cname__icontains=dburl, db_type=dbtype) if dburl != '' else False
    if con_db_int and dburl != '':
        response1 = {'success': True, 'id': con_db_int[0].id, 'msg': dburl}
    else:
        response1 = {'success': False, 'id': 0, 'msg': u'%s' % error_msg}
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


@permission_classes((AllowAny,))
def get_dbname(string):
    if 'mysql' in string:
        return 'mysql'
    elif 'oracle' in string:
        return 'oracle'
    else:
        return ''


@permission_classes((AllowAny,))
def get_dbupdate_list():
    # con_tmp = ConfigInfo.objects.filter(Q(config_type=1), Q(group_status__status=0),
    #                                      Q(data_id__icontains='datasource') | Q(data_id__icontains='jdbc') | Q(
    #                                          data_id__icontains='mongo') | Q(data_id__icontains='mysql') | Q(
    #                                          data_id__icontains='datesource') | Q(data_id__icontains='imp-conf') | Q(
    #                                          data_id__icontains='db1_read') | Q(data_id__icontains='db1_write') | Q(
    #                                          data_id__icontains='pis.search') | Q(
    #                                          data_id__icontains='yihaodian_search') | Q(
    #                                          data_id__icontains='detector-batch'),
    #                                      Q(content__icontains='password=') | Q(content__icontains='jdbc')).exclude(
    #     Q(content__icontains='model') | Q(content__icontains='?xml')).order_by('-id')
    configinfo = ConfigInfo.objects.filter(Q(config_type__in=[1, 3]), Q(group_status__status=0),
                                           Q(group_status__group__status=1),
                                           Q(data_id__icontains='datasource') | Q(data_id__icontains='jdbc') | Q(
                                               data_id__icontains='mysql') | Q(
                                               data_id__icontains='datesource') | Q(data_id__icontains='imp-conf') | Q(
                                               data_id__icontains='db1_read') | Q(data_id__icontains='db1_write') | Q(
                                               data_id__icontains='pis.search') | Q(
                                               data_id__icontains='yihaodian_search') | Q(
                                               data_id__icontains='detector-batch'),
                                           Q(content__icontains='password=') | Q(content__icontains='jdbc')).exclude(
        Q(content__icontains='model') | Q(content__icontains='?xml') | Q(content__icontains='mongo')).order_by('-id')
    return configinfo


@api_view(['GET'])
@permission_classes((AllowAny,))
def syn_dbupdate(request):
    ConfigInfoTmp.objects.all().delete()
    # con_tmp = get_dbupdate_list()
    con_tmp = ConfigInfo.objects.filter(config_type=3)
    flag = 0
    total_count = 0
    for xx in con_tmp:
        flag = syn_dbupdate_one(xx.id, xx.content, 'add')
        total_count += 1
    if flag == 0:
        response1 = {'success': True, 'msg': u'初始化成功!!!！总共：%s条' % total_count}
    else:
        response1 = {'success': False, 'msg': u'%s' % flag}
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


# @api_view(['GET'])
@permission_classes((AllowAny,))
def syn_dbupdate_one(configinfo_id, content, action):
    test_arry1 = content.split('\n')
    tmp_arr = []
    tmp_cddi_def_arr = dict()
    tmp_cddi_cut_arr = dict()
    tmp_cddi_def_name_arr = dict()
    tmp_cddi_cut_name_arr = dict()
    tmp_cddi_jdbcurl = ''
    dbtype = ''
    flag = 0
    for i in test_arry1:
        if "%s=" % jdbc_url_key_name in i and '#' not in i:
            dbtype = get_dbname(i)
            # flag += 1
    # if flag > 1:
    #     return "请删除多余的url或者拆分！"
    # elif flag == 0:
    #     return "配置文件内容中缺少jdbc.url参数"
    try:
        con_db_def_instances = ConfigDbKvDefault.objects.filter(dbtype=dbtype)
    except ConfigDbKvDefault.DoesNotExist:
        return "1、无URL；2、URL中没有mysql或者oracle关键字。"

    for cddi in con_db_def_instances:
        if cddi.jdbctype == 1:
            tmp_cddi_def_arr[cddi.jdbckey.lower()] = cddi.jdbcval
            tmp_cddi_def_name_arr[cddi.jdbckey.lower()] = cddi.jdbckey
        elif cddi.jdbctype == 2:
            tmp_cddi_cut_arr[cddi.jdbckey.lower()] = cddi.jdbcval
            tmp_cddi_cut_name_arr[cddi.jdbckey.lower()] = cddi.jdbckey
    if '' in test_arry1:
        test_arry1.remove('')
    for i in test_arry1:
        if '#' not in i.strip().split('=', 1)[0] and '=' in i:
            tmp1 = i.split('=', 1)
            if tmp1[0].lower() == jdbc_url_key_name:
                tmp_arr.append("%s=%s" % (jdbc_url_key_name, tmp1[1]))
            elif tmp1[0].lower() == jdbc_username_key_name:
                tmp_arr.append("%s=%s" % (jdbc_username_key_name, tmp1[1]))
            elif 'password' in tmp1[0].lower():
                tmp_arr.append("%s=%s" % (jdbc_password_key_name, '******'))
            elif tmp1[0].lower() in tmp_cddi_def_arr.keys():
                tmp_arr.append("%s=%s" % (tmp1[0], tmp_cddi_def_arr[tmp1[0].lower()]))
                tmp_cddi_def_arr.pop(tmp1[0].lower())
            elif tmp1[0].lower() in tmp_cddi_cut_arr.keys():
                tmp_arr.append("%s=%s" % (tmp1[0], tmp1[1]))
                tmp_cddi_cut_arr.pop(tmp1[0].lower())
    for tcda_key in tmp_cddi_def_arr:
        tmp_arr.append("%s=%s" % (tmp_cddi_def_name_arr[tcda_key], tmp_cddi_def_arr[tcda_key]))
    for tcca_key in tmp_cddi_cut_arr:
        tmp_arr.append("%s=%s" % (tmp_cddi_cut_name_arr[tcca_key], tmp_cddi_cut_arr[tcca_key]))
    tmp_content = "\n".join(tmp_arr)
    message = 0
    if action == 'add':
        ConfigInfoTmp.objects.create(configinfo_id=configinfo_id, content=tmp_content)
        ConfigInfo.objects.filter(id=configinfo_id).update(config_type=3)
    elif action == 'update':
        ConfigInfoTmp.objects.filter(configinfo_id=configinfo_id).update(content=tmp_content)
        ConfigInfo.objects.filter(id=configinfo_id).update(config_type=3)
    return message


@api_view(['GET', 'POST'])
@permission_classes((AllowAny,))
def configpull(request):
    if request.method == 'POST':
        return getProbeRsp(request)
    elif request.method == 'GET':
        return getConfigInfoRsp(request)
    else:
        return Response({"message": 'Unsupported http method'})


def isChangedDataId(md5, dataid, groupid, env, ycc_code, architecture_name):
    idc = 1
    groupid_no_idc = groupid
    if ycc_code and architecture_name:
        room_obj = Room.objects.filter(ycc_code=ycc_code, architecture_name=architecture_name).first()
        if room_obj is None:
            room_obj = Room.objects.filter(ycc_code=ycc_code, parent__architecture_name=architecture_name).first()
            if room_obj is not None:
                idc = room_obj.id
        else:
            idc = room_obj.id
    else:
        if groupid.lower().endswith('_jq'):
            idc = 4
            groupid_no_idc = groupid.replace('_jq', '')
        if groupid.lower().endswith('_jq-shopping_process'):
            idc = 10
            groupid_no_idc = groupid.replace('_jq-shopping_process', '')
        # for special group such as yihaodian_common_jq_ycache_nh
        elif groupid.lower().count('_jq') > 0:
            idc = 4
        elif groupid.lower().endswith('_idc_mc'):
            idc = 5
            groupid_no_idc = groupid.replace('_idc_mc', '')
        elif groupid.lower().endswith('_sam'):
            idc = 6
            groupid_no_idc = groupid.replace('_sam', '')
        elif groupid.lower().endswith('_idc_mc@nh'):
            idc = 12
            groupid_no_idc = groupid.replace('_idc_mc@nh', '')
        elif groupid.lower().endswith('_idc_mc@jq'):
            idc = 13
            groupid_no_idc = groupid.replace('_idc_mc@jq', '')
    if env == 'test':
        env = 'base'
    cache_dataid_md5_key = 'ycc.%d.%s.%s.%s.md5' % (idc, env, groupid_no_idc, dataid)
    try:
        cache_dataid_md5 = cache.get(cache_dataid_md5_key)
    except ConnectionError:
        cache_dataid_md5 = None
    except TimeoutError:
        cache_dataid_md5 = None
    if cache_dataid_md5 is not None and cache_dataid_md5 == md5:
        return 0
    return 1


def getProbeRsp(request):
    probeReq = request.POST.get("Probe-Modify-Request")
    ycc_code = request.QUERY_PARAMS.get("zone")
    architecture_name = request.QUERY_PARAMS.get("idc")
    probeRsp = str('')
    LINE_SEPARATOR = '\001'
    FIELD_SEPARATOR = '\002'
    configinfoItems = probeReq.split(LINE_SEPARATOR)

    if len(configinfoItems) > 0:
        config_list = []
        for item in configinfoItems:
            fields = item.split(FIELD_SEPARATOR)
            filedslen = len(fields)
            if filedslen > 1:
                    # defaultlly dataid is changed, we only check it for probe string with env
                changed = True
                dataid = fields[0]
                groupid = fields[1]
                config_list.append({'group_id': groupid, 'data_id': dataid})
                if filedslen > 3:
                    md5 = fields[2]
                    env = fields[3]
                    changed = not CATCH_REDIS or isChangedDataId(md5, dataid, groupid, env, ycc_code, architecture_name) == 1
                if changed:
                    probeRsp = probeRsp + dataid
                    probeRsp += FIELD_SEPARATOR
                    probeRsp += groupid
                    probeRsp += LINE_SEPARATOR
        if random.randint(0, 19) == 1:
            if 'HTTP_X_FORWARDED_FOR' in request.META:
                client_ip = request.META['HTTP_X_FORWARDED_FOR']
                client_ip = client_ip.split(",")[0]
            else:
                client_ip = request.META['REMOTE_ADDR']
            amqp = Pika(task='ycc.tasks.config_post_info', args=[client_ip, config_list])
            amqp.basic_publish()

    response = HttpResponse()
    response.status_code = 200
    response['Probe-Modify-Response'] = probeRsp
    response['Pragma'] = 'no-cache'
    response['Expires'] = 0
    response['Cache-Control'] = 'no-cache,no-store'
    response.write(probeRsp)
    return response



def getConfigInfoRsp(request):
    headermd5 = request.META.get("HTTP_CONTENT_MD5", None)
    # headermd5 = '7b70fce7ff737a21a62078f2abf901bf'
    dataid = request.QUERY_PARAMS.get("dataId", None)
    groupidInReq = request.QUERY_PARAMS.get("group", None)
    env = request.QUERY_PARAMS.get("env")
    ycc_code = request.QUERY_PARAMS.get("zone")
    architecture_name = request.QUERY_PARAMS.get("idc")
    if dataid is None or groupidInReq is None or env is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": 'params wrong!'})
    idc = 1
    groupid = groupidInReq
    if ycc_code and architecture_name:
        room_obj = Room.objects.filter(ycc_code=ycc_code, architecture_name=architecture_name).first()
        if room_obj is None:
            room_obj = Room.objects.filter(ycc_code=ycc_code, parent__architecture_name=architecture_name).first()
            if room_obj is None:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": 'zone or idc error!'})
        idc = room_obj.id
    else:
        if groupidInReq.lower().endswith('_jq'):
            idc = 4
            groupid = groupidInReq.replace('_jq', '')
        elif groupidInReq.lower().endswith('_jq-shopping_process'):
            idc = 10
            groupid = groupidInReq.replace('_jq-shopping_process', '')
        # for special group such as yihaodian_common_jq_ycache_nh
        elif groupidInReq.lower().count('_jq') > 0:
            idc = 4
        elif groupidInReq.lower().endswith('_idc_mc'):
            idc = 5
            groupid = groupidInReq.replace('_idc_mc', '')
        elif groupidInReq.lower().endswith('_sam'):
            idc = 6
            groupid = groupidInReq.replace('_sam', '')
        elif groupidInReq.lower().endswith('_idc_mc@nh'):
            idc = 12
            groupid = groupidInReq.replace('_idc_mc@nh', '')
        elif groupidInReq.lower().endswith('_idc_mc@jq'):
            idc = 13
            groupid = groupidInReq.replace('_idc_mc@jq', '')

    response = HttpResponse()
    response['Content-Type'] = 'text/html;charset=UTF-8'
    group_status = 0
    if env == 'test':
        env = 'base'
    elif env == 'production':
        group_status = 4
        try:
            reqip = request.META['HTTP_X_FORWARDED_FOR']
        except KeyError:
            reqip = None
        if reqip == None:
            reqip = ''

        if CATCH_REDIS:
            cache_gray_key = 'ycc.gray.list'
            try:
                cache_gray_value = cache.get(cache_gray_key)
            except ConnectionError:
                cache_gray_value = None
            except TimeoutError:
                cache_gray_value = None

            if cache_gray_value is not None:
                if reqip in cache_gray_value:
                    response.status_code = 304
                    response['Content-MD5'] = headermd5
                    return response
            else:
                tmp_list = []
                gray_list = GrayReleaseBlackip.objects.all()
                for item in gray_list:
                    tmp_list.append(item.ip)
                try:
                    cache.set(cache_gray_key, tmp_list)
                except ConnectionError:
                    pass
                if reqip in tmp_list:
                    response.status_code = 304
                    response['Content-MD5'] = headermd5
                    return response
        else:
            if GrayReleaseBlackip.objects.filter(ip=reqip).exists():
                response.status_code = 304
                response['Content-MD5'] = headermd5
                return response

    cache_dataid_md5_key = None
    if CATCH_REDIS:
        cache_dataid_md5_key = 'ycc.%d.%s.%s.%s.md5' % (idc, env, groupid, dataid)
        try:
            cache_dataid_md5 = cache.get(cache_dataid_md5_key)
        except ConnectionError:
            cache_dataid_md5 = None
        except TimeoutError:
            cache_dataid_md5 = None

        if cache_dataid_md5 is not None and cache_dataid_md5 == headermd5:
            response.status_code = 304
            response['Content-MD5'] = headermd5
            return response
        elif cache_dataid_md5 == -1:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'group_status_id is not exists!'})
        elif cache_dataid_md5 == -2:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'group_id is not exists!'})
        elif cache_dataid_md5 == -3:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={"detail": 'this group_id has not just one record.'})
        elif cache_dataid_md5 == -4:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'data_id is not exists!'})
        elif cache_dataid_md5 == -5:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={"detail": 'this data_id has not just one record.'})

    try:
        config_group = ConfigGroup.objects.get(idc=idc, group_id=groupid, status=1)
        group_status_id = ConfigGroupStatus.objects.get(group=config_group, status=group_status)
        configinfo = ConfigInfo.objects.get(data_id=dataid, group_status_id=group_status_id, env__name=env)
    except ConfigGroupStatus.DoesNotExist:
        cache_set(cache_dataid_md5_key, -1)
        return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'group_status_id is not exists!'})
    except ConfigGroup.DoesNotExist:
        cache_set(cache_dataid_md5_key, -2)
        return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'group_id is not exists!'})
    except ConfigGroup.MultipleObjectsReturned:
        cache_set(cache_dataid_md5_key, -3)
        return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": 'this group_id has not just one record.'})
    except ConfigInfo.DoesNotExist:
        cache_set(cache_dataid_md5_key, -4)
        return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": 'data_id is not exists!'})
    except ConfigInfo.MultipleObjectsReturned:
        cache_set(cache_dataid_md5_key, -5)
        return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": 'this data_id has not just one record.'})

    if configinfo.content_md5 == headermd5:
        response.status_code = 304
        response['Content-MD5'] = configinfo.content_md5
    else:
        response.status_code = 200
        response['Content-MD5'] = configinfo.content_md5
        response['Pragma'] = 'no-cache'
        response['Expires'] = 0
        response['Cache-Control'] = 'no-cache,no-store'
        response[
            'Last-Modified'] = configinfo.modified_time if configinfo.modified_time is not None else configinfo.created_time
        response.write(configinfo.content)
    if CATCH_REDIS:
        try:
            cache.set(cache_dataid_md5_key, configinfo.content_md5)
        except ConnectionError:
            pass
    return response


@api_view(['GET'])
@permission_classes((AllowAny,))
def exportGroupData(request):
    groupid = request.QUERY_PARAMS.get('group', None)
    idc = request.QUERY_PARAMS.get('idc', None)
    env = request.QUERY_PARAMS.get('env', None)
    version = int(request.QUERY_PARAMS.get('version', 0))
    if groupid == None or idc == None or env == None:
        raise YAPIException('少了参数group/idc/env')
    if env == 'test':
        env = 'base'
    srcgroupstatus = ConfigGroupStatus.objects.get(group__group_id=groupid,
                                                   group__idc__id=idc,
                                                   version=version)
    configInfos = ConfigInfo.objects.filter(group_status=srcgroupstatus, env__name=env)
    if not configInfos.exists():
        raise YAPIException('GROUP_IDC指定环境没有配置文件。')
    temp = tempfile.TemporaryFile()
    archive = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
    # name = groupid + '_' + env + '_' + str(int(time.time()))
    name = groupid + '_' + env + '_' + stamp2str(time.time(), '%Y%m%d%H%M%S')
    path = name + '/'
    os.mkdir(path)
    for c in configInfos:
        filename = path + c.data_id
        file = open(filename, 'w')
        file.write(hidepwd(env, c.content))
        file.close()
        archive.write(filename)
    archive.close()
    wrapper = FileWrapper(temp)
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=' + name + '.zip'
    response['Content-Length'] = temp.tell()
    temp.seek(0)
    shutil.rmtree(path, True)
    return response


@api_view(['GET'])
@permission_classes((AllowAny,))
def serverlistpull(request):
    response = HttpResponse()
    path = os.getcwd() + '/ycc/ycc'
    response.write(open(path).read())
    return response


@api_view(['GET'])
@permission_classes((AllowAny,))
def clientackpull(request):
    response = HttpResponse()
    path = os.getcwd() + '/ycc/client.ack'
    response.write(open(path).read())
    return response


# only for test cmp
@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def cmpconfiginfos(request):
    group = int(request.QUERY_PARAMS['group'])
    env = request.QUERY_PARAMS['env']
    groupstatus = ConfigGroupStatus.objects.get(group=group, version=0, status=0)
    configInfos = ConfigInfo.objects.filter(group_status=groupstatus)
    srcConfigInfos = configInfos.filter(env=env)
    envs = ConfigEnv.objects.all()
    resultsDic = {}
    configInfoDic = {}
    for e in envs:
        configInfoDic[e.id] = {}
    for configInfo in configInfos:
        configInfoDic[envs.get(name=configInfo.env).id][configInfo.data_id] = configInfo.content_md5
    for srcConfigInfo in srcConfigInfos:
        dataid = srcConfigInfo.data_id
        resultsDic[srcConfigInfo.data_id] = {}
        for e2 in envs:
            if e2.id == envs.get(name=srcConfigInfo.env):
                cmpres = 0
            else:
                cmpMd5 = None
                if configInfoDic[e2.id].has_key(dataid):
                    cmpMd5 = configInfoDic[e2.id].get(dataid)
                if cmpMd5 == None:
                    cmpres = 2
                else:
                    if cmpMd5 != srcConfigInfo.content_md5:
                        cmpres = 1
                    else:
                        cmpres = 0
                    del configInfoDic[e2.id][dataid]
            resultsDic[dataid]['data_id'] = dataid
            resultsDic[dataid][e2.id] = cmpres
    for e3 in envs:
        for cdataid in configInfoDic[e3.id]:
            if not resultsDic.has_key(cdataid):
                resultsDic[cdataid] = {}
            resultsDic[cdataid]['data_id'] = cdataid
            resultsDic[cdataid][e3.id] = 3
    data = {}
    data['count'] = len(resultsDic)
    data['results'] = resultsDic.values()
    return Response(status=status.HTTP_200_OK, data=data)


def tridentcmpconfiginfos_cmpimpl(resultsDic, curconfiginfos, cmpgroupstatus, env):
    cmpconfigInfoDic = {}
    if cmpgroupstatus != None:
        cmpconfiginfos = ConfigInfo.objects.filter(group_status=cmpgroupstatus, env=env)
        if cmpconfiginfos.exists():
            for pc in cmpconfiginfos:
                cmpconfigInfoDic[pc.data_id] = {}
                cmpconfigInfoDic[pc.data_id]['content'] = pc.content
                cmpconfigInfoDic[pc.data_id]['md5'] = pc.content_md5
    for cc in curconfiginfos:
        dataid = cc.data_id
        # resultsDic[dataid] = {}
        pccontent = ''
        pcmd5 = None
        if cmpconfigInfoDic.has_key(dataid):
            pccontent = cmpconfigInfoDic[dataid]['content']
            pcmd5 = cmpconfigInfoDic[dataid]['md5']
        if pcmd5 == None:
            cmpres = 2
            cmpcolor = 'green'
        else:
            if pcmd5 != cc.content_md5:
                cmpres = 1
                cmpcolor = 'blue'
            else:
                cmpres = 0
                cmpcolor = 'gray'
            del cmpconfigInfoDic[dataid]
        if cmpres == 0:
            continue
        resultsDic[dataid] = {}
        resultsDic[dataid]['data_id'] = dataid
        resultsDic[dataid]['cmpres'] = cmpres
        resultsDic[dataid]['cmpcolor'] = cmpcolor
        resultsDic[dataid]['cur_content'] = hidepwd('production', cc.content)
        resultsDic[dataid]['cmp_content'] = hidepwd('production', pccontent)
    for pcdataid in cmpconfigInfoDic:
        if not resultsDic.has_key(pcdataid):
            resultsDic[pcdataid] = {}
        resultsDic[pcdataid]['data_id'] = pcdataid
        resultsDic[pcdataid]['cmpres'] = 3
        resultsDic[pcdataid]['cmpcolor'] = 'red'
        resultsDic[pcdataid]['cur_content'] = None
        resultsDic[pcdataid]['cmp_content'] = hidepwd('production', cmpconfigInfoDic[pcdataid]['content'])


# only for trident pro commit/approve/publish
@api_view(['GET'])
@permission_classes((AllowAny,))
def tridentcmpconfiginfos(request):
    env = request.QUERY_PARAMS['env']
    pool = request.QUERY_PARAMS['pool']
    idc_ycc_code = request.QUERY_PARAMS['idc']
    curstatus = int(request.QUERY_PARAMS['curstatus'])
    cmpstatus = -1
    if env == 'staging':
        env = 6
        cmpstatus = 0
    elif env == 'production':
        env = 7
        cmpstatus = 4
    else:
        raise YAPIException('bad env')
    group_id = pool.replace('/', '_')
    group = ConfigGroup.objects.filter(group_id=group_id, idc__ycc_code=idc_ycc_code, status=1)
    if not group.exists():
        raise YAPIException('bad group or idc')
    group = group[0]
    groupstatus = ConfigGroupStatus.objects.filter(group=group)
    curgroupstatus = groupstatus.filter(status=curstatus)
    if curstatus == 5:
        maxversion = curgroupstatus.aggregate(Max('version'))['version__max']
        curgroupstatus = curgroupstatus.filter(version=maxversion)
    if not curgroupstatus.exists():
        raise YAPIException('bad curstatus')
    curgroupstatus = curgroupstatus[0]
    cmpgroupstatus = groupstatus.filter(status=cmpstatus)
    cmpgroupstatus = cmpgroupstatus[0] if cmpgroupstatus.exists() else None

    curconfiginfos = ConfigInfo.objects.filter(group_status=curgroupstatus, env=7)
    cmpResultsDic = {}
    tridentcmpconfiginfos_cmpimpl(cmpResultsDic, curconfiginfos, cmpgroupstatus, env)
    resultsDicList = sorted(cmpResultsDic.values(), key=lambda s: s['cmpres'], reverse=True)
    data = {}
    data['count'] = len(cmpResultsDic)
    data['results'] = resultsDicList
    return Response(status=status.HTTP_200_OK, data=data)


# only for pro commit/approve/publish
@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def procmpconfiginfos(request):
    group = request.QUERY_PARAMS['group']
    curstatus = int(request.QUERY_PARAMS['curstatus'])
    groupstatus = ConfigGroupStatus.objects.filter(group=group)
    curgroupstatus = groupstatus.filter(status=curstatus)
    if curstatus == 5:
        maxversion = curgroupstatus.aggregate(Max('version'))['version__max']
        curgroupstatus = curgroupstatus.filter(version=maxversion)
    # if not curgroupstatus.exists():
    #     raise YAPIException('The group has no groupstatus or dataid')
    curgroupstatus = curgroupstatus[0]
    publishedgroupstatus = None
    if groupstatus.filter(status=4).exists():
        publishedgroupstatus = groupstatus.filter(status=4)[0]
    # 7 means production env
    curconfiginfos = ConfigInfo.objects.filter(group_status=curgroupstatus, env=7)
    publishedconfigInfoDic = {}
    resultsDic = {}
    if publishedgroupstatus != None:
        # 7 means production env
        publishedconfiginfos = ConfigInfo.objects.filter(group_status=publishedgroupstatus, env=7)
        if publishedconfiginfos.exists():
            for pc in publishedconfiginfos:
                publishedconfigInfoDic[pc.data_id] = pc.content_md5
    for cc in curconfiginfos:
        dataid = cc.data_id
        resultsDic[dataid] = {}
        pcmd5 = None
        if publishedconfigInfoDic.has_key(dataid):
            pcmd5 = publishedconfigInfoDic.get(dataid)
        if pcmd5 == None:
            cmpres = 2
            cmpcolor = 'green'
        else:
            if pcmd5 != cc.content_md5:
                cmpres = 1
                cmpcolor = 'blue'
            else:
                cmpres = 0
                cmpcolor = 'gray'
            del publishedconfigInfoDic[dataid]
        resultsDic[dataid]['data_id'] = dataid
        resultsDic[dataid]['cmpres'] = cmpres
        resultsDic[dataid]['cmpcolor'] = cmpcolor
    for pcdataid in publishedconfigInfoDic:
        if not resultsDic.has_key(pcdataid):
            resultsDic[pcdataid] = {}
        resultsDic[pcdataid]['data_id'] = pcdataid
        resultsDic[pcdataid]['cmpres'] = 3
        resultsDic[pcdataid]['cmpcolor'] = 'red'
    resultsDicList = sorted(resultsDic.values(), key=lambda s: s['cmpres'], reverse=True)
    data = {}
    data['count'] = len(resultsDic)
    data['results'] = resultsDicList
    return Response(status=status.HTTP_200_OK, data=data)


class OldGroupList(generics.ListAPIView):
    """
    YCC配置组列表/新增.

    输入参数：

    输出参数：

    * group_id                    -   PK
    * pool                        -   POOLID
    * idc                         -   IDC
    """
    queryset = OldConfigGroup.objects.all()
    serializer_class = OldConfigGroupSerializer
    permission_classes = (IsAuthenticated,)


# noinspection PyPackageRequirements
@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def copyGroupData(request):
    srcgroup = int(request.QUERY_PARAMS['srcgroup'])
    srcenv = request.QUERY_PARAMS['srcenv']
    srcver = int(request.QUERY_PARAMS['srcver'])
    dstgroup = int(request.QUERY_PARAMS['dstgroup'])
    dstenv = request.QUERY_PARAMS['dstenv']
    srcgroupstatus = ConfigGroupStatus.objects.get(group=srcgroup,
                                                   version=srcver)
    srcConfigInfos = ConfigInfo.objects.filter(group_status=srcgroupstatus, env=srcenv)
    if not srcConfigInfos.exists():
        raise YAPIException('源GROUP_IDC指定环境没有配置文件。')
    dstgroupstatus = ConfigGroupStatus.objects.get(group=dstgroup,
                                                   version=0,
                                                   status=0)
    oldConfigInfos = ConfigInfo.objects.filter(group_status=dstgroupstatus, env=dstenv)
    if oldConfigInfos.exists():
        oldConfigInfos.delete()
    configInfo2Create = []
    configInfo2CreateDic = {}
    for srcConfigInfo in srcConfigInfos:
        dataidname = srcConfigInfo.data_id
        configInfo2Create.append(ConfigInfo(data_id=dataidname, group_status=dstgroupstatus, env_id=dstenv,
                                            content=srcConfigInfo.content, content_md5=srcConfigInfo.content_md5,
                                            created_time=int(time.time()), modified_time=0,
                                            created_by=srcConfigInfo.created_by, modified_by='', remark='',
                                            file_type=srcConfigInfo.file_type, cmp=0, config_type=1))
        configInfo2CreateDic[dataidname] = dataidname
    ConfigInfo.objects.bulk_create(configInfo2Create)
    dataids = ' '.join(configInfo2CreateDic.keys())
    dataidnum = len(configInfo2CreateDic.keys())
    return Response(status=status.HTTP_200_OK, data={'result': True, 'dataids': dataids, 'dataidnum': dataidnum})


@api_view(['POST'])
@permission_classes((YccCommitPermission,))
def copy_group_data_v2(request):
    src_group = request.POST['src_group']
    src_env = request.POST['src_env']
    src_version = request.POST['src_version']
    src_data_partial = request.POST['src_data_partial']
    src_data_id_id_list = request.POST['src_data_id_id_list']
    dst_group = request.POST['dst_group']
    dst_env = request.POST['dst_env']
    src_group_status = ConfigGroupStatus.objects.get(group=src_group, version=src_version)
    dst_group_status = ConfigGroupStatus.objects.get(group=dst_group, version=0)
    src_config_info_filters = {
        'id__in': json.loads(src_data_id_id_list)
    } if json.loads(src_data_partial) else {
        'group_status': src_group_status,
        'env': src_env
    }
    src_config_info_queryset = ConfigInfo.objects.filter(**src_config_info_filters)
    if src_version != '0' and src_config_info_queryset.exclude(config_type=1).count() > 0:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'result': '源文件包含非编辑版本的DB配置文件，复制失败，请选择非DB配置文件进行复制'})
    dst_config_info_filters = {
        'group_status': dst_group_status,
        'env': dst_env,
    }
    if json.loads(src_data_partial):
        dst_config_info_filters['data_id__in'] = [obj.data_id for obj in src_config_info_queryset]
    ConfigInfo.objects.filter(**dst_config_info_filters).delete()
    # dst_config_info_list = []
    for obj in src_config_info_queryset:
        if obj.config_type == 2:
            src_db_config_info_obj = ConfigDbConfiginfo.objects.filter(config_info_id=obj.id).first()
            src_db_kv_custom_queryset = ConfigDbKvCustom.objects.filter(configinfo_id=obj.id)
            if src_db_config_info_obj is None or src_db_kv_custom_queryset.count() == 0:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'result': 'error occurred when copying %s' % obj.data_id})
        dst_config_info_obj = ConfigInfo.objects.create(
            data_id=obj.data_id,
            group_status=dst_group_status,
            env_id=dst_env,
            content=obj.content,
            content_md5=obj.content_md5,
            created_time=int(time.time()),
            modified_time=0,
            created_by=request.user.username,
            file_type=obj.file_type,
            cmp=0,
            config_type=obj.config_type
        )
        if obj.config_type == 2:
            ConfigDbConfiginfo.objects.create(
                config_info_id=dst_config_info_obj.id,
                config_db_instance_id=src_db_config_info_obj.config_db_instance_id
            )
            for src_db_kv_custom_obj in src_db_kv_custom_queryset:
                ConfigDbKvCustom.objects.create(
                    configinfo_id=dst_config_info_obj.id,
                    dbtype=src_db_kv_custom_obj.dbtype,
                    jdbckey=src_db_kv_custom_obj.jdbckey,
                    jdbcval=src_db_kv_custom_obj.jdbcval,
                    jdbctype=src_db_kv_custom_obj.jdbctype
                )
    # ConfigInfo.objects.bulk_create(dst_config_info_list)
    return Response(status=status.HTTP_200_OK, data={'result': True})


@api_view(['POST'])
@permission_classes((YccCommitPermission,))
def copy_group_data_v3(request):
    src_group_id = request.POST['src_group_id']
    src_data_partial = json.loads(request.POST['src_data_partial'])
    src_data_id_list = json.loads(request.POST['src_data_id_list'])
    dst_group_id = request.POST['dst_group_id']
    for src_config_group_obj in ConfigGroup.objects.filter(group_id=src_group_id, status=1):
        dst_config_group_obj = ConfigGroup.objects.filter(group_id=dst_group_id, status=1, idc=src_config_group_obj.idc).first()
        if dst_config_group_obj is None:
            continue
        src_group_status = ConfigGroupStatus.objects.get(group=src_config_group_obj, version=0, status=0)
        dst_group_status = ConfigGroupStatus.objects.get(group=dst_config_group_obj, version=0, status=0)
        src_config_info_filters = {'group_status': src_group_status}
        dst_config_info_filters = {'group_status': dst_group_status}
        if src_data_partial:
            src_config_info_filters['data_id__in'] = src_data_id_list
            dst_config_info_filters['data_id__in'] = src_data_id_list
        ConfigInfo.objects.filter(**dst_config_info_filters).delete()
        for obj in ConfigInfo.objects.filter(**src_config_info_filters):
            if obj.config_type == 2:
                src_db_config_info_obj = ConfigDbConfiginfo.objects.filter(config_info_id=obj.id).first()
                src_db_kv_custom_queryset = ConfigDbKvCustom.objects.filter(configinfo_id=obj.id)
                if src_db_config_info_obj is None or src_db_kv_custom_queryset.count() == 0:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data={'result': 'error occurred when copying %s' % obj.data_id})
            dst_config_info_obj = ConfigInfo.objects.create(
                data_id=obj.data_id,
                group_status=dst_group_status,
                env_id=obj.env.id,
                content=obj.content,
                content_md5=obj.content_md5,
                created_time=int(time.time()),
                modified_time=0,
                created_by=request.user.username,
                file_type=obj.file_type,
                cmp=0,
                config_type=obj.config_type
            )
            if obj.config_type == 2:
                ConfigDbConfiginfo.objects.create(
                    config_info_id=dst_config_info_obj.id,
                    config_db_instance_id=src_db_config_info_obj.config_db_instance_id
                )
                for src_db_kv_custom_obj in src_db_kv_custom_queryset:
                    ConfigDbKvCustom.objects.create(
                        configinfo_id=dst_config_info_obj.id,
                        dbtype=src_db_kv_custom_obj.dbtype,
                        jdbckey=src_db_kv_custom_obj.jdbckey,
                        jdbcval=src_db_kv_custom_obj.jdbcval,
                        jdbctype=src_db_kv_custom_obj.jdbctype
                    )
    dst_config_info_queryset = ConfigInfo.objects.filter(env=7, group_status__version=0, group_status__status=0,
                                                         group_status__group__group_id=dst_group_id,
                                                         group_status__group__idc=1, group_status__group__status=1)
    dst_data_id_list = [dst_config_info_obj.data_id for dst_config_info_obj in dst_config_info_queryset]
    for dst_data_id in dst_data_id_list:
        config_info_queryset = ConfigInfo.objects.filter(data_id=dst_data_id, group_status__version=0,
                                                         group_status__status=0,
                                                         group_status__group__group_id=dst_group_id,
                                                         group_status__group__status=1)
        same = 1 if len(set([config_info_obj.content_md5 for config_info_obj in config_info_queryset])) == 1 else 0
        obj, created = ConfiginfoCmp.objects.get_or_create(group_id=dst_group_id, data_id=dst_data_id, defaults={
            'cmp': same
        })
        if not created:
            obj.cmp = same
            obj.save()
    ConfiginfoCmp.objects.filter(group_id=dst_group_id).exclude(data_id__in=dst_data_id_list).delete()
    return Response(status=status.HTTP_200_OK, data={'result': True})


def isSaPermission(request):
    if request.user is None:
        return False
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    return True if YCC_GROUP_ID in group_id_list else False


class ProConfigInfoListV2(generics.ListAPIView):
    """
    production YCC配置文件查询

    输入参数：

    输出参数：

    * id                    -   PK
    * data_id               -   配置文件
    * groupid_id            -   配置组
    * env                   -   环境
    * content               -   配置文件内容
    * content_md5           -   配置文件内容MD5
    * created_time          -   配置文件创建时间
    * modified_time         -   配置文件修改时间
    * created_by            -   配置文件创建人
    * updated_by            -   配置文件修改人
    * remark                -   配置文件说明
    * file_type             -   配置文件类型
    * cmp                   -   配置文件staging和production是否一致，0表示一致
    * config_type           -   配置文件类型，1表示普通配置文件，2表示DB配置文件
    """
    queryset = ConfigInfo.objects.filter(group_status__status__in=[0, 1, 2, 4, 5, 6]).order_by('-id')
    # serializer_class = ProConfigInfoSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    # filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('data_id', 'content')
    filter_fields = (
        'group_status__group__idc__id', 'group_status__group__group_id', 'group_status__status',
        'group_status__version', 'env')
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        # if isSaPermission(self.request):
        #     return ConfigInfoSerializer
        # return ProConfigInfoSerializer
        return ConfigInfoSerializer if self.request.user.is_superuser else ProConfigInfoSerializer


class ConfigInfoListV2(generics.ListCreateAPIView):
    """
    YCC配置文件f表/新增

    输入参数：

    输出参数：

    * id                    -   PK
    * data_id               -   配置文件
    * groupid_id            -   配置组
    * env                   -   环境
    * content               -   配置文件内容
    * content_md5           -   配置文件内容MD5
    * created_time          -   配置文件创建时间
    * modified_time         -   配置文件修改时间
    * created_by            -   配置文件创建人
    * updated_by            -   配置文件修改人
    * remark                -   配置文件说明
    * file_type             -   配置文件类型
    * cmp                   -   配置文件staging和production是否一致，0表示一致
    * config_type           -   配置文件类型，1表示普通配置文件，2表示DB配置文件
    """
    queryset = ConfigInfo.objects.filter(group_status__status=0, group_status__group__status=1).order_by('-id')
    serializer_class = ConfigInfoSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, ycc_filters.ConfigInfoFilterBackend)
    # filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    search_fields = ('data_id', 'content')
    filter_fields = ('group_status__group__idc__id', 'env', 'group_status__group__group_id', 'group_status__group__id',
                     'group_status__status', 'group_status__version', 'group_status__group__app_id')
    permission_classes = (YccCommitPermission,)

    def get_serializer_class(self):
        # if YCC_ENV == 'production' and not isSaPermission(self.request) and self.request.method == 'GET':
        #     return ProConfigInfoSerializer
        # return ConfigInfoSerializer
        return ProConfigInfoSerializer if YCC_ENV == 'production' and not self.request.user.is_superuser and self.request.method == 'GET' else ConfigInfoSerializer

    def perform_create(self, serializer):
        # if not isSaPermission(self.request):
        #     raise YAPIException('You do not have permission to perform this action.')
        data_id = serializer.validated_data.get('data_id')
        group_status_id = serializer.validated_data.get('group_status')
        user = self.request.user.username
        db_instance_id = self.request.DATA.get('db_instance_id', None)
        config_type = self.request.DATA.get('config_type')
        env = serializer.validated_data.get('env')
        jdbckv_string = self.request.DATA.get('jdbckv_string')
        db_type = self.request.DATA.get('db_type', None)
        group_name = self.request.DATA.get('group_name', None)
        idc_name = self.request.DATA.get('idc_name', None)
        current_time = int(time.time())
        content = ''
        content_md5 = ''
        if YCC_ENV == 'production':
            cmp = 0
        elif YCC_ENV == 'test':
            cmp = 1
        else:
            cmp = 0
        if db_instance_id is None:
            content = serializer.validated_data.get('content')
            content_md5 = md5(content)
        if YCC_ENV == 'production':
            for ds in DB_SUPPORT:
                if ds in content:
                    raise YAPIException('如果是DB配置文件请使用新建“DB配置文件”，如果不是请联系ZhangZaibin。')
        envs = ConfigEnv.objects.exclude(name='both')
        # both在staging与production中各添加
        if env.name == 'both':
            envs = envs.exclude(name='both')
        else:
            envs = envs.filter(id=env.id)

        try:
            jdbc_default_instance = ConfigDbKvDefault.objects.filter(jdbctype=1, dbtype=db_type)
        except:
            raise YAPIException('miss dbtype!')
        for item in envs:
            if ConfigInfo.objects.filter(group_status_id=group_status_id, data_id=data_id, env=item.id).exists():
                raise YAPIException('配置文件(%s)在相同配置组和相同环境(%s)中已经存在）,建议找到该配置组直接修改或上传!' % (data_id, item.name))
            ain = ConfigInfo.objects.create(
                data_id=data_id,
                group_status_id=group_status_id.id,
                env_id=item.id,
                content_md5=content_md5,
                content=content,
                created_time=current_time,
                modified_time=0,
                created_by=user,
                modified_by=user,
                cmp=cmp,
                config_type=config_type,
            )
            if db_instance_id is not None:
                ConfigDbConfiginfo.objects.get_or_create(config_info_id=ain.id, defaults={
                    'config_db_instance_id': db_instance_id
                })
                if jdbckv_string is not None:
                    line_content = []
                    content = ''
                    try:
                        confinfo = ConfigInfo.objects.get(data_id=data_id, group_status_id=group_status_id, env=item.id)
                    except:
                        raise YAPIException('错误！data_id = %s' % data_id)
                    jdbckv_arr1 = jdbckv_string.split(',,,,,,,')
                    if confinfo:
                        config_db_instance = ConfigDbInstance.objects.get(id=db_instance_id)
                        line_content.append("%s=%s" % (jdbc_username_key_name, config_db_instance.username))
                        line_content.append("%s=%s" % (jdbc_password_key_name, config_db_instance.password))
                        # 添加jdbc允许修改项
                        for arr_item in jdbckv_arr1:
                            jdbckv_arr2 = arr_item.split('^^^^^^^')
                            dbtype_string = jdbckv_arr2[0]
                            jdbckey_string = jdbckv_arr2[1]
                            jdbcval_string = jdbckv_arr2[2]
                            if 'jdbcurl' in jdbckey_string:
                                jdbckey_string = jdbc_url_key_name
                            ConfigDbKvCustom.objects.create(configinfo_id=confinfo.id, dbtype=dbtype_string,
                                                            jdbckey=jdbckey_string,
                                                            jdbcval=jdbcval_string,
                                                            jdbctype=2)
                            line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                        # 添加jdbc默认项
                        for jd_default in jdbc_default_instance:
                            ConfigDbKvCustom.objects.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                            jdbckey=jd_default.jdbckey,
                                                            jdbcval=jd_default.jdbcval,
                                                            jdbctype=1)
                            line_content.append("%s=%s" % (jd_default.jdbckey, jd_default.jdbcval))
                        content = "\n".join(line_content)
                        # 更新配置文件显示内容
                        ConfigInfo.objects.filter(id=confinfo.id).update(content=content, content_md5=md5(content))
                    else:
                        raise YAPIException('配置文件不存在!')
                else:
                    raise YAPIException('字符串为空！')
            # 变更系统
            collect_type_name = 'db_configinfo' if config_type == "2" else "configinfo"
            collect_index = '%s/%s/%s/%s' % (data_id, group_name, idc_name.lower(), item.name)
            collect({'type': collect_type_name, 'action': 'add', 'index': collect_index, 'level': 'normal',
                     'message': hidepwd(YCC_ENV, content),
                     'user': user, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})


class ConfigInfoDetailV2(generics.RetrieveUpdateDestroyAPIView):
    """
    YCC配置文件表/修改删除

    输入参数： 无

    输出参数：

    * id                    -   PK
    * data_id               -   配置文件
    * groupid_id            -   配置组
    * env                   -   环境
    """
    permission_classes = (YccCommitPermission,)
    queryset = ConfigInfo.objects.filter().order_by('-id')
    serializer_class = ConfigInfoSerializer

    def perform_update(self, serializer):
        user = self.request.user.username
        current_time = int(time.time())
        delete_dbtype_flag = 0
        delete_dbtype_name = ''
        config_type = self.request.DATA.get('config_type', None)
        content = self.request.DATA.get('content', None)
        data_id = self.request.DATA.get('data_id', None)
        env_name = self.request.DATA.get('env_name', None)
        group_status_id = serializer.validated_data.get('group_status')
        group_name = self.request.DATA.get('group_name', None)
        db_type = self.request.DATA.get('db_type', None)
        idc = self.request.DATA.get('idc', None)
        db_instance_id = self.request.DATA.get('db_instance_id', None)
        op = self.request.DATA.get('op', None)
        configinfo_id = self.request.DATA.get('editid', None)
        flag_new_pass = 0
        old_pass_arr = []
        new_pass_arr = []
        new_cont_arr = []
        old_password = '******'
        # raise YAPIException(idc)
        idc_ins = Room.objects.get(id=idc)
        collect_idc = idc_ins.name_ch

        if op == 'old_db':
            try:
                configinfo_instanace = ConfigInfo.objects.get(id=configinfo_id)
                old_pass_arr = configinfo_instanace.content.split('\n')
                for oc in old_pass_arr:

                    # if '#' not in oc and 'password' in oc:
                    if len(oc.strip()) > 0:
                        if oc.strip()[0] != '#' and 'password' in oc:
                            old_password = oc.split('=')[1]
                if content:
                    new_pass_arr = content.split('\n')
                    for ct in new_pass_arr:
                        if '#' not in ct and 'password' in ct:
                            new_cont_arr.append("%s=%s" % (ct.split('=')[0], old_password))
                            flag_new_pass += 1
                        else:
                            new_cont_arr.append(ct)
                if flag_new_pass > 1:
                    raise YAPIException('muti password key!')
                content = '\n'.join(new_cont_arr)
                content_md5 = md5(content)
            except ConfigInfo.MultipleObjectsReturned:
                raise YAPIException('muti config_instance!')
            except ConfigInfo.DoesNotExist:
                raise YAPIException('miss config_instance!')
        else:
            if config_type == "1":
                content = self.request.DATA.get('content', None)
                content_md5 = md5(content)
            else:
                db_instance_id = int(content)
                content_md5 = md5(content)
        instance = serializer.save(content=content, content_md5=content_md5, modified_time=current_time,
                                   modified_by=user)

        # It's tmp for dbupdate || can be delete.
        if op == 'old_db':
            if ConfigInfoTmp.objects.filter(configinfo_id=instance.id).exists():
                syn_dbupdate_one(instance.id, content, 'update')
            else:
                syn_dbupdate_one(instance.id, content, 'add')

        if config_type == "2":
            # ConfigDbConfiginfo.objects.filter(config_info_id=instance.id).update(
            #     config_db_instance_id=db_instance_id)
            config_db_info_insts = ConfigDbConfiginfo.objects.filter(config_info_id=instance.id)
            if config_db_info_insts.exists():
                config_db_info_insts.update(config_db_instance_id=db_instance_id)
            else:
                config_db_info_insts.create(config_info_id=instance.id, config_db_instance_id=db_instance_id)
            jdbckv_string = self.request.DATA.get('jdbckv_string')
            line_content = []
            db_default_val_dic = dict()
            db_default_key_dic = dict()
            # nodelete_dbtype_arr = []
            is_insert = False
            if jdbckv_string is not None:
                try:
                    jdbc_default_instance = ConfigDbKvDefault.objects.filter(dbtype=db_type)
                except:
                    raise YAPIException('miss dbtype!')
                for jdi in jdbc_default_instance.filter(jdbctype=1):
                    db_default_val_dic[jdi.jdbckey.lower()] = jdi.jdbcval
                    db_default_key_dic[jdi.jdbckey.lower()] = jdi.jdbckey
                env = ConfigEnv.objects.get(name=env_name)
                confinfo = ConfigInfo.objects.get(data_id=data_id, group_status_id=group_status_id, env=env.id)
                jdbckv_arr1 = jdbckv_string.split(',,,,,,,')
                if confinfo:
                    config_db_instance = ConfigDbInstance.objects.get(id=db_instance_id)
                    line_content.append("%s=%s" % (jdbc_username_key_name, config_db_instance.username))
                    line_content.append("%s=%s" % (jdbc_password_key_name, config_db_instance.password))
                    cdkc_instances = ConfigDbKvCustom.objects.filter(configinfo_id=confinfo.id)
                    for arr_item in jdbckv_arr1:
                        jdbckv_arr2 = arr_item.split('^^^^^^^')
                        dbtype_string = jdbckv_arr2[0]
                        jdbckey_string = jdbckv_arr2[1]
                        jdbcval_string = jdbckv_arr2[2]
                        if 'jdbcurl' in jdbckey_string:
                            jdbckey_string = jdbc_url_key_name
                        # 判断配置文件是否存在
                        if cdkc_instances.filter(configinfo_id=confinfo.id).exists():
                            # 判断配置文件与dbtype是否存在
                            if cdkc_instances.filter(configinfo_id=confinfo.id,
                                                     dbtype=dbtype_string).exists():
                                # 判断配置文件、dbtype、jdbckey是否存在
                                if cdkc_instances.filter(configinfo_id=confinfo.id, dbtype=dbtype_string,
                                                         jdbckey=jdbckey_string).exists():
                                    cdkc_instances.filter(configinfo_id=confinfo.id,
                                                          dbtype=dbtype_string,
                                                          jdbckey=jdbckey_string).update(
                                        jdbcval=jdbcval_string)
                                    line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                    # nodelete_dbtype_arr.append(jdbckey_string)
                                else:
                                    cdkc_instances.create(configinfo_id=confinfo.id,
                                                          dbtype=dbtype_string,
                                                          jdbckey=jdbckey_string,
                                                          jdbcval=jdbcval_string,
                                                          jdbctype=2)
                                    line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                    # nodelete_dbtype_arr.append(jdbckey_string)
                            else:
                                cdkc_instances.create(configinfo_id=confinfo.id,
                                                      dbtype=dbtype_string,
                                                      jdbckey=jdbckey_string,
                                                      jdbcval=jdbcval_string,
                                                      jdbctype=2)
                                line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                is_insert = True
                                delete_dbtype_flag = 1
                                delete_dbtype_name = jdbckv_arr2[0]
                        else:
                            cdkc_instances.create(configinfo_id=confinfo.id,
                                                      dbtype=dbtype_string,
                                                      jdbckey=jdbckey_string,
                                                      jdbcval=jdbcval_string,
                                                      jdbctype=2)
                            line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                    # true插入默认jdbc参数,false同步增加或者删除Default数据
                    if is_insert:
                        for jd_default in jdbc_default_instance.filter(jdbctype=1):
                            cdkc_instances.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                  jdbckey=jd_default.jdbckey,
                                                  jdbcval=jd_default.jdbcval,
                                                  jdbctype=1)
                            line_content.append("%s=%s" % (jd_default.jdbckey, jd_default.jdbcval))
                            # nodelete_dbtype_arr.append(jd_default.jdbckey)
                            jdbc_key_val_tmp = "%s=%s" % (jd_default.jdbckey, jd_default.jdbcval)
                            if jdbc_key_val_tmp not in line_content:
                                line_content.append(jdbc_key_val_tmp)
                    else:
                        for cdkc in cdkc_instances.filter(jdbctype=1):
                            if cdkc.jdbckey.lower() in db_default_val_dic.keys():
                                if cdkc.jdbcval != db_default_val_dic[cdkc.jdbckey.lower()]:
                                    cdkc_instances.filter(jdbckey=cdkc.jdbckey, jdbctype=1).update(
                                        jdbcval=db_default_val_dic[cdkc.jdbckey.lower()])
                                line_content.append("%s=%s" % (
                                    db_default_key_dic[cdkc.jdbckey.lower()], db_default_val_dic[cdkc.jdbckey.lower()]))
                                db_default_val_dic.pop(cdkc.jdbckey.lower())
                            else:
                                cdkc_instances.filter(jdbckey=cdkc.jdbckey, jdbctype=1).delete()
                        if db_default_val_dic:
                            for ddvd_key in db_default_val_dic:
                                cdkc_instances.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                      jdbckey=db_default_key_dic[ddvd_key],
                                                      jdbcval=db_default_val_dic[ddvd_key], jdbctype=1)
                                line_content.append(
                                    "%s=%s" % (db_default_key_dic[ddvd_key], db_default_val_dic[ddvd_key]))
                    # 变更dbtype时删除原dbtype的jdbc记录，如dbtype未修改则删除未在修改范围的jdbc记录
                    if delete_dbtype_flag > 0 and delete_dbtype_name != '':
                        cdkc_instances.exclude(
                            dbtype=delete_dbtype_name).delete()
                    # ######nodelete_dbtype_arr +++ not in line_content
                    # else:
                    #     cdkc_instances.filter(configinfo_id=confinfo.id).exclude(
                    #         jdbckey__in=nodelete_dbtype_arr).delete()
                    content = "\n".join(line_content)
                    ConfigInfo.objects.filter(id=confinfo.id).update(content=content, content_md5=md5(content))
                else:
                    raise YAPIException('配置文件不存在!')
            else:
                raise YAPIException('字符串为空！')

        # 变更系统
        collect_type_name = 'db_configinfo' if config_type == "2" else "configinfo"
        collect_index = '%s/%s/%s/%s' % (data_id, group_name, collect_idc, env_name)
        collect({'type': collect_type_name, 'action': 'edit', 'index': collect_index, 'level': 'normal',
                 'message': hidepwd(YCC_ENV, content),
                 'user': user, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
        # raise YAPIException('ycc.%d.%s.%s.%s.md5' % (idc, env_name, group_name, data_id))
        if CATCH_REDIS and env_name.lower() != 'production':
            if idc != '':
                cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (idc, env_name, group_name, data_id)
                cache.delete(cache_dataid_md5_key)
            else:
                cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (1, env_name, group_name, data_id)
                cache.delete(cache_dataid_md5_key)
                cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (4, env_name, group_name, data_id)
                cache.delete(cache_dataid_md5_key)

    def perform_destroy(self, instance):
        # if not isSaPermission(self.request):
        #     raise YAPIException('You do not have permission to perform this action.')
        rmv_id = self.request.DATA.get('configinfo_id', None)
        rmv_group = self.request.DATA.get('rmv_group', None)
        rmv_env = self.request.DATA.get('rmv_env', None)
        rmv_dataid = self.request.DATA.get('rmv_dataid', None)
        rmv_idc = self.request.DATA.get('rmv_idc', None)

        idc_ins = Room.objects.get(id=rmv_idc)
        collect_idc = idc_ins.name_ch
        try:
            configinfo_instance = ConfigInfo.objects.get(id=rmv_id)
            configinfo_instance.delete()
            ConfigDbKvCustom.objects.filter(configinfo_id=rmv_id).delete()
            ConfigDbConfiginfo.objects.filter(config_info_id=rmv_id).delete()

            # 变更系统
            collect_index = '%s/%s/%s/%s' % (rmv_dataid, rmv_group, collect_idc, rmv_env)
            collect({'type': 'configinfo', 'action': 'delete', 'index': collect_index, 'level': 'normal',
                     'message': hidepwd(YCC_ENV, configinfo_instance.content),
                     'user': self.request.user.username,
                     'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
            if CATCH_REDIS and rmv_env.lower() != 'production':
                cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (rmv_idc, rmv_env, rmv_group, rmv_dataid)
                cache.delete(cache_dataid_md5_key)
        except ConfigInfo.DoesNotExist:
            raise YAPIException("ConfigInfo is not exist!")
        except ConfigInfo.MultipleObjectsReturned:
            raise YAPIException("ConfigInfo is MultipleObjectsReturned!")


# It's tmp for dbupdate || can be delete.
@permission_classes((AllowAny,))
def ConfigInfoTmpSynUpdate(id, content):
    test_arry1 = content.split('\n')
    tmp_arr = []
    if '' in test_arry1:
        test_arry1.remove('')
    for i in test_arry1:
        if '#' not in i.strip().split('=', 1)[0] and '=' in i:
            tmp1 = []
            tmp1 = i.split('=', 1)
            tmp_arr.append("%s=%s" % (tmp1[0], tmp1[1]))
    tmp_content = "\n".join(tmp_arr)
    ConfigInfoTmp.objects.filter(configinfo_id=id).update(content=tmp_content)


@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
# @csrf_exempt
def ConfigInfoListUpload(request):
    input_name = request.DATA.get('input_name', None)
    files = request.FILES.getlist(input_name)
    group_status_upload_id = request.DATA.get('group_status_upload', None)
    group_name = request.DATA.get('group_name', None)
    env_id = request.DATA.get('env', None)
    upload_data_id = request.DATA.get('upload_data_id', None)
    op_type = request.DATA.get('op_type', None)
    euid = request.DATA.get('euid', None)
    idc = request.DATA.get('upload_idc', None)

    idc_ins = Room.objects.get(id=idc)
    collect_idc = idc_ins.name_ch
    current_time = int(time.time())
    data_id = ''
    content_arr = []
    username = request.DATA.get('username', None)

    if files:
        for f in files:
            # destination = open("C:/ZZB/Projects/assetv2/static/tmp/" + f.name, 'wb+')
            data_id = f.name
            for chunk in f.chunks():
                content_arr.append(chunk)
                # destination.write(chunk)
                # destination.close()
        # f = codecs.open('C:/ZZB/Projects/assetv2/static/tmp/' + f.name)
        # try:
        #      all_the_text = f.read()
        # finally:
        #      f.close( )
        # import mimetypes
        # mime = mimetypes.guess_type('C:/ZZB/Projects/assetv2/static/tmp/' + f.name)
        if YCC_ENV == 'production':
            cmp = 0
        elif YCC_ENV == 'test':
            cmp = 1
        else:
            cmp = 0
        content = ''.join(content_arr)
        if YCC_ENV == 'production':
            for ds in DB_SUPPORT:
                if ds in content:
                    raise YAPIException('如果是DB配置文件请使用新建“DB配置文件”，如果不是请联系ZhangZaibin。')
        fs = chardet.detect(content)
        try:
            if 'ascii' in fs['encoding'] or 'GB2312' in fs['encoding']:
                content = content.decode('gbk', 'ignore').encode('utf-8')
        except:
            content = content

        # try:
        #     # content = content.decode('gbk', 'ignore').encode('utf-8')
        #     content = content
        # except:
        #     content = content

        # content = content.decode('gbk', 'ignore').encode('utf-8')
        # content = all_the_text
        content_md5 = md5(content)
        if op_type == 'add':
            if files == '':
                raise YAPIException('请选择上传配置文件！')
            if env_id == '':
                raise YAPIException('请选择环境和配置组！')
            if group_status_upload_id == '':
                raise YAPIException('请选择环境和配置组！')

            env = ConfigEnv.objects.get(id=env_id)
            envs = ConfigEnv.objects.exclude(name='both')
            if envs is None:
                raise YAPIException('未选择环境！')
            if env.name == 'both':
                envs = envs.filter(name__in=['staging', 'production'])
            else:
                envs = envs.filter(id=env.id)
            for item in envs:
                if ConfigInfo.objects.filter(group_status_id=group_status_upload_id, data_id=data_id,
                                             env=item.id).exists():
                    raise YAPIException('配置文件(%s)在相同配置组和相同环境(%s)中已经存在）,建议找到该配置组直接修改或上传!' % (data_id, item.name))
                try:
                    ain = ConfigInfo.objects.create(
                        data_id=data_id,
                        group_status_id=group_status_upload_id,
                        env_id=item.id,
                        content_md5=content_md5,
                        content=content,
                        created_time=current_time,
                        modified_time=0,
                        created_by=username,
                        modified_by=username,
                        cmp=cmp,
                        config_type=1,
                    )
                except:
                    raise YAPIException('上传失败,文件格式不对！')
                # 变更系统
                collect_index = '%s/%s/%s/%s' % (data_id, group_name, collect_idc, item.name)
                collect({'type': 'configinfo', 'action': 'add_upload', 'index': collect_index, 'level': 'normal',
                         'message': hidepwd(YCC_ENV, content),
                         'user': username,
                         'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
            idc = 0
        elif op_type == 'edit':
            try:
                ConfigInfo.objects.filter(id=euid).update(content=content, content_md5=content_md5,
                                                          modified_time=current_time, modified_by=username)
            except ConfigInfo.DoesNotExist:
                raise YAPIException('ConfigInfo is not exists!!!')
            if CATCH_REDIS and env_id.lower() != 'production':
                if idc != '':
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        idc, env_id, group_status_upload_id, upload_data_id)
                    cache.delete(cache_dataid_md5_key)
                else:
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        1, env_id, group_status_upload_id, upload_data_id)
                    cache.delete(cache_dataid_md5_key)
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        4, env_id, group_status_upload_id, upload_data_id)
                    cache.delete(cache_dataid_md5_key)

            # 变更系统
            collect_index = '%s/%s/%s/%s' % (upload_data_id, group_status_upload_id, collect_idc, env_id)
            collect({'type': 'configinfo', 'action': 'edit_upload', 'index': collect_index, 'level': 'normal',
                     'message': hidepwd(YCC_ENV, content),
                     'user': username, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})

            # It's tmp for dbupdate || can be delete.
            if ConfigInfoTmp.objects.filter(configinfo_id=euid).exists():
                ConfigInfoTmpSynUpdate(euid, content)

    response1 = {'success': True, 'id': 1,
                 'msg': u'ycc.%s.%s.%s.%s.md5' % (idc, env_id, group_status_upload_id, upload_data_id)}
    # else:
    #     raise YAPIException('请选择上传文件！')
    #     # response1 = {'success': False, 'id': 0, 'msg': u'上传配置组文件失败!!!！'}
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


class DbUpdateList(generics.ListCreateAPIView):
    queryset = get_dbupdate_list()

    serializer_class = ConfigInfoSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('data_id', 'content')
    filter_fields = ('group_status__group__idc__id', 'env', 'group_status__group__group_id', 'group_status__group__id',
                     'group_status__status', 'group_status__version')
    permission_classes = (IsAuthenticated,)

    # def get_serializer_class(self):
    #     if YCC_ENV == 'production' and not isSaPermission(self.request) and self.request.method == 'GET':
    #         return ProConfigInfoSerializer
    #     return ConfigInfoSerializer


class DbUpdateListOne(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = ConfigInfoTmp.objects.all()
    serializer_class = ConfigInfoTmpSerializer

    def get_queryset(self):
        queryset = ConfigInfoTmp.objects.all()
        configinfoid = self.request.QUERY_PARAMS.get('configinfoid', None)
        if configinfoid is not None:
            queryset = queryset.filter(configinfo_id=configinfoid)
        else:
            queryset = ''
        return queryset


class DbUpdateDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = ConfigInfo.objects.filter().order_by('-id')
    serializer_class = ConfigInfoSerializer

    def perform_update(self, serializer):
        user = self.request.user.username
        current_time = int(time.time())
        configinfo_id = self.request.DATA.get('editid', None)
        key_val_url = self.request.DATA.get('key_val_url', None)
        # jdbc_string = self.request.DATA.get('jdbc_string', None)
        int_id = self.request.DATA.get('int_id', None)
        group_id = self.request.DATA.get('group_id', None)
        data_id = self.request.DATA.get('data_id', None)
        env_name = self.request.DATA.get('env_name', None)
        idc = self.request.DATA.get('idc', None)

        idc_ins = Room.objects.get(id=idc)
        collect_idc = idc_ins.name_ch
        # jdbc_default_arr = []
        jdbc_key_val_dict = dict()
        jdbc_key_name_dict = dict()
        flag_url = 0
        flag_pwd = 0
        flag_usr = 0

        dbtype = get_dbname(key_val_url.lower())
        try:
            jdbc_default_instance = ConfigDbKvDefault.objects.filter(jdbctype=1, dbtype=dbtype)
            for jda in jdbc_default_instance:
                # jdbc_default_arr.append(jda.jdbckey.lower())
                jdbc_key_val_dict[jda.jdbckey.lower()] = jda.jdbcval
                jdbc_key_name_dict[jda.jdbckey.lower()] = jda.jdbckey
            conf_tmp_instance = ConfigInfoTmp.objects.get(configinfo_id=configinfo_id)
            config_db_instance = ConfigDbInstance.objects.get(id=int_id)
            content = conf_tmp_instance.content if conf_tmp_instance.content else ''
            jdbc_arr = content.split('\n')
            tmp_content = []
            for item in jdbc_arr:
                if jdbc_username_key_name in item:
                    flag_usr += 1
                    if flag_usr > 1:
                        raise YAPIException('配置文件存在2个username')
                    if item.split('=', 1)[1].strip() != config_db_instance.username:
                        raise YAPIException('username与DB实例（DB标识符）不相等！')
                if jdbc_password_key_name in item:
                    flag_pwd += 1
                    if flag_pwd > 1:
                        raise YAPIException('配置文件存在2个password')
                        # if config_db_instance.password != item.split('=', 1)[1]:
                        #     raise YAPIException('jdbc.password不正确，请联系DBA！')
                if jdbc_url_key_name in item:
                    flag_url += 1
                    if flag_url > 1:
                        raise YAPIException('配置文件存在2个URL')
            if flag_url == 0:
                raise YAPIException('配置缺少jdbc.url=')
            if flag_pwd == 0:
                raise YAPIException('配置缺少jdbc.password或key不匹配！')
            if flag_usr == 0:
                raise YAPIException('配置缺少jdbc.username！')
            for item in jdbc_arr:
                if '#' not in item and item != '':
                    if '=' in item:
                        if jdbc_url_key_name in item:
                            if 'mysql' in item:
                                jdbc_url = "%s?%s" % (item.split('=', 1)[1].split('?', 1)[0],
                                                      "useUnicode=true&characterEncoding=utf-8&autoReconnect=true&autoReconnectForPools=true&failOverReadOnly=false&rewriteBatchedStatements=true&allowMultiQueries=true")
                            else:
                                jdbc_url = item.split('=', 1)[1]
                            tmp_content.append("%s=%s" % (jdbc_url_key_name, jdbc_url))
                            ConfigDbKvCustom.objects.create(configinfo_id=configinfo_id, dbtype=dbtype,
                                                            jdbckey=jdbc_url_key_name,
                                                            jdbcval=jdbc_url,
                                                            jdbctype=2)
                        elif jdbc_username_key_name in item:
                            tmp_content.append("%s=%s" % (jdbc_username_key_name, config_db_instance.username))
                        elif jdbc_password_key_name in item:
                            tmp_content.append("%s=%s" % (jdbc_password_key_name, config_db_instance.password))
                        else:
                            # jdbctype:1-默认值;2-允许修改
                            if item.split('=', 1)[0].lower() in jdbc_key_val_dict.keys():
                                jdbctype = 1
                                jdbc_key_val_dict.pop(item.split('=', 1)[0].lower())
                            else:
                                jdbctype = 2
                            tmp_content.append("%s=%s" % (item.split('=', 1)[0], item.split('=', 1)[1]))
                            ConfigDbKvCustom.objects.create(configinfo_id=configinfo_id, dbtype=dbtype,
                                                            jdbckey=item.split('=', 1)[0],
                                                            jdbcval=item.split('=', 1)[1],
                                                            jdbctype=jdbctype)
            if jdbc_key_val_dict:
                for jkvd_key in jdbc_key_val_dict:
                    tmp_content.append("%s=%s" % (jdbc_key_name_dict[jkvd_key], jdbc_key_val_dict[jkvd_key]))
            update_content = ('\n').join(tmp_content) if tmp_content else ''
            ConfigInfo.objects.filter(id=configinfo_id).update(content=update_content, config_type=2,
                                                               content_md5=md5(
                                                                   update_content), modified_time=current_time,
                                                               modified_by=user)
            ConfigDbConfiginfo.objects.get_or_create(config_info_id=configinfo_id, defaults={
                'config_db_instance_id': int_id
            })

            # 变更系统
            collect_index = '%s/%s/%s/%s' % (data_id, group_id, collect_idc, env_name)
            collect({'type': 'DB_SOA', 'action': 'edit', 'index': collect_index, 'level': 'normal',
                     'message': hidepwd(YCC_ENV, update_content),
                     'user': self.request.user.username,
                     'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
            if CATCH_REDIS and env_name.lower() != 'production':
                if idc != '':
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        idc, env_name, group_id, data_id)
                    cache.delete(cache_dataid_md5_key)
                else:
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        idc, env_name, group_id, data_id)
                    cache.delete(cache_dataid_md5_key)
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        idc, env_name, group_id, data_id)
                    cache.delete(cache_dataid_md5_key)
        except ConfigDbKvDefault.DoesNotExist:
            raise YAPIException('miss dbtype!')
        except ConfigInfoTmp.MultipleObjectsReturned:
            raise YAPIException('ConfigInfoTmp_id is MultipleObjectsReturned')
        except ConfigInfoTmp.DoesNotExist:
            raise YAPIException('ConfigInfoTmp_id is not find')
        except ConfigDbInstance.MultipleObjectsReturned:
            raise YAPIException('ConfigDbInstance_id MultipleObjectsReturned')
        except ConfigDbInstance.DoesNotExist:
            raise YAPIException('ConfigDbInstance_id is not find')


class ConfigGroupStatusListNormal(generics.ListAPIView):
    serializer_class = ConfigGroupStatusSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend, ycc_filters.ConfigGroupStatusFilterBackend)
    # filter_backends = (filters.DjangoFilterBackend,)
    # filter_fields = ('group__idc__id', )
    # queryset = ConfigGroupStatus.objects.all()

    def get_queryset(self):
        idc = self.request.QUERY_PARAMS.get('idc')
        queryset = ConfigGroupStatus.objects.filter(group__idc=idc, status=0)
        return queryset


class ConfigGroupStatusListV2(generics.ListCreateAPIView):
    serializer_class = ConfigGroupStatusSerializer
    permission_classes = (YccCommitPermission,)

    def get_queryset(self):
        # for page group management
        group = self.request.QUERY_PARAMS.get('group')
        op = self.request.QUERY_PARAMS.get('op')
        status = self.request.QUERY_PARAMS.get('status')
        # for page production configinfo detail
        if group == None:
            group_id = self.request.QUERY_PARAMS.get('group_id')
            idc = self.request.QUERY_PARAMS.get('idc')
            group = ConfigGroup.objects.filter(group_id=group_id, idc=idc, status=1)
            if group.exists():
                group = group[0]
            else:
                raise YAPIException('bad group_id or idc')
        queryset = ConfigGroupStatus.objects.filter(group=group)
        if status != None:
            queryset = queryset.filter(status=int(status))
        if op == 'rollback':
            queryset = [queryset.order_by('-version')[0]]
        return queryset

    def perform_create(self, serializer):
        group = int(self.request.DATA.get('group'))
        # raise YAPIException(group)
        configgroup = ConfigGroup.objects.get(id=group, status=1)
        # status=0 means edit status
        editconfigstatus = ConfigGroupStatus.objects.get(group=configgroup, status=0)
        # env=7 means production environment
        editconfiginfos = ConfigInfo.objects.filter(group_status=editconfigstatus, env=7)
        if not editconfiginfos.exists():
            raise YAPIException('该配置组没有配置文件。')
        maxversion = ConfigGroupStatus.objects.filter(group=group).aggregate(Max('version'))['version__max']
        maxversion = maxversion + 1
        # status=1 means commited status, 2 means approved status
        created = False
        if not ConfigGroupStatus.objects.filter(group=configgroup, status=2).exists():
            commitedconfigstatus, created = ConfigGroupStatus.objects.get_or_create(group=configgroup, status=1,
                                                                                    defaults={'version': maxversion,
                                                                                              'pre_version': 0})
        if not created:
            raise YAPIException('配置组在待审核或待发布。')
        commitedconfigInfos = []
        collect_content = []
        for ecf in editconfiginfos:
            collect_content.append(ecf.data_id)
            commitedconfigInfos.append(ConfigInfo(data_id=ecf.data_id, group_status=commitedconfigstatus,
                                                  env=ConfigEnv.objects.get(name='production'),
                                                  content=ecf.content, content_md5=ecf.content_md5,
                                                  created_time=ecf.created_time, modified_time=ecf.modified_time,
                                                  created_by=ecf.created_by, modified_by=ecf.modified_by,
                                                  remark=ecf.remark, file_type=ecf.file_type, cmp=ecf.cmp,
                                                  config_type=ecf.config_type))

        ConfigInfo.objects.bulk_create(commitedconfigInfos)
        # 变更系统
        collect_type = '应用类' if configgroup.type == 1 else '公共组建类'
        collect_index = '%s/%s/%s/%s/%s' % (
            configgroup.group_id, configgroup.site_name, configgroup.app_name, Room.objects.get(
                name=configgroup.idc).ycc_code.lower(), collect_type)
        collect(
            {'type': "group_status", 'action': 'commit', 'index': collect_index, 'level': 'normal',
             'message': '//'.join(collect_content),
             'user': self.request.user.username,
             'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})


# publish
class ConfigGroupStatusDetailV2(generics.RetrieveUpdateDestroyAPIView):
    queryset = ConfigGroupStatus.objects.all().order_by('-id')
    serializer_class = ConfigGroupStatusSerializer
    permission_classes = (YccGroupStatusPermission,)

    def perform_update(self, serializer):
        op = self.request.DATA.get('op')
        group = self.request.DATA.get('group')
        if op == 'publish':
            ConfigGroupStatus.objects.filter(group=group, status=4).update(status=5)
        elif op == 'rollback':
            ConfigGroupStatus.objects.filter(group=group, status=4).update(status=6)
        serializer.save()
        # delete redis keys when status = 4

        try:
            configgroup_instance = ConfigGroup.objects.get(id=group, status=1)
            room_instance = Room.objects.get(name=configgroup_instance.idc)
            ycc_code = room_instance.name_ch
            configgroupstatus_instances = ConfigGroupStatus.objects.filter(status=4,
                                                                           group=configgroup_instance)
            configinfo_instances = ConfigInfo.objects.filter(group_status=configgroupstatus_instances)
            collect_content = []
            if op == 'publish' or op == 'rollback':
                for item in configinfo_instances:
                    # cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                    #     room_instance.id, 'production', configgroup_instance.group_id, item.data_id)
                    # cache.delete(cache_dataid_md5_key)
                    collect_content.append(item.data_id)
                cache.delete_pattern("ycc.%s.production.%s.*.md5" % (room_instance.id, configgroup_instance.group_id))
            # 变更系统
            collect_type = '应用类' if configgroup_instance.type == 1 else '公共组建类'
            collect_index = '%s/%s/%s/%s/%s' % (
                configgroup_instance.group_id, configgroup_instance.site_name, configgroup_instance.app_name, ycc_code,
                collect_type)
            collect(
                {'type': "group_status", 'action': op, 'index': collect_index, 'level': 'normal',
                 'message': '//'.join(collect_content),
                 'user': self.request.user.username,
                 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
        except ConfigInfo.DoesNotExist:
            raise YAPIException('ConfigGroup is not exist!')
        except Room.DoesNotExist:
            raise YAPIException('Room is not exist!')
        except ConfigGroupStatus.DoesNotExist:
            raise YAPIException('ConfigGroupStatus is not exist!')
        except ConfigInfo.DoesNotExist:
            raise YAPIException('ConfigInfo is not exist!')


@api_view(['GET'])
@permission_classes((AllowAny,))
def prodiffcontent(request):
    group = int(request.QUERY_PARAMS.get('group'))
    curgroupstatus = int(request.QUERY_PARAMS.get('cur_group_status'))
    cmpgroupstatus = int(request.QUERY_PARAMS.get('cmp_group_status'))
    dataid = request.QUERY_PARAMS.get('data_id')
    # 7 means production env
    curconfiginfo = ConfigInfo.objects.filter(data_id=dataid, group_status__group__id=group,
                                              group_status__status=curgroupstatus, env=7).order_by(
        '-group_status__version')
    curcontent = ''
    if curconfiginfo.exists():
        curcontent = curconfiginfo[0].content
    # 7 means production env
    cmpconfiginfos = ConfigInfo.objects.filter(data_id=dataid, group_status__group__id=group,
                                               group_status__status=cmpgroupstatus, env=7)
    cmpcontent = ''
    if cmpconfiginfos.exists():
        cmpcontent = cmpconfiginfos[0].content
    return Response(status=status.HTTP_200_OK, data={'result': True,
                                                     'curcontent': curcontent,
                                                     'cmpcontent': cmpcontent})


def hidepwd_impl(pwdkey, content):
    # tobereplaced = re.compile(pwdkey + '[  ]*=.*\n')
    # content_nopwd = tobereplaced.sub(pwdkey + '=******\n', content)
    # tobereplaced = re.compile(pwdkey + '[  ]*=.*')
    # content_nopwd = tobereplaced.sub(pwdkey + '=******', content_nopwd)
    tmp_arr = []
    for cn in content.split('\n'):
        if pwdkey in cn.split('=', 1)[0]:
            tmp_arr.append('%s=%s' % (cn.split('=', 1)[0], '******'))
        else:
            tmp_arr.append(cn)
    content_nopwd = '\n'.join(tmp_arr)
    return content_nopwd


def hidepwd(env, content):
    content_nopwd = content
    if YCC_ENV == 'production':
        # pwdkey = 'jdbc.password.encrypt'
        # content_nopwd = hidepwd_impl(pwdkey, content_nopwd)
        # if content_nopwd == content:
        #     pwdkey = 'jdbc.password'
        #     content_nopwd = hidepwd_impl(pwdkey, content_nopwd)
        # if content_nopwd == content:
        #     pwdkey = 'password'
        #     content_nopwd = hidepwd_impl(pwdkey, content_nopwd)
        pwdkey = 'password'
        content_nopwd = hidepwd_impl(pwdkey, content_nopwd)
    return content_nopwd


@api_view(['GET'])
@permission_classes((AllowAny,))
def diffcontent(request):
    group = int(request.QUERY_PARAMS.get('group'))
    curenv = int(request.QUERY_PARAMS.get('cur_env'))
    cmpenv = int(request.QUERY_PARAMS.get('cmp_env'))
    dataid = request.QUERY_PARAMS.get('data_id')
    # curstatus = 4 if curenv == 7 else 0
    curstatus = 0
    # cmpstatus = 4 if cmpenv == 7 else 0
    cmpstatus = 0
    curcontent = ''
    # 7 means production env
    curconfiginfos = ConfigInfo.objects.filter(data_id=dataid, group_status__group__id=group,
                                               group_status__status=curstatus, env=curenv)
    if curconfiginfos.exists():
        curcontent = curconfiginfos[0].content
        curcontent = hidepwd(curenv, curcontent)
    # 7 means production env
    cmpconfiginfos = ConfigInfo.objects.filter(data_id=dataid, group_status__group__id=group,
                                               group_status__status=cmpstatus, env=cmpenv)
    cmpcontent = ''
    if cmpconfiginfos.exists():
        cmpcontent = cmpconfiginfos[0].content
        cmpcontent = hidepwd(cmpenv, cmpcontent)
    return Response(status=status.HTTP_200_OK, data={'result': True,
                                                     'curcontent': curcontent,
                                                     'cmpcontent': cmpcontent})


@api_view(['GET', ])
@permission_classes((AllowAny,))
def getGroupstatus(request):
    idc = request.QUERY_PARAMS.get('idc')
    pool = request.QUERY_PARAMS.get('pool')
    if not idc:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='idc can\'t be empty.')
    if not pool:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='pool can\'t be empty.')
    group_id = pool.replace('/', '_')
    group = ConfigGroup.objects.filter(group_id=group_id, idc__ycc_code=idc, status=1)
    groupstatus = -1
    desc = 'Unknown'
    if ConfigGroupStatus.objects.filter(group=group, status=1):
        groupstatus = 1
        desc = 'commited'
    elif ConfigGroupStatus.objects.filter(group=group, status=2):
        groupstatus = 2
        desc = 'approved'
    elif ConfigGroupStatus.objects.filter(group=group, status=0):
        groupstatus = 0
        desc = 'edit/published'
    return Response(status=status.HTTP_200_OK, data={'status': groupstatus, 'desc': desc})


@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
def tridentDeployApi(request):
    op = request.QUERY_PARAMS.get('op')
    idc = request.QUERY_PARAMS.get('idc')
    pool = request.QUERY_PARAMS.get('pool')
    group_id = pool.replace('/', '_')
    group = ConfigGroup.objects.filter(group_id=group_id, idc__ycc_code=idc, status=1)
    statuscode = status.HTTP_400_BAD_REQUEST
    detailmsg = 'successful to ' + op
    result = True
    if group.exists():
        if op == 'audit':
            curstatus = 1
            newstatus = 2
        elif op == 'reject':
            curstatus = 1
            newstatus = 3
        elif op == 'publish':
            curstatus = 2
            newstatus = 4
        elif op == 'rollback':
            curstatus = 5
            newstatus = 4
        elif op == 'rmvpublish':
            curstatus = 2
            newstatus = 7
        elif op == 'rmvaudit':
            curstatus = 1
            newstatus = 8
        elif op == 'rollback_publish':
            curstatus = 2
            newstatus = 1
        else:
            result = False
            detailmsg = 'bad parameter op'
            return Response(status=statuscode, data={'result': result, 'detail': detailmsg})
        group = group[0]
        curconfiggroupstatus = ConfigGroupStatus.objects.filter(group=group, status=curstatus)
        if curconfiggroupstatus.exists():
            if op == 'publish':
                ConfigGroupStatus.objects.filter(group=group, status=4).update(status=5)
            elif op == 'rollback':
                curconfiggroupstatus = curconfiggroupstatus.order_by('-version')
                ConfigGroupStatus.objects.filter(group=group, status=4).update(status=6)
            curconfiggroupstatus = curconfiggroupstatus[0]
            curconfiggroupstatus.status = newstatus
            curconfiggroupstatus.save(update_fields=['status'])
            statuscode = status.HTTP_200_OK
            # delete redis keys when status = 4
            if op == 'publish' or op == 'rollback':
                try:
                    if idc.lower() == 'sh':
                        idc = 1
                    elif idc.lower() == 'jq':
                        idc = 4
                    else:
                        idc = ''
                        raise YAPIException('IDC is none. Plase check it!')
                    configgroupstatus_instances = ConfigGroupStatus.objects.filter(status=4,
                                                                                   group=group)
                    # configinfo_instances = ConfigInfo.objects.filter(group_status=configgroupstatus_instances)
                    if idc != '':
                        # for item in configinfo_instances:
                        #     cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                        #         idc, 'production', group.group_id, item.data_id)
                        #     cache.delete(cache_dataid_md5_key)
                        cache.delete_pattern("ycc.%s.production.%s.*.md5" % (idc, group.group_id))
                    else:
                        detailmsg = 'param have not idc or idc is error'
                except ConfigInfo.DoesNotExist:
                    raise YAPIException('ConfigGroup is not exist!')
                except Room.DoesNotExist:
                    raise YAPIException('Room is not exist!')
                except ConfigGroupStatus.DoesNotExist:
                    raise YAPIException('ConfigGroupStatus is not exist!')
                except ConfigInfo.DoesNotExist:
                    raise YAPIException('ConfigInfo is not exist!')
        else:
            result = False
            detailmsg = 'Current status is not allowed to ' + op
    else:
        result = False
        detailmsg = 'bad parameter pool/idc'
    return Response(status=statuscode, data={'result': result, 'detail': detailmsg})


@api_view(['POST'])
@permission_classes((AllowAny,))
def grayReleaseIpSet(request):
    iplist = request.POST.get('iplist')
    if iplist == None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='no input param iplist.')
    try:
        iplist = json.loads(iplist)
    except Exception:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='input param iplist is not json.')
    white = iplist.get('white')
    black = iplist.get('black')
    statuscode = status.HTTP_400_BAD_REQUEST
    result = False
    if white == None and black == None:
        detailmsg = 'missing parameter white/black'
        return Response(status=statuscode, data={'result': result, 'detail': detailmsg})
    else:
        if white != None:
            GrayReleaseBlackip.objects.filter(ip__in=white).delete()
        if black != None:
            for bip in black:
                GrayReleaseBlackip.objects.get_or_create(ip=bip)
        statuscode = status.HTTP_200_OK
        result = True
        detailmsg = 'success'
        cache.delete('ycc.gray.list')
        return Response(status=statuscode, data={'result': result, 'detail': detailmsg})


class GrayReleaseBlackIp(generics.ListCreateAPIView):
    queryset = GrayReleaseBlackip.objects.all().order_by('-id')
    serializer_class = blackipSerializer


class GrayReleaseBlackIpD(generics.DestroyAPIView):
    queryset = GrayReleaseBlackip.objects.all().order_by('-id')
    serializer_class = blackipSerializer


class ConfigSubscribeLogList(generics.ListCreateAPIView):
    queryset = ConfigSubscribeLog.objects.all().order_by('-id')
    serializer_class = ConfigSubscribeLogSerializer
    filter_fields = ('status_code', 'update_time')
    search_fields = ('ip', 'group_id', 'config_file')
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)

    def perform_create(self, serializer):
        ip = serializer.validated_data.get('ip')
        try:
            server = Server.objects.exclude(server_status_id=400).get(ip=ip)
            server_id = server.id
        except Server.DoesNotExist:
            server_id = 0
        serializer.save(server_id=server_id)


class ConfigHostList(generics.ListAPIView):
    queryset = ConfigHost.objects.all()
    serializer_class = ConfigHostSerializer
    search_fields = (
        'server__ip', 'pool_name', 'ori_pool_name', 'ori_main_group_id', 'main_group__group_id', 'create_time')
    filter_backends = (filters.SearchFilter,)


@api_view(['PUT'])
@permission_classes((YccCommitPermission,))
def revert(request):
    edit_config_info_id = request.DATA.get('edit_config_info_id')
    edit_config_info_obj = ConfigInfo.objects.get(id=edit_config_info_id)
    published_group_status_queryset = ConfigGroupStatus.objects.filter(group=edit_config_info_obj.group_status.group,
                                                                       status=4)
    if not published_group_status_queryset.exists():
        return Response(status=status.HTTP_400_BAD_REQUEST, data='没有历史发布信息，不能还原')
    published_config_info_queryset = ConfigInfo.objects.filter(
        group_status=published_group_status_queryset.first(),
        env=edit_config_info_obj.env,
        data_id=edit_config_info_obj.data_id,
    )
    if not published_config_info_queryset.exists():
        return Response(status=status.HTTP_400_BAD_REQUEST, data='最近一次发布的版本中没有该文件，不能还原')
    published_config_info_obj = published_config_info_queryset.first()
    edit_config_info_obj.content = published_config_info_obj.content
    edit_config_info_obj.content_md5 = published_config_info_obj.content_md5
    edit_config_info_obj.modified_time = int(time.time())
    edit_config_info_obj.modified_by = request.user.username
    edit_config_info_obj.remark = published_config_info_obj.remark
    edit_config_info_obj.file_type = published_config_info_obj.file_type
    edit_config_info_obj.cmp = published_config_info_obj.cmp
    edit_config_info_obj.config_type = published_config_info_obj.config_type
    edit_config_info_obj.save()
    return Response(status=status.HTTP_200_OK, data={'result': True})


@api_view(['GET'])
@permission_classes((AllowAny,))
def compare(request):
    edit_config_info_id = request.GET.get('edit_config_info_id')
    edit_config_info_obj = ConfigInfo.objects.get(id=edit_config_info_id)
    published_group_status_queryset = ConfigGroupStatus.objects.filter(group=edit_config_info_obj.group_status.group,
                                                                       status=4)
    if not published_group_status_queryset.exists():
        return Response(status=status.HTTP_400_BAD_REQUEST, data='没有历史发布信息，不能对比')
    published_config_info_queryset = ConfigInfo.objects.filter(
        group_status=published_group_status_queryset.first(),
        env=edit_config_info_obj.env,
        data_id=edit_config_info_obj.data_id,
    )
    if not published_config_info_queryset.exists():
        return Response(status=status.HTTP_400_BAD_REQUEST, data='最近一次发布的版本中没有该文件，不能对比')
    published_config_info_obj = published_config_info_queryset.first()
    return Response(status=status.HTTP_200_OK, data={
        'edit': hidepwd(None, edit_config_info_obj.content),
        'published': hidepwd(None, published_config_info_obj.content)
    })


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_group_cmp_idc(request):
    group_id = request.QUERY_PARAMS['id'] if request.QUERY_PARAMS['id'] else ''
    tmp_cmp_insts_id = []
    resultlist = []
    cgs_insts = ConfigGroupStatus.objects.filter(group=ConfigGroup.objects.filter(id=group_id), status=4)
    if len(cgs_insts) > 1:
        raise YAPIException('cgs_data error!')
    if cgs_insts:
        configinfo_inst = ConfigInfo.objects.filter(group_status=cgs_insts[0].id, env=7)
        if configinfo_inst:
            for ci in configinfo_inst:
                cmp_configinfo_insts = ConfigInfo.objects.filter(data_id=ci.data_id, env=7, group_status__status=4,
                                                                 group_status__group__group_id=ci.group_status.group.group_id).exclude(
                    group_status__group__idc__id=ci.group_status.group.idc.id)
                group_id = ci.group_status.group.group_id if ci.group_status.group.group_id else ''
                idc = ci.group_status.group.idc.name_ch if ci.group_status.group.idc.name_ch else ''
                this_content = ci.content if ci.content else ''
                data_id = ci.data_id if ci.data_id else ''
                if len(cmp_configinfo_insts) == 0:
                    tmp_cmp_insts_id.append(int(ci.id))
                    resultlist.append({
                        'id': ci.id,
                        'data_id': data_id,
                        'cmp': 'new',
                        'color': 'green',
                        'this_content': this_content,
                        'other_content': '',
                        'group_id': group_id,
                        'idc': idc,
                        'other_dataid': '',
                        'other_groupid': '',
                        'other_idc': ''
                    })
                else:
                    for cci in cmp_configinfo_insts:
                        if cci.content_md5 != ci.content_md5:
                            other_content = cci.content if cci.content else ''
                            other_dataid = cci.data_id if cci.data_id else ''
                            other_groupid = cci.group_status.group.group_id if cci.group_status.group.group_id else ''
                            other_idc = cci.group_status.group.idc.name_ch if cci.group_status.group.idc.name_ch else ''
                            resultlist.append({
                                'id': '%s_%s' % (ci.id, cci.id),
                                'data_id': cci.data_id,
                                'cmp': 'different',
                                'color': 'blue',
                                'this_content': this_content,
                                'other_content': other_content,
                                'group_id': group_id,
                                'idc': idc,
                                'other_dataid': other_dataid,
                                'other_groupid': other_groupid,
                                'other_idc': other_idc
                            })
                            tmp_cmp_insts_id.append(int(cci.id))
                        else:
                            tmp_cmp_insts_id.append(int(cci.id))
                    tmp_cmp_insts_id.append(int(ci.id))

            # cmp_configinfo_del_insts = ConfigInfo.objects.filter(env=7, group_status__status=4,group_status__group__group_id=group_id).exclude(id=353737, group_status__group__idc__id=cgs_insts[0].group.idc.id)
            cmp_configinfo_del_insts = ConfigInfo.objects.filter(env=7, group_status__status=4,
                                                                 group_status__group__group_id=group_id).exclude(
                id__in=tmp_cmp_insts_id)
            for ccdi in cmp_configinfo_del_insts:
                resultlist.append({
                    'id': ccdi.id,
                    'data_id': ccdi.data_id,
                    'cmp': 'delete',
                    'color': 'red',
                    'this_content': ccdi.content,
                    'other_content': '',
                    'group_id': ccdi.group_status.group.group_id,
                    'idc': ccdi.group_status.group.idc.name_ch,
                    'other_dataid': data_id,
                    'other_groupid': group_id,
                    'other_idc': idc,
                    'tmp': tmp_cmp_insts_id,
                    'tmp1': cgs_insts[0].group.idc.id
                })
    return Response(resultlist)


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_db_instance(request):
    group_id = request.QUERY_PARAMS['group_id'] if request.QUERY_PARAMS['group_id'] else ''
    if not group_id:
        return Response('')
    ct_type = request.QUERY_PARAMS['ct_type'] if request.QUERY_PARAMS['ct_type'] else ''
    try:
        dd_dom_inst = DdDomain.objects.get(id=App.objects.get(id=ConfigGroup.objects.get(id=group_id).app_id).domainid)
    except ConfigGroup.DoesNotExist:
        dd_dom_inst = ''
    except ConfigGroup.MultipleObjectsReturned:
        dd_dom_inst = ''
    except App.DoesNotExist:
        dd_dom_inst = ''
    except App.MultipleObjectsReturned:
        dd_dom_inst = ''
    except DdDomain.DoesNotExist:
        dd_dom_inst = ''
    except DdDomain.MultipleObjectsReturned:
        dd_dom_inst = ''
    try:
        tmp_ci_id = []
        tmp_cdci_id = []
        childenlist = []
        resultlist = []
        par = ''

        # for cgsi in conf_group_status_insts:
        #     tmp_cgsi_id.append(ConfigInfo.objects.get(group_status__id=cgsi.id).id)
        conf_group_status_insts = ConfigGroupStatus.objects.get(group__id=group_id, status=0)
        configinfo_insts = ConfigInfo.objects.filter(group_status__id=conf_group_status_insts.id)
        if configinfo_insts:
            for ci in configinfo_insts:
                tmp_ci_id.append(ci.id)

            conf_db_confinfo_insts = ConfigDbConfiginfo.objects.filter(config_info_id__in=tmp_ci_id)
            for cdci in conf_db_confinfo_insts:
                tmp_cdci_id.append(cdci.config_db_instance_id)

            conf_db_insts = ConfigDbInstance.objects.filter(id__in=tmp_cdci_id)
            for cdi in conf_db_insts:
                if ct_type == 'instance':
                    resultlist.append({
                        'id': ci.group_status.group.id,
                        'cname': cdi.cname,
                    })
                elif ct_type == 'association':
                    childenlist.append(cdi.dbname)
            if ct_type == 'association':
                conf_group_inst = ConfigGroup.objects.get(id=group_id)
                if dd_dom_inst:
                    par = '%s/%s/%s/%s' % (
                        conf_group_inst.group_id, conf_group_inst.idc.name_ch, dd_dom_inst.domainname,
                        dd_dom_inst.domainleaderaccount)
                else:
                    par = '%s/%s' % (conf_group_inst.group_id, conf_group_inst.idc.name_ch)
                if childenlist:
                    resultlist = {
                        'par': par,
                        'val': childenlist
                    }
                else:
                    resultlist = ''
        elif not configinfo_insts and ct_type == 'association':
            resultlist = ''
        return Response(resultlist)
    except ConfigGroupStatus.DoesNotExist:
        return Response('')
    except ConfigGroupStatus.MultipleObjectsReturned:
        return Response('')


class ConfigInfoListV3(generics.ListAPIView):
    """
    发布申请单列表.

    输入参数：

    输出参数：

    """

    queryset = ConfigInfo.objects.all()
    serializer_class = ConfigInfoSerializer
    filter_backends = (filters.DjangoFilterBackend, ycc_filters.ConfigInfoFilterBackend)
    filter_fields = ('env', 'group_status__group__id', 'group_status__status', 'group_status__version')


class ConfigInfoListV3(generics.ListCreateAPIView):
    """
    YCC配置文件f表/新增

    输入参数：

    输出参数：

    * id                    -   PK
    * data_id               -   配置文件
    * groupid_id            -   配置组
    * env                   -   环境
    * content               -   配置文件内容
    * content_md5           -   配置文件内容MD5
    * created_time          -   配置文件创建时间
    * modified_time         -   配置文件修改时间
    * created_by            -   配置文件创建人
    * updated_by            -   配置文件修改人
    * remark                -   配置文件说明
    * file_type             -   配置文件类型
    * cmp                   -   配置文件staging和production是否一致，0表示一致
    * config_type           -   配置文件类型，1表示普通配置文件，2表示DB配置文件
    """
    queryset = ConfigInfoV3.objects.filter(group_status__status=0, group_status__group__status=1, env=YCC_CMP_ENV,
                                           group_status__group__idc=1).order_by('-id')
    serializer_class = ConfigInfoSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, ycc_filters.ConfigInfoFilterBackend)
    # filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    search_fields = ('data_id', 'content')
    filter_fields = ('group_status__group__idc__id', 'env', 'group_status__group__group_id', 'group_status__group__id',
                     'group_status__status', 'group_status__version', 'group_status__group__app_id', 'config_type')
    permission_classes = (YccCommitPermission,)

    def get_serializer_class(self):
        # if YCC_ENV == 'production' and not isSaPermission(self.request) and self.request.method == 'GET':
        #     return ProConfigInfoSerializer
        # return ConfigInfoSerializer
        return ProConfigInfoSerializer if YCC_ENV == 'production' and not self.request.user.is_superuser and self.request.method == 'GET' else ConfigInfoSerializer

    def perform_create(self, serializer):
        # if not isSaPermission(self.request):
        #     raise YAPIException('You do not have permission to perform this action.')
        data_id = serializer.validated_data.get('data_id')
        group_status_id = serializer.validated_data.get('group_status')
        user = self.request.user.username
        db_instance_id = self.request.DATA.get('db_instance_id', None)
        config_type = self.request.DATA.get('config_type')
        env = serializer.validated_data.get('env')
        jdbckv_string = self.request.DATA.get('jdbckv_string')
        db_type = self.request.DATA.get('db_type', None)
        group_name = self.request.DATA.get('group_name', None)
        idc_name = self.request.DATA.get('idc_name', None)
        current_time = int(time.time())
        content = ''
        content_md5 = ''
        ain = ''
        if YCC_ENV == 'production':
            cmp = 0
        elif YCC_ENV == 'test':
            cmp = 1
        else:
            cmp = 0
        if db_instance_id is None:
            content = serializer.validated_data.get('content')
            content_md5 = md5(content)
        if YCC_ENV == 'production':
            for ds in DB_SUPPORT:
                if ds in content:
                    raise YAPIException('如果是DB配置文件请使用新建“DB配置文件”，如果不是请联系ZhangZaibin。')
        idcs_envs = get_room_idc(group_name)
        try:
            jdbc_default_instance = ConfigDbKvDefault.objects.filter(jdbctype=1, dbtype=db_type)
        except:
            raise YAPIException('miss dbtype!')
        cmp_md5 = []
        insert_cmp = configinfov3_insert_cmp(group_name, data_id, content_md5)
        if not insert_cmp['result']:
            raise YAPIException(insert_cmp['message'])
        is_same_configtype = ConfigInfo.objects.filter(group_status__group__group_id=group_name, group_status__status=0,
                                                       group_status__group__status=1, data_id=data_id)
        if is_same_configtype:
            if config_type == '1':
                config_in = [1, 3]
            elif config_type == '2':
                config_in = [2]
            else:
                raise YAPIException('Config_in is error.')
            if not is_same_configtype.filter(config_type__in=config_in):
                raise YAPIException('请新增相同类型的配置文件!')
        for idc, items in idcs_envs.iteritems():
            for item in items['room']:
                # if ConfigInfoV3.objects.filter(group_status_id=group_status_id, data_id=data_id, env=item.id).exists():
                config_info_v3 = ConfigInfoV3.objects.filter(group_status_id=items['group_status'].id, data_id=data_id, env=item.id)
                if config_info_v3.exists():
                    # raise YAPIException('配置文件(%s)在相同配置组和相同环境(%s)中已经存在）,建议找到该配置组直接修改或上传!' % (data_id, item.name))
                    cmp_md5.append(config_info_v3[0].content_md5)
                    continue
                ain = ConfigInfoV3.objects.create(
                    data_id=data_id,
                    group_status_id=items['group_status'].id,
                    env_id=item.id,
                    content_md5=content_md5,
                    content=content,
                    created_time=current_time,
                    modified_time=0,
                    created_by=user,
                    modified_by=user,
                    cmp=cmp,
                    config_type=config_type,
                )
                cmp_md5.append(ain.content_md5)
                if db_instance_id is not None:
                    ConfigDbConfiginfo.objects.get_or_create(config_info_id=ain.id, defaults={
                        'config_db_instance_id': db_instance_id
                    })
                    if jdbckv_string is not None:
                        line_content = []
                        content = ''
                        try:
                            confinfo = ConfigInfoV3.objects.get(data_id=data_id, group_status_id=items['group_status'].id, env=item.id)
                        except:
                            raise YAPIException('错误！data_id = %s' % data_id)
                        jdbckv_arr1 = jdbckv_string.split(',,,,,,,')
                        if confinfo:
                            config_db_instance = ConfigDbInstance.objects.get(id=db_instance_id)
                            line_content.append("%s=%s" % (jdbc_username_key_name, config_db_instance.username))
                            line_content.append("%s=%s" % (jdbc_password_key_name, config_db_instance.password))
                            # 添加jdbc允许修改项
                            for arr_item in jdbckv_arr1:
                                jdbckv_arr2 = arr_item.split('^^^^^^^')
                                dbtype_string = jdbckv_arr2[0]
                                jdbckey_string = jdbckv_arr2[1]
                                jdbcval_string = jdbckv_arr2[2]
                                if 'jdbcurl' in jdbckey_string:
                                    jdbckey_string = jdbc_url_key_name
                                ConfigDbKvCustom.objects.create(configinfo_id=confinfo.id, dbtype=dbtype_string,
                                                                jdbckey=jdbckey_string,
                                                                jdbcval=jdbcval_string,
                                                                jdbctype=2)
                                line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                            # 添加jdbc默认项
                            for jd_default in jdbc_default_instance:
                                ConfigDbKvCustom.objects.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                                jdbckey=jd_default.jdbckey,
                                                                jdbcval=jd_default.jdbcval,
                                                                jdbctype=1)
                                line_content.append("%s=%s" % (jd_default.jdbckey, jd_default.jdbcval))
                            content = "\n".join(line_content)
                            # 更新配置文件显示内容
                            ConfigInfoV3.objects.filter(id=confinfo.id).update(content=content, content_md5=md5(content))
                        else:
                            raise YAPIException('配置文件不存在!')
                    else:
                        raise YAPIException('字符串为空！')
                # 变更系统 ok
                collect_type_name = 'db_configinfo' if config_type == "2" else "configinfo"
                collect_index = '%s/%s/%s/%s' % (data_id, group_name, items['idc_name'], item.name)
                collect({'type': collect_type_name, 'action': 'add', 'index': collect_index, 'level': 'normal',
                         'message': hidepwd(YCC_ENV, content),
                         'user': user, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
        if ain:
            if YCC_ENV == 'test':
                tmp_cmp = 0
            else:
                tmp_cmp = get_cmp_result(db_instance_id, cmp_md5)
            create_or_update_configinfocmp(tmp_cmp, group_name, data_id)
        else:
            raise YAPIException('配置文件已存在！')


class ConfigInfoDetailV3(generics.RetrieveUpdateDestroyAPIView):
    """
    YCC配置文件表/修改删除

    输入参数： 无

    输出参数：

    * id                    -   PK
    * data_id               -   配置文件
    * groupid_id            -   配置组
    * env                   -   环境
    """
    permission_classes = (YccCommitPermission,)
    queryset = ConfigInfoV3.objects.filter().order_by('-id')
    serializer_class = ConfigInfoSerializer

    def perform_update(self, serializer):
        user = self.request.user.username
        current_time = int(time.time())
        delete_dbtype_flag = 0
        delete_dbtype_name = ''
        config_type = self.request.DATA.get('config_type', None)
        content = self.request.DATA.get('content', None)
        data_id = self.request.DATA.get('data_id', None)
        env_name = self.request.DATA.get('env_name', None)
        group_status_id = serializer.validated_data.get('group_status')
        group_name = self.request.DATA.get('group_name', None)
        db_type = self.request.DATA.get('db_type', None)
        idc = self.request.DATA.get('idc', None)
        db_instance_id = self.request.DATA.get('db_instance_id', None)
        op = self.request.DATA.get('op', None)
        configinfo_id = self.request.DATA.get('editid', None)
        flag_new_pass = 0
        old_pass_arr = []
        new_pass_arr = []
        new_cont_arr = []
        old_password = '******'
        # raise YAPIException(idc)
        idc_ins = Room.objects.get(id=idc)
        collect_idc = idc_ins.name_ch

        if op == 'old_db':
            try:
                configinfo_instanace = ConfigInfoV3.objects.get(id=configinfo_id)
                old_pass_arr = configinfo_instanace.content.split('\n')
                for oc in old_pass_arr:

                    # if '#' not in oc and 'password' in oc:
                    if len(oc.strip()) > 0:
                        if oc.strip()[0] != '#' and 'password' in oc:
                            old_password = oc.split('=')[1]
                if content:
                    new_pass_arr = content.split('\n')
                    for ct in new_pass_arr:
                        if '#' not in ct and 'password' in ct:
                            new_cont_arr.append("%s=%s" % (ct.split('=')[0], old_password))
                            flag_new_pass += 1
                        else:
                            new_cont_arr.append(ct)
                if flag_new_pass > 1:
                    raise YAPIException('muti password key!')
                content = '\n'.join(new_cont_arr)
                content_md5 = md5(content)
            except ConfigInfoV3.MultipleObjectsReturned:
                raise YAPIException('muti config_instance!')
            except ConfigInfoV3.DoesNotExist:
                raise YAPIException('miss config_instance!')
        else:
            if config_type == "1":
                content = self.request.DATA.get('content', None)
                content_md5 = md5(content)
            else:
                db_instance_id = int(content)
                content_md5 = md5(content)
        instance = serializer.save(content=content, content_md5=content_md5, modified_time=current_time,
                                   modified_by=user)
        if instance.is_cmp == 1:
            configinfo_cmp = ConfigInfoV3.objects.filter(data_id=instance.data_id, group_status__group__group_id=group_name, group_status__status=0, group_status__group__status=1)
            configinfo_cmp.update(content=content, content_md5=content_md5, modified_time=current_time)
            cache_and_collect = configinfo_cmp
        elif instance.is_cmp == 0:
            cache_and_collect = ConfigInfoV3.objects.filter(id=instance.id)
        else:
            raise YAPIException('ConfigInfoDetailV3 Warning!')

        # It's tmp for dbupdate || can be delete.
        if op == 'old_db':
            if ConfigInfoTmp.objects.filter(configinfo_id=instance.id).exists():
                syn_dbupdate_one(instance.id, content, 'update')
            else:
                syn_dbupdate_one(instance.id, content, 'add')

        if config_type == "2":
            # ConfigDbConfiginfo.objects.filter(config_info_id=instance.id).update(
            #     config_db_instance_id=db_instance_id)
            config_db_info_insts = ConfigDbConfiginfo.objects.filter(config_info_id=instance.id)
            if config_db_info_insts.exists():
                config_db_info_insts.update(config_db_instance_id=db_instance_id)
            else:
                config_db_info_insts.create(config_info_id=instance.id, config_db_instance_id=db_instance_id)
            jdbckv_string = self.request.DATA.get('jdbckv_string')
            line_content = []
            db_default_val_dic = dict()
            db_default_key_dic = dict()
            # nodelete_dbtype_arr = []
            is_insert = False
            if jdbckv_string is not None:
                try:
                    jdbc_default_instance = ConfigDbKvDefault.objects.filter(dbtype=db_type)
                except:
                    raise YAPIException('miss dbtype!')
                for jdi in jdbc_default_instance.filter(jdbctype=1):
                    db_default_val_dic[jdi.jdbckey.lower()] = jdi.jdbcval
                    db_default_key_dic[jdi.jdbckey.lower()] = jdi.jdbckey
                env = ConfigEnv.objects.get(name=env_name)
                confinfo = ConfigInfoV3.objects.get(data_id=data_id, group_status_id=group_status_id, env=env.id)
                jdbckv_arr1 = jdbckv_string.split(',,,,,,,')
                if confinfo:
                    config_db_instance = ConfigDbInstance.objects.get(id=db_instance_id)
                    line_content.append("%s=%s" % (jdbc_username_key_name, config_db_instance.username))
                    line_content.append("%s=%s" % (jdbc_password_key_name, config_db_instance.password))
                    cdkc_instances = ConfigDbKvCustom.objects.filter(configinfo_id=confinfo.id)
                    for arr_item in jdbckv_arr1:
                        jdbckv_arr2 = arr_item.split('^^^^^^^')
                        dbtype_string = jdbckv_arr2[0]
                        jdbckey_string = jdbckv_arr2[1]
                        jdbcval_string = jdbckv_arr2[2]
                        if 'jdbcurl' in jdbckey_string:
                            jdbckey_string = jdbc_url_key_name
                        # 判断配置文件是否存在
                        if cdkc_instances.filter(configinfo_id=confinfo.id).exists():
                            # 判断配置文件与dbtype是否存在
                            if cdkc_instances.filter(configinfo_id=confinfo.id,
                                                     dbtype=dbtype_string).exists():
                                # 判断配置文件、dbtype、jdbckey是否存在
                                if cdkc_instances.filter(configinfo_id=confinfo.id, dbtype=dbtype_string,
                                                         jdbckey=jdbckey_string).exists():
                                    cdkc_instances.filter(configinfo_id=confinfo.id,
                                                          dbtype=dbtype_string,
                                                          jdbckey=jdbckey_string).update(
                                        jdbcval=jdbcval_string)
                                    line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                    # nodelete_dbtype_arr.append(jdbckey_string)
                                else:
                                    cdkc_instances.create(configinfo_id=confinfo.id,
                                                          dbtype=dbtype_string,
                                                          jdbckey=jdbckey_string,
                                                          jdbcval=jdbcval_string,
                                                          jdbctype=2)
                                    line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                    # nodelete_dbtype_arr.append(jdbckey_string)
                            else:
                                cdkc_instances.create(configinfo_id=confinfo.id,
                                                      dbtype=dbtype_string,
                                                      jdbckey=jdbckey_string,
                                                      jdbcval=jdbcval_string,
                                                      jdbctype=2)
                                line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                                is_insert = True
                                delete_dbtype_flag = 1
                                delete_dbtype_name = jdbckv_arr2[0]
                        else:
                            cdkc_instances.create(configinfo_id=confinfo.id,
                                                      dbtype=dbtype_string,
                                                      jdbckey=jdbckey_string,
                                                      jdbcval=jdbcval_string,
                                                      jdbctype=2)
                            line_content.append("%s=%s" % (jdbckey_string, jdbcval_string))
                    # true插入默认jdbc参数,false同步增加或者删除Default数据
                    if is_insert:
                        for jd_default in jdbc_default_instance.filter(jdbctype=1):
                            cdkc_instances.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                  jdbckey=jd_default.jdbckey,
                                                  jdbcval=jd_default.jdbcval,
                                                  jdbctype=1)
                            line_content.append("%s=%s" % (jd_default.jdbckey, jd_default.jdbcval))
                            # nodelete_dbtype_arr.append(jd_default.jdbckey)
                            jdbc_key_val_tmp = "%s=%s" % (jd_default.jdbckey, jd_default.jdbcval)
                            if jdbc_key_val_tmp not in line_content:
                                line_content.append(jdbc_key_val_tmp)
                    else:
                        for cdkc in cdkc_instances.filter(jdbctype=1):
                            if cdkc.jdbckey.lower() in db_default_val_dic.keys():
                                if cdkc.jdbcval != db_default_val_dic[cdkc.jdbckey.lower()]:
                                    cdkc_instances.filter(jdbckey=cdkc.jdbckey, jdbctype=1).update(
                                        jdbcval=db_default_val_dic[cdkc.jdbckey.lower()])
                                line_content.append("%s=%s" % (
                                    db_default_key_dic[cdkc.jdbckey.lower()], db_default_val_dic[cdkc.jdbckey.lower()]))
                                db_default_val_dic.pop(cdkc.jdbckey.lower())
                            else:
                                cdkc_instances.filter(jdbckey=cdkc.jdbckey, jdbctype=1).delete()
                        if db_default_val_dic:
                            for ddvd_key in db_default_val_dic:
                                cdkc_instances.create(configinfo_id=confinfo.id, dbtype=db_type,
                                                      jdbckey=db_default_key_dic[ddvd_key],
                                                      jdbcval=db_default_val_dic[ddvd_key], jdbctype=1)
                                line_content.append(
                                    "%s=%s" % (db_default_key_dic[ddvd_key], db_default_val_dic[ddvd_key]))
                    # 变更dbtype时删除原dbtype的jdbc记录，如dbtype未修改则删除未在修改范围的jdbc记录
                    if delete_dbtype_flag > 0 and delete_dbtype_name != '':
                        cdkc_instances.exclude(
                            dbtype=delete_dbtype_name).delete()
                    # ######nodelete_dbtype_arr +++ not in line_content
                    # else:
                    #     cdkc_instances.filter(configinfo_id=confinfo.id).exclude(
                    #         jdbckey__in=nodelete_dbtype_arr).delete()
                    content = "\n".join(line_content)
                    ConfigInfoV3.objects.filter(id=confinfo.id).update(content=content, content_md5=md5(content))
                else:
                    raise YAPIException('配置文件不存在!')
            else:
                raise YAPIException('字符串为空！')

        for cmp in cache_and_collect:
            # 变更系统
            collect_type_name = 'db_configinfo' if config_type == "2" else "configinfo"
            collect_index = '%s/%s/%s/%s' % (cmp.data_id, group_name, cmp.group_status.group.idc.name_ch, cmp.env.name)
            # print collect_type_name
            # print collect_index
            collect({'type': collect_type_name, 'action': 'edit', 'index': collect_index, 'level': 'normal',
                     'message': hidepwd(YCC_ENV, content),
                     'user': user, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
            # raise YAPIException('ycc.%d.%s.%s.%s.md5' % (idc, env_name, group_name, data_id))
            if CATCH_REDIS and env_name.lower() != 'production':
                if idc != '':
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (cmp.group_status.group.idc.id, cmp.env.name, group_name, cmp.data_id)
                    # print cache_dataid_md5_key
                    cache.delete(cache_dataid_md5_key)
                else:
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (1, cmp.env.name, group_name, cmp.data_id)
                    # print cache_dataid_md5_key
                    cache.delete(cache_dataid_md5_key)
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (4, cmp.env.name, group_name, cmp.data_id)
                    # print cache_dataid_md5_key
                    cache.delete(cache_dataid_md5_key)

    def perform_destroy(self, instance):
        # if not isSaPermission(self.request):
        #     raise YAPIException('You do not have permission to perform this action.')
        rmv_id = self.request.DATA.get('configinfo_id', None)
        rmv_group = self.request.DATA.get('rmv_group', None)
        rmv_env = self.request.DATA.get('rmv_env', None)
        rmv_dataid = self.request.DATA.get('rmv_dataid', None)
        rmv_idc = self.request.DATA.get('rmv_idc', None)

        idc_ins = Room.objects.get(id=rmv_idc)
        collect_idc = idc_ins.name_ch
        try:
            configinfo_cmp = ConfigInfoV3.objects.filter(data_id=rmv_dataid, group_status__group__group_id=rmv_group, group_status__status=0, group_status__group__status=1)
            for conf in configinfo_cmp:
                configinfo_instance = ConfigInfoV3.objects.get(id=conf.id)
                configinfo_instance.delete()
                ConfigDbKvCustom.objects.filter(configinfo_id=conf.id).delete()
                ConfigDbConfiginfo.objects.filter(config_info_id=conf.id).delete()
                ConfiginfoCmp.objects.filter(group_id=configinfo_instance.group_status.group.group_id, data_id=configinfo_instance.data_id).delete()

                # 变更系统 ok
                collect_index = '%s/%s/%s/%s' % (conf.data_id, conf.group_status.group.group_id, conf.group_status.group.idc.name_ch, conf.env.name)
                collect({'type': 'configinfo', 'action': 'delete', 'index': collect_index, 'level': 'normal',
                         'message': hidepwd(YCC_ENV, configinfo_instance.content),
                         'user': self.request.user.username,
                         'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
                if CATCH_REDIS and rmv_env.lower() != 'production':
                    cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (conf.group_status.group.idc.id, conf.env.name, conf.group_status.group.group_id, conf.data_id)
                    cache.delete(cache_dataid_md5_key)
        except ConfigInfoV3.DoesNotExist:
            raise YAPIException("ConfigInfo is not exist!")
        except ConfigInfoV3.MultipleObjectsReturned:
            raise YAPIException("ConfigInfo is MultipleObjectsReturned!")


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_configinfos(request):
    data_id = request.QUERY_PARAMS['data_id'] if request.QUERY_PARAMS['data_id'] else ''
    group_id = request.QUERY_PARAMS['group_id'] if request.QUERY_PARAMS['group_id'] else ''
    configinfos = ConfigInfoV3.objects.filter(data_id=data_id, group_status__group__group_id=group_id,
                                              group_status__status=0)
    if not request.user.is_superuser:
        configinfos = configinfos.filter(group_status__group__idc__status=1)
    resultlist = []
    for configinfo in configinfos:
        db_instance_id = configinfo.db_info.config_db_instance_id if configinfo.db_info else 0
        is_status = False
        if configinfo.env.id == 7:
            configinfo_tmp = ConfigInfo.objects.filter(
                group_status__group__group_id=configinfo.group_status.group.group_id,
                group_status__group__idc=configinfo.group_status.group.idc,
                group_status__group__status=1, group_status__status__in=[1, 2],
                data_id=configinfo.data_id, env__id=configinfo.env.id)
            if configinfo_tmp.exists():
                is_status = True
        resultlist.append({
            'group_id': configinfo.group_status.group.group_id,
            'idc': configinfo.group_status.group.idc.name_ch,
            'idc_id': configinfo.group_status.group.idc.id,
            'status': configinfo.group_status.status,
            'version': configinfo.group_status.version,
            'env_name': configinfo.env.name,
            'db_instance_id': db_instance_id,
            'app_id': configinfo.group_status.group.app_id,
            # 'status_cn': configinfo.group_status.get_status_display,
            'app_status': configinfo.group_status.group.app_status,
            'is_cmp': configinfo.is_cmp,
            'id':  configinfo.id,
            'data_id':  configinfo.data_id,
            'group_status':  configinfo.group_status.id,
            'env':  configinfo.env.id,
            'content':  configinfo.content,
            'content_md5':  configinfo.content_md5,
            'created_time': configinfo.created_time,
            'modified_time': configinfo.modified_time,
            'created_by': configinfo.created_by,
            'modified_by': configinfo.modified_by,
            'remark': configinfo.remark,
            'file_type': configinfo.file_type,
            'cmp': configinfo.cmp,
            'config_type': configinfo.config_type,
            'is_cmp_type': configinfo.is_cmp_type,
            'is_configinfo_status': is_status
        })
    return Response(resultlist)


@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
# @csrf_exempt
def ConfigInfoListUploadV3(request):
    input_name = request.DATA.get('input_name', None)
    files = request.FILES.getlist(input_name)
    group_status_upload_id = request.DATA.get('group_status_upload', None)
    group_name = request.DATA.get('group_name', None)
    env_id = request.DATA.get('env', None)
    upload_data_id = request.DATA.get('upload_data_id', None)
    op_type = request.DATA.get('op_type', None)
    euid = request.DATA.get('euid', None)
    idc = request.DATA.get('upload_idc', None)

    current_time = int(time.time())
    data_id = ''
    content_arr = []
    username = request.DATA.get('username', None)

    if files:
        for f in files:
            data_id = f.name
            for chunk in f.chunks():
                content_arr.append(chunk)
        if YCC_ENV == 'production':
            cmp = 0
        elif YCC_ENV == 'test':
            cmp = 1
        else:
            cmp = 0
        content = ''.join(content_arr)
        if YCC_ENV == 'production':
            for ds in DB_SUPPORT:
                if ds in content:
                    raise YAPIException('如果是DB配置文件请使用新建“DB配置文件”，如果不是请联系ZhangZaibin。')
        fs = chardet.detect(content)
        try:
            if 'ascii' in fs['encoding'] or 'GB2312' in fs['encoding']:
                content = content.decode('gbk', 'ignore').encode('utf-8')
        except:
            content = content

        content_md5 = md5(content)
        cmp_md5 = []
        ain = ''
        if op_type == 'add':
            if files == '':
                raise YAPIException('请选择上传配置文件！')
            idcs_envs = get_room_idc(group_name)
            insert_cmp = configinfov3_insert_cmp(group_name, data_id, content_md5)
            if not insert_cmp['result']:
                raise YAPIException(insert_cmp['message'])
            is_same_configtype = ConfigInfo.objects.filter(group_status__group__group_id=group_name,
                                                           group_status__status=0, group_status__group__status=1,
                                                           data_id=data_id)
            if is_same_configtype:
                if not is_same_configtype.filter(config_type__in=[1, 3]):
                    raise YAPIException('请新增相同类型的配置文件!')
            for idc, items in idcs_envs.iteritems():
                for item in items['room']:
                    collect_idc = Room.objects.get(id=idc).name_ch
                    configinfo_v3 = ConfigInfoV3.objects.filter(group_status_id=items['group_status'].id, data_id=data_id,
                                                 env=item.id)
                    if configinfo_v3.exists():
                        # raise YAPIException('配置文件(%s)在相同配置组和相同环境(%s)中已经存在）,建议找到该配置组直接修改或上传!' % (data_id, item.name))
                        cmp_md5.append(configinfo_v3[0].content_md5)
                        continue
                    try:
                        ain = ConfigInfoV3.objects.create(
                            data_id=data_id,
                            group_status_id=items['group_status'].id,
                            env_id=item.id,
                            content_md5=content_md5,
                            content=content,
                            created_time=current_time,
                            modified_time=0,
                            created_by=username,
                            modified_by=username,
                            cmp=cmp,
                            config_type=1,
                        )
                    except Exception:
                        content = '%s%s' % ('configcentre-binary-file:', (binascii.b2a_hex(content)))
                        ain = ConfigInfoV3.objects.create(
                            data_id=data_id,
                            group_status_id=items['group_status'].id,
                            env_id=item.id,
                            content_md5=content_md5,
                            content=content,
                            created_time=current_time,
                            modified_time=0,
                            created_by=username,
                            modified_by=username,
                            cmp=cmp,
                            config_type=1,
                        )
                        # raise YAPIException('上传失败,文件格式不对！')
                    cmp_md5.append(ain.content_md5)
                    # 变更系统 ok
                    collect_index = '%s/%s/%s/%s' % (data_id, group_name, collect_idc, item.name)
                    # print collect_index
                    collect({'type': 'configinfo', 'action': 'add_upload', 'index': collect_index, 'level': 'normal',
                             'message': hidepwd(YCC_ENV, content),
                             'user': username,
                             'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})
            if ain:
                if YCC_ENV == 'test':
                    tmp_cmp = 0
                else:
                    tmp_cmp = get_cmp_result(None, cmp_md5)
                create_or_update_configinfocmp(tmp_cmp, group_name, data_id)
            else:
                raise YAPIException('配置文件已存在！')
            idc = 0
        elif op_type == 'edit':
            try:
                configinfo_v3 = ConfigInfoV3.objects.filter(id=euid)
            except ConfigInfoV3.DoesNotExist:
                raise YAPIException('ConfigInfo is not exists!!!')
            try:
                configinfo_v3.update(content=content, content_md5=content_md5, modified_time=current_time,
                                     modified_by=username)
            except Exception:
                content = '%s%s' % ('configcentre-binary-file:', (binascii.b2a_hex(content)))
                configinfo_v3.update(content=content, content_md5=content_md5, modified_time=current_time,
                                     modified_by=username)
            if configinfo_v3[0].is_cmp == 1:
                configinfo_cmp = ConfigInfoV3.objects.filter(data_id=configinfo_v3[0].data_id,
                                                             group_status__group__group_id=configinfo_v3[
                                                                 0].group_status.group.group_id, group_status__status=0,
                                                             group_status__group__status=1)
                configinfo_cmp.update(content=content, content_md5=content_md5, modified_time=current_time)
                cache_and_collect = configinfo_cmp
            elif configinfo_v3[0].is_cmp == 0:
                cache_and_collect = configinfo_v3
            else:
                raise YAPIException('ConfigInfoListUploadV3 Warning!')
            for cmp in cache_and_collect:
                if CATCH_REDIS and env_id.lower() != 'production':
                    if idc != '':
                        cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                            cmp.group_status.group.idc.id, cmp.env.name, cmp.group_status.group.group_id, cmp.data_id)
                        cache.delete(cache_dataid_md5_key)
                    else:
                        cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                            1, cmp.env.name, cmp.group_status.group.group_id, cmp.data_id)
                        cache.delete(cache_dataid_md5_key)
                        cache_dataid_md5_key = 'ycc.%s.%s.%s.%s.md5' % (
                            4, cmp.env.name, cmp.group_status.group.group_id, cmp.data_id)
                        cache.delete(cache_dataid_md5_key)
                        cache.delete(cache_dataid_md5_key)
                # 变更系统 ok
                collect_index = '%s/%s/%s/%s' % (cmp.data_id, cmp.group_status.group.group_id, cmp.group_status.group.idc.name_ch, cmp.env.name)
                collect({'type': 'configinfo', 'action': 'edit_upload', 'index': collect_index, 'level': 'normal',
                         'message': hidepwd(YCC_ENV, content),
                         'user': username, 'happen_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))})

            # It's tmp for dbupdate || can be delete.
            if ConfigInfoTmp.objects.filter(configinfo_id=euid).exists():
                ConfigInfoTmpSynUpdate(euid, content)

    response1 = {'success': True, 'id': 1,
                 'msg': u'ycc.%s.%s.%s.%s.md5' % (idc, env_id, group_status_upload_id, upload_data_id)}
    # else:
    #     raise YAPIException('请选择上传文件！')
    #     # response1 = {'success': False, 'id': 0, 'msg': u'上传配置组文件失败!!!！'}
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


class GroupV3ViewSet(viewsets.ModelViewSet):
    permission_classes = (YccAdminPermission,)
    queryset = ConfigGroup.objects.filter(status=1)
    serializer_class = GroupSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter, ycc_filters.ConfigGroupFilterBackend)
    filter_fields = ('idc', 'group_id', 'idc__ycc_display')
    search_fields = ('site_name', 'app_name', 'group_id', 'idc__name_ch')


def cache_set(key, value):
    if CATCH_REDIS:
        try:
            cache.set(key, value)
        except Exception:
            pass

class RoomAppsList(generics.ListCreateAPIView):
    queryset = RoomApps.objects.all()
    serializer_class = RoomAppsSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_fields = ('room__id',)
    def perform_create(self, serializer):
        room= self.request.DATA.get('room')
        addapplist =self.request.DATA.get('addapplist')
        deleteapplist =self.request.DATA.get('deleteapplist')
        if addapplist:
            for app in addapplist.split(','):
                RoomApps.objects.create(room_id=room,app_id=app)
        if deleteapplist:
            RoomApps.objects.filter(room_id=room,app_id__in=deleteapplist.split(',')).delete()


class RoomAppsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = RoomApps.objects.all()
    serializer_class = RoomAppsSerializer
    # def perform_destroy(self, instance):

@api_view(['GET'])
@permission_classes((AllowAny, ))
def configcalllist(request):
    '''
    app_id: 查询参数app_id
    group_id: 该app_id对应的配置组
    callapp：调用该配置组的app
    calldomain:调用该配置组的app所属的domain
    callemail：调用该配置组的app所属的domain邮箱
    data_id:该app调用的配置组的配置文件
    '''
    results=[]
    app_id=request.GET.get('app_id')
    group_ids=ConfigGroup.objects.filter(app_id=app_id,status=1).values('group_id').distinct()
    for group_id in group_ids:

        configinfos=ConfigPostInfoV2.objects.filter(group_id=group_id['group_id']).values('ip','data_id').distinct()
        configinfos_jq=ConfigPostInfoV2.objects.filter(group_id=group_id['group_id']+'_jq').values('ip','data_id').distinct()
        if configinfos:
            calllist={}
            for obj in configinfos:
                try:
                    server_app=Server.objects.exclude(server_status_id=400).get(ip=obj['ip']).app
                    if server_app :
                        if not calllist.has_key(server_app.id):
                            domain=server_app.domain
                            domainname=domain.domainname if domain else None
                            domainemail=domain.domainemailgroup if domain else None
                            calllist[server_app.id]={'appname':server_app.name,'site':server_app.site.name if server_app.site else None,'data_id':[obj['data_id']],'domainname':domainname,'domainemail':domainemail}
                        else:
                            if obj['data_id'] not in calllist[server_app.id]['data_id']:
                                calllist[server_app.id]['data_id'].append(obj['data_id'])

                except Server.DoesNotExist:
                    server_app=None
            for key,value in calllist.iteritems():
                results.append(
                    {
                        'app_id':app_id,
                        'group_id':group_id['group_id'],
                        # 'ip':configinfos,
                        'callapp':value['site']+'/'+value['appname'],
                        'calldomain':value['domainname'],
                        'callemail':value['domainemail'],
                        'data_id':value['data_id'],

                    }
                    )
        if configinfos_jq:
            calllist={}
            for obj in configinfos_jq:
                try:
                    server_app=Server.objects.exclude(server_status_id=400).get(ip=obj['ip']).app
                    if server_app:
                        if not calllist.has_key(server_app.id):
                            domain=server_app.domain
                            domainname=domain.domainname if domain else None
                            domainemail=domain.domainemailgroup if domain else None
                            calllist[server_app.id]={'appname':server_app.name,'site':server_app.site.name if server_app.site else None,'data_id':[obj['data_id']],'domainname':domainname,'domainemail':domainemail}
                        else:
                            if obj['data_id'] not in calllist[server_app.id]['data_id']:
                                calllist[server_app.id]['data_id'].append(obj['data_id'])

                except Server.DoesNotExist:
                    server_app=None
            for key,value in calllist.iteritems():
                results.append(
                    {
                        'app_id':app_id,
                        'group_id':group_id['group_id']+'_jq',
                        # 'ip':configinfos,
                        'callapp':value['site']+'/'+value['appname'],
                        'calldomain':value['domainname'],
                        'callemail':value['domainemail'],
                        'data_id':value['data_id'],

                    }
                    )
    return Response(status=status.HTTP_200_OK, data=results)


class SoaSearchFilter(filters.SearchFilter):
    def filter_queryset(self, request, queryset, view):
        search_fields = getattr(view, 'search_fields', None)

        if not search_fields:
            return queryset

        orm_lookups = [self.construct_search(six.text_type(search_field))
                       for search_field in search_fields]

        for search_term in self.get_search_terms(request):
            or_queries = [models.Q(**{orm_lookup: search_term})
                          for orm_lookup in orm_lookups]
            queryset = queryset.filter(reduce(operator.or_, or_queries))

        if not queryset:
            for search_term in self.get_search_terms(request):
                ips = SoaServiceGroupBind.objects.filter(serverstandard__ip__icontains=search_term.strip())
                ids = []
                for item in ips:
                    ids.append(item.soa_service_group.soa_service.id)
                if ids:
                    queryset = SoaService.objects.filter(id__in=ids)
        return queryset


class SoaServiceList(generics.ListAPIView):
    queryset = SoaService.objects.all()
    serializer_class = SoaServiceSerializer
    filter_backends = (SoaSearchFilter, filters.DjangoFilterBackend)
    search_fields = ('service_path',)
    filter_fields = ('app__id', 'room__id', 'env__id', 'id')
    permission_classes = (YccCommitPermission,)

    def get_queryset(self):
        try:
            soa_service_id = self.request.QUERY_PARAMS['id']
            return self.queryset.filter(id=soa_service_id)
        except MultiValueDictKeyError:
            pass
        try:
            server_env_id = self.request.QUERY_PARAMS['server_env_id']
            app_id = self.request.QUERY_PARAMS['app__id']
            room_id = self.request.QUERY_PARAMS['room__id']
            server_env = ServerEnv.objects.get(id=server_env_id)
            soa_env = SoaEnv.objects.filter(server_env_id=server_env.id)
            if soa_env:
                if len(soa_env) > 1:
                    raise YAPIException('SoaEnv vs ServerEnv MultipleObjectsReturned')
                return self.queryset.filter(app__id=app_id, room__id=room_id, env__id=soa_env[0].id)
            else:
                raise YAPIException('SoaEnv DoesNotExist')
        except MultiValueDictKeyError:
            return self.queryset
        except ServerEnv.DoesNotExist:
            raise YAPIException('ServerEnv DoesNotExist')
        except ServerEnv.MultipleObjectsReturned:
            raise YAPIException('ServerEnv MultipleObjectsReturned')


class SoaServiceGroupRegisterList(generics.ListAPIView):
    queryset = SoaServiceGroupRegister.objects.all()
    serializer_class = SoaServiceGroupRegisterSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('port',)
    filter_fields = ('soa_service__app__id', 'soa_service__room__id', 'soa_service__id')
    permission_classes = (YccAdminPermission,)

    def get_queryset(self):
        soa_service_id = self.request.QUERY_PARAMS['soa_service__id']
        if soa_service_id:
            init_result = init_service_reg(soa_service_id)
            if not init_result.get('result'):
                raise YAPIException(init_result['msg'])
            queryset = SoaServiceGroupRegister.objects.filter(soa_service__id=soa_service_id)
        else:
            queryset = self.queryset
        return queryset


class SoaServiceGroupList(generics.ListAPIView):
    queryset = SoaServiceGroup.objects.filter(status=1)
    serializer_class = SoaServiceGroupSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('cname',)
    filter_fields = ('cname', 'status', 'soa_service__id')
    permission_classes = (YccAdminPermission,)


class SoaServiceGroupCreate(generics.CreateAPIView):
    queryset = SoaServiceGroup.objects.filter(status=1)
    serializer_class = SoaServiceGroupSerializer
    permission_classes = (permissions.DjangoModelPermissions,)

    def perform_create(self, serializer):
        servers = self.request.DATA.get('servers', None)
        soa_service_id = self.request.DATA.get('soa_service', None)
        cname = self.request.DATA.get('cname', None)
        if soa_service_id:
            result = add_group(soa_service_id, cname, self.request.user.username)
            if result['result']:
                if servers:
                    servers = servers.split(',')
                    add_result = add_servers(servers, result['instance'].id, self.request.user.username)
                    if not add_result['result']:
                        raise YAPIException(add_result['msg'])
            else:
                raise YAPIException(result['msg'])
        else:
            raise YAPIException('SoaServiceGroupList: soa_service_id is none.')


class SoaServiceGroupDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.DjangoModelPermissions,)
    queryset = SoaServiceGroup.objects.filter(status=1)
    serializer_class = SoaServiceGroupSerializer

    def perform_destroy(self, instance):
        service_group_id = self.request.DATA.get('remove_id')
        if service_group_id:
            del_result = del_group(service_group_id, self.request.user.username)
            if not del_result['result']:
                raise YAPIException(del_result['msg'])
        else:
            raise YAPIException('SoaServiceGroupDetail: service_group_id is none.')


class SoaServiceGroupBindList(generics.ListAPIView):
    queryset = SoaServiceGroupBind.objects.all()
    serializer_class = SoaServiceGroupBindSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('id',)
    filter_fields = ('soa_service_group__id',)
    permission_classes = (YccAdminPermission,)

    def get_queryset(self):
        soa_service_id = self.request.QUERY_PARAMS.get('soa_service_group__id')
        if soa_service_id:
            return SoaServiceGroupBind.objects.filter(soa_service_group__id=soa_service_id)
        else:
            return self.queryset


class SoaServiceGroupBindCreate(generics.CreateAPIView):
    queryset = SoaServiceGroupBind.objects.all()
    serializer_class = SoaServiceGroupBindSerializer
    permission_classes = (permissions.DjangoModelPermissions,)

    def perform_create(self, serializer):
        service_group_id = self.request.DATA.get('soa_service_group')
        servers = self.request.DATA.get('servers')
        if service_group_id:
            if servers:
                servers = servers.split(',')
                add_result = add_servers(servers, service_group_id, self.request.user.username)
                if not add_result['result']:
                    raise YAPIException(add_result['msg'])
            else:
                raise YAPIException('请选择服务器')
        else:
            raise YAPIException('SoaServiceGroupBindList: service_group_id is none.')


class SoaServiceGroupBindDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = SoaServiceGroupBind.objects.all()
    serializer_class = SoaServiceGroupBindSerializer
    permission_classes = (permissions.DjangoModelPermissions,)

    def perform_destroy(self, instance):
        server_bind_ids = self.request.DATA.get('remove_id')
        if server_bind_ids:
            # SOA URL RESULT
            del_result = del_servers(server_bind_ids, self.request.user.username)
            if not del_result['result']:
                raise YAPIException(del_result['msg'])
        else:
            raise YAPIException('SoaServiceGroupBindDetail: server_bind_id is none.')


# UPDATE
@api_view(['POST'])
@permission_classes((AllowAny,))
def soa_service_group_bind_delete(request):
    server_bind_ids = request.DATA.get('remove_id')
    response = Response()
    response['Content-Type'] = 'text/html;charset=UTF-8'
    response.data = 'Finish'
    response.status_code = 200
    if server_bind_ids:
        # SOA URL RESULT
        del_result = del_servers(server_bind_ids, request.user.username)
        if not del_result['result']:
            response.status_code = 400
            response.data = del_result['msg']
    else:
        response.status_code = 400
        response.data = 'SoaServiceGroupBindDetail: server_bind_id is none.'
    return response


def check_soa_api(result, type):
    types = ['add_group', 'del_group', 'add_server', 'del_server']
    add_group_parms = ['0', '1']
    add_server_parms = ['0', '1']
    if type not in types:
        return {'result': False, 'msg': 'TYPE IS ERROR.'}
    if type == 'add_group':
        if not result.get('resultCode'):
            return {'result': False, 'msg': "SOA API \'ADD GROUP\' NOT FOUND."}
        if not result.get('resultCode') in add_group_parms:
            return {'result': False, 'msg': "SOA API \'ADD GROUP\' PRAM ERROR."}
    elif type == 'add_server':
        if not result.get('resultCode'):
            return {'result': False, 'msg': "SOA API \'ADD SERVER\' NOT FOUND."}
        if not result.get('resultCode') in add_server_parms:
            return {'result': False, 'msg': "SOA API \'ADD SERVER\' PRAM ERROR."}
    elif type == 'del_server':
        if not result.get('resultCode'):
            return {'result': False, 'msg': "SOA API \'DEL SERVER\' NOT FOUND."}
        if not result.get('resultCode') in add_server_parms:
            return {'result': False, 'msg': "SOA API \'DEL SERVER\' PRAM ERROR."}
    elif type == 'del_group':
        if not result.get('resultCode'):
            return {'result': False, 'msg': "SOA API \'DEL GROUP\' NOT FOUND."}
        if not result.get('resultCode') in add_server_parms:
            return {'result': False, 'msg': "SOA API \'DEL GROUP\' PRAM ERROR."}
    return {'result': True, 'msg': 'FINISH'}


# UPDATE
def check_soa_refugee_and_init(soa_service_id):
    try:
        soa_service = SoaService.objects.get(id=soa_service_id)
        soa_domain = get_soadomain(soa_service.room.id, soa_service.env.id)
        url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'getGroupsByApp',p:{zkClusterId:'1',app:'%s/hedwig_camps'},z:'%s'}" \
              % (soa_domain.domain, urllib.quote(soa_service.service_path), soa_domain.zone_code)
        info_j = get_url_to_json(url)
        if info_j:
            for info in get_yield_list(info_j):
                if info['text'] == 'refugee':
                    if info['children']:
                        soa_service_group = SoaServiceGroup.objects.get(soa_service__id=soa_service.id, cname='refugee')
                        SoaServiceGroupBind.objects.filter(soa_service_group__id=soa_service_group.id).delete()
                        for ips in get_yield_list(info['children']):
                            ip_port = ips['text'].split(':')
                            port = ip_port.pop()
                            ip = ip_port.pop()
                            server_inst = ServerStandard.objects.get(ip=ip, server_status__id__in=[200, 210])
                            SoaServiceGroupBind.objects.create(serverstandard=server_inst,
                                                               soa_service_group=soa_service_group, port=port)
        return {'result': True, 'msg': "finish."}
    except SoaService.DoesNotExist:
        return {'result': False, 'msg': "check_soa_refugee: SoaService DoesNotExist."}
    except SoaServiceGroup.DoesNotExist:
        return {'result': False, 'msg': "check_soa_refugee: %s have not refugee." % soa_service.service_path}
    except ServerStandard.DoesNotExist:
        return {'result': False, 'msg': "check_soa_refugee: ServerStandard DoesNotExist."}
    except ServerStandard.MultipleObjectsReturned:
        return {'result': False, 'msg': "check_soa_refugee: ServerStandard MultipleObjectsReturned."}


# UPDATE
@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
def get_soa_group_used_servers_show(request):
    soa_service_groupid = request.QUERY_PARAMS['soa_service_groupid']
    if soa_service_groupid:
        ip_list = []
        groups = SoaServiceGroup.objects.filter(status=1, id=soa_service_groupid)
        for group in groups:
            servers = SoaServiceGroupBind.objects.filter(soa_service_group=group.id)
            for server in servers:
                ip_list.append(server.serverstandard.ip.strip() + ':' + str(server.port).strip())
        result = '||'.join(ip_list)
    else:
        result = ''
    response = json.dumps(result, ensure_ascii=False)
    return HttpResponse(response)


# UPDATE
@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
def get_soa_group_servers(request):
    soa_service_id = request.QUERY_PARAMS['soa_service_id']
    group_servers = {}
    if soa_service_id:
        groups = SoaServiceGroup.objects.filter(status=1, soa_service__id=soa_service_id)
        for group in get_yield_list(groups):
            if group.cname not in group_servers.keys():
                group_servers[group.cname] = []
            servers = SoaServiceGroupBind.objects.filter(soa_service_group=group.id)
            for server in servers:
                group_servers[group.cname].append(server.serverstandard.ip.strip() + ':' + str(server.port).strip())
    response = json.dumps(group_servers, ensure_ascii=False)
    return HttpResponse(response)


# UPDATE
@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
def get_del_ip(request):
    soa_service_id = request.QUERY_PARAMS.get('soa_service_group__id')
    result = []
    if soa_service_id:
        soa_service_rows = SoaServiceGroupBind.objects.filter(soa_service_group__id=soa_service_id)
        for ssr in soa_service_rows:
            result.append({
                'id': ssr.id,
                'ip': ssr.serverstandard.ip,
                'port': ssr.port,
                'type': ssr.type,
                'ip_port': '%s:%s' % (ssr.serverstandard.ip.strip(), str(ssr.port).strip())
            })
    return Response(result)


# UPDATE
def add_group(soa_service_id, cname, username='', is_vail_cname=True):
    try:
        soa_server_obj = SoaService.objects.get(id=soa_service_id)
        soa_domain = get_soadomain(soa_server_obj.room.id, soa_server_obj.env.id)
    except SoaService.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupList: SoaService DoesNotExist', 'instance': ''}
    soa_server_group = SoaServiceGroup.objects.filter(soa_service__id=soa_server_obj.id, cname=cname, status=1)
    url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'addGroup',p:{zkClusterId:'1',app:'%s',group:'%s',username:'%s'},z:'%s'}" \
          % (soa_domain.domain, urllib.quote(soa_server_obj.service_path), urllib.quote(cname), username,
             soa_domain.zone_code)
    info_j = get_url_to_json(url)
    if info_j:
        soa_url_group_result = info_j
        # {"msg":"已经完成创建分组","resultCode":"0"} or {"msg":"创建的分组已经存在","resultCode":"1"}
        check_group = check_soa_api(soa_url_group_result, 'add_group')
        if not check_group['result']:
            return {'result': False, 'msg': check_group['msg'], 'instance': ''}
        if soa_url_group_result['resultCode'] in ['0', '1']:
            if soa_url_group_result['resultCode'] == '1':
                if soa_server_group.exists():
                    if is_vail_cname:
                        return {'result': False, 'msg': 'SoaServiceGroupList: 分组已经存在', 'instance': ''}
                    else:
                        instance = soa_server_group[0]
                else:
                    if not cname == 'refugee':
                        check_soa_refugee_and_init(soa_service_id)
                    instance = SoaServiceGroup.objects.create(soa_service=soa_server_obj, cname=cname)
            elif soa_url_group_result['resultCode'] == '0':
                if soa_server_group.exists():
                    instance = soa_server_group[0]
                else:
                    if not cname == 'refugee':
                        check_soa_refugee_and_init(soa_service_id)
                    instance = SoaServiceGroup.objects.create(soa_service=soa_server_obj, cname=cname)
        else:
            return {'result': False, 'msg': 'SoaServiceGroupList: {添加分组}不在接口范围', 'instance': ''}
    else:
        return {'result': False, 'msg': 'SoaServiceGroupList: API URL ERROR.', 'instance': ''}
    change_message = 'PATH: %s || IDC: %s || GROUP_NAME: %s' % (
    soa_server_obj.service_path, soa_server_obj.room.name_ch, cname)
    soa_group_add(username, soa_server_obj.service_path, change_message, soa_server_obj.app.id)
    return {'result': True, 'msg': 'finish', 'instance': instance}


# UPDATE
def del_group(service_group_id, username=''):
    try:
        SoaServiceGroupBind.objects.filter(soa_service_group=service_group_id)
        soa_service_group = SoaServiceGroup.objects.get(id=service_group_id, status=1)
        soa_service = SoaService.objects.get(id=soa_service_group.soa_service.id)
        soa_domain = get_soadomain(soa_service.room.id, soa_service.env.id)
    except SoaServiceGroup.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupDetail: SoaServiceGroup DoesNotExist.'}
    except SoaService.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupDetail: SoaService DoesNotExist.'}
    if soa_service_group.cname == 'refugee':
        return {'result': False, 'msg': '默认分组refugee不能删除'}
    if SoaServiceGroupBind.objects.filter(soa_service_group=service_group_id).exists():
        return {'result': False, 'msg': '请先删除该分组下的机器'}
    # SOA URL RESULT
    # {"msg": "已经完成删除分组操作", "resultCode": "0"}
    idc_code = get_zk_idc(str(soa_service.room.id))
    url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'deleteIpsOrGroups',p:{zkClusterId:'1',app:'%s',groups:{'%s':['all']},username:'%s'},z:'%s'}" \
          % (
              soa_domain.domain, urllib.quote(soa_service.service_path), urllib.quote(soa_service_group.cname),
              username,
              soa_domain.zone_code)
    soa_url_result = get_url_to_json(url)
    if soa_url_result:
        check = check_soa_api(soa_url_result, 'del_group')
        if not check['result']:
            return {'result': False, 'msg': check['msg']}
        if soa_url_result['resultCode'] == '0':
            soa_service_group.delete()
        elif soa_url_result['resultCode'] == '1':
            soa_service_group.delete()
        else:
            return {'result': False, 'msg': 'SoaServiceGroupDetail: {删除分组}不在接口范围'}
    else:
        return {'result': False, 'msg': 'SoaServiceGroupDetail: API URL ERROR.'}
    change_message = 'PATH: %s || IDC: %s || GROUP_NAME: %s' % (
    soa_service.service_path, soa_service.room.name_ch, soa_service_group.cname)
    soa_group_del(username, soa_service.service_path, change_message, soa_service.app.id)
    return {'result': True, 'msg': 'finish'}


# UPDATE
def add_servers(serversid_list, service_group_id, username=''):
    api_true = {}
    api_false = {}
    api_unknow = []
    api_error_show = []
    changeinfo_ip_port = []
    ip_port_list = {}
    try:
        server_group_obj = SoaServiceGroup.objects.get(id=service_group_id)
        soa_service_obj = SoaService.objects.get(id=server_group_obj.soa_service.id)
        soa_domain = get_soadomain(soa_service_obj.room.id, soa_service_obj.env.id)
    except SoaServiceGroup.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupBindList: SoaServiceGroup DoesNotExist.'}
    except SoaService.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupBindList: SoaService DoesNotExist.'}
    if serversid_list:
        for server_id_port in serversid_list:
            # SOA URL RESULT
            # soa_url_result = {"msg": "插入成功", "resultCode": "0"}
            if ':' not in server_id_port:
                return {'result': False, 'msg': 'SoaServiceGroupBindList: parameter must be ":", example id:port'}
            server_id = server_id_port.split(':')[0].strip()
            server_port = server_id_port.split(':')[1].strip()
            try:
                server_reg = ServerStandard.objects.get(id=server_id)
            except ServerStandard.DoesNotExist:
                # type = 0 为一键部署业务的关键参数，不在注册范围的机器该服务会不断尝试添加。
                return {'result': False, 'msg': 'SoaServiceGroupBindList: ServerStandard DoesNotExist.', 'type': 0}
            ip_port = '%s:%s' % (server_reg.ip, server_port)
            changeinfo_ip_port.append(ip_port)
            if not ip_port_list.get(ip_port):
                ip_port_list[ip_port] = {}
            if not ip_port_list[ip_port].get('inst'):
                ip_port_list[ip_port]['inst'] = ''
            if not ip_port_list[ip_port].get('port'):
                ip_port_list[ip_port]['port'] = ''
            ip_port_list[ip_port]['inst'] = server_reg
            ip_port_list[ip_port]['port'] = server_port
    else:
        return {'result': False, 'msg': 'SoaServiceGroupBindList: Parameter server_list is null. Please check it.'}
    for ip_port, val in ip_port_list.iteritems():
        url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'addIPtoGroup',p:{zkClusterId:'1',app:'%s',groups:{'%s':['%s']},username:'%s'},z:'%s'}" \
              % (soa_domain.domain, urllib.quote(soa_service_obj.service_path), urllib.quote(server_group_obj.cname),
                 ip_port,
                 username,
                 soa_domain.zone_code)
        soa_url_result = get_url_to_json(url)
        if soa_url_result:
            check = check_soa_api(soa_url_result, 'add_server')
            if not check['result']:
                api_error_show.append('%s: result check false.' % ip_port)
            if soa_url_result['resultCode'] == '0':
                if ip_port not in api_true.keys():
                    api_true[ip_port] = {}
                if not api_true[ip_port].get('inst'):
                    api_true[ip_port]['inst'] = ''
                if not api_true[ip_port].get('port'):
                    api_true[ip_port]['port'] = ''
                api_true[ip_port]['inst'] = val['inst']
                api_true[ip_port]['port'] = val['port']
            elif soa_url_result['resultCode'] == '1':
                if ip_port not in api_false.keys():
                    api_false[ip_port] = {}
                if not api_false[ip_port].get('inst'):
                    api_false[ip_port]['inst'] = ''
                if not api_false[ip_port].get('port'):
                    api_false[ip_port]['port'] = ''
                api_false[ip_port]['inst'] = val['inst']
                api_false[ip_port]['port'] = val['port']
            else:
                api_unknow.append(ip_port)
        else:
            return {'result': False, 'msg': 'SoaServiceGroupBindList: API URL ERROR.'}
    for at, inst in api_true.iteritems():
        ip_port = at.split(':')
        port = ip_port.pop()
        ip = ip_port.pop()
        soa_service_bind = SoaServiceGroupBind.objects.filter(serverstandard__ip=ip, port=port,
                                                              soa_service_group__id=server_group_obj.id)
        if soa_service_bind.exists():
            continue
        else:
            instance = SoaServiceGroupBind.objects.create(serverstandard=inst['inst'],
                                                          soa_service_group=server_group_obj, port=inst['port'])
    for af, inst in api_false.iteritems():
        ip_port = af.split(':')
        port = ip_port.pop()
        ip = ip_port.pop()
        soa_service_bind = SoaServiceGroupBind.objects.filter(serverstandard__ip=ip, port=port,
                                                              soa_service_group__id=server_group_obj.id)
        if not soa_service_bind.exists():
            instance = SoaServiceGroupBind.objects.create(serverstandard=inst['inst'],
                                                          soa_service_group=server_group_obj, port=inst['port'])
    for an in api_unknow:
        ip_port = af.split(':')
        port = ip_port.pop()
        ip = ip_port.pop()
        soa_service_bind = SoaServiceGroupBind.objects.filter(serverstandard__ip=ip, port=port,
                                                              soa_service_group__id=server_group_obj.id)
        if soa_service_bind.exists():
            api_error_show.append('%s: 本地存在' % an)
        else:
            api_error_show.append('%s: 本地不存在' % an)
    if api_error_show:
        # raise YAPIException('{%s} %s' % ('||'.join(api_error_show), '请联系乐道管理员！'))
        return {'result': False, 'msg': '{%s} %s' % ('||'.join(api_error_show), '请联系乐道管理员！')}
    change_message = 'PATH: %s || IDC: %s || GROUP_NAME: %s || SERVERS: %s' % (
    soa_service_obj.service_path, soa_service_obj.room.name_ch, server_group_obj.cname, changeinfo_ip_port)
    soa_server_add(username, soa_service_obj.service_path, change_message, soa_service_obj.app.id)
    return {'result': True, 'msg': 'finish'}


# UPDATE
def del_servers(server_bind_ids, username=''):
    server_result = {}
    server_list = server_bind_ids.split(',')
    for server_id in server_list:
        # SOA URL RESULT
        try:
            soa_service_group_bind = SoaServiceGroupBind.objects.get(id=server_id)
            soa_service_group = SoaServiceGroup.objects.get(id=soa_service_group_bind.soa_service_group.id,
                                                            status=1)
            soa_service = SoaService.objects.get(id=soa_service_group.soa_service.id)
            soa_domain = get_soadomain(soa_service.room.id, soa_service.env.id)
            if not server_result.get(server_id):
                server_result[server_id] = {}
            if not server_result[server_id].get('soa_service_group_bind'):
                server_result[server_id]['soa_service_group_bind'] = soa_service_group_bind
            if not server_result[server_id].get('soa_domain'):
                server_result[server_id]['soa_domain'] = soa_domain
        except SoaServiceGroup.DoesNotExist:
            return {'result': False,
                    'msg': 'SoaServiceGroupBindDetail: SoaServiceGroup DoesNotExist. Detail: %s' % server_id}
        except SoaService.DoesNotExist:
            return {'result': False,
                    'msg': 'SoaServiceGroupBindDetail: SoaService DoesNotExist. Detail: %s' % server_id}
        except SoaServiceGroupBind.DoesNotExist:
            return {'result': False,
                    'msg': 'SoaServiceGroupBindDetail: SoaServiceGroupBind DoesNotExist. Detail: %s' % server_id}
    if server_result:
        for sr in get_yield_list_iteritems(server_result):
            sr_group_bind = sr['val']['soa_service_group_bind']
            sr_domain = sr['val']['soa_domain']
            ip_port = '%s:%s' % (
                sr_group_bind.serverstandard.ip, sr_group_bind.port)
            url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'deleteIpsOrGroups',p:{zkClusterId:'1',app:'%s',groups:{'%s':['%s']},username:'%s'},z:'%s'}" \
                  % (
                      sr_domain.domain,
                      urllib.quote(sr_group_bind.soa_service_group.soa_service.service_path),
                      urllib.quote(sr_group_bind.soa_service_group.cname),
                      ip_port,
                      username,
                      sr_domain.zone_code
                  )
            soa_url_result = get_url_to_json(url)
            if soa_url_result:
                # {"msg": "已经完成删除机器操作", "resultCode": "0"}
                check = check_soa_api(soa_url_result, 'del_server')
                if not check.get('result'):
                    return {'result': False, 'msg': check.get('msg')}
                if soa_url_result.get('resultCode') == '0':
                    sr_group_bind.delete()
                elif soa_url_result.get('resultCode') == '1':
                    sr_group_bind.delete()
                else:
                    return {'result': False, 'msg': 'SoaServiceGroupBindDetail: {删除机器}不在接口范围'}
            else:
                return {'result': False, 'msg': 'SoaServiceGroupList: API URL ERROR.'}
            change_message = 'PATH: %s || IDC: %s || GROUP_NAME: %s || SERVERS: %s' % (
                sr_group_bind.soa_service_group.soa_service.service_path,
                sr_group_bind.soa_service_group.soa_service.room.name_ch,
                sr_group_bind.soa_service_group.cname,
                '%s:%s' % (
                    sr_group_bind.serverstandard.ip, sr_group_bind.port)
            )
            soa_server_del(username, soa_service.service_path, change_message, soa_service.app.id)
    return {'result': True, 'msg': 'finish'}


# UPDATE
def init_service_reg(soa_service_id):
    flag = True
    flag_ip = []
    try:
        soa_service = SoaService.objects.get(id=soa_service_id)
        soa_domain = get_soadomain(soa_service.room.id, soa_service.env.id)
    except SoaService.DoesNotExist:
        return {'result': False, 'msg': 'SoaServiceGroupRegisterList: SoaService DoesNotExist'}
    soa_service_reg = SoaServiceGroupRegister.objects.filter(soa_service__id=soa_service_id)
    soa_service_reg.delete()

    pool_name = '%s/%s' % (soa_service.app.site.name, soa_service.app.name)
    url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'getAppInfo',p:{zkClusterId:'1',appCode:'%s'},z:'%s'}" \
          % (soa_domain.domain, pool_name, soa_domain.zone_code)
    info_j = get_url_to_json(url)
    if info_j:
        for info in info_j:
            if info:
                for paths in get_yield_list_iteritems(info):
                    if paths['key'] == 'children':
                        for reg_info in get_yield_list(paths['val']):
                            if reg_info:
                                get_path = reg_info.get('service_path').strip()
                                if ',' in get_path:
                                    get_path = get_path.split(',')[0].strip()
                                # print get_path
                                if get_path == soa_service.service_path.strip():
                                    ip_port = reg_info.get('text').split(':')
                                    ip = ip_port.pop(0)
                                    port = ip_port.pop()
                                    try:
                                        server_inst1 = ServerStandard.objects.get(ip=ip,
                                                                                  server_status__id=200)
                                        soa_service_group_reg_inst = SoaServiceGroupRegister.objects.create(
                                            serverstandard=server_inst1, soa_service=soa_service, port=port)
                                        # print 'reg_ip:' + reg_info.get('text')
                                    except ServerStandard.DoesNotExist:
                                        flag = False
                                        if ip not in flag_ip:
                                            flag_ip.append(ip)
        if not flag:
            return {'result': False, 'msg': 'IP 不存在或者状态不是使用中 ：{%s}' % ', '.join(flag_ip)}
    else:
        return {'result': False, 'msg': 'SoaServiceGroupRegisterList: API URL ERROR.'}
    return {'result': True, 'msg': 'finish'}


# UPDATE
@api_view(['PUT', 'POST', 'GET'])
@permission_classes((AllowAny,))
def get_service_reg(request):
    soa_service_id = request.QUERY_PARAMS['soa_service_id']
    result = get_service_reg_realtime(soa_service_id)
    return Response({'result': result['result'], 'msg': result['msg'], 'detail': result['detail']})


def get_service_reg_realtime(soa_service_id):
    flag_ip = []
    flag_ip_list = []
    ips = []
    excepts = []
    excepts_list = []
    status_220 = []
    try:
        soa_service = SoaService.objects.get(id=soa_service_id)
        soa_domain = get_soadomain(soa_service.room.id, soa_service.env.id)
    except SoaService.DoesNotExist:
        return Response({'result': False, 'msg': 'get_service_reg: SoaService DoesNotExist.'})
    except SoaService.MultipleObjectsReturned:
        return Response({'result': False, 'msg': 'get_service_reg: SoaService MultipleObjectsReturned.'})
    pool_name = '%s/%s' % (soa_service.app.site.name, soa_service.app.name)
    url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'getAppInfo',p:{zkClusterId:'1',appCode:'%s'},z:'%s'}" \
          % (soa_domain.domain, pool_name, soa_domain.zone_code)
    # info_j = [
    #     {
    #         "children": [
    #             {
    #                 "children": [],
    #                 "service_path": "/TheStore/601SOA/LaserbeakApp,192.168.26.199:1920",
    #                 "text": "192.168.26.199:1920"
    #             },
    #             {
    #                 "children": [],
    #                 "service_path": "/TheStore/601SOA/LaserbeakApp,192.168.1.1:2000",
    #                 "text": "192.168.1.1:2000"
    #             }
    #         ],
    #         "text": "/TheStore/601SOA/LaserbeakApp"
    #     }
    # ]
    info_j = get_url_to_json(url)
    if info_j:
        for info in info_j:
            if info:
                for paths in get_yield_list_iteritems(info):
                    if paths['key'] == 'children':
                        for reg_info in get_yield_list(paths['val']):
                            if reg_info:
                                get_path = reg_info.get('service_path').strip()
                                if ',' in get_path:
                                    get_path = get_path.split(',')[0].strip()
                                if get_path == soa_service.service_path.strip():
                                    ip_port = reg_info.get('text').split(':')
                                    ip = ip_port.pop(0)
                                    port = ip_port.pop()
                                    server_inst1 = ServerStandard.objects.filter(ip=ip)
                                    try:
                                        # server_inst1 = ServerStandard.objects.get(ip=ip,
                                        #                                           server_status__id=200)
                                        # soa_service_group_reg_inst = SoaServiceGroupRegister.objects.create(
                                        #     serverstandard=server_inst1, soa_service=soa_service, port=port)
                                        server_inst1 = server_inst1.get(server_status__id=200)
                                        ips.append({
                                            'server_id': server_inst1.id,
                                            'ip': '%s:%s' % (ip, port)
                                        })
                                    except ServerStandard.DoesNotExist:
                                        server_inst1 = server_inst1.filter(server_status__id=220)
                                        if server_inst1.exists():
                                            status_220.append('%s:%s' % (ip, port))
                                        else:
                                            if ip not in flag_ip:
                                                flag_ip.append(ip)
                                    except ServerStandard.MultipleObjectsReturned:
                                        if ip not in excepts:
                                            excepts.append(ip)
        if excepts:
            for ip in excepts:
                excepts_list.append({
                    'ip': ip
                })
        if flag_ip:
            for ip in flag_ip:
                flag_ip_list.append({
                    'ip': ip
                })
    else:
        return {'result': False, 'msg': 'get_service_reg: API URL ERROR. Detail: %s' % url}
    return {'result': True, 'msg': 'finish.',
            'detail': {'in_ip': ips, 'notin_ip': flag_ip_list, 'except_ip': excepts_list, 'status_220': status_220}}


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_userdserver_regserver(request):
    try:
        response = Response()
        response['Content-Type'] = 'text/html;charset=UTF-8'
        bind_list = []
        reg_list = []
        reg_result = []
        available_list = []
        available_result = []
        soa_group_id = request.QUERY_PARAMS['group_id']
        soa_group = SoaServiceGroup.objects.get(id=soa_group_id)
        soa_bind = SoaServiceGroupBind.objects.filter(soa_service_group__id=soa_group.id)
        soa_reg = get_service_reg_realtime(soa_group.soa_service.id)
        if soa_reg['result']:
            for reg in soa_reg['detail']['in_ip']:
                reg_list.append(reg['ip'])
                available_list.append(reg['ip'])
        if soa_bind:
            for bind in soa_bind:
                ip_port_tmp = '%s:%s' % (bind.serverstandard.ip, bind.port)
                if ip_port_tmp in available_list:
                    available_list.remove(ip_port_tmp)
                bind_list.append({
                    "id": bind.id,
                    "soa_service_group": bind.soa_service_group.id,
                    "type": bind.type,
                    "server_ip": bind.serverstandard.ip,
                    "port": bind.port
                })
        if available_list:
            for al in available_list:
                ip_al = al.split(':')[0]
                port_al = al.split(':')[1]
                try:
                    server_stand = ServerStandard.objects.get(ip=ip_al, server_status__id=200)
                except ServerStandard.DoesNotExist:
                    soa_reg['detail']['notin_ip'].append(ip_al)
                    continue
                except ServerStandard.MultipleObjectsReturned:
                    soa_reg['detail']['except_ip'].append(ip_al)
                    continue
                available_result.append({
                    'server_id': server_stand.id,
                    'ip': al,
                    'value': '%s:%s' % (server_stand.id, port_al)
                })
        if reg_list:
            for rl in reg_list:
                ip_al = rl.split(':')[0]
                try:
                    server_stand = ServerStandard.objects.get(ip=ip_al, server_status__id=200)
                except ServerStandard.DoesNotExist:
                    soa_reg['detail']['notin_ip'].append(ip_al)
                    continue
                except ServerStandard.MultipleObjectsReturned:
                    soa_reg['detail']['except_ip'].append(ip_al)
                    continue
                reg_result.append({
                    'server_id': server_stand.id,
                    'ip': rl
                })
        response.data = {
            "userd_server": bind_list,
            "available_server": {
                'available_ip': available_result,
                'notin_ip': soa_reg['detail']['notin_ip'],
                'except_ip': soa_reg['detail']['except_ip']
                # 'not_200':
            },
            "reg_server": reg_result
        }
    except KeyError:
        response.status_code = 400
        response.data = 'Not find group_id.'
    except SoaServiceGroup.DoesNotExist:
        response.status_code = 400
        response.data = 'Not find group.'
    except ValueError as e:
        print e
        response.status_code = 400
        response.data = 'Not find group_ids.'
    except ServerStandard.DoesNotExist:
        response.status_code = 400
        response.data = 'ServerStandard DoesNotExist.'
    except ServerStandard.MultipleObjectsReturned:
        response.status_code = 400
        response.data = 'ServerStandard MultipleObjectsReturned.'
    return response


# UPDATE
@api_view(['GET'])
@permission_classes((AllowAny,))
def get_app_idc_env(request):
    try:
        username = request.QUERY_PARAMS['username']
    except KeyError:
        username = 'ALL'
    dd_users = ''
    env_list = []
    soa_env = SoaEnv.objects.all()
    for env in soa_env:
        env_list.append({
            'id': env.id,
            'name': env.name,
            'name_ch': env.name_ch,
        })
    idc_list = []
    soa_idc = Room.objects.filter(status=1)
    for idc in soa_idc:
        idc_list.append({
            'id': idc.id,
            'name': idc.name,
            'name_ch': idc.name_ch,
        })
    app_list = []
    apps = App.objects.filter(status=0)
    if not username == 'ALL' and not request.user.is_superuser:
        domain_id_list = []
        dd_users = DdUsers.objects.filter(username=username)
        if dd_users:
            dd_users = dd_users[0]
            for domain in dd_users.domains.all():
                domain_id_list.append(domain.id)
            apps = apps.filter(domainid__in=domain_id_list)
    if username == 'ALL' or dd_users:
        for app in apps:
            if SoaService.objects.filter(app__id=app.id).exists():
                app_list.append({
                    'id': app.id,
                    'site_name': app.site.name,
                    'app_name': app.name,
                    'site_app_name': app.site.name + '_' + app.name
                })
    result = {
        'app': app_list,
        'idc': idc_list,
        'env': env_list
    }
    return HttpResponse(json.dumps(result, ensure_ascii=False))


def get_url_to_json(url):
    try:
        data = urllib2.urlopen(url)
        return json.loads(data.read())
    except urllib2.HTTPError as e:
        print '%s\nPlease check url. ' % e
        return False
    except Exception as e:
        print e
        print 'Other error.'
        return False


def get_zk_idc(idc_id):
    zone = ''
    if idc_id == '1':
        zone = 'ZONE_NH'
    elif idc_id == '4':
        zone = 'ZONE_JQ'
    return zone


def get_yield_list_iteritems(list_iteritems):
    for key, val in list_iteritems.iteritems():
        yield {
            'key': key,
            'val': val
        }


def get_yield_list(li):
    for l in li:
        yield l


def get_soadomain(room_id, env_id):
    try:
        soa_domain = SoaDomain.objects.get(idc=room_id, env=env_id)
    except SoaDomain.MultipleObjectsReturned:
        raise YAPIException('SoaDomain MultipleObjectsReturned')
    return soa_domain


class ExceptionConfigList(generics.ListCreateAPIView):
    queryset = ExceptionConfigAccessDetail.objects.all()
    serializer_class = ExceptionConfigAccessDetailSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, ycc_filters.ConfigExceptionFilterBackend)
    search_fields = ('ip', 'group_id', 'data_id', 'site__name', 'app__name', 'domain__domainname')
    filter_fields = ('error', 'app', 'domain')
