# -*- coding: utf-8 -*-
from rest_framework import generics
from serializers import *
import time, random
from rest_framework.exceptions import APIException
from rest_framework import status
from asset.models import IpTotal
from rest_framework import filters, viewsets
from change.utiltask import *
import json, urllib
from rest_framework.response import Response
from assetv2.settingsapi import NVWA_PHYSICS_INSTALL_API, NVWA_VIRTURE_INSTALL_API, SERVER_ZABBIX_ID, SERVER_MAILLIST,SERVER_ZABBIX_API, SERVER_DELETE_DOCKER, EMAIL_LIST_FOR_HAPROXY
from hybrid.models import HybridRequirementDetail
from util.sendmail import sendmail_html, sendmail_v2
from util.timelib import stamp2str
from deploy.utils.Pika import Pika
from django.template import loader
from rest_framework.views import APIView
from rest_framework import permissions
from django.conf import settings
import requests
import threading
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from util.utils import *
from deploy.utils.HaproxyRegistration import HaproxyRegistration
from deploy.utils.HedwigRegistration import HedwigRegistration
from celery.utils import uuid
from deploy.models import DeployPath, TNewPool, TDockerIp
from deploy.utils.Utils import ssh
import permissions as mypermissions
import logging
from monitor.process.process import process_notification
from ycc.views_api import del_servers
from ycc.models import SoaServiceGroupBind

logger = logging.getLogger('django')

class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class ServerOsTemplateList(generics.ListCreateAPIView):
    """
    服务器操作系统模板.

    输入参数： 无

    输出参数：

    * id        -   pk
    * cname   -   女娲装机用标识符
    * show_name - CMDB展示用说明
    * status  -   1 为可用
    """

    queryset = ServerOsTemplate.objects.filter(status=1)
    serializer_class = ServerOsTemplateSerializer


class ServerAppTemplateList(generics.ListCreateAPIView):
    """
    服务器应用模板.

    输入参数： 无

    输出参数：

    * id        -   pk
    * cname   -   女娲装机用标识符
    * show_name - CMDB展示用说明
    * status  -   1 为可用
    """

    queryset = ServerAppTemplate.objects.filter(status=1)
    serializer_class = ServerAppTemplateSerializer


