# -*- coding: utf-8 -*-
import time, json

from rest_framework import generics
from netaddr import IPNetwork
from rest_framework import filters
from django.http import HttpResponse
from django.db import connections
from server.models import Server
from serializers import *
from util.timelib import stamp2str
from change.utiltask import *
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils import six
from rest_framework.permissions import AllowAny
import time
import operator
import django_filters
import urllib
from  assetv2.settingsapi import SERVER_ZABBIX_ID,SERVER_MAILLIST,SERVER_ZABBIX_API
from cmdb.models import App, Site
from util.sendmail import sendmail_html
from django.template import loader

class AssetSearchFilter(filters.SearchFilter):

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
                ips = IpTotal.objects.filter(ip=search_term)
                ids = []
                for item in ips:
                    ids.append(item.asset_info)
                if ids:
                    queryset = Asset.objects.filter(assetid__in=ids)

        return queryset


class IpBindPermission(permissions.BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        if request.user is not None:
            if request.user.username == 'yuqiang' or request.user.username == 'pengbo2' \
                    or request.user.username == 'chenjialiang1' or request.user.username == 'liuyuanguo' \
                    or request.user.username == 'testteam' :
                return True
        return request.user and request.user.is_staff

class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


def healthcheck(request):
    return HttpResponse('OK')


def getuniqueassetid(asset_type):
    try:
        atype = AssetType.objects.get(id=asset_type)
    except AssetType.DoesNotExist:
        return None
    short_name = atype.short_name
    c = connections['default'].cursor()
    try:
        c.execute("replace into unique_asset(cname) values('asset')")
    finally:
        c.close()
    unique_aseetid = UniqueAsset.objects.latest("id")
    return "%s-%d" % (short_name, unique_aseetid.id)

class AssetListFilter(django_filters.FilterSet):
    start_exp_time = django_filters.NumberFilter(name="expiration_time", lookup_type='gte')
    end_exp_time = django_filters.NumberFilter(name="expiration_time", lookup_type='lte')
    class Meta:
        model = Asset
        fields = ['new_status', 'asset_type', 'rack__room__id', 'start_exp_time', 'end_exp_time']

class AssetList(generics.ListCreateAPIView):
    """
    设备列表页/创建设备.

    输入参数：
    * search    -   查询值（可查ID/序列号/设备编号/机架名称/型号/设备类型）

    输出参数：

    * id                    -   PK
    * service_tag           -   设备序列号
    * mac                   -   设备mac地址
    * asset_type_id         -   资产类型ID
    * asset_type            -   资产类型名称
    * rack_id               -   机柜ID
    * rack                  -   机柜名称
    * rack_real_name        -   机柜真实名称
    * asset_model_id        -   设备型号ID
    * asset_model           -   型号名称
    * expiration_time       -   过期时间
    * create_time           -   创建时间
    * last_modified         -   修改时间
    * new_status            -   设备状态：0-未交付 1-已申请 2-已交付
    * comment               -   备注
    """
    queryset = Asset.objects.all().order_by('-id')
    serializer_class = AssetSerializer
    filter_class = AssetListFilter
    filter_backends = (AssetSearchFilter, filters.DjangoFilterBackend)
    search_fields = ('id', 'service_tag', 'assetid', 'mac', 'asset_type__comment', 'asset_model__name',
                     'rack__name', 'rack__room__name', 'new_status')

    def perform_create(self, serializer):
        current_time = int(time.time())
        assetid = getuniqueassetid(self.request.DATA.get('asset_type', None))
        rack_flag = serializer.validated_data.has_key('rack')
        rack_space_flag = self.request.DATA.get('rack_space_id', False)
        if (rack_flag and not rack_space_flag) or (not rack_flag and rack_space_flag):
            raise YAPIException('服务器上架必须选择机架号和机柜号！')

        instance = serializer.save(create_time=current_time, last_modified=current_time, assetid=assetid)

        if instance.asset_type_id == 9:
            rack, created = Rack.objects.get_or_create(name=assetid, room_id=instance.rack.room_id, defaults={
                'height': 20,
                'valid': 0,
                'ctime': int(time.time()),
            })
            rack_id = Rack.objects.get(name = assetid).id
            for ind in range(1, 21):
                    RackSpace.objects.get_or_create(rack_id=rack_id, unit_no=ind)

        CB_asset = {
            'assetid':  assetid,
            'service_tag'    : instance.service_tag,
            'asset_type_id'  : instance.asset_type_id,
            'asset_model_id' : instance.asset_model_id,
            'create_time'    : current_time,
            'last_modified'  : current_time,
            'expiration_time': instance.expiration_time,
        }

        CB_asset_create(assetid, self.request.user.username, json.dumps(CB_asset, ensure_ascii=False))

        rack_space_ids = self.request.DATA.get('rack_space_id', None)
        if rack_space_ids is not None:
            space_id_arr = rack_space_ids.split(',')
            RackSpace.objects.filter(id__in=space_id_arr).update(assetid=assetid)

            CB_rack_info = {
                'assetid':  assetid,
                'rack_id':  instance.rack.id,
                'rack_name': instance.rack.name,
                'room_id': instance.rack.room_id,
                'rack_space': rack_space_ids,
                'asset_type_id': instance.asset_type_id
            }
            CB_rack_deploy(assetid, self.request.user.username, json.dumps(CB_rack_info, ensure_ascii=False))

    def get_queryset(self):
        queryset = Asset.objects.all().order_by('-id')
        query_key = self.request.QUERY_PARAMS.get('query_key', None)
        query_value = self.request.QUERY_PARAMS.get('query_value', None)
        if query_value is not None:
            filter_list = query_value.split(',')
            if query_key is not None:
                if 'ip' == query_key:
                    servers = Server.objects.exclude(server_status_id=400).filter(ip__in = filter_list, server_type_id = 1)
                    queryset = queryset.filter(assetid__in=[s.assetid for s in servers])
                elif 'site_app' == query_key:
                    app_list = []
                    site_list = []
                    for sa in filter_list:
                        site_app = sa.split('/')
                        if len(site_app) == 2:
                            site_list.append(site_app[0])
                            app_list.append(site_app[1])
                    sites = Site.objects.filter(name__in = site_list)
                    apps = App.objects.filter(name__in = app_list, site_id__in = [s.id for s in sites], status = 0)
                    servers = Server.objects.exclude(server_status_id=400).filter(app_id__in = [a.id for a in apps], server_type_id = 1)
                    queryset = queryset.filter(assetid__in=[s.assetid for s in servers])
                elif 'assetid' == query_key:
                    queryset = queryset.filter(assetid__in=filter_list)
                elif 'muti_sn' == query_key:
                    queryset = queryset.filter(service_tag__in=filter_list)

        return queryset

class AssetDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    设备单页.

    输入参数： 无

    输出参数：

    * id                    -   PK
    * service_tag           -   设备序列号
    * mac                   -   设备mac地址
    * assetid               -   资产编号
    * asset_type_id         -   资产类型
    * rack_id               -   机柜ID
    * asset_model_id        -   设备型号ID
    * expiration_time       -   过期时间
    * create_time           -   创建时间
    * last_modified         -   修改时间
    """
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

    def perform_update(self, serializer):
        instance = serializer.save()

        CB_asset = {
            'assetid':  instance.assetid,
            'service_tag'    : instance.service_tag,
            'asset_type_id'  : instance.asset_type_id,
            'asset_model_id' : instance.asset_model_id,
            'create_time'    : instance.create_time,
            'last_modified'  : instance.last_modified,
            'expiration_time': instance.expiration_time,
            'new_status': instance.new_status,
            'rack_id': instance.rack_id,
            'room_id': instance.rack.room_id,
        }
        CB_asset_change(instance.assetid, self.request.user.username, json.dumps(CB_asset, ensure_ascii=False))

        rack_space_ids = self.request.DATA.get('rack_space_id', "")

        rack_flag = serializer.validated_data.has_key('rack')
        rack_space_flag = self.request.DATA.get('rack_space_id', False)
        if (rack_flag and not rack_space_flag) or (not rack_flag and rack_space_flag):
            raise YAPIException('服务器上架必须选择机架号和机柜号！')

        if rack_space_ids !="":
            space_id_arr = rack_space_ids.split(',')
            RackSpace.objects.filter(assetid=instance.assetid).update(assetid="")
            RackSpace.objects.filter(id__in=space_id_arr).update(assetid=instance.assetid)

            if instance.rack != 0:
                if Server.objects.exclude(server_status_id=400).filter(assetid=instance.assetid).exists():
                    real_rack_id = instance.rack_id
                    if instance.rack.valid == 0:
                        try:
                            real_rack_id = Rack.objects.get(name=instance.rack.real_name, room_id=instance.rack.room_id).id
                        except Exception, e:
                            raise YAPIException('服务器找不到对应的真实机柜！')
                    Server.objects.exclude(server_status_id=400).filter(assetid=instance.assetid).update(rack_id=real_rack_id)
                    Server.objects.exclude(server_status_id=400).filter(parent=instance.assetid).update(rack_id=real_rack_id)

            CB_rack_info = {
                'assetid':  instance.assetid,
                'rack_id':  instance.rack.id,
                'rack_name': instance.rack.name,
                'room_id': instance.rack.room_id,
                'rack_space': rack_space_ids,
                'asset_type_id': instance.asset_type_id
            }
            CB_rack_move(instance.assetid, self.request.user.username, json.dumps(CB_rack_info, ensure_ascii=False))

    def perform_destroy(self, instance):
        #server判断
        if Server.objects.filter(assetid=instance.assetid).exclude(server_status_id=400).exists():
            raise YAPIException('该设备有正在服务的server，请将该server报废后再删除设备！')

        if instance.rack_id !=0:
            rack_name = instance.rack.name
            rack_id = instance.rack.id
            room_id = instance.rack.room_id
        else:
            rack_name = None
            rack_id = None
            room_id = None

        #机架、机位处理
        CB_asset_info = {
            'assetid':  instance.assetid,
            'service_tag'    : instance.service_tag,
            'asset_type_id'  : instance.asset_type_id,
            'asset_model_id' : instance.asset_model_id,
            'create_time'    : instance.create_time,
            'last_modified'  : instance.last_modified,
            'expiration_time': instance.expiration_time,
            'rack_id': rack_id,
            'room_id': room_id,
        }

        CB_asset_delete(instance.assetid, self.request.user.username, json.dumps(CB_asset_info, ensure_ascii=False))
        rackspace = RackSpace.objects.filter(assetid=instance.assetid)
        rack_space = []
        for item in rackspace:
            rack_space.append(str(item.id))

        CB_rack_info = {
                'assetid':  instance.assetid,
                'rack_id':  rack_id,
                'rack_name': rack_name,
                'room_id': room_id,
                'rack_space': ",".join(rack_space),
                'asset_type_id': instance.asset_type_id,
        }
        CB_rack_deletasset(instance.assetid, self.request.user.username, json.dumps(CB_rack_info, ensure_ascii=False))
        rackspace.update(assetid="")

        ip_tmp = IpTotal.objects.exclude(type=1).filter(asset_info=instance.assetid)
        for item in ip_tmp:
            CB_ip_info = {
                'assetid': instance.assetid,
                'ip': item.ip,
            }
            item.is_used = 0
            item.asset_info = ""
            item.save()
            if item.type == 2:
                CB_mgip_unbind_by_deleteasset(instance.assetid, self.request.user.username,
                                            json.dumps(CB_ip_info, ensure_ascii=False))
            elif item.type == 3:
                CB_ip_unbind_by_deleteasset(instance.assetid, self.request.user.username,
                                            json.dumps(CB_ip_info, ensure_ascii=False))

                if instance.asset_type_id!=1:
                    action_name=u'设备删除'
                    mail_list = SERVER_MAILLIST['scrap']
                    api_url = SERVER_ZABBIX_API['DELETE'] % (SERVER_ZABBIX_ID, item.ip)
                    res = json.loads(urllib.urlopen(api_url).read())
                    zabbix_content = u'请求URL：%s, 请求结果：%s' % (api_url, res['msg'].encode('utf8'))
                    if res['success'] == True:
                        CB_zabbix_delete( item.ip, self.request.user.username)
                    #zabbix调用失败后发送邮件
                    poolname = None
                    sitename = None
                    if res['success'] == False:
                        logger.info(__name__ + ": send failed email.")
                        mail_title = action_name + u'，zabbix状态更新异常：%s' % item.ip
                        html_content = loader.render_to_string('mail/server.html',{'action':action_name,'action_time':stamp2str(time.time()),
                                                                           'poolname':poolname,'ips':item.ip,'username':self.request.user.username,
                                                                           'sitename':sitename,'server_change_content':zabbix_content})
                        sendmail_html(mail_title,html_content,mail_list)
        instance.delete()


class ZoneList(generics.ListCreateAPIView):
    """
    IDC列表页/创建IDC.

    输入参数：

    输出参数：

    * id                    -   PK
    * name                  -   机房编码
    * area_id               -   区域ID
    * area                  -   区域中文名称
    * comment               -   说明
    * points                -   机房经纬坐标
    * ycc_code              -   YCC针对机房的标示符  JQ  SH
    * name_ch               -   机房名称（中文） 金桥（ycc_code=JQ） 南汇（ycc_code=SH）
    * zk_cluster            -   使用的ZK集群
    * rack_total            -   所在zone的总机架数量
    * rack_blade_total      -   所在zone的刀片数量
    * rack_real_total       -   所在zone的真实机架数量

    """
    paginate_by = None
    queryset = Room.objects.all()

    search_fields = ('name', 'area__name_cn', 'comment')
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    filter_fields = ('status', 'ycc_display')
    serializer_class = ZoneSerializer

    def perform_create(self, serializer):
        name = serializer.validated_data['name']
        if Room.objects.filter(name=name):
            raise YAPIException('机房%s已存在，无需重新录入！' % name)
        serializer.save()

class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    IDC详情页.

    输入参数：

    输出参数：

    * id                    -   PK
    * name                  -   机房编码
    * area                  -   区域ID
    * comment               -   说明
    * points                -   机房经纬坐标
    * ycc                   -   YCC针对机房的标示符
    * zk_cluster            -   使用的ZK集群
    """

    queryset = Room.objects.all()
    serializer_class = ZoneSerializer


class AssetTypeList(generics.ListCreateAPIView):
    """
    设备类型列表页/创建设备类型页面.

    输入参数：

    输出参数：

    * id                    -   PK
    * name                  -   英文名称
    * comment               -   说明
    * short_name            -   缩写（资产编号用到）
    """
    paginate_by = None
    queryset = AssetType.objects.all()
    serializer_class = AssetTypeSerializer


class AssetTypeDetail(generics.RetrieveUpdateAPIView):
    """
    设备类型详情页

    输入参数：无

    输出参数：

    * id                    -   PK
    * name                  -   英文名称
    * comment               -   说明
    * short_name            -   缩写（资产编号用到）
    """
    paginate_by = None
    queryset = AssetType.objects.all()
    serializer_class = AssetTypeSerializer


class AssetModelList(generics.ListCreateAPIView):
    """
    设备类型列表页/创建设备类型页面.

    输入参数：无

    输出参数：

    * id                    -   PK
    * name                  -   型号
    * comment               -   备注
    """
    paginate_by = None
    queryset = AssetModel.objects.all().order_by("-id")

    search_fields = ('name', )
    filter_backends = (filters.SearchFilter,)
    serializer_class = AssetModelSerializer

    def perform_create(self, serializer):
        name = serializer.validated_data['name']
        if AssetModel.objects.filter(name=name):
            raise YAPIException('%s的设备型号信息已存在，无需重新录入！' % name)
        serializer.save()

class AssetModelDetail(generics.RetrieveUpdateAPIView):
    """
    设备型号详情页

    输入参数：无

    输出参数：

    * id                    -   PK
    * name                  -   型号
    * comment               -   备注
    """
    paginate_by = None
    queryset = AssetModel.objects.all()
    serializer_class = AssetModelSerializer


class IpSegmentList(generics.ListCreateAPIView):
    """
    IP段列表.

    输入参数：
    * ip        -   按IP筛选
    * type      -   按IP类型筛选
    * mask      -   按简码筛选
    * idc       -   按IDC筛选
    * owner     -   按供应商类型筛选
    * is_gen_ip -   是否生成IP地址
    * page_size - 每页显示的数量。如page_size=50则表示每页展示50条记录

    输出参数：

    * id        -   pk
    * ip        -   ip地址
    * type      -   IP类型   1-外网  2-带外  3-内网
    * type_name -   IP类型
    * mask      -   子网简码
    * idc       -   所属IDC  1-南汇  4-金桥  8-CDS（混合云）
    * idc       -   所属IDC
    * owner     -   IP所属供应商   1-电信  2-联通  3-BGP  5-内网  6-带外
    * owner_name-   IP所属供应商
    * comment   -   备注
    * status    -   IP状态 1-有效  0-无效
    * created   -   创建时间
    """
    queryset = IpSegment.objects.filter(status=1).order_by('-id')
    search_fields = ('ip', 'type', 'mask', 'idc', 'owner')
    filter_backends = (filters.SearchFilter,)
    serializer_class = IpSegmentSerializer

    def perform_create(self, serializer):
        segment = serializer.validated_data['ip']
        mask = serializer.validated_data['mask']
        ip_network_obj = IPNetwork('/'.join([segment, str(mask)]))
        for ip_segment_obj in IpSegment.objects.filter(status=1):
            old_ip_network = '/'.join([ip_segment_obj.ip, str(ip_segment_obj.mask)])
            old_ip_network_obj = IPNetwork(old_ip_network)
            if set(range(ip_network_obj.first, ip_network_obj.last + 1)) & set(
                    range(old_ip_network_obj.first, old_ip_network_obj.last + 1)):
                raise Exception('新建的网段和已有网段(%s)有交集，创建失败' % old_ip_network)
        instance = serializer.save(created=stamp2str(time.time()))
        is_gen_ip = self.request.DATA.get('is_gen_ip', None)
        if is_gen_ip is not None:
            ip_str = "%s/%d" % (instance.ip, instance.mask)
            records = []
            ipnet = IPNetwork(ip_str)
            status = 1
            for ip in ipnet:
                ip_string = "%s" % ip
                ip_array = ip_string.split('.')
                if instance.type == 2: #管理IP地址生成规则
                    if ip == ipnet.network or ip == ipnet.broadcast or ip_array[3] == '0' or ip_array[3] == '255':
                        status = 0
                    else:
                        status = 1

                    if instance.idc == 1 and ip_string.find("10.61.15") == 0: #南汇管理IP
                        status = 0

                    if instance.idc == 4 and int(ip_array[3]) >= 249:
                        status = 0
                elif instance.type == 3: #内网IP地址生成规则
                    if ip == ipnet.network or ip == ipnet.broadcast:
                        status = 0
                    else:
                        status = 1
                    if int(ip_array[3]) > 230:
                        status = 0
                    if int(ip_array[3]) >=191 and int(ip_array[3]) <=200:
                        status = 0
                records.append(IpTotal(ip=ip, ip_segment_id=instance.id, type=instance.type, idc=instance.idc, status=status, ip1=int(ip_array[0]), ip2=int(ip_array[1]), ip3=int(ip_array[2]), ip4=int(ip_array[3])))
            IpTotal.objects.bulk_create(records, batch_size=1024)


class IpSegmentDetail(generics.RetrieveUpdateAPIView):
    """
    IP段详情页.

    输入参数： 无

    输出参数：

    * id        -   pk
    * ip        -   ip地址
    * type      -   IP类型   1-外网  2-带外  3-内网
    * mask      -   子网简码
    * idc       -   所属IDC  1-南汇  4-金桥  8-CDS（混合云）
    * owner     -   IP所属供应商   1-电信  2-联通  3-BGP  5-内网  6-带外
    * comment   -   备注
    * status    -   IP状态 1-有效  0-无效
    * created   -   创建时间
    """
    queryset = IpSegment.objects.filter(status=1)
    serializer_class = IpSegmentSerializer

class IpListFilter2(django_filters.FilterSet):
   # start_exp_time = django_filters.NumberFilter(name="expiration_time", lookup_type='gte')
   # ip_search = django_filters.CharFilter(name="ip", lookup_type='startswith')
    class Meta:
        model = IpTotal2
        fields = [ 'type', 'idc', 'asset_type', 'asset_info', 'ip', 'is_virtual', 'is_used','ip_segment__owner']

class IpList2(generics.ListAPIView):
    """
    IP列表.

    输入参数：
    * ip                    -   按IP筛选
    * type                  -   按IP类型筛选  1-外网  2-管理  3-内网
    * ip_segment_id         -   按所属IP段ID筛选
    * asset_type            -   按设备类型筛选
    * is_virtual            -   按是否虚IP筛选
    * is_used               -   按IP是否使用筛选
    * page_size             - 每页显示的数量。如page_size=50则表示每页展示50条记录

    输出参数：

    * id                    -   pk
    * ip_segment_id         -   ip段ID
    * ip                    -   IP
    * asset_type            -   设备类型 0-暂无 1-路由器 2-交换机 3-防火墙 4-A10 5-NETSCALER 6-HAPROXY 7-临时设备 8-软路由 9-VPN 10-服务器
    * business_info         -   IP用途
    * is_used               -   是否被使用
    * is_virtual            -   是否虚IP
    * status                -   IP是否可用
    """
    queryset = IpTotal2.objects.filter(status=1)
    #queryset = IpTotal.objects.filter(type=2)
   # filter_fields = ('ip_segment_id', 'type', 'idc', 'asset_type', 'asset_info', 'ip', 'is_virtual', 'is_used')
    search_fields = ('ip',)
    filter_class=IpListFilter2
    # filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter,)
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter,)
    serializer_class = IpSerializer2

    def get_queryset(self):
        queryset = IpTotal2.objects.filter(status=1)
        muti_key = self.request.QUERY_PARAMS.get('muti_key', None)
        if muti_key is not None:
            filter_list = muti_key.split(',')
            #filter_list = muti_key
            queryset = queryset.filter(ip__in=filter_list)

        return queryset