class ServerByIpDetail(generics.RetrieveUpdateAPIView):
    """
    服务器列表（按IP筛选/女娲装机成功回写CMDB）.

    输入参数： 无

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机
    * server_type_name - 类型英文名称
    * server_status_id -  30-待装机 50-装机中  100-空闲  200-使用中   210-维护中 220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerSerializer
    lookup_field = 'ip'

    # def perform_update(self, serializer):
    #     is_first_install = self.request.DATA.get('is_first_install', None)
    #     instance = serializer.save()
    #     if is_first_install is not None and int(is_first_install) == 1:
    #         CB_server_installed(instance.ip, self.request.user.username)
    #
    #         api_url = SERVER_ZABBIX_API['FREE'] % (SERVER_ZABBIX_ID, instance.ip)
    #         res = json.loads(urllib.urlopen(api_url).read())
    #         zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
    #         if res['success'] == True:
    #             CB_zabbix_free(instance.ip, self.request.user.username)
    #         else:
    #             mail_title = u'装机成功，开启zabbix监控异常：%s' % instance.ip
    #             mail_list = SERVER_MAILLIST['installed']
    #             html_content = loader.render_to_string('mail/server.html',{'action':'虚拟机装机成功','action_time':stamp2str(time.time()),
    #                                                                        'poolname':None,'ips':instance.ip,'username':self.request.user.username,
    #                                                                        'sitename':None,'server_change_content':zabbix_content})
    #             sendmail_html(mail_title,html_content,mail_list)

class ServerBySnDetail(generics.RetrieveUpdateAPIView):
    """
    服务器装机（按SN筛选/调女娲装机）.

    输入参数： 无

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机
    * server_type_name - 类型英文名称
    * server_status_id - 30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerSerializer
    lookup_field = 'sn'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        is_call_nvwa = self.request.QUERY_PARAMS.get('is_call_nvwa', None)
        is_virtual = self.request.QUERY_PARAMS.get('is_virtual', '0')
        sn = serializer.data.get('sn', None)
        ip = serializer.data.get('ip', None)
        if is_call_nvwa is not None and is_call_nvwa == '1':
            if is_virtual == '0':
                api_url = NVWA_PHYSICS_INSTALL_API + '&option=' + sn
            elif is_virtual == '1':
                server = Server.objects.exclude(server_status_id=400).get(sn=sn)
                parent_server = Server.objects.exclude(server_status_id=400).get(assetid=server.parent)
                # xen_name = parent_server.app.name
                host_type = server.parent_server_obj.app.name
                if host_type == 'xenserver':
                    host_type = 'CentOSxen'
                api_url = NVWA_VIRTURE_INSTALL_API + '&option=%s%s%s' % (sn, '%20', host_type)
            response = json.loads(urllib.urlopen(api_url).read())
            if response['success'] == 'true':
                Server.objects.exclude(server_status_id=400).filter(sn=sn).update(server_status_id=50)
                CB_server_installing(ip, self.request.user.username)

                api_url = SERVER_ZABBIX_API['DISABLE'] % (SERVER_ZABBIX_ID, instance.ip)
                res = json.loads(urllib.urlopen(api_url).read())
                zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
                if res['success'] == True:
                    CB_zabbix_disable(instance.ip, self.request.user.username)
                else:
                    mail_title = u'正在装机，关闭zabbix监控异常：%s' % instance.ip
                    mail_list = SERVER_MAILLIST['installing']
                    html_content = loader.render_to_string('mail/server.html',{'action':'装机','action_time':stamp2str(time.time()),
                                                                               'poolname':None,'ips':instance.ip,'username':self.request.user.username,
                                                                               'sitename':None,'server_change_content':zabbix_content})
                    sendmail_html(mail_title,html_content,mail_list)
            return Response(response)
        return Response(serializer.data)

    def perform_update(self, serializer):
        is_first_install = self.request.DATA.get('is_first_install', None)
        instance = serializer.save()
        if is_first_install is not None and int(is_first_install) == 1:
            CB_server_installed(instance.ip, self.request.user.username)
            Asset.objects.filter(assetid=instance.assetid).update(new_status=2)

            api_url = SERVER_ZABBIX_API['FREE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_free(instance.ip, self.request.user.username)
            else:
                mail_title = u'装机成功，开启zabbix监控异常：%s' % instance.ip
                mail_list = SERVER_MAILLIST['installed']
                html_content = loader.render_to_string('mail/server.html',{'action':'物理机装机成功','action_time':stamp2str(time.time()),
                                                                           'poolname':None,'ips':instance.ip,'username':self.request.user.username,
                                                                           'sitename':None,'server_change_content':zabbix_content})
                sendmail_html(mail_title,html_content,mail_list)

    # def get_queryset(self):
    #     queryset = Server.objects.exclude(server_status_id=400)
    #     is_call_nvwa = self.request.QUERY_PARAMS.get('is_call_nvwa', None)
    #     sn = self.lookup_field
    #     print sn
    #     if is_call_nvwa is not None and is_call_nvwa == 1:
    #         sn = self.request.DATA.get('sn', None)
    #         print sn


class ServerDetail(generics.RetrieveAPIView):
    """
    服务器列表（按ID筛选）.

    输入参数： 无

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机
    * server_type_name - 类型英文名称
    * server_status_id - 30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerSerializer


class ServerList(generics.ListCreateAPIView):
    """
    服务器列表（按ID筛选）.

    输入参数：
    * app_id    -   按app_id筛选
    * page_size -   每页展示最大数据
    * tag_id    -   按服务器应用筛选
    * server_env_id - 按照环境筛选  1-stg环境  2-生产环境

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * sn        -   sn
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机
    * server_type_name - 类型英文名称
    * server_status_id -  30-待装机 50-装机中  100-空闲  200-使用中   210-维护中 220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('assetid', 'ip', 'sn', 'hostname')

    def get_queryset(self):
        queryset = Server.objects.exclude(server_status_id=400).order_by('app_id')
        app_id = self.request.QUERY_PARAMS.get('app_id', None)
        server_env_id = self.request.QUERY_PARAMS.get('server_env_id', None)

        if app_id is not None:
            appids = app_id.split(',')
            if len(appids) >= 2:
                queryset = queryset.filter(app_id__in=appids)
            else:
                queryset = queryset.filter(app_id=app_id)

        if server_env_id is not None:
            queryset = queryset.filter(server_env_id=server_env_id)

        return queryset

    def perform_create(self, serializer):
        asset_id = self.request.DATA.get('asset_id', None)
        install_type = self.request.DATA.get('install_type', None)
        server_env_id = self.request.DATA.get('server_env_id', None)
        server_os_template_id = self.request.DATA.get('server_os_template_id', None)
        server_app_template_id = self.request.DATA.get('server_app_template_id', None)

        install_type = int(install_type)
        server_env_id = int(server_env_id)
        server_os_template_id = int(server_os_template_id)
        server_app_template_id = int(server_app_template_id)

        if asset_id is None or install_type is None:
            raise YAPIException('asset_id or install_type or server_env_id or server_os_template_id or '
                                'server_app_template_id can not allowed None')
        #检查assetid的正确性
        try:
            asset = Asset.objects.get(pk=asset_id)
        except Asset.DoesNotExist:
            raise YAPIException('asset_id does not exists')
        if asset.new_status > 0 :
            raise YAPIException('asset_id has already deploy,please contact lizhigang!')
        if asset.rack_id == 0:
            raise YAPIException('asset_id has not deploy to rack!')
        #确保设备在server表中无记录
        if Server.objects.exclude(server_status_id=400).filter(assetid=asset.assetid).exists():
            raise YAPIException('server table has already exists,please contact lizhigang!')
        #IP、管理IP检查，设备绑定过IP、MGIP是不允许自动分配IP的
        if IpTotal.objects.filter(asset_info=asset.assetid).exists():
            raise YAPIException('asset has already bind IP or MGIP,please contact lizhigang!')
        #IP分配
        assetid = asset.assetid
        idc = asset.rack.room.id
        if idc == 1: #DCB南汇 从起始点分配
            mgip_info = IpTotal.objects.filter(type=2, idc=idc, ip3__gte=8,
                                                   is_used=0, status=1)[0:1]
            ip_info = self._get_ip_obj(int(install_type), idc, server_env_id)
        elif idc == 4 or idc == 10: #DCD金桥，从起始点分配，并且结合机架设定的IP范围
            mgip_info = IpTotal.objects.filter(type=2, idc=4, is_used=0, status=1)[0:1]
            ip_info = self._get_ip_obj(int(install_type), idc, server_env_id)
        else:
            raise YAPIException('idc does not exists!')
        if len(mgip_info) == 0 :
            raise YAPIException('MGIP pool has already full,please ext MGIP pool')
        # if ip_info is None:
        if not ip_info:
            raise YAPIException('IP pool has already full,please ext IP pool')
        mgip = mgip_info[0]
        ip = ip_info[0]
        #更新IP、管理IP表
        mgip.is_used = 1
        mgip.asset_info = assetid
        mgip.save()

        CB_mgip = {
            'assetid':  assetid,
            'mgip': mgip.ip,
        }

        CB_mgip_bindip_by_initasset(assetid, self.request.user.username, json.dumps(CB_mgip, ensure_ascii=False))

        ip.is_used = 1
        ip.asset_info = assetid
        ip.save()

        CB_ip = {
            'assetid':  assetid,
            'ip':       ip.ip,
        }

        CB_ip_bindip_by_initasset(assetid, self.request.user.username, json.dumps(CB_ip, ensure_ascii=False))

        rack_name = asset.rack.real_name
        rack_id = asset.rack_id
        if rack_name:
            try:
                rack_id = Rack.objects.get(name=rack_name,valid=1, room_id=asset.rack.room_id).id
            except (Rack.DoesNotExist, Rack.MultipleObjectsReturned):
                rack_id = asset.rack_id

        serializer.save(assetid=assetid, sn=asset.service_tag, ip=ip.ip, mgmt_ip=mgip.ip,
                       hostname=assetid, server_type_id=1, server_class_id=install_type,
                       server_status_id=30, server_env_id=server_env_id,
                       server_os_template_id=server_os_template_id,
                       server_app_template_id=server_app_template_id, created_time=int(time.time()),
                       rack_id=rack_id)

        CB_server = {
            'assetid':  assetid,
            'sn': asset.service_tag,
            'ip': ip.ip,
            'mgmt_ip': mgip.ip,
            'hostname': assetid,
            'server_type_id': 1,
            'server_class_id': install_type,
            'server_status_id': 30,
            'server_env_id': server_env_id,
            'server_os_template_id': server_os_template_id,
            'server_app_template_id': server_app_template_id,
        }

        CB_server_create_bycreateasset(assetid, self.request.user.username, json.dumps(CB_server, ensure_ascii=False))

        #更新asset表，状态改为已申请
        asset.new_status = 1
        asset.save()


    def _get_ip_obj(self, install_type, idc, server_env_id):
        if install_type <= 0 or install_type >= 13:
            raise YAPIException('install_type value is not allowed')
        if idc == 1: #南汇IP
            if server_env_id == 1: #stg环境
                raise YAPIException('DCB IDC can not allowed deploy stging env')
            elif server_env_id ==2: #production
                if install_type == 1: #xenserver
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=53, ip3__lte=84,
                                                  ip4__gte=201, ip4__lte=215, is_used=0, status=1)[0:1]
                elif install_type == 2: #db
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=0, ip3__gte=5, ip3__lte=9,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 3: #物理机应用
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=47, ip3__lte=50,
                                                  ip4__gte=157, ip4__lte=160, is_used=0, status=1)[0:1]
                elif install_type == 4: #squid
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=100, ip3__lte=178,
                                                  ip4__gte=161, ip4__lte=172, is_used=0, status=1)[0:1]
                elif install_type == 5: #memcache
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=100, ip3__lte=178,
                                                  ip4__gte=173, ip4__lte=190, is_used=0, status=1)[0:1]
                elif install_type == 6: #hadoop
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=221, ip3__lte=222,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 7: #后台
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3=225,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 8: #软负载项目
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=223, ip3__lte=224,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 9: #特殊业务
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=100, ip3__lte=178,
                                                  ip4__gte=151, ip4__lte=156, is_used=0, status=1)[0:1]
                elif install_type == 10 or install_type == 11: #其他
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=100, ip3__lte=178,
                                                  ip4__gte=231, ip4__lte=250, is_used=0, status=1)[0:1]
                elif install_type == 12:
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=4, ip3__gte=179, ip3__lte=198,
                                                  ip4__gte=211, ip4__lte=230, is_used=0, status=1)[0:1]
        elif idc == 4 or idc == 10: #金桥
            idc = 4
            if server_env_id == 1: #stg环境
                if install_type == 12:
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=248, ip3__lte=250, ip4__gte=221,
                                                  ip4__lte=230, is_used=0, status=1)[0:1]
                else:
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=63, ip3__gte=20, ip3__lte=21, ip4__gte=221,
                                                  ip4__lte=230, is_used=0, status=1)[0:1]
            elif server_env_id ==2: #production
                if install_type == 1: #xenserver
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=53, ip3__lte=84,
                                                  ip4__gte=201, ip4__lte=215, is_used=0, status=1)[0:1]
                elif install_type == 2: #db
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=1, ip3__lte=9,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 3: #物理机应用
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=47, ip3__lte=50,
                                                  ip4__gte=157, ip4__lte=160, is_used=0, status=1)[0:1]
                elif install_type == 4: #squid
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=29, ip3__lte=199,
                                                  ip4__gte=161, ip4__lte=172, is_used=0, status=1)[0:1]
                elif install_type == 5: #memcache
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=29, ip3__lte=199,
                                                  ip4__gte=173, ip4__lte=190, is_used=0, status=1)[0:1]
                elif install_type == 6: #hadoop
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=221, ip3__lte=222,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 7: #后台
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3=225,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 8: #软负载项目
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=223, ip3__lte=224,
                                                  is_used=0, status=1)[0:1]
                elif install_type == 9: #特殊业务
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=29, ip3__lte=199,
                                                  ip4__gte=151, ip4__lte=156, is_used=0, status=1)[0:1]
                elif install_type == 10 or install_type == 11: #其他
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=100, ip3__lte=199,
                                                  ip4__gte=231, ip4__lte=250, is_used=0, status=1)[0:1]
                elif install_type == 12:
                    return IpTotal.objects.filter(type=3, idc=idc, ip2=17, ip3__gte=11, ip3__lte=30,
                                                  ip4__gte=211, ip4__lte=230, is_used=0, status=1)[0:1]


class ServerDetailList(generics.ListAPIView):

    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerDetailSerializer
    filter_backends = (filters.SearchFilter,  filters.DjangoFilterBackend)
    search_fields = ('assetid', 'sn', 'ip', 'parent_ip', 'hostname')
    filter_fields = ('parent_ip', 'app_id', 'rack_id')

class ResourcesVmList(generics.ListCreateAPIView):
    """
    宿主机资源池.

    输入参数： 无

    输出参数：

    * id        -   pk
    * host_ip   -   宿主机IP
    * available_num - 可用数量
    * used_num  -   已经使用的数量
    * script_num - 已经使用的数量（脚本采集专用）
    * total_num -   一台宿主机可虚数量
    * status    -   状态
    * created   -   创建时间
    * update    -   修改时间
    * script_updated - 脚本修改时间
    """

    queryset = ResourcesVm.objects.exclude(status=0)
    serializer_class = ResourcesVmSerializer

    def perform_create(self, serializer):
        serializer.save(created=time.time())


class ResourcesVmDetail(generics.RetrieveUpdateAPIView):
    """
    宿主机资源池.

    输入参数： 无

    输出参数：

    * id        -   pk
    * host_ip   -   宿主机IP
    * hardware_id - 硬件配置ID
    * available_num - 可用数量
    * used_num  -   已经使用的数量
    * script_num - 已经使用的数量（脚本采集专用）
    * total_num -   一台宿主机可虚数量
    * status    -   状态
    * created   -   创建时间
    * update    -   修改时间
    * script_updated - 脚本修改时间
    """

    queryset = ResourcesVm.objects.exclude(status=0)
    serializer_class = ResourcesVmSerializer

    def perform_create(self, serializer):
        serializer.save(created=time.time())