class IpDetail2(generics.RetrieveUpdateAPIView):
    queryset = IpTotal2.objects.filter(status=1)
    serializer_class = IpSerializer2

class IpListFilter(django_filters.FilterSet):
   # start_exp_time = django_filters.NumberFilter(name="expiration_time", lookup_type='gte')
    ip_search = django_filters.CharFilter(name="ip", lookup_type='startswith')
    class Meta:
        model = IpTotal
        fields = ['ip_segment_id', 'type', 'idc', 'asset_type', 'asset_info', 'ip','ip_search', 'is_virtual', 'is_used']


class IpList(generics.ListAPIView):
    """
    IP列表.

    输入参数：
    * ip                    -   按IP筛选
    * type                  -   按IP类型筛选  1-外网  2-管理  3-内网
    * ip_segment_id         -   按所属IP段ID筛选
    * asset_type            -   按设备类型筛选
    * is_virtual            -   按是否虚IP筛选
    * is_used               -   按IP是否使用筛选
    * page_size             - 每页显示的数量。如page_size=50则表示每页展示50条记录

    输出参数：

    * id                    -   pk
    * ip_segment_id         -   ip段ID
    * ip                    -   IP
    * asset_type            -   设备类型 0-暂无 1-路由器 2-交换机 3-防火墙 4-A10 5-NETSCALER 6-HAPROXY 7-临时设备 8-软路由 9-VPN 10-服务器
    * business_info         -   IP用途
    * is_used               -   是否被使用
    * is_virtual            -   是否虚IP
    * status                -   IP是否可用
    """
    queryset = IpTotal.objects.filter(status=1)
    #queryset = IpTotal.objects.filter(type=2)
   # filter_fields = ('ip_segment_id', 'type', 'idc', 'asset_type', 'asset_info', 'ip', 'is_virtual', 'is_used')
    filter_class=IpListFilter
    filter_backends = (filters.DjangoFilterBackend,)
    serializer_class = IpSerializer
    def get_queryset(self):
        queryset = IpTotal.objects.filter(status=1)
        muti_key = self.request.QUERY_PARAMS.get('muti_key', None)
        if muti_key is not None:
            filter_list = muti_key.split(',')
            #filter_list = muti_key
            queryset = queryset.filter(ip__in=filter_list)

        return queryset

    # def get_queryset(self):
    #     queryset = IpTotal.objects.filter(status=1)
    #     type = self.request.QUERY_PARAMS.get('type', None)
    #     if type is not None:
    #         ipsegments = IpSegment.objects.filter(type=type)
    #         segments_ids = [item.id for item in ipsegments]
    #         queryset = queryset.filter(ip_segment_id__in=segments_ids)
    #     return queryset

class IpBind(APIView):

    permission_classes = (IpBindPermission,)

    def get(self, request, format=None):
        dd = {
            'assetid': '设备编号',
            'ip': '待绑定的IP地址',
            'mgip': '待绑定的管理IP地址',
        }
        return Response(dd)

    def post(self, request, format=None):
        assetid = request.POST.get('assetid', None)
        mgip = request.POST.get('mgip', None)
        ip = request.POST.get('ip', None)
        if ip == "":
            ip = None
        if mgip == "":
            mgip = None
        if assetid is None or (mgip is None and ip is None):
            return Response(status=status.HTTP_400_BAD_REQUEST, data='input params can\'t be empty.')

        #判断设备是否存在
        try:
            asset = Asset.objects.get(assetid=assetid)
        except Asset.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='%s is not exists.' % assetid)

        #IP如果存在
        if ip is not None:
            if asset.asset_type_id == 1:
                if not Server.objects.filter(assetid=assetid).exclude(server_status_id=400).exists():
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not init,please init asset first.' % assetid)
            #判断主机记录是否服务中
            if Server.objects.filter(assetid=assetid, server_status_id__in=[50, 200, 210]).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data='%s is not allowed bind/unbind.' % assetid)

            #IP解绑逻辑
            if ip == '-1':
                server_tmp = None
                if asset.asset_type_id == 1:
                    try:
                        server_tmp = Server.objects.exclude(server_status_id=400).get(assetid=assetid)
                        if server_tmp.server_status_id == 100:
                            api_url = "http://oms.yihaodian.com.cn/itil/api/?action=monitor_temple2&auth_id=%s&method=delete&ip=%s" % (SERVER_ZABBIX_ID, server_tmp.ip)
                            res = json.loads(urllib.urlopen(api_url).read())
                            if res['success'] == True:
                                CB_zabbix_delete(server_tmp.ip, self.request.user.username)
                    except Server.DoesNotExist:
                        return Response(status=status.HTTP_400_BAD_REQUEST,
                                        data='%s has not exists in server table.' % assetid)
                    except Server.MultipleObjectsReturned:
                        return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has multip server record.please contact lizhigang.' % assetid)

                try:
                    ip_tmp = IpTotal.objects.get(type=3, asset_info=assetid)
                    CB_ip_info = {
                        'assetid': assetid,
                        'ip': ip_tmp.ip,
                    }
                    ip_tmp.is_used = 0
                    ip_tmp.asset_info = ""
                    ip_tmp.save()
                    CB_ip_unbind_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
                    if asset.asset_type_id == 1 and server_tmp:
                        server_tmp.ip = ''
                        server_tmp.save()
                        CB_server_unbindip_by_changeasset(assetid, self.request.user.username,
                                                      json.dumps(CB_ip_info, ensure_ascii=False))
                    if asset.asset_type_id != 1:
                        api_url = SERVER_ZABBIX_API['DELETE'] % (SERVER_ZABBIX_ID, ip_tmp.ip)
                        res = json.loads(urllib.urlopen(api_url).read())
                        if res['success'] == True:
                            CB_zabbix_delete(ip_tmp.ip, self.request.user.username)

                except IpTotal.DoesNotExist:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not exists in ip table.' % assetid)
                except IpTotal.MultipleObjectsReturned:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has alread bind multip ip.please contact lizhigang.' % assetid)
            else:
            #IP绑定逻辑
                #设备从来没有绑定过
                if IpTotal.objects.filter(type=3, asset_info=assetid).exists():
                    return Response(status=status.HTTP_400_BAD_REQUEST, data='%s has been bound already.' % assetid)
                #要绑定的IP可用
                if IpTotal.objects.filter(type=3, ip=ip, is_used=0, status=1).exists():
                    ip_tmp1 = IpTotal.objects.get(ip=ip)
                    CB_ip_info = {
                        'assetid': assetid,
                        'ip': ip,
                    }
                    ip_tmp1.is_used = 1
                    ip_tmp1.asset_info = assetid
                    ip_tmp1.save()
                    CB_ip_bind_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
                    #判断是否需要同步server表
                    if asset.asset_type_id == 1:
                        try:
                            server_tmp1 = Server.objects.exclude(server_status_id=400).get(assetid=assetid)
                            server_tmp1.ip = ip
                            server_tmp1.save()
                            CB_ip_info = {
                                'assetid': assetid,
                                'ip': ip,
                            }
                            CB_server_bindip_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
                            api_url = "http://oms.yihaodian.com.cn/itil/api/?action=monitor_temple2&auth_id=%s&method=free&ip=%s" % (SERVER_ZABBIX_ID, ip)
                            res = json.loads(urllib.urlopen(api_url).read())
                            if res['success'] == True:
                                CB_zabbix_free(ip, self.request.user.username)
                        except Server.DoesNotExist:
                            return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not init,please init asset first.' % assetid)
                    else:
                        api_url = SERVER_ZABBIX_API['FREE'] % (SERVER_ZABBIX_ID, ip)
                        res = json.loads(urllib.urlopen(api_url).read())
                        if res['success'] == True:
                            CB_zabbix_free(ip, self.request.user.username)
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='your input %s has not exists in ip table.' % ip)

        #如果管理IP存在
        if mgip is not None:
            if mgip == '-1':
                try:
                    ip_tmp = IpTotal.objects.get(type=2, asset_info=assetid)
                    server_tmp = Server.objects.exclude(server_status_id=400).get(assetid=assetid)
                    CB_ip_info = {
                        'assetid': assetid,
                        'ip': ip_tmp.ip,
                    }
                    ip_tmp.is_used = 0
                    ip_tmp.asset_info = ""
                    ip_tmp.save()
                    CB_mgip_unbind_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
                    server_tmp.mgmt_ip = ""
                    server_tmp.save()
                    CB_server_unbindmgip_by_changeasset(assetid, self.request.user.username,
                                                      json.dumps(CB_ip_info, ensure_ascii=False))
                except IpTotal.DoesNotExist:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not exists in ip table.' % assetid)
                except IpTotal.MultipleObjectsReturned:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has alread bind multip ip.please contact lizhigang.' % assetid)
                except Server.DoesNotExist:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not exists in server table.' % assetid)
                except Server.MultipleObjectsReturned:
                    return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has multip server record.please contact lizhigang.' % assetid)
            else:
                #设备从来没有绑定过
                if IpTotal.objects.filter(type=2, asset_info=assetid).exists():
                    return Response(status=status.HTTP_400_BAD_REQUEST, data='%s has been bound already.' % assetid)
                if IpTotal.objects.filter(type=2, ip=mgip, is_used=0, status=1).exists():
                    mgip_tmp = IpTotal.objects.get(ip=mgip)
                    CB_ip_info = {
                        'assetid': assetid,
                        'mgip': mgip,
                    }
                    mgip_tmp.is_used = 1
                    mgip_tmp.asset_info = assetid
                    mgip_tmp.save()
                    CB_mgip_bind_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))

                    #判断是否需要同步server表
                    if asset.asset_type_id == 1:
                        try:
                            server_tmp1 = Server.objects.exclude(server_status_id=400).get(assetid=assetid)
                            server_tmp1.mgmt_ip = mgip
                            server_tmp1.save()
                            CB_ip_info = {
                                'assetid': assetid,
                                'mgip': mgip,
                            }
                            CB_server_bindmgip_by_changeasset(assetid, self.request.user.username,
                                                json.dumps(CB_ip_info, ensure_ascii=False))
                        except Server.DoesNotExist:
                            return Response(status=status.HTTP_400_BAD_REQUEST,
                                    data='%s has not init,please init asset first.' % assetid)
                elif IpTotal.objects.filter(type=2, ip=mgip, is_used=1, status=1).exists():
                    return Response(status=status.HTTP_400_BAD_REQUEST, data='your input %s has been used.' % mgip)
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST, data='your input %s is not available.please contact lizhigang.' % mgip)
        return Response(status=status.HTTP_200_OK, data='bind/unbind IP success')