class ServerInstallList(generics.ListCreateAPIView):
    """
    服务器列表（装机界面用）.

    输入参数：
    *

    输出参数：

    * id        -   pk
    * sn        -   序列号
    * assetid   -   资产号
    * ip        -   IP
    * mgmt_ip   -   管理IP
    * mac       -   mac地址
    * server_os_template_id   -   系统模板ID
    * server_os_template_name -   系统模板名称
    * server_app_template_id   -   应用模板ID
    * server_app_template_name -   应用模板名称
    * server_type_id - 类型ID  0-虚拟机  1-物理机
    * server_type_name  -  类型名称
    * server_status_id -  30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中  230-预上架失败 300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 真实机架号
    * room - idc
    """
    queryset = Server.objects.exclude(server_status_id=400).order_by('-id')
    serializer_class = ServerInstallSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('sn', 'assetid', 'ip', 'mgmt_ip', 'mac')
    filter_fields = ('server_status_id','server_type_id')

    def get_queryset(self):
        queryset = Server.objects.exclude(server_status_id=400)
        query_key = self.request.QUERY_PARAMS.get('query_key', None)
        query_value = self.request.QUERY_PARAMS.get('query_value', None)
        if query_value is not None:
            filter_list = query_value.split(',')
            if query_key is not None:
                if 'ip' == query_key:
                    queryset = queryset.filter(ip__in=filter_list)
                elif 'assetid' == query_key:
                    queryset = queryset.filter(assetid__in=filter_list)
                else:
                    queryset = queryset.filter(hostname__in=filter_list)
        return queryset

    def perform_create(self, serializer):
        server_env_id = int(self.request.DATA.get('server_env_id', 0))
        template_id = self.request.DATA.get('template_id', None)
        parent = self.request.DATA.get('parent', None)
        count = int(self.request.DATA.get('count', 0))

        if server_env_id == 0 or template_id is None or parent is None or count == 0:
            raise YAPIException('server_env_id or template_id or parent or count '
                                ' can not allowed None')

        try:
            parent_server = Server.objects.exclude(server_status_id=400).get(assetid=parent)
        except Server.DoesNotExist:
            raise YAPIException('parent is not exists.')

        vir_num = Server.objects.exclude(server_status_id=400).filter(parent=parent).count()
        vir_total = vir_num+count
        # if vir_total > 10:
        #     raise YAPIException('the suzhuji is full.can not create virtual machine.')

        ip_t = parent_server.ip.split('.')
        if server_env_id == 1:
            create_ip = IpTotal.objects.filter(type=3, is_used=0, status=1, ip1=int(ip_t[0]), ip2=int(ip_t[1]),
                                               ip3=int(ip_t[2]), ip4__lte=220)[0:count]
        else:
            create_ip = IpTotal.objects.filter(type=3, is_used=0, status=1, ip1=int(ip_t[0]), ip2=int(ip_t[1]),
                                               ip3=int(ip_t[2]), ip4__lte=150)[0:count]
        if create_ip is None:
            raise YAPIException('virtual IP pool has full.please contact lizhigang.')

        if len(create_ip) < count:
            raise YAPIException('virtual IP pool has not enough.please contact lizhigang.')

        j = Server.objects.filter(parent=parent).count() + 1
        last = {}
        aa = None
        for item in create_ip:
            parent_sn = parent_server.sn
            assetid = '%s__%s' % (parent, item.ip)
            sn = '%s__%s' % (parent_sn, item.ip.replace(".",""))
            hostname_last = u"-vm0" + str(j)
            hostname = parent + hostname_last
            parent_ip = parent_server.ip
            rack_id = parent_server.rack_id
            if item == create_ip[0]:
                aa = item.ip
                last = {
                    'assetid': assetid,
                    'sn': sn,
                    'ip': item.ip,
                    'hostname': hostname,
                    'server_type_id': 0,
                    'server_os_template_id': 0,
                    'server_app_template_id': 0,
                    'server_status_id': 30,
                    'server_env_id': server_env_id,
                    'created_time': int(time.time()),
                    'template_id': template_id,
                    'parent': parent,
                    'parent_ip': parent_ip,
                    'rack_id': rack_id,
                }

                item.is_used = 1
                item.asset_info = assetid
                item.save()
                CB_ip_info = {
                    'assetid': assetid,
                    'ip': item.ip,
                }
                CB_ip_createip_bycreatevm(item.ip, self.request.user.username,
                                                    json.dumps(CB_ip_info, ensure_ascii=False))

                j = j + 1
                continue

            server, created = Server.objects.exclude(server_status_id = 400).get_or_create(assetid=assetid, sn=sn, defaults={
                'ip'             : item.ip,
                'hostname'       : hostname,
                'app_id'         : 0,
                'server_env_id'  : server_env_id,
                'server_type_id' : 0,
                'server_status_id': 30,
                'template_id':  template_id,
                'parent'         : parent,
                'parent_ip'      : parent_ip,
                'server_os_template_id': 0,
                'server_app_template_id': 0,
                'created_time': int(time.time()),
                'rack_id': rack_id,

            })

            if not created:
                server.ip             = item.ip
                server.hostname       = hostname
                server.server_type_id = 0
                server.server_env_id  = server_env_id
                server.parent         = parent
                server.parent_ip      = parent_ip
                server.rack_id        = rack_id
                server.template_id    = template_id
                server.server_os_template_id = 0
                server.server_app_template_id = 0
                server.save()

            CB_server = {
                'assetid':  server.assetid,
                'sn': server.sn,
                'ip': server.ip,
                'hostname': server.hostname,
                'server_type_id': server.server_type_id,
                'server_class_id': server.server_class_id,
                'server_status_id': server.server_status_id,
                'server_env_id': server.server_env_id,
                'server_os_template_id': server.server_os_template_id,
                'server_app_template_id': server.server_app_template_id,
            }
            CB_server_createvm(assetid, self.request.user.username, json.dumps(CB_server, ensure_ascii=False))

            item.is_used = 1
            item.asset_info = assetid
            item.save()

            CB_ip_info = {
                'assetid': assetid,
                'ip': item.ip,
            }
            CB_ip_createip_bycreatevm(item.ip, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))

            j = j + 1
        serializer.save(**last)
        CB_server_createvm(aa, self.request.user.username, json.dumps(last, ensure_ascii=False))