class IpDetail(generics.RetrieveUpdateAPIView):
    queryset = IpTotal.objects.filter(status=1)
    serializer_class = IpSerializer


class RackSpaceList(generics.ListCreateAPIView):
    """
    IP列表.

    输入参数：
    * rack_id               -   按机架筛选
    * assetid               -   按资产编号筛选

    输出参数：

    * id                    -   pk
    * rack_id               -   机架ID
    * unit_no               -   真实机架编号
    * assetid               -   资产编号
    """
    queryset = RackSpace.objects.all()
    filter_fields = ('rack_id', 'assetid')
    filter_backends = (filters.DjangoFilterBackend,)
    serializer_class = RackSpaceSerializer


class RackList(generics.ListCreateAPIView):
    """
    机柜列表.

    输入参数：
    * room               -   按机房筛选。1-DCB  4-DCD
    * name               -   按机柜名称筛选
    * valid              -   机柜类型 0为刀片笼子  1为真实机柜


    输出参数：
    * id                    -   pk
    * name                  -   机柜名称
    * real_name             -   机柜名称，如果类型为刀片时，该字段表示刀片笼子所在的真实机柜位置
    * room                  -   机房ID
    * room_name             -   机房编号
    * height                -   机柜高度
    * valid                 -   类型
    * type_name             -   类型名称，对应valid
    * comment               -   备注
    """
    queryset = Rack.objects.all().order_by('-id')

    search_fields = ('name', 'valid', 'room__name')
    filter_backends = (filters.SearchFilter,)
    serializer_class = RackSerializer

    def perform_create(self, serializer):
        current_time = int(time.time())
        name = self.request.QUERY_PARAMS.get('name')
        # name = serializer.validated_data['name']
        if Rack.objects.filter(name=name, room_id=int(self.request.DATA.get('room'))):
            raise YAPIException('%s的机架信息已存在，无需重新录入！' % name)
        if self.request.QUERY_PARAMS.get('valid') == 0:
            try:
                asset_info = Asset.objects.get(assetid=name)
                if Rack.objects.filter(id=asset_info.rack_id):
                    raise YAPIException('该机架的信息已存在，无需重新录入！')
            except Asset.DoesNotExist:
                raise YAPIException('该机架的容器设备不存在，请先录入容器信息！')
        else:
            ip_min = self.request.QUERY_PARAMS.get('ip_min', 0)
            ip_max = self.request.QUERY_PARAMS.get('ip_max', 0)
            # ip_min = serializer.validated_data['ip_min']
            # ip_max = serializer.validated_data['ip_max']

            # serializer.save(ctime=current_time, ip_min=ip_min, ip_max=ip_max)
            # room_id = serializer.data['room']
            # cname = serializer.data['name']
            # dd = Rack.objects.get(room_id=room_id, name=cname)
            # id = dd.id
            # height = serializer.data['height']
            #
            # if id:
            #     for ind in range(1, height+1):
            #         RackSpace.objects.get_or_create(rack_id=id, unit_no=ind)
            rack = serializer.save(ctime=current_time, ip_min=ip_min, ip_max=ip_max)
            if rack.id:
                for ind in range(1, rack.height+1):
                    RackSpace.objects.get_or_create(rack_id=rack.id, unit_no=ind)

class RackDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    机柜列表.

    输入参数：


    输出参数：
    """
    queryset = Rack.objects.all()
    serializer_class = RackSerializer


class AssetRepairList(generics.ListCreateAPIView):

    queryset = AssetRepair.objects.all().order_by('-id')
    serializer_class = AssetRepairSerializer

    search_fields = ('asset__assetid', 'asset__service_tag')
    filter_backends = (filters.SearchFilter,)

    def perform_create(self, serializer):
        ctime = int(time.time())
        instance = serializer.save(reson_time=ctime)
        asset_id = instance.asset.id
        Asset.objects.filter(pk=asset_id).update(new_status=3)


class AssetRepairDetail(generics.RetrieveUpdateDestroyAPIView):

    queryset = AssetRepair.objects.all().order_by('-id')
    serializer_class = AssetRepairSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        is_repair = int(self.request.DATA.get('is_repair', 0))
        if is_repair != 0:
            if is_repair == 1:
                new_status = 0
            elif is_repair == 2:
                new_status = 1
            elif is_repair == 3:
                new_status = 2
            Asset.objects.filter(pk=instance.asset_id).update(new_status=new_status)