class ServerInstallDetail(generics.RetrieveUpdateAPIView):
    """
    服务器单页 （修改主机状态：置为待装机/装机中/空闲）.

    输入参数：
    *

    输出参数：

    * id        -   pk
    * sn        -   序列号
    * assetid   -   资产号
    * ip        -   IP
    * mgmt_ip   -   管理IP
    * mac       -   mac地址
    * server_os_template_id   -   系统模板ID
    * server_os_template_name -   系统模板名称
    * server_app_template_id   -   应用模板ID
    * server_app_template_name -   应用模板名称
    * server_type_id - 类型ID  0-虚拟机  1-物理机
    * server_type_name  -  类型名称
    * server_status_id -  30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中 230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 真实机架号
    * room - idc
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerInstallSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.server_status_id == 30:
            CB_server_resetinstall(instance.ip, self.request.user.username)
            api_url = SERVER_ZABBIX_API['DISABLE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            if res['success'] == True:
                CB_zabbix_disable(instance.ip, self.request.user.username)
        elif instance.server_status_id == 50:
            CB_server_installing(instance.ip, self.request.user.username)

            api_url = SERVER_ZABBIX_API['DISABLE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            if res['success'] == True:
                CB_zabbix_disable(instance.ip, self.request.user.username)
        elif instance.server_status_id == 60:
            CB_server_installfailure(instance.ip, self.request.user.username)
        elif instance.server_status_id == 100:
            CB_server_installed(instance.ip, self.request.user.username)
            if instance.server_type_id == 1:
                Asset.objects.filter(assetid=instance.assetid).update(new_status=2)

            api_url = SERVER_ZABBIX_API['FREE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            if res['success'] == True:
                CB_zabbix_free(instance.ip, self.request.user.username)

class ServerForHybridList(generics.ListCreateAPIView):
    """
    Server(服务器)列表接口.

    输入参数：

    * ip   -   需要导入CMDB的IP
    * hostname -

    输出参数：

    * ip        -   pk
    * assetid      -   资产号
    * sn   -   序列号
    * ip   -   IP地址
    * app_id      -   pool id
    * tag_id     -   服务器类型
    * mgmt_ip    -   管理IP
    * hostname   -   主机名
    * praent     -   宿主机资产号
    """
    serializer_class = ServerInfoForHybridSerializer
    queryset = Server.objects.filter(server_owner=1)

    def perform_create(self, serializer):
        ip = self.request.DATA.get('ip', None)

        if Server.objects.exclude(server_status_id=400).filter(ip=ip).exists():
            raise YAPIException('repeat ip.please check.')

        try:
            requirementdetail = HybridRequirementDetail.objects.get(ip=ip, status=4)
        except HybridRequirementDetail.DoesNotExist:
            raise YAPIException('ip is not exist.')
        except HybridRequirementDetail.MultipleObjectsReturned:
            raise YAPIException('repeat ip in use.please check again')

        is_long = requirementdetail.requirement.is_long

        if is_long == 0:
            parent = 'SRV-300994'
            assetid = '%s__%s__%s' % (parent, ip, str(random.randint(100, 999)))
            rack_id = 270
        else:
            parent = 'SRV-303085'
            assetid = '%s__%s__%s' % (parent, ip, str(random.randint(100, 999)))
            rack_id = 385

        sn = '%s__%s__%s' % ('cds-0001', ip.replace(".", ""), str(random.randint(100, 999)))
        server_owner = 1
        server_type_id = 0
        server_env_id = 1
        parent = parent
        server_status_id = 100
        created_time = int(time.time())
        instance = serializer.save(assetid=assetid, sn=sn, server_owner=server_owner, server_type_id=server_type_id,
                                   server_env_id=server_env_id, parent=parent, created_time=created_time,
                                   server_status_id=server_status_id, rack_id=rack_id)
        HybridRequirementDetail.objects.filter(ip=ip, status=4).update(status=5)


class ServerInstallForDocker_bak(generics.ListCreateAPIView):
    """
    Server(服务器)创建容器接口.

    输入参数：

    * node_ip   -   宿主容器
    * require_num - 需要生成的容器数量

    输出参数：

    * ip        -   pk
    * assetid      -   资产号
    * sn   -   序列号
    * ip   -   IP地址
    * app_id      -   pool id
    * tag_id     -   服务器类型
    * mgmt_ip    -   管理IP
    * hostname   -   主机名
    * praent     -   宿主机资产号
    """
    serializer_class = ServerInfoForHybridSerializer
    queryset = Server.objects.filter(server_owner=2)

    def perform_create(self, serializer):
        node_ip = self.request.DATA.get('node_ip', None)
        require_num = int(self.request.DATA.get('require_num', None))
        print node_ip
        print require_num

        try:
            parent = Server.objects.exclude(server_status_id=400).get(ip=node_ip)
        except Server.DoesNotExist:
            raise YAPIException('node_ip is not exist')
        except Server.MultipleObjectsReturned:
            raise YAPIException('node_ip has muti records')

        if parent.app_id != 946:
            raise YAPIException('node_ip had wrong poolid')

        ip_t = parent.ip.split('.')

        create_ip = IpTotal.objects.filter(type=3, is_used=0, status=1, ip1=int(ip_t[0]), ip2=int(ip_t[1]),
                                           ip3=int(ip_t[2]))[0:require_num]

        if create_ip is None:
            raise YAPIException('docker IP pool has full.please contact lizhigang.')

        if len(create_ip) < require_num:
            raise YAPIException('docker IP pool has not enough.please contact lizhigang.')

        last = {}
        aa = None
        for item in create_ip:
            parent_sn = parent.sn
            assetid = '%s__%s' % (parent.assetid, item.ip)
            sn = '%s__%s' % (parent_sn, item.ip.replace(".", ""))
            parent_ip = parent.ip
            rack_id = parent.rack_id

            if item == create_ip[0]:
                aa = item.ip
                last = {
                    'assetid': assetid,
                    'sn': sn,
                    'ip': item.ip,
                    'hostname': '',
                    'server_type_id': 0,
                    'server_os_template_id': 0,
                    'server_app_template_id': 0,
                    'server_status_id': 50,
                    'server_owner': 2,
                    'server_env_id': parent.server_env_id,
                    'created_time': int(time.time()),
                    'template_id': 0,
                    'parent': parent.assetid,
                    'parent_ip': parent_ip,
                    'rack_id': rack_id,
                }

                item.is_used = 1
                item.asset_info = assetid
                item.save()
                CB_ip_info = {
                    'assetid': assetid,
                    'ip': item.ip,
                }
                CB_ip_createip_bycreatevm(item.ip, self.request.user.username,
                                                    json.dumps(CB_ip_info, ensure_ascii=False))

                continue

            server, created = Server.objects.exclude(server_status_id = 400).get_or_create(assetid=assetid, sn=sn, defaults={
                'ip'             : item.ip,
                'hostname'       : '',
                'app_id'         : 0,
                'server_env_id'  : parent.server_env_id,
                'server_type_id' : 0,
                'server_status_id': 50,
                'template_id':  0,
                'parent'         : parent.assetid,
                'parent_ip'      : parent_ip,
                'server_os_template_id': 0,
                'server_app_template_id': 0,
                'created_time': int(time.time()),
                'rack_id': rack_id,
                'server_owner': 2,

            })

            if not created:
                server.ip             = item.ip
                server.hostname       = ''
                server.server_type_id = 0
                server.server_env_id  = parent.server_env_id
                server.parent         = parent
                server.parent_ip      = parent_ip
                server.rack_id        = rack_id
                server.template_id    = 0
                server.server_os_template_id = 0
                server.server_app_template_id = 0
                server.save()

            CB_server = {
                'assetid':  server.assetid,
                'sn': server.sn,
                'ip': server.ip,
                'hostname': server.hostname,
                'server_owner': 2,
                'server_type_id': server.server_type_id,
                'server_class_id': server.server_class_id,
                'server_status_id': server.server_status_id,
                'server_env_id': server.server_env_id,
                'server_os_template_id': server.server_os_template_id,
                'server_app_template_id': server.server_app_template_id,
            }
            CB_server_createvm(assetid, self.request.user.username, json.dumps(CB_server, ensure_ascii=False))

            item.is_used = 1
            item.asset_info = assetid
            item.save()

            CB_ip_info = {
                'assetid': assetid,
                'ip': item.ip,
            }
            CB_ip_createip_bycreatevm(item.ip, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))

        serializer.save(**last)
        CB_server_createvm(aa, self.request.user.username, json.dumps(last, ensure_ascii=False))
        return Response(last)


class DockerPermission(permissions.BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        if request.user is not None:
            if request.user.username == 'yuqiang' or request.user.username == 'pengbo2' \
                    or request.user.username == 'chenjialiang1' or request.user.username == 'liuyuanguo' \
                    or request.user.username == 'testteam':
                return True
        return request.user and request.user.is_staff


class ServerInstallForDocker(APIView):
    """
    Server(服务器)创建容器接口.

    输入参数：

    * node_ip   -   宿主容器
    * require_num - 需要生成的容器数量

    输出参数：

    * ip        -   pk
    * assetid      -   资产号
    * sn   -   序列号
    * ip   -   IP地址
    * app_id      -   pool id
    * tag_id     -   服务器类型
    * mgmt_ip    -   管理IP
    * hostname   -   主机名
    * praent     -   宿主机资产号
    """
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        dd = {
            'node_ip': '容器宿主机IP',
            'require_num': '申请的容器数量',
        }
        return Response(dd)

    def post(self, request, format=None):
        node_ip = request.DATA.get('node_ip', None)
        require_num = int(self.request.DATA.get('require_num', None))

        try:
            parent = Server.objects.exclude(server_status_id=400).get(ip=node_ip)
        except Server.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='node_ip is not exist')
        except Server.MultipleObjectsReturned:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='node_ip has muti records')

        print parent.app_id
        if parent.app_id != 946:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='node_ip had wrong poolid')

        ip_t = parent.ip.split('.')

        create_ip = IpTotal.objects.filter(type=3, is_used=0, status=1, ip1=int(ip_t[0]), ip2=int(ip_t[1]),
                                           ip3=int(ip_t[2]))[0:require_num]

        if create_ip is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='docker IP pool has full.please contact lizhigang.')

        # if len(create_ip) < require_num:
        #     return Response(status=status.HTTP_400_BAD_REQUEST, data='docker IP pool has not enough.please contact lizhigang.')

        data = []
        for item in create_ip:
            parent_sn = parent.sn
            assetid = '%s__%s' % (parent.assetid, item.ip)
            sn = '%s__%s' % (parent_sn, item.ip.replace(".", ""))
            parent_ip = parent.ip
            rack_id = parent.rack_id

            server, created = Server.objects.exclude(server_status_id = 400).get_or_create(assetid=assetid, sn=sn, defaults={
                'ip'             : item.ip,
                'hostname'       : '',
                'app_id'         : 0,
                'server_env_id'  : parent.server_env_id,
                'server_type_id' : 3,
                'server_status_id': 50,
                'template_id':  0,
                'parent'         : parent.assetid,
                'parent_ip'      : parent_ip,
                'server_os_template_id': 0,
                'server_app_template_id': 0,
                'created_time': int(time.time()),
                'rack_id': rack_id,

            })

            if not created:
                server.ip             = item.ip
                server.hostname       = ''
                server.server_type_id = 3
                server.server_env_id  = parent.server_env_id
                server.parent         = parent
                server.parent_ip      = parent_ip
                server.rack_id        = rack_id
                server.template_id    = 0
                server.server_os_template_id = 0
                server.server_app_template_id = 0
                server.save()

            CB_server = {
                'id': server.id,
                'assetid':  server.assetid,
                'sn': server.sn,
                'ip': server.ip,
                'hostname': server.hostname,
                'server_type_id': server.server_type_id,
                'server_class_id': server.server_class_id,
                'server_status_id': server.server_status_id,
                'server_env_id': server.server_env_id,
                'server_os_template_id': server.server_os_template_id,
                'server_app_template_id': server.server_app_template_id,
            }
            CB_server_createvm(assetid, self.request.user.username, json.dumps(CB_server, ensure_ascii=False))

            item.is_used = 1
            item.asset_info = assetid
            item.save()

            CB_ip_info = {
                'assetid': assetid,
                'ip': item.ip,
            }
            CB_ip_createip_bycreatevm(item.ip, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
            data.append(CB_server)

        return Response(status=status.HTTP_200_OK, data=data)


class ServerStandardList(generics.ListCreateAPIView):
    """
    服务器列表（按ID筛选）.

    输入参数：
    * app_id    -   按app_id筛选
    * page_size -   每页展示最大数据
    * tag_id    -   按服务器应用筛选
    * server_env_id - 按照环境筛选  1-stg环境  2-生产环境

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机 3-容器
    * server_type_name - 类型英文名称
    * server_status_id - 30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = ServerStandard.objects.exclude(server_status_id=400).order_by('ip')
    serializer_class = ServerStandardSerializer
    filter_backends = (filters.SearchFilter,  filters.DjangoFilterBackend)
    search_fields = ('assetid', 'sn', 'ip', 'mgmt_ip', 'parent_ip', 'rack__name', 'hostname', 'server_type__comment', 'comment')
    filter_fields = ('id', 'server_status__id','rack__room__id', 'server_type__id', 'server_env__id', 'app__id', 'assetid', 'sn', 'ip','hostname', 'rack__name')

    def get_queryset(self):
        queryset = ServerStandard.objects.exclude(server_status_id=400).order_by('ip')
        query_key = self.request.QUERY_PARAMS.get('query_key', None)
        query_value = self.request.QUERY_PARAMS.get('query_value', None)
        if query_value is not None:
            filter_list = query_value.split(',')
            if query_key is not None:
                if 'ip' == query_key:
                    queryset = queryset.filter(ip__in=filter_list)
                elif 'assetid' == query_key:
                    queryset = queryset.filter(assetid__in=filter_list)
                else:
                    queryset = queryset.filter(hostname__in=filter_list)
        return queryset

class ServerStandardDetail(generics.RetrieveUpdateAPIView):
    """
    服务器列表（按ID筛选）.

    输入参数：
    * app_id    -   按app_id筛选
    * page_size -   每页展示最大数据
    * tag_id    -   按服务器应用筛选
    * server_env_id - 按照环境筛选  1-stg环境  2-生产环境
    * action        - 操作类型  deploy-上架 predeploy-预上架 change_using-预上架失败修改为使用中 change_maintain-预上架失败修改为维护
                              trash-主机报废  maintain-维护 maintain_finish-维护完成 recycle-下架回收 edit-修改备注

    输出参数：

    * id        -   pk
    * assetid   -   资产号
    * ip        -   IP
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_type_id - 应用是否为业务POOL， 1为非业务POOL  0为业务POOL
    * app_name  -   应用名称
    * tag_id    -   标签ID
    * mgmt_ip   -   管理IP
    * hostname  -   主机名
    * server_type_id - 类型  0-虚拟机  1-物理机 3-容器
    * server_type_name - 类型英文名称
    * server_status_id - 30-待装机 50-装机中  100-空闲  200-使用中   210-维护中  220-预上架中  230-预上架失败  300-已下架  400-已报废
    * server_status_name - 10-ready 30-install 50-installing 100-free 200-online 210-offline 400-delete
    * server_env_id - 1 - stg环境   2 - 生产环境
    * server_env_name - stagging  production
    * rack_name - 机柜名称
    * room - 机房名称
    * rack_real_name - 真实机柜名称（兼容刀片机架）
    * parent - 宿主机设备编号
    * created_time - 记录创建时间
    * online_time - IP上架时间
    """
    queryset = Server.objects.exclude(server_status_id=400)
    serializer_class = ServerSerializer

    def _del_servers(self, id_):
        username = self.request.user and self.request.user.username
        server_bind_ids = SoaServiceGroupBind.objects.filter(serverstandard=id_)
        if server_bind_ids:
            server_bind_ids = ','.join([str(x.id) for x in server_bind_ids])
            ret = del_servers(server_bind_ids, username)
            if not ret['result']:
                raise Exception({'server_bind_ids': server_bind_ids, 'msg': ret['msg']})

    def perform_update(self, serializer):
        #zabbix调用失败后发送邮件的参数
        action = self.request.DATA.get('action', '')
        username = (self.request.user.username or '') if self.request.user else '未定义'
        mail_list = []
        action_name = u'未定义操作'
        ip = ''
        poolname = None
        sitename = None
        zabbix_content = ""
        res = {}

        logger.info("****** update server excute action: " + action + " ********")

        if action == '':
            logger.warning("action is null, please check your parameter.")
            raise YAPIException('action（操作类型）为必填参数！')
        if action == 'predeploy':
            uniq_id = self.request.DATA.get('uniq_id')
            haproxy_group = self.request.DATA.get('haproxy_group')
            haproxy_room = self.request.DATA.get('haproxy_room')
            action_name = u'主机预上架'

            is_init_tomcat = self.request.DATA.get('is_init_tomcat', None)
            is_one_click = self.request.DATA.get('is_one_click', None)

            service_id = self.request.DATA.get('service_id', None)
            ports = self.request.DATA.get('ports', None)

            group_id = self.request.DATA.get('group_id', None)
            from_user = self.request.DATA.get('from_user', None)

            instance = serializer.save(server_status_id = 220)
            logger.info(__name__ + ": instance saved ok.")

            CB_server_info = {
                'ip':  instance.ip,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'mgmt_ip': instance.mgmt_ip,
                'assetid': instance.assetid,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id
            }
            logger.info(__name__ + ": prepare changes -> " + json.dumps(CB_server_info))
            CB_server_predeploy(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)
            logger.info(__name__ + ": changes write done.")
            # if is_init_tomcat == '2':
            #     if App.objects.get(id = instance.app_id) .service_name == 'tomcat':
            #         is_init_tomcat = 1
            #     else:
            #         is_init_tomcat = 0
            # else:
            #     is_init_tomcat = None
            # if is_one_click == '1':
            #     is_one_click = 1
            # else:
            #     is_one_click = None
            if is_init_tomcat is not None and App.objects.get(id=instance.app_id).service_name != 'tomcat':
                is_init_tomcat = 0

            change_server_data = {
                'index': instance.ip,
                'level': 'change',
                'user': username,
                'action': 'deploy',
                'message': CB_server_info,
                'type': 'server'
            }

            change_zabbix_data = {
                'type': 'zabbix',
                'action': 'add',
                'index': instance.ip,
                'level': 'change',
                'message': 'zabbix->上架成功，开启监控',
                'user': username,
                'auth_id': SERVER_ZABBIX_ID
            }

            logger.info(__name__ + ": prepare changes and zabbix data ok.")

            amqp = Pika(task='deploy.tasks.auto_single_deploy',
                        args=[instance.ip, is_one_click, is_init_tomcat, change_server_data, change_zabbix_data,
                              uniq_id, {'method': 'register', 'group_dict': {haproxy_room: [haproxy_group]} if haproxy_group else {}},
                              instance.id, service_id, ports, group_id, from_user])
            logger.info(__name__ + ": excuete task -> deploy.tasks.auto_single_deploy ")
            instance.task_id = amqp.basic_publish()
            instance.save()
            logger.info(__name__ + ": instance saved ok.")

        elif action == 'deploy':
            action_name = u'主机上架'
            mail_list = SERVER_MAILLIST['deploy']
            logger.info(__name__ + ": -> " + action_name)

            instance = serializer.save(server_status_id = 200, online_time = int(time.time()))

            logger.info(__name__ + " : instace data saved ok.")

            ip = instance.ip
            poolname = instance.app.name
            sitename = instance.app.site.name

            CB_server_info = {
                'ip':  instance.ip,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'mgmt_ip': instance.mgmt_ip,
                'assetid': instance.assetid,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
                'online_time': stamp2str(instance.online_time)
            }

            logger.info(__name__ + ":preare to write change data: " + json.dumps(CB_server_info))

            CB_server_deploy(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)

            logger.info(__name__ + ": CB_server_deploy write changes done.")

            api_url = SERVER_ZABBIX_API['ADD'] % (SERVER_ZABBIX_ID, instance.ip)
            if instance.server_type_id == 3:
                api_url = api_url + '&v_type=1'
            res = json.loads(urllib.urlopen(api_url).read())

            logger.info(__name__ + ": zabbix add response -> " + json.dumps(res))

            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_add(instance.ip, username, app_id=instance.app_id)
            logger.info(__name__ + ": zabbix change written done.")

        elif action == 'change_using':
            action_name = u'主机预上架失败处理,修改为使用中'
            logger.info(action_name)
            mail_list = SERVER_MAILLIST['change_using']

            instance = serializer.save(server_status_id = 200, online_time = int(time.time()))
            logger.info("instace data saved ok.")
            ip = instance.ip
            poolname = instance.app.name
            sitename = instance.app.site.name

            CB_server_info = {
                'ip':  instance.ip,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'assetid': instance.assetid,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
                'online_time': stamp2str(instance.online_time)
            }

            logger.info(__name__ + ": preare change data -> " + json.dumps(CB_server_info))

            CB_server_predeployfail_to_using(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)

            logger.info(__name__ + ": write CB_server_predeployfail_to_using changes done.")

            api_url = SERVER_ZABBIX_API['ADD'] % (SERVER_ZABBIX_ID, instance.ip)
            if instance.server_type_id == 3:
                api_url = api_url + 'v_type=1'
            res = json.loads(urllib.urlopen(api_url).read())

            logger.info(__name__ + ": zabbix api request -> " + json.dumps(res))

            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_add(instance.ip, username, app_id=instance.app_id)

            logger.info("write zabbix change done.")
        elif action == 'change_maintain':
            action_name = u'主机预上架失败处理——修改为维护中'
            logger.info(action_name)
            mail_list = SERVER_MAILLIST['change_maintain']

            instance = serializer.save(server_status_id = 210)
            ip = instance.ip
            poolname = instance.app.name
            sitename = instance.app.site.name

            CB_server_info = {
                'ip':  instance.ip,
                'assetid': instance.assetid,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'server_status_id': instance.server_status_id,
            }

            logger.info(__name__ + ": preare change data -> " + json.dumps(CB_server_info))            

            CB_server_predeployfail_to_maintain(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)

            logger.info(__name__ + ": write change data CB_server_predeployfail_to_maintain done.")

            api_url = SERVER_ZABBIX_API['DISABLE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())

            logger.info(__name__ + "zabbix api request data -> " + json.dumps(res))

            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_disable(instance.ip, username, app_id=instance.app_id)
                logger.info(__name__ + ": zabbix disabled ok.")

        elif action == 'trash':
            action_name = u'主机报废'
            mail_list = SERVER_MAILLIST['scrap']
            # if serializer.data.get('server_type_id') == 3:
            #     url = SERVER_DELETE_DOCKER % serializer.data.get('id')
            #     headers = {'Authorization': 'Basic Y21kYjpyODkhQ1VrczhJ', 'X-Auth-User':'admin'}
            #     del_res = requests.delete(url, headers=headers)
            #     if del_res.status_code != 204:
            #         error = json.loads(del_res.text)
            #         raise YAPIException('调用删除Docker实例的接口失败,详情：%s:%s' % (error['title'], error['description']))

            id_ = serializer.data.get('id')
            self._del_servers(id_)

            uuid4 = uuid()
            ip = serializer.data.get('ip')
            app_id = serializer.data.get('app_id')
            if json.loads(self.request.DATA.get('haproxy')):
                haproxy_dict = get_haproxy_info_by_ip(ip)
                for haproxy_room in haproxy_dict:
                    for haproxy_group in haproxy_dict[haproxy_room]:
                        haproxy_registration = HaproxyRegistration(ip=ip, haproxy_room=haproxy_room, haproxy_group=haproxy_group, task_id=uuid4)
                        haproxy_registration.unregister()
            if json.loads(self.request.DATA.get('hedwig')):
                hedwig_registration = HedwigRegistration(ip=ip, task_id=uuid4)
                hedwig_registration.unregister()
            # deploy_path_obj = DeployPath.objects.filter(app_id=app_id).first()
            # if deploy_path_obj is not None:
            #     ssh('/bin/rm -rf %s' % deploy_path_obj.path.rstrip('/'), ip)

            instance = serializer.save(server_status_id=400, app_id=0, task_id=uuid4)
            ip = instance.ip
            poolname = None
            sitename = None

            CB_server_info = {
                'ip':  instance.ip,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'assetid': instance.assetid,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
                'online_time': stamp2str(instance.online_time)
            }
            CB_server_trash(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False))

            IpTotal.objects.filter(asset_info = instance.assetid).update(asset_info = '', is_used = 0)
            CB_ip_info = {
                'asset_info': instance.assetid,
                'ip': instance.ip,
                'type': 3,
                'is_used': 0,
            }
            CB_ip_unbind_by_scrapoffserver(instance.ip, username, json.dumps(CB_ip_info, ensure_ascii=False))

            api_url = SERVER_ZABBIX_API['DELETE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_delete(instance.ip, username)

            if instance.server_type_id == 1:
                Asset.objects.filter(assetid = instance.assetid).update(new_status = 0, last_modified = int(time.time()))
                CB_asset_info = {
                    'assetid':  instance.assetid,
                    'new_status': 0,
                    'rack_id': instance.rack_id,
                    'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0
                }
                CB_asset_change(instance.assetid, username, json.dumps(CB_asset_info, ensure_ascii=False))

        elif action == 'maintain':
            action_name = u'主机维护'
            logger.info(action_name)
            mail_list = SERVER_MAILLIST['maintain']

            instance = serializer.save(server_status_id = 210)
            ip = instance.ip
            poolname = instance.app.name
            sitename = instance.app.site.name

            CB_server_info = {
                'ip':  instance.ip,
                'assetid': instance.assetid,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
            }
            logger.info(__name__ + ": prepare CB_server_maintain data -> " + json.dumps(CB_server_info))
            CB_server_maintain(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)
            logger.info(__name__ + ": changes CB_server_maintain write done.")

            api_url = SERVER_ZABBIX_API['DISABLE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())

            logger.info(__name__ + ': zabbix request data -> ' + json.dumps(res))

            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_disable(instance.ip, username, app_id=instance.app_id)

                logger.info(__name__ + ": CB_zabbix_disable write change done.")

            uuid4 = uuid()
            instance.task_id = uuid4.replace('-', '*')
            instance.save()

            logger.info("server instance saved ok.")

            if json.loads(self.request.DATA.get('haproxy')):
                haproxy_dict = get_haproxy_info_by_ip(ip)
                for haproxy_room in haproxy_dict:
                    for haproxy_group in haproxy_dict[haproxy_room]:
                        haproxy_registration = HaproxyRegistration(ip=ip, haproxy_room=haproxy_room, haproxy_group=haproxy_group, task_id=uuid4)
                        haproxy_registration.annotate()
                        logger.info(__name__ + ": haproxy_registration annotate ok.")
            if json.loads(self.request.DATA.get('hedwig')):
                hedwig_registration = HedwigRegistration(ip=ip, task_id=uuid4)
                hedwig_registration.unregister()
                logger.info(__name__ + ": hedwig_registration unregister ok.")

        elif action == 'maintain_finish':
            action_name = u'主机维护完成重新预上架'

            logger.info(action_name)

            instance = serializer.save(server_status_id = 220, online_time = int(time.time()))
            logger.info("server instance saved ok.")

            CB_server_info = {
                'ip':  instance.ip,
                'assetid': instance.assetid,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
                'online_time': stamp2str(instance.online_time)
            }

            logger.info(__name__ + ": prepare CB_server_maintainfinish data -> " + json.dumps(CB_server_info))

            CB_server_maintainfinish(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False), app_id=instance.app_id)

            logger.info(__name__ + ": CB_server_maintainfinish write changes done.")

            change_server_data = {
                'index': instance.ip,
                'level': 'change',
                'user': username,
                'action': 'deploy',
                'message': CB_server_info,
                'type': 'server'
            }

            change_zabbix_data = {
                'type': 'zabbix',
                'action': 'enable',
                'index': instance.ip,
                'level': 'change',
                'message': 'zabbix->维护完成，开启监控',
                'user': username,
                'auth_id': SERVER_ZABBIX_ID
            }

            amqp = Pika(task='deploy.tasks.auto_single_deploy', args=[instance.ip, 1, None, change_server_data, change_zabbix_data, None, {'method': 'deannotate', 'group_dict': get_haproxy_info_by_ip(instance.ip) if json.loads(self.request.DATA.get('haproxy')) else {}}])
            instance.task_id = amqp.basic_publish()
            logger.info(__name__ + ": excute task auto_single_deploy ok.")
            instance.save()
            logger.info(__name__+" : instance saved task_id")

        elif action == 'recycle':
            if serializer.data.get('server_type_id') == 3:
                raise YAPIException('Docker类型的机器不允许做下架回收操作！')
            action_name = u'维护主机下架回收'
            mail_list = SERVER_MAILLIST['recycle']
            poolname = self.request.DATA.get('poolname', None)
            sitename = self.request.DATA.get('sitename', None)

            id_ = serializer.data.get('id')
            self._del_servers(id_)

            uuid4 = uuid()
            ip = serializer.data.get('ip')
            app_id = serializer.data.get('app_id')
            if json.loads(self.request.DATA.get('haproxy')):
                haproxy_dict = get_haproxy_info_by_ip(ip)
                for haproxy_room in haproxy_dict:
                    for haproxy_group in haproxy_dict[haproxy_room]:
                        haproxy_registration = HaproxyRegistration(ip=ip, haproxy_room=haproxy_room, haproxy_group=haproxy_group, task_id=uuid4)
                        haproxy_registration.unregister()
            if json.loads(self.request.DATA.get('hedwig')):
                hedwig_registration = HedwigRegistration(ip=ip, task_id=uuid4)
                hedwig_registration.unregister()
            deploy_path_obj = DeployPath.objects.filter(app_id=app_id).first()
            if deploy_path_obj is not None:
                ssh('/depot/boot.sh stop; /bin/rm -rf %s' % deploy_path_obj.path.rstrip('/'), ip)

            instance = serializer.save(server_status_id=100, app_id=0, task_id=uuid4)
            ip = instance.ip

            CB_server_info = {
                'ip':  instance.ip,
                'assetid': instance.assetid,
                'app_id': instance.app_id,
                'rack_id': instance.rack_id,
                'room_id': instance.asset.rack.room_id if (instance.asset and instance.asset.rack) else 0,
                'server_env_id': instance.server_env_id,
                'server_type_id': instance.server_type_id,
                'server_status_id': instance.server_status_id,
            }
            CB_server_recycle(instance.ip, username, json.dumps(CB_server_info, ensure_ascii=False))

            api_url = SERVER_ZABBIX_API['FREE'] % (SERVER_ZABBIX_ID, instance.ip)
            res = json.loads(urllib.urlopen(api_url).read())
            zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
            if res['success'] == True:
                CB_zabbix_free(instance.ip, username)

        elif action == 'edit': #修改备注
            serializer.save()
        # try:
        #     develop_mail = AppContact.objects.get(pool_id=app_id)
        # except AppContact.DoesNotExist:
        #     develop_mail = None
        # if develop_mail is not None and develop_mail.domain_email !='':
        #     mail_list.append(develop_mail.domain_email)

        #发送邮件
        # mail_title = u'主机变更提醒：%s %s' %(ip, action_name)
        #
        # if (action in ('predeploy', 'maintain_finish')):
        #     amqp = Pika(task='deploy.tasks.online_report', args=[REDIS['HOST'], REDIS['PORT'], task_dict, action, username, server_change_content, mail_list, poolname, sitename])
        #     amqp.basic_publish()
        # else:
        #     html_content = loader.render_to_string('mail/server.html',{'action':action_name,
        #                                                                'action_time':stamp2str(time.time()),
        #                                                                'poolname':poolname,'ips':ip,'username':username,
        #                                                                'sitename':sitename,'server_change_content':server_change_content})
        #     sendmail_html(mail_title,html_content,mail_list)

        #zabbix调用失败后发送邮件
        if(action not in ('predeploy', 'maintain_finish', 'edit', '')):
            if res['success'] == False:
                logger.info(__name__ + ": send failed email.")
                mail_title = action_name + u'，zabbix状态更新异常：%s' % ip
                html_content = loader.render_to_string('mail/server.html',{'action':action_name,'action_time':stamp2str(time.time()),
                                                                           'poolname':poolname,'ips':ip,'username':username,
                                                                           'sitename':sitename,'server_change_content':zabbix_content})
                sendmail_html(mail_title,html_content,mail_list)


# fanxinchao1
def parse_request(request, t=0):
    """
    服务于 VmExpand 和 VmReduce
    :param request: 标准request实例
    :param t: 0: expand   1: reduce
    :return: 如果参数无误，则返回一个包含所有参数的tuple。如果参数错误（不存在或类型不正确），则返回一个包含错误信息的Response
    """
    params = [('app_id', 'env_id', 'room_id', 'num', 'is_init_tomcat', 'is_one_click', 'ycc_zone_id', 'group_id',
               'service_id', 'ports', 'from_user', 'uniq_id'),
              ('app_id', 'env_id', 'room_id', 'num', 'uniq_id')][t]
    n = [3, 1][t]  # 不须传入整型的参数数量
    result = tuple([request.data.get(param, None) for param in params])
    st = set([4]) if t else set([7, 9, 11])  # 可不传的参数下标

    for i, v in enumerate(result):
        if i not in st and v is None:
            return Response('need <%s>' % params[i], status.HTTP_402_PAYMENT_REQUIRED)
        if v is not None and i < len(result)-n and not isinstance(v, int):
            return Response('<%s> should be (int)' % params[i], status.HTTP_400_BAD_REQUEST)

    return result


# fanxinchao1
def select_server_by_room(room_id):
    """
    服务于 VmExpand 和 VmReduce
    :param room_id: 整型
    :return: 返回此room中所有的server
    """
    racks = Rack.objects.all()
    racks = racks.filter(room_id=room_id)
    rack_ids = []
    for rack in racks:
        rack_ids.append(rack.id)

    servers = Server.objects.all()
    servers = servers.filter(rack_id__in=rack_ids)  # 筛选room(通过给定<room>中所有的rack_id)
    return servers


# fanxinchao1
def min_num_rack_ids(rack_id2num, rack_id=None):
    """
    服务于 VmExpand
    :param rack_id2num: list类型，其中的element为包含2个element的tuple，第一个为rack_id, 第二个为此rack中在跑虚拟机的数量
    :param rack_id: 顾名思义
    :return: 如果rack_id 为 None, 返回一个list，其中的element为此rack中在跑虚拟机数量最少的rank_id
            如果rack_id 不为 None， 则将此rack中在跑虚拟机数量+1
    """
    if rack_id is not None:
        for v in rack_id2num:
            if v[0] == rack_id:
                rack_id2num.append((v[0], v[1]+1))
                rack_id2num.remove(v)
                return True
        return False

    min_ = rack_id2num[0][1]
    for v in rack_id2num:
        min_ = min(min_, v[1])

    rack_ids = []
    for v in rack_id2num:
        if v[1] == min_:
            rack_ids.append(v[0])

    return rack_ids


# fanxinchao1
def max_num_servers(rack_id2server):
    """
    服务于 VmReduce
    :param rack_id2server: dict类型， key为rack_id， value为list，其中包含此rack中在跑虚拟机
    :return: 返回list， 其中element为 在跑虚拟机数量最多的rack中所有的虚拟机
    """
    keys = rack_id2server.keys()
    _max = len(rack_id2server[keys[0]])
    for key in keys:
        _max = max(_max, len(rack_id2server[key]))

    servers = []
    for key in keys:
        if len(rack_id2server[key]) == _max:
            servers.extend(rack_id2server[key])
    return servers

# 锁，防止两个请求选出相同的空闲虚拟机
# lock = threading.Lock()


# fanxinchao1
def get_servers_by_room_and_env(room_id, env_id):
    servers = select_server_by_room(room_id)
    servers = servers.filter(server_type_id=0)  # 筛选虚拟机
    servers = servers.filter(server_env_id=env_id)  # 筛选环境

    # 排出某些不可选ip
    exips = ['10.4.88.',  # 互联网金融
             '10.18.',  # 同上
             '10.0.',  # DBA
             '10.20.',  # 京东借用
             ]
    # '10.17.1-9.' DBA
    exip = '10.17.'
    for exip_last in range(1, 10):
        exip_ = exip + str(exip_last) + '.'
        exips.append(exip_)
    for exip in exips:
        servers = servers.exclude(ip__startswith=exip)

    return servers


# fanxinchao 1
class NumOfFreeServers(APIView):
    permission_classes = (mypermissions.IsValid4VM,)

    def post(self, request, format=None):
        room_id = request.data.get('room_id', None)
        env_id = request.data.get('env_id', None)

        try:
            room_id = int(room_id)
            env_id = int(env_id)
        except Exception:
            return Response('参数错误', status=status.HTTP_406_NOT_ACCEPTABLE)

        servers = get_servers_by_room_and_env(room_id, env_id)
        servers_free = servers.filter(server_status_id=100)

        return Response({'num': len(servers_free)}, status=status.HTTP_200_OK)


# fanxinchao1
class VmExpand(APIView):
    """
    虚拟机扩容
    data = {} 请求数据
    headers = {} 请求头
    headers['content-type'] = 'application/json'
    data['app_id'] = xxx
    data['env_id'] = xxx
    data['room_id'] = xxx
    data['num'] = xxx
    data['uniq_id'] = xxx
    其中 xxx 为整型
    """
    permission_classes = (mypermissions.IsValid4VM,)

    def post(self, request, format=None):
        result = parse_request(request)
        if isinstance(result, Response):
            return result
        app_id, env_id, room_id, num, is_init_tomcat, is_one_click, ycc_zone_id, group_id, \
            service_id, ports, from_user, uniq_id = result
        if num <= 0:
            return Response('<num> should be a positive integer number', status.HTTP_400_BAD_REQUEST)

        servers = get_servers_by_room_and_env(room_id, env_id)
        servers_free = servers.filter(server_status_id=100)  # 空闲的虚拟机

        if len(servers_free) < num:
            return Response("Don't have enough servers to expand.", status.HTTP_406_NOT_ACCEPTABLE)
        servers = servers.filter(app_id=app_id)  # 筛选pool
        servers_online = servers.filter(server_status_id=200)  # 运行中的虚拟机

        # 每个物理机在跑虚拟机的数量
        # 不统计数量<=0的情况
        parent2num = {}
        for server in servers_online:
            parent2num[server.parent] = parent2num.get(server.parent, 0) + 1

        # 空闲虚拟机的rack_id
        rack_ids_free = set()
        for server in servers_free:
            rack_ids_free.add(server.rack_id)

        # 跑在每个rack上的server总数
        # 忽略当前无空闲虚拟机的rack
        rack_id2num = {}
        for rack_id in rack_ids_free:
            rack_id2num[rack_id] = 0
        for server in servers_online:
            rack_id = server.rack_id
            if rack_id in rack_ids_free:
                rack_id2num[rack_id] += 1
        rack_id2num = rack_id2num.items()

        # 每个rack中可选的空闲虚拟机列表
        rack_id2servers = {}
        for server in servers_free:
            rack_id = server.rack_id
            rack_id2servers.setdefault(rack_id, []).append(server)

        # 选择空闲虚拟机
        servers_result = []
        for _ in range(num):
            # 从有空闲虚拟机的rack中
            # 选出正在跑的虚拟机数量最少的rack_id
            rack_ids = min_num_rack_ids(rack_id2num)
            servers_all = []
            for rack_id in rack_ids:
                servers = rack_id2servers[rack_id]
                servers_all.extend(servers)

            selected = servers_all[0]
            _min = parent2num.setdefault(selected.parent, 0)
            for server in servers_all:
                if _min == 0:
                    break
                if parent2num.setdefault(server.parent, 0) < _min:
                    _min = parent2num[server.parent]
                    selected = server

            servers_result.append(selected)
            parent2num[selected.parent] += 1
            for rack_id in rack_ids:
                servers = rack_id2servers[rack_id]
                if selected in servers:
                    servers.remove(selected)
                    if len(servers) == 0:
                        rack_id2servers.pop(rack_id)
                        for v in rack_id2num:
                            if v[0] == rack_id:
                                rack_id2num.remove(v)
                    else:
                        min_num_rack_ids(rack_id2num, rack_id)
                    break
        server_id_list = []
        server_ip_list = []
        for server in servers_result:
            server_id_list.append(server.id)
            server_ip_list.append(server.ip)

        if uniq_id:  # 方便测试
            tnp = TNewPool.objects.using('db_ticket').get(uniq_id=uniq_id)
            tnp.ip = ','.join(server_ip_list)
            tnp.save()

            for ip in server_ip_list:
                tdi = TDockerIp.objects.using('db_ticket').create(ip=ip, uniq_id=uniq_id)
                tdi.save()

        for id_ in server_id_list:
            url = 'http://%s/api/server/serverstandard/%s/' % (settings.OMS_HOST, id_)
            data = {
                'action': 'predeploy',
                'app_id': app_id,
                'is_init_tomcat': is_init_tomcat,
                'is_one_click': is_one_click,
                'uniq_id': uniq_id,
                'ycc_zone': ycc_zone_id,
                'service_id': service_id,
                'ports': ports,
                'group_id': group_id,
                'from_user': from_user,
            }
            resp = requests.patch(url, data=data, auth=('docker', '26xDUm1q'))
            # resp = requests.patch(url, data=data, auth=('admin', 'admin'))
        # lock.release()
        # http_host = request.META.get('HTTP_HOST')
        # username = request.user.username

        # if group_id is None:
        #     sendmail_for_haproxy(server_id_list)
        return Response({'ip': server_ip_list}, status.HTTP_200_OK)


# fanxinchao1
class VmReduce(APIView):
    """
        虚拟机缩容
        data = {} 请求数据
        headers = {} 请求头
        headers['content-type'] = 'application/json'
        data['app_id'] = xxx
        data['env_id'] = xxx
        data['room_id'] = xxx
        data['num'] = xxx
        data['uniq_id'] = xxx
        其中 xxx 为整型
        """
    permission_classes = (mypermissions.IsValid4VM,)

    def post(self, request, format=None):
        result = parse_request(request, 1)
        if isinstance(result, Response):
            return result
        app_id, env_id, room_id, num, uniq_id = result
        if num <= 0:
            return Response('<num> should be a positive integer number', status.HTTP_400_BAD_REQUEST)

        servers = select_server_by_room(room_id)
        servers = servers.filter(server_type_id=0)  # 筛选虚拟机
        servers = servers.filter(server_env_id=env_id)  # 筛选环境
        servers = servers.filter(app_id=app_id)  # 筛选pool
        servers = servers.filter(server_status_id=200)  # 运行中的虚拟机
        if len(servers) < num:
            return Response("Don't have enough servers to reduce.", status.HTTP_406_NOT_ACCEPTABLE)

        parent2num = {}
        rack_id2servers = {}
        for server in servers:
            rack_id2servers.setdefault(server.rack_id, []).append(server)
            parent2num[server.parent] = parent2num.get(server.parent, 0) + 1

        result = []
        for _ in range(num):
            servers = max_num_servers(rack_id2servers)
            selected = servers[0]
            _max = parent2num[selected.parent]
            for server in servers:
                max_cur = parent2num[server.parent]
                if max_cur > _max:
                    selected = server
                    _max = max_cur
            result.append(selected)
            rack_id2servers[selected.rack_id].remove(selected)
            if len(rack_id2servers[selected.rack_id]) == 0:
                rack_id2servers.pop(selected.rack_id)
            parent2num[selected.parent] -= 1
            if parent2num[selected.parent] == 0:
                parent2num.pop(selected.parent)

        ret = {}
        for server in result:
            ret.setdefault('server_ip', []).append(server.ip)
            url = 'http://%s/api/server/serverstandard/%s/' % (settings.OMS_HOST, server.id)
            data = {
                'action': 'recycle',
                'uniq_id': uniq_id
            }
            # resp = requests.patch(url, data=data, auth=('docker', '26xDUm1q'))

        return Response(ret, status.HTTP_200_OK)


# class LBGroupViewSet(viewsets.ModelViewSet):
#     queryset = LBGroup.objects.all()
#     serializer_class = LBGroupSerializer
#     filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
#     filter_fields = ('app', 'name')
#     search_fields = ('app__name', 'name')

@api_view(['GET'])
@permission_classes((AllowAny, ))
def haproxy_group(request):
    app_id = request.GET.get('app_id')
    room_name = request.GET.get('room_name')
    if app_id is None or room_name is None:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    app_obj = App.objects.filter(status=0, id=app_id).first()
    if app_obj is None:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    room_obj = Room.objects.filter(name=room_name).first()
    if room_obj is None:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    haproxy_group_list = get_haproxy_group_by_app_obj(app_obj, room_obj)
    return Response(status=status.HTTP_200_OK, data=haproxy_group_list)


def sendmail_for_haproxy(server_id_list):
    server_queryset = Server.objects.filter(id__in=server_id_list)
    html_content = loader.render_to_string('cmdbv2/server/notification_for_haproxy.html', locals()).encode('utf8')
    subject = u'主机管理 - 一键部署 - 请求上架haproxy'
    data = {
        'level_id': 500,
        'title': subject,
        'send_to': ','.join(EMAIL_LIST_FOR_HAPROXY),
        'get_time': time.time()
    }
    process_notification(json.dumps(data), template=html_content)


def sendmail(server_id_list, title, http_host, username):
    server_queryset = Server.objects.filter(id__in=server_id_list)
    action = {
        'maintain': u'维护',
        'maintain_finish': u'维护完成: 预上架',
        'recycle': u'下架回收',
        'trash': u'下架报废',
        'predeploy': u'预上架'
    }.get(title, u'未知操作')
    subject = u'主机管理 - ' + action
    sendmail_v2(
        subject,
        loader.render_to_string('cmdbv2/server/notification.html', locals()).encode('utf8'),
        [username + '@yhd.com']
    )


@api_view(['POST'])
@permission_classes((AllowAny, ))
def notification(request):
    server_id_list = json.loads(request.POST.get('server_id_list'), [])
    title = request.POST.get('title')
    http_host = request.META.get('HTTP_HOST')
    username = request.user.username
    sendmail(server_id_list, title, http_host, username)

    return Response(status=status.HTTP_200_OK)

class VirtualLog(generics.ListCreateAPIView):
    """
    虚拟化LOG采集接口.

    输入参数：

    * index   -   索引ID （可选，如无此参数则为所有LOG）

    输出参数：

    * id            -   pk
    * is_error      -   是否为错误log，1为错误日志  2为提醒日志
    * happen_time   -   LOG发生时间
    * type          -   应用模块名称
    * action        -   应用模块动作
    * index         -   索引值，装机脚本可采用虚拟机的IP
    * content       -   内容
    """

    queryset = LogMain.objects.all()
    serializer_class = VirtualLogSerializer

    def get_queryset(self):
        queryset = LogMain.objects.all().order_by('-id')
        index = self.request.QUERY_PARAMS.get('index', None)
        if index is not None:
            queryset = queryset.filter(index=index)
        return queryset

    # def pre_save(self, obj):
    #     obj.created = stamp2str(time.time())
    #     obj.happen_time = stamp2str(time.time())
    def perform_create(self, serializer):
        serializer.save(created=stamp2str(time.time()))

