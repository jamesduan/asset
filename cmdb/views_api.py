# -*- coding: utf-8 -*-
from itertools import chain
import json
from django.http import HttpResponse
from rest_framework import generics,status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from serializers import *
from rest_framework import filters
import time,re
from cmdb.models import *
from django.db import connection
from ycc.models import ConfigInfo, ConfigDbConfiginfo
from ycc.models import ConfigEnv
from rest_framework import status
from util.utils import get_app_filter_by_request_user
from ycc.models import ConfigGroup
from cmdb.utils import sync_by_cmis
from django.db.models import Q
from cmdb.permissions import *

# ConfigDbInstanceList管理员名称配置
cdilname = "DB管理员"


class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class SiteList(generics.ListCreateAPIView):
    """
    站点列表接口.

    输入参数：page_size  每页展示数量

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID（同步过来）
    * name      -   站点名称（英文）
    * comment   -   站点名称（中文）
    * created   -   创建时间
    """
    queryset = Site.objects.filter(status=0)

    search_fields = ('name', 'comment')
    filter_backends = (filters.SearchFilter,)

    serializer_class = SiteSerializer

    def perform_create(self, serializer):
        name = self.request.DATA.get('name')
        if Site.objects.filter(name = name):
            raise YAPIException('error:this site_name has already exists!')
        else:
            serializer.save(created=time.time())


class SiteDetail(generics.RetrieveUpdateAPIView):
    """
    站点信息接口.

    输入参数：无

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID（同步过来）
    * name      -   站点名称（英文）
    * comment   -   站点名称（中文）
    * created   -   创建时间
    """
    queryset = Site.objects.filter(status=0)
    serializer_class = SiteSerializer

    def perform_update(self, serializer):
        serializer.save(status=1)

class SiteByNameDetail(generics.RetrieveUpdateAPIView):
    """
    站点信息接口.

    输入参数：无

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID（同步过来）
    * name      -   站点名称（英文）
    * comment   -   站点名称（中文）
    * created   -   创建时间
    """
    queryset = Site.objects.filter(status=0)
    serializer_class = SiteSerializer
    lookup_field = 'name'


class AppList(generics.ListCreateAPIView):
    """
    APP(pool)列表接口.

    输入参数：

    * site_id   -   站点ID （可选，如无此参数则为所有app列表）
    * type      -   筛选业务POOL或非业务POOL
    * level     -   按POOL级别筛选
    * name      -   pool名
    * site_name -   站点名（查询可选）
    * domainid  -   Domain ID（查询可选）
    * domain_id_list    -   Domain ID列表（查询可选）

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID号
    * cmis_site_id - CMIS系统的site ID号
    * name      -   app名称（英文）
    * site_id   -   站点ID（中文）
    * type      -   0-业务POOL（数据来源CMIS系统）  1-非业务POOL
    * type_name -   pool类型（中文）
    * comment   -   注释字段
    * type      -   pool类型
    * level     -   pool重要级别
    * hudson_job -  废弃字段
    * domainid  -   Domain ID
    * ctime     -   创建时间
    * service_name  -   tomcat标签
    * groups    -   pool分组
    """
    queryset = App.objects.filter(status=0).order_by('name')
    serializer_class = AppSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    filter_fields = ('site_id', 'id', 'type', 'level', 'domainid',)
    search_fields = ('name', 'level')

    def perform_create(self, serializer):
        site_id = self.request.DATA.get('site_id')
        name = self.request.DATA.get('name')
        if App.objects.filter(site_id = site_id, name = name):
            raise YAPIException('error:%s site_name/app_name has already exists!' % name)
        else:
            serializer.save(ctime=time.time())

    def get_queryset(self):
        queryset = App.objects.filter(status=0).order_by('name')
        site_name = self.request.QUERY_PARAMS.get('site_name', None)
        name = self.request.QUERY_PARAMS.get('name', None)
        domain_id_list = self.request.QUERY_PARAMS.get('domain_id_list', [])
        acl_domain = self.request.QUERY_PARAMS.get('acl_domain', None)
        filters = dict()
        if site_name:
            try:
                site = Site.objects.get(name=site_name)
            except Site.DoesNotExist:
                raise YAPIException('error:%s does not exists in Site table!' % site_name)
            filters['site_id'] = site.id
        if name:
            filters['name'] = name
        if domain_id_list:
            filters['domainid__in'] = domain_id_list.split(',')
        queryset=queryset.filter(**filters)
        return queryset

class AppWebList(generics.ListCreateAPIView):
    """
    APP(pool管理页面)列表接口.

    输入参数：

    * site_id   -   站点ID （可选，如无此参数则为所有app列表）
    * type      -   筛选业务POOL或非业务POOL
    * level     -   按POOL级别筛选
    * name      -   pool名
    * site_name -   站点名（查询可选）
    * domainid  -   Domain ID（查询可选）
    * domain_id_list    -   Domain ID列表（查询可选）

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID号
    * cmis_site_id - CMIS系统的site ID号
    * name      -   app名称（英文）
    * site_id   -   站点ID（中文）
    * type      -   0-业务POOL（数据来源CMIS系统）  1-非业务POOL
    * type_name -   pool类型（中文）
    * comment   -   注释字段
    * type      -   pool类型
    * level     -   pool重要级别
    * hudson_job -  废弃字段
    * domainid  -   Domain ID
    * ctime     -   创建时间
    * service_name  -   tomcat标签
    * groups    -   pool分组
    """
    queryset = AppWeb.objects.filter(status=0).order_by('name')
    serializer_class = AppWebSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    filter_fields = ('site_id', 'id', 'type', 'level', 'domainid',)
    search_fields = ('name', 'level')

    def perform_create(self, serializer):
        site_id = self.request.DATA.get('site_id')
        name = self.request.DATA.get('name')
        if AppWeb.objects.filter(site_id = site_id, name = name):
            raise YAPIException('error:%s site_name/app_name has already exists!' % name)
        else:
            serializer.save(ctime=time.time())

    def get_queryset(self):
        queryset = AppWeb.objects.filter(status=0).order_by('name')
        site_name = self.request.QUERY_PARAMS.get('site_name', None)
        name = self.request.QUERY_PARAMS.get('name', None)
        domain_id_list = self.request.QUERY_PARAMS.get('domain_id_list', [])
        filters = dict()
        if site_name:
            try:
                site = Site.objects.get(name=site_name)
            except Site.DoesNotExist:
                raise YAPIException('error:%s does not exists in Site table!' % site_name)
            filters['site_id'] = site.id
        if name:
            filters['name'] = name
        if domain_id_list:
            filters['domainid__in'] = domain_id_list.split(',')
        return queryset.filter(**filters)


class AppDetail(generics.RetrieveUpdateAPIView):
    """
    APP(pool)单页接口.

    输入参数：无

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID号
    * cmis_site_id - CMIS系统的site ID号
    * name      -   app名称（英文）
    * site_id   -   站点ID（中文）
    * type      -   0-业务POOL（数据来源CMIS系统）  1-非业务POOL
    * comment   -   注释字段
    * type      -   pool类型
    * level     -   pool重要级别
    * hudson_job -  废弃字段
    * domainid  -   CMIS系统domainID表
    """
    queryset = App.objects.filter(status=0).order_by('name')
    serializer_class = AppSerializer

    def perform_update(self, serializer):
        serializer.save(status=1)


class AppByNameDetail(generics.RetrieveAPIView):
    """
    APP(pool)单页接口.

    输入参数：无

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID号
    * cmis_site_id - CMIS系统的site ID号
    * name      -   app名称（英文）
    * site_id   -   站点ID（中文）
    * type      -   0-业务POOL（数据来源CMIS系统）  1-非业务POOL
    * comment   -   注释字段
    * type      -   pool类型
    * level     -   pool重要级别
    * hudson_job -  废弃字段
    """
    queryset = App.objects.filter(status=0)
    serializer_class = AppSerializer
    lookup_field = 'name'


class AppContactList(generics.ListAPIView):
    """
    APP联系人列表接口.

    输入参数：

    * site_id   -   按照站点ID
    * site_name -   按照站点名称筛选
    * pool_id   -   按POOLID筛选
    * pool_name -   按POOL名称筛选

    输出参数：

    * site_id               -   站点ID
    * site_name             -   站点名称
    * app_id               -   应用ID
    * app_name             -   应用名称
    * app_level            -   应用级别
    * department_id         -   部门ID
    * department            -   部门名称
    * p_user                -   domain leader联系人
    * p_email               -   domain leader邮箱
    * p_no                  -   domain leader手机
    * domain_email          -   domain组邮件
    * sa_user               -   SA联系人
    * sa_email              -   SA联系人邮箱
    * sa_no                 -   SA联系人手机
    * b_user                -   domain leader备联系人
    * b_email               -   domain leader备联系人邮箱
    * b_no                  -   domain leader备联系人手机
    * domain_id             -   domain ID号
    * domain_name           -   domain名称
    * domain_code           -   domain标识符
    * domain_leader         -   domain leader
    * domain_account        -   domain leader
    * sa_backup_user        -   SA备联系人
    * sa_backup_email       -   SA备联系人邮箱
    * sa_backup_no          -   SA备联系人手机
    * head_user             -   head联系人
    * head_email            -   head邮箱
    * head_no               -   head联系电话
    """
    queryset = AppContact.objects.filter(pool_status = 0)
    serializer_class = AppContactSerializer
    filter_fields = ('site_id', 'site_name', 'pool_id', 'pool_name')
    search_fields = ('site_name', 'pool_name', 'department', 'domain_name', 'domain_email', 'head_user', 'head_email', 'p_user', 'p_email', 'b_user',
    'b_email', 'sa_user', 'sa_email', 'sa_backup_user', 'sa_backup_email')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    paginate_by = None


class DdUsersList(generics.ListAPIView):
    """
    基础用户表.

    输入参数：

    *

    输出参数：

    * id                -   PK
    * username          -   域控账号
    * display_name      -   展示名称
    * email             -   域控邮箱
    * domains           -   所属domain
    """
    queryset = DdUsers.objects.filter(enable=0)
    serializer_class = DdUsersSerializer
    filter_fields = ('username', 'domains')
    search_fields = ('username', 'display_name', 'username_ch')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)

    def get_queryset(self):
        queryset =  DdUsers.objects.filter(enable=0)
        usertel = self.request.QUERY_PARAMS.get('usertel',None)
        if usertel is not None:
            queryset = queryset.filter(Q(username = usertel)|Q(username_ch = usertel)|Q(telephone = usertel))
        return queryset


class DdUsersListV2(generics.ListAPIView):
    """
    基础用户表.

    输入参数：

    *

    输出参数：

    * id                -   PK
    * username          -   域控账号
    * display_name      -   展示名称
    * email             -   域控邮箱
    * domains           -   所属domain
    """
    queryset = DdUsers.objects.filter(enable=0)
    serializer_class = DdUsersV2Serializer
    filter_fields = ('username',)
    search_fields = ('username', 'display_name', 'username_ch')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None


class DdDomainList(generics.ListAPIView):
    """
    domain信息接口.

    输入参数：

    * departmentid   -   部门ID
    * domaincode     -   按照domaincode筛选
    * domainname     -   domain名称
    * departmentname -   按部门名称
    * page_size      -   每页显示数量

    输出参数：

    * id                  -   pk
    * domaincode          -   domain编码
    * domainname          -   domain名称
    * domainemailgroup    -   domain邮箱
    * domainleaderaccount -   DL
    * backupdomainleaderaccount         -  后备DL
    * departmentid            -   部门ID
    * departmentname               -   所属部门名称
    """
    queryset = DdDomain.objects.filter(enable=0)
    serializer_class = DdDomainSerializer
    filter_fields = ('id', 'domaincode', 'domainname', 'departmentid', 'departmentname')
    search_fields = ('domaincode', 'domainname', 'domainemailgroup', 'domainleaderaccount', 'backupdomainleaderaccount')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)


class DdDomainListV2(generics.ListAPIView):
    """
    domain信息接口.

    输入参数：

    * departmentid   -   部门ID
    * domaincode     -   按照domaincode筛选
    * domainname     -   domain名称
    * departmentname -   按部门名称
    * page_size      -   每页显示数量

    输出参数：

    * id                  -   pk
    * domaincode          -   domain编码
    * domainname          -   domain名称
    * domainemailgroup    -   domain邮箱
    * domainleaderaccount -   DL
    * backupdomainleaderaccount         -  后备DL
    * departmentid            -   部门ID
    * departmentname               -   所属部门名称
    """
    queryset = DdDomainV2.objects.select_related().filter(enable=0)
    serializer_class = DdDomainV2Serializer
    filter_fields = ('id', 'domaincode', 'domainname', 'department__id', 'departmentname')
    filter_backends = (filters.DjangoFilterBackend, )

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):
        dept_id_in = self.request.QUERY_PARAMS.get('dept_id_in', None)
        filters = {}
        if dept_id_in:
            filters['department__id__in'] = dept_id_in.split(',')
        return self.queryset.filter(**filters)


class DdUsersDomainsList(generics.ListAPIView):
    """
    user和domain关系查询信息接口.

    输入参数：

    * ddusers__username        -   域控账号
    * dddomain__domaincode     -   按照domaincode筛选
    * dddomain__domainname     -   domain名称
    * page_size                -   每页显示数量

    输出参数：

    * id              -   pk
    * ddusers         -   用户
    * dddomain        -   Domain
    """
    queryset = DdUsersDomains.objects.all()
    serializer_class = DdUsersDomainsSerializer
    filter_fields = ('id', 'ddusers__username', 'dddomain__domaincode', 'dddomain__domainname','dddomain__id')
    search_fields = ('ddusers__username', 'ddusers__username_ch', 'ddusers__display_name', 'dddomain__domaincode', 'dddomain__domainname', 'dddomain__domainemailgroup')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)

class DdUsersDomainsforrotaList(generics.ListAPIView):
    queryset = DdUsersDomains.objects.all()
    serializer_class = DdUsersDomainsforrotaSerializer
    filter_fields = ('id', 'ddusers__username', 'dddomain__domaincode', 'dddomain__domainname','dddomain__id')
    search_fields = ('ddusers__username', 'ddusers__display_name', 'dddomain__domaincode', 'dddomain__domainname', 'dddomain__domainemailgroup')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)


class DdDepartmentList(generics.ListAPIView):
    """
    部门列表接口.

    输入参数：

    * deptlevel   -   部门级别
    * pid         -   父级部门ID
    * page_size      -   每页显示数量

    输出参数：

    * id                -   pk
    * deptcode          -   部门编码
    * deptname          -   部门名称
    * deptemailgroup    -   部门邮箱
    * deptleaderaccount -   部门领导
    * deptlevel         -   部门所属分级
    * pid               -   所属上级部门ID
    """
    queryset = DdDepartmentNew.objects.filter(enable=0)
    filter_fields = ('deptlevel', 'pid')
    filter_backends = (filters.DjangoFilterBackend,)
    serializer_class = DdDepartmentSerializer

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None

    def get_queryset(self):
        pid_in = self.request.QUERY_PARAMS.get('pid_in', None)
        filters = {}
        if pid_in is not None:
            filters['pid__in'] = pid_in.split(',')
        return self.queryset.filter(**filters)


class ConfigDbInstanceList(generics.ListCreateAPIView):
    queryset = ConfigDbInstance.objects.order_by('-id')
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('cname',)
    # filter_fields = ('idc__id', 'db_type', 'instance_type')
    filter_fields = ('idc__id', 'db_type')

    # 判断管理员并获取数据
    def get_serializer_class(self):
        if isDBPwdShow(self.request):
            return ConfigDbInstanceSerializer
        return ConfigDbInstanceFilterPasswordSerializer

    def perform_create(self, serializer):
        cname = self.request.DATA.get('cname', None)
        dbname = self.request.DATA.get('dbname', None)
        db_type = self.request.DATA.get('db_type', None)
        username = self.request.DATA.get('username', None)
        password = self.request.DATA.get('password', None)
        idc = self.request.DATA.get('idc', None)
        instance_url = self.request.DATA.get('instance_url', None)
        port = self.request.DATA.get('port', None)

        db_instance = ConfigDbInstance.objects.filter(cname=cname.strip(), idc=idc)
        room_instance = Room.objects.get(id=idc)
        if db_instance.exists():
            raise YAPIException('DB实例已存在！')
        ConfigDbInstance.objects.create(cname=cname.strip(), dbname=dbname.strip(), db_type=db_type.strip(),
                                        username=username.strip(), password=password.strip(), idc=room_instance,
                                        instance_url=instance_url.strip(), port=port.strip())

    def get_queryset(self):
        return self.queryset


class ConfigDbInstanceDetail(generics.RetrieveUpdateAPIView):
    queryset = ConfigDbInstance.objects.all()
    serializer_class = ConfigDbInstanceSerializer

    def perform_update(self, serializer):
        id = self.request.DATA.get('id', None)
        cname = self.request.DATA.get('cname', None)
        dbname = self.request.DATA.get('dbname', None)
        db_type = self.request.DATA.get('db_type', None)
        username = self.request.DATA.get('username', None)
        password = self.request.DATA.get('password', None)
        idc = self.request.DATA.get('idc', None)
        instance_url = self.request.DATA.get('instance_url', None)
        port = self.request.DATA.get('port', None)

        db_instance = ConfigDbInstance.objects.filter(cname=cname.strip(), idc=idc)
        room_instance = Room.objects.get(id=idc)
        if db_instance.exclude(id=id).exists():
            raise YAPIException('DB实例已存在！')
        # raise YAPIException(dbname)
        ConfigDbInstance.objects.filter(id=id).update(cname=cname.strip(), dbname=dbname.strip(),
                                                      db_type=db_type.strip(),
                                                      username=username.strip(), password=password.strip(),
                                                      idc=room_instance,
                                                      instance_url=instance_url.strip(), port=port.strip())


class ConfigDbKvDefaultList(generics.ListCreateAPIView):
    queryset = ConfigDbKvDefault.objects.all()
    serializer_class = ConfigDbKvDefaultSerializer
    lookup_field = 'dbtype'

    def get_queryset(self):
        queryset = ConfigDbKvDefault.objects.all()
        dbtype = self.request.QUERY_PARAMS.get('dbtype', None)
        if dbtype is not None:
            queryset = queryset.filter(dbtype__in=['all', dbtype], jdbctype__in=[0, 2])
        return queryset


class ConfigDbKvCustomList(generics.ListCreateAPIView):
    queryset = ConfigDbKvCustom.objects.all()
    serializer_class = ConfigDbKvCustomSerializer
    lookup_field = 'jdbckey'

    def get_queryset(self):
        # queryset = ConfigDbKvCustom.objects.all()
        dataid = self.request.QUERY_PARAMS.get('dataid', None)
        action = self.request.QUERY_PARAMS.get('action', None)
        group_status = self.request.QUERY_PARAMS.get('group_status', None)
        env_name = self.request.QUERY_PARAMS.get('env', None)
        dbtype = self.request.QUERY_PARAMS.get('dbtype', None)
        env = ConfigEnv.objects.get(name=env_name)
        if action == 'one':
            queryset = ConfigDbKvCustom.objects.filter(jdbctype=2)
            configinfo = ConfigInfo.objects.get(data_id=dataid, group_status_id=group_status, env=env.id)
            if dataid is not None:
                queryset = queryset.filter(configinfo_id=configinfo.id)
        else:
            queryset = ConfigDbKvCustom.objects.all()
        return queryset


# 判断是否管理员
def isDBPwdShow(request):
    if request.user is None:
        return False
    cursor = connection.cursor()
    # 数据检索操作,不需要提交
    sql = "SELECT a.id FROM asset.auth_user AS a LEFT JOIN asset.auth_user_groups AS b ON a.id = b.user_id LEFT JOIN asset.auth_group AS c ON b.group_id = c.id WHERE a.username = '%s' and c.name = '%s'" % (
        request.user, cdilname)
    cursor.execute(sql)
    queryset = cursor.fetchone()
    return True if queryset else False
    # groupid = AuthGroup.objects.get(name='DB管理员').id
    # userid = AuthUser.objects.get(username=request.user).id
    # queryset = AuthUserGroups.objects.filter(user_id=userid, group_id=groupid)
    # queryset = AuthUserGroups.objects.raw("SELECT * FROM asset.auth_user AS a LEFT JOIN asset.auth_user_groups AS b ON a.id = b.user_id LEFT JOIN asset.auth_group AS c ON b.group_id = c.id WHERE a.username = 'zhangzaibin' and c.name = 'DB管理员'")


@api_view(['GET'])
@permission_classes((AllowAny,))
def is_exists_dbinstane(request):
    id = request.QUERY_PARAMS['id'] if request.QUERY_PARAMS['id'] else ''
    success = False
    if id:
        config_db_configinfo_instance = ConfigDbConfiginfo.objects.filter(config_db_instance_id=id)
        if config_db_configinfo_instance:
            success = True
    response1 = {'success': success, 'msg': 'test'}
    response = json.dumps(response1)
    return HttpResponse(response)

@api_view(['GET'])
@permission_classes((AllowAny,))
def get_instanes_group(request):
    db_instanes_id = request.QUERY_PARAMS['id'] if request.QUERY_PARAMS['id'] else ''
    if db_instanes_id == '':
        return Response('')
    ct_type = request.QUERY_PARAMS['ct_type'] if request.QUERY_PARAMS['ct_type'] else ''
    cdc_insts = ConfigDbConfiginfo.objects.filter(config_db_instance_id=db_instanes_id)
    tmp_id = []
    resultlist = []
    childenlist = []
    if cdc_insts:
        configinfo_ids = []
        for cdcs in cdc_insts:
            configinfo_ids.append(cdcs.config_info_id)
        configinfo_ids = list(set(configinfo_ids))
        configinfo_insts = ConfigInfo.objects.filter(id__in=configinfo_ids)
        for ci in configinfo_insts:
            gid = ci.group_status.group.id
            if gid not in tmp_id:
                try:
                    dd_dom_inst = DdDomain.objects.get(
                        id=App.objects.get(id=ConfigGroup.objects.get(id=gid).app_id).domainid)
                    domain_name = dd_dom_inst.domainname
                    domain_leader = dd_dom_inst.domainleaderaccount
                    domain_email_group = dd_dom_inst.domainemailgroup
                except ConfigGroup.DoesNotExist:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                except ConfigGroup.MultipleObjectsReturned:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                except App.DoesNotExist:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                except App.MultipleObjectsReturned:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                except DdDomain.DoesNotExist:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                except DdDomain.MultipleObjectsReturned:
                    dd_dom_inst = ''
                    domain_name = ''
                    domain_leader = ''
                    domain_email_group = ''
                if ct_type == 'instance':
                    resultlist.append({
                        'id': ci.group_status.group.id,
                        'app_name': ci.group_status.group.app_name,
                        'site_name': ci.group_status.group.site_name,
                        'group_id': ci.group_status.group.group_id,
                        'idc': ci.group_status.group.idc.name_ch,
                        'domain_name': domain_name,
                        'domain_leader': domain_leader,
                        'domain_email_group': domain_email_group
                    })
                    tmp_id.append(gid)
                elif ct_type == 'association':
                    if dd_dom_inst:
                        par = '%s/%s/%s/%s' % (
                            ci.group_status.group.group_id, ci.group_status.group.idc.name_ch, dd_dom_inst.domainname,
                            dd_dom_inst.domainleaderaccount)
                    else:
                        par = '%s/%s' % (ci.group_status.group.group_id, ci.group_status.group.idc.name_ch)
                    childenlist.append(par)
        if ct_type == 'association':
            resultlist = {
                'par': ConfigDbInstance.objects.get(id=db_instanes_id).cname,
                'val': childenlist
            }
    elif not cdc_insts and ct_type == 'association':
        resultlist = ''
    return Response(resultlist)


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_instanes_configinfo(request):
    db_instanes_id = request.QUERY_PARAMS['id'] if request.QUERY_PARAMS['id'] else ''
    if db_instanes_id == '':
        return Response('')
    cdc_insts = ConfigDbConfiginfo.objects.filter(config_db_instance_id=db_instanes_id)
    tmp_id = []
    resultlist = []
    if cdc_insts:
        configinfo_ids = []
        for cdcs in cdc_insts:
            configinfo_ids.append(cdcs.config_info_id)
        configinfo_ids = list(set(configinfo_ids))
        configinfo_insts = ConfigInfo.objects.filter(id__in=configinfo_ids)
        for ci in configinfo_insts:
            try:
                config_group_inst = ConfigGroup.objects.get(id=ci.group_status.group.id)
                app_inst = App.objects.get(id=config_group_inst.app_id)
                dd_dom_inst = DdDomain.objects.get(id=app_inst.domainid)
                domain_name = dd_dom_inst.domainname
                domain_leader = dd_dom_inst.domainleaderaccount
                domain_email_group = dd_dom_inst.domainemailgroup
            except ConfigGroup.DoesNotExist:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''
            except ConfigGroup.MultipleObjectsReturned:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''
            except App.DoesNotExist:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''
            except App.MultipleObjectsReturned:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''
            except DdDomain.DoesNotExist:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''
            except DdDomain.MultipleObjectsReturned:
                domain_name = ''
                domain_leader = ''
                domain_email_group = ''

            if ci.id not in tmp_id:
                resultlist.append({
                    'id': ci.id,
                    'data_id': ci.data_id,
                    'env': ci.env.name,
                    'group_id': ci.group_status.group.group_id,
                    'idc': ci.group_status.group.idc.name_ch,
                    'domain_name': domain_name,
                    'domain_leader': domain_leader,
                    'domain_email_group': domain_email_group
                })
                tmp_id.append(ci.id)
    return Response(resultlist)


class AppListByUser(generics.ListAPIView):
    """
    APP(pool)列表接口.

    输入参数：
    * group_name    -   查看全部App的组

    输出参数：

    * id        -   pk
    * cmis_id   -   CMIS系统ID号
    * cmis_site_id - CMIS系统的site ID号
    * name      -   app名称（英文）
    * site_id   -   站点ID（中文）
    * type      -   0-业务POOL（数据来源CMIS系统）  1-非业务POOL
    * comment   -   注释字段
    * type      -   pool类型
    * level     -   pool重要级别
    * hudson_job -  废弃字段
    """

    serializer_class = AppSerializer

    def get_queryset(self):
        return get_app_filter_by_request_user(self.request)


class DomainListByDeptV2(generics.ListAPIView):
    """
    Domain查询(根据二级部门)接口.

    输入参数：
    * deptid    -   二级部门ID

    输出参数：

    * id                        -   pk
    * domaincode                -   domain编码
    * domainname                -   domain名称
    * domainemailgroup          -   domain邮箱
    * domainleaderaccount       -   DL
    * backupdomainleaderaccount -  后备DL
    * departmentid              -   部门ID
    * departmentname            -   所属部门名称
    """

    queryset = DdDomain.objects.filter(enable=0)
    serializer_class = DdDomainSerializer
    paginate_by = None

    def get_queryset(self):
        dept_v2_id = self.request.QUERY_PARAMS.get('deptid', None)
        deptid__in = self.request.QUERY_PARAMS.get('deptid__in', None)
        filters = {}
        all_domains = DdDomainV2.objects.filter(enable=0)
        if dept_v2_id:
            dm_ids = [dm.id for dm in all_domains.filter(department__id=dept_v2_id)]
            dm2_ids = [dm2.id for dm2 in DdDomainV2.objects.using('default').filter(department__pid=dept_v2_id)]
            filters['id__in'] = dm_ids + dm2_ids
        elif deptid__in:
            dept_ids = deptid__in.split(',')
            dm_ids = [dm.id for dm in all_domains.filter(department__id__in=dept_ids)]
            dm2_ids = [dm2.id for dm2 in DdDomainV2.objects.using('default').filter(department__pid__in=dept_ids)]
            filters['id__in'] = dm_ids + dm2_ids
        return self.queryset.filter(**filters)


@api_view(['GET'])
@permission_classes((AllowAny,))
def domains_by_deptv2(request):
    dept_v2_id = int(request.GET.get('deptid', 0))
    deptid__in = request.GET.get('deptid__in', '')

    all_domain = DdDomainV2.objects.filter(enable=0)
    all_dept3 = DdDepartmentNew.objects.filter(enable=0, deptlevel=3)

    domain_list = []
    if dept_v2_id != 0:

        dept_ids = []
        for dept3 in all_dept3:
            if dept3.pid == dept_v2_id:
                dept_ids.append(dept3.id)
        dept_ids.append(dept_v2_id)
        if dept_ids:
            for dm in all_domain:
                if dm.department_id in dept_ids:
                    domain_list.append(dm)
    elif deptid__in:
        dept_ids = [int(id) for id in deptid__in.split(',')]
        for dept3 in all_dept3:
            if dept3.pid in dept_ids:
                dept_ids.append(dept3.id)
        for dm in all_domain:
            if dm.department_id in dept_ids:
                domain_list.append(dm)
    else:
        domain_list = all_domain
    results = [{
        'id': dm.id,
        'domainname': dm.domainname
    } for dm in domain_list]
    return HttpResponse(json.dumps(results))


@api_view(['GET'])
@permission_classes((AllowAny,))
def sync_app_and_appcontact(request):
    response1 = sync_by_cmis.syn_appcontact()
    response = json.dumps(response1, ensure_ascii=False)
    return HttpResponse(response)


class RotaenterList(generics.ListCreateAPIView):
    '''
    输出参数：

    * id                        -   pk
    * duty_date_start           -   开始时间
    * duty_date_end           -   结束时间
    * activity_name"            -   值班活动
    * duty_domain_name            -   值班角色
    * duty_man             -  值班人员
    * duty_way_name             -   值班方式
    * duty_backup          -   后备值班人员
    '''
    queryset = Rota.objects.all().order_by('-id')
    serializer_class = RotaSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    search_fields = ('duty_domain__domainname','duty_domain__departmentname','rota_activity__name','duty_man__username','duty_backup__username','duty_man__username_ch','duty_backup__username_ch',)
    filter_fields =('rota_activity',)
    # permission_classes = (RotaPermission, )
    permission_classes = (AllowAny, )
    def perform_create(self, serializer):
        duty_date_start= self.request.DATA.get('duty_date_start')
        duty_date_end =self.request.DATA.get('duty_date_end')
        duty_domain = self.request.DATA.get('duty_domain')
        rota_activity = self.request.DATA.get('rota_activity')
        promotion = self.request.DATA.get('promotion')
        dutyman_id = self.request.DATA.get('duty_man')
        backup_id = self.request.DATA.get('duty_backup')
        if promotion=='0':
            if  Rota.objects.filter(Q(duty_date_start__gte=duty_date_start,duty_date_start__lt=duty_date_end)|Q(duty_date_end__gt=duty_date_start,duty_date_end__lte=duty_date_end)|Q(duty_date_start__lte=duty_date_start,duty_date_end__gte=duty_date_end),promotion=promotion,duty_domain=duty_domain) :
                raise YAPIException('该部门该时间段值班信息已存在或值班时间重合，无需录入。请检查！')

        instance = serializer.save()
        for id in dutyman_id.split(','):
            RotaMan.objects.create(rota_id=instance.id,man_id=id)
        if backup_id:
            for id in backup_id.split(','):
                RotaBackup.objects.create(rota_id=instance.id,backup_id=id)

    def get_queryset(self):
        queryset = Rota.objects.all().order_by('-id')
        duty_date_0 = self.request.QUERY_PARAMS.get('duty_date_0', None)
        duty_date_24 = self.request.QUERY_PARAMS.get('duty_date_24', None)
        activity = self.request.QUERY_PARAMS.get('activity', None)
        if duty_date_0 is not None:
            queryset = Rota.objects.exclude(duty_date_end__lte = duty_date_0)
            queryset = queryset.exclude(duty_date_start__gte = duty_date_24).order_by('rota_activity','duty_domain','duty_date_start')
            queryset=queryset.exclude(promotion=2)
        if activity is not None:
            queryset = Rota.objects.filter(rota_activity = activity).order_by('duty_domain','duty_date_start')
        return queryset.distinct()


class RotaenterDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rota.objects.all().order_by('-id')
    serializer_class = RotaSerializer
    # permission_classes = (RotaPermission, )
    permission_classes = (AllowAny, )
    def perform_update(self, serializer):
        id = self.request.DATA.get('id')
        rota_activity = self.request.DATA.get('rota_activity')
        promotion = self.request.DATA.get('promotion')
        duty_date_start= self.request.DATA.get('duty_date_start')
        duty_date_end =self.request.DATA.get('duty_date_end')
        shift_time = self.request.DATA.get('shift_time')
        duty_domain = self.request.DATA.get('duty_domain')
        dutyman_id = self.request.DATA.get('duty_man')
        backup_id = self.request.DATA.get('duty_backup')
        duty_way = self.request.DATA.get('duty_way')
        # comment = self.request.DATA.get('comment')
        if promotion=='0':
            update=Rota.objects.filter(Q(duty_date_start__gte=duty_date_start,duty_date_start__lt=duty_date_end)|Q(duty_date_end__gt=duty_date_start,duty_date_end__lte=duty_date_end)|Q(duty_date_start__lte=duty_date_start,duty_date_end__gte=duty_date_end),promotion=promotion,duty_domain=duty_domain)
            if update.exclude(id=id).exists():
                raise YAPIException('该部门该时间段值班信息已存在或值班时间重合，无需录入。请检查！')
        # Rota.objects.filter(id=id).update(rota_activity=rota_activity,promotion=promotion,duty_date_start=duty_date_start,duty_date_end=duty_date_end,shift_time=shift_time,duty_domain=duty_domain,duty_way=duty_way,comment=comment)
        serializer.save()
        RotaMan.objects.filter(rota=id).delete()
        RotaBackup.objects.filter(rota=id).delete()
        for man in dutyman_id.split(','):
            RotaMan.objects.create(rota_id=id,man_id=man)
        if backup_id:
            for back in backup_id.split(','):
                 RotaBackup.objects.create(rota_id=id,backup_id=back)

class RotaActivityList(generics.ListCreateAPIView):
    queryset = RotaActivity.objects.all().order_by('-id')
    serializer_class = RotaActivitySerializer
    search_fields = ('name',)
    filter_backends = (filters.SearchFilter,)
    def perform_create(self, serializer):
        name = self.request.DATA.get('name')
        domains_id = self.request.DATA.get('domains')
        # if  RotaActivity.objects.filter(name=name) :
        #     raise YAPIException('该值班活动已存在，无需录入。请检查！' )
        # else:
        instance = serializer.save()
        if domains_id:
            for id in domains_id.split(','):
                try:
                    domain=DdDomain.objects.get(id=id)
                    instance.domains.add(domain)
                except DdDomain.DoesNotExist:
                    domain=None

class RotaActivityDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = RotaActivity.objects.all().order_by('-id')
    serializer_class = RotaActivitySerializer
    def perform_update(self, serializer):
        id = self.request.DATA.get('id')
        name = self.request.DATA.get('name')
        start_time =self.request.DATA.get('start_time')
        end_time = self.request.DATA.get('end_time')
        promotion = self.request.DATA.get('promotion')
        domains_id = self.request.DATA.get('domains')
        update = RotaActivity.objects.filter(name=name)
        # if update.exclude(id=id).exists():
        #     raise YAPIException('该活动已存在请检查！' )
        # else:
        # RotaActivity.objects.filter(id=id).update(name=name,start_time=start_time,end_time=end_time,promotion=promotion)
        serializer.save()
        object = RotaActivity.objects.get(id=id)
        object.domains.clear()
        if domains_id:
            for id in domains_id.split(','):
                try:
                    domain=DdDomain.objects.get(id=id)
                    object.domains.add(domain)
                except DdDomain.DoesNotExist:
                    domain=None


class ShiftTimeList(generics.ListCreateAPIView):
    queryset = ShiftTime.objects.all().order_by('id')
    serializer_class = ShiftTimeSerializer
    # search_fields = ('name',)
    # filter_backends = (filters.SearchFilter,)

class ShiftTimeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftTime.objects.all().order_by('id')
    serializer_class = ShiftTimeSerializer
    def perform_update(self, serializer):
        id = self.request.DATA.get('id')
        start = self.request.DATA.get('start')
        end =self.request.DATA.get('end')

        # if ShiftTime.objects.get(id=id).start !=start or ShiftTime.objects.get(id=id).end !=end:
        # ShiftTime.objects.filter(id=id).update(start=start,end=end)
        serializer.save()
        Rota.objects.filter(shift_time=id).update(duty_date_start=start,duty_date_end=end)


class DailyDutyConfigList(generics.ListCreateAPIView):
    queryset = DailyDutyConfig.objects.all()
    serializer_class = DailyDutyConfigSerializer

class DailyDutyTimeList(generics.ListCreateAPIView):
    queryset = DailyDutyTime.objects.all()
    serializer_class = DailyDutyTimeSerializer

class Pooltoacllist(generics.ListCreateAPIView):
    queryset = Pooltoacl.objects.using('urldatabase').all()
    serializer_class = PooltoaclSerializer
    filter_fields = ('hdr',)
    filter_backends = (filters.DjangoFilterBackend,)

class Acltobackendlist(generics.ListCreateAPIView):
    queryset = Acltobackend.objects.using('urldatabase').all()
    serializer_class = AcltobackendSerializer
    # filter_fields = ('acl_domain',)
    filter_backends = (filters.DjangoFilterBackend,)
    # if acl_domain:
    #     acl_domain=acl_domain.split(',')
    #     acl_domainlist = Acltobackend.objects.using('urldatabase').filter(acl_domain__in=acl_domain)
    #     backendlist = acl_domainlist.values('backend_name').distinct()
    #     count = 0
    #     for item in backendlist:
    #         site_pool = item['backend_name'].split('__')
    #         if len(site_pool) ==1:
    #             site_name = "yihaodian"
    #         else:
    #             site_name = site_pool[0]
    #         try:
    #             site=Site.objects.get(name=site_name)
    #         except Site.DoesNotExist:
    #             site=None
    #         app=App.objects.filter(name=site_pool[-1],site_id=site.id)
    #         if count==0:
    #             queryset=app
    #         else:
    #             queryset=queryset|app
    #         count=count+1

@api_view(['GET'])
@permission_classes((AllowAny, ))
def url_app(request):
    from cmdb.serializers import AppContactSerializer
    dict_total={}
    result=[]
    hdr = request.GET.get('hdr')
    path_beg = request.GET.get('path_beg')
    if path_beg:
        re_path_beg = r'^%s?$' % path_beg
        acl_name_domains = Pooltoacl.objects.using('urldatabase').filter(hdr=hdr).values('acl_name','hdr').distinct()
        # acl_name_urls = Pooltoacl.objects.using('urldatabase').filter(path_beg=path_beg).values('acl_name','path_beg').distinct()
        acl_name_urls = Pooltoacl.objects.using('urldatabase').filter(path_beg__regex= re_path_beg).values('acl_name','path_beg').distinct()

        if len(acl_name_urls) ==0:
            index=[i for i,v in enumerate(path_beg) if v=='/' ]
            count=len(index)
            for i in range(count-2):
                ha_path_beg =path_beg[:index[-i-2]+1]
                ha_path_beg= r'^%s?$' % ha_path_beg
                acl_name_urls = Pooltoacl.objects.using('urldatabase').filter(path_beg__regex=ha_path_beg).values('acl_name','path_beg').distinct()
                if acl_name_urls:
                    break

        acl_domains=[]
        acl_urls=[]

        for item in acl_name_domains:
            acl_domains.append(item['acl_name'])
            display_hdr=item['hdr']
        for item in acl_name_urls:
            acl_urls.append(item['acl_name'])
            diaplay_path_beg = item['path_beg']

        backendlist=Acltobackend.objects.using('urldatabase').filter(acl_domain__in=acl_domains,acl_url__in=acl_urls).values('backend_name').distinct()

        if not backendlist:
            emlist=['*','.','$','^','?','{','(','[','|','\b','\B','\cx','\d','\D','\f','\n','\r','\s','\S','\t','\v','\w','\W','\un','\p']
            regexqueryset=Pooltoacl.objects.using('urldatabase').filter(path_beg__contains='+').values('acl_name','path_beg')
            acl_urls=[]
            for element in emlist:
                regexqueryset=regexqueryset|Pooltoacl.objects.using('urldatabase').filter(path_beg__contains=element).values('acl_name','path_beg')
            regexqueryset.distinct()
            for item in regexqueryset:
                flag=re.findall(r'%s' % item['path_beg'],path_beg)
                if flag:
                    acl_name_urls=Pooltoacl.objects.using('urldatabase').filter(path_beg=item['path_beg']).values('acl_name','path_beg').distinct()
                    for subobject in acl_name_urls:
                        acl_urls.append(subobject['acl_name'])
                    diaplay_path_beg = item['path_beg']
                    break

            backendlist=Acltobackend.objects.using('urldatabase').filter(acl_domain__in=acl_domains,acl_url__in=acl_urls).values('backend_name').distinct()

        for item in backendlist:
            url_dict = dict()
            url_dict['hdr']=display_hdr
            url_dict['path_beg']=diaplay_path_beg
            site_pool = item['backend_name'].split('__')
            if len(site_pool) ==1:
                site_name = "yihaodian"
            else:
                site_name = site_pool[0]
            try:
                site_id=Site.objects.get(name=site_name).id
            except Site.DoesNotExist:
                site_id=None
            try:
                appcontact=AppContact.objects.get(pool_name=site_pool[-1],site_id=site_id,pool_status=0)
                url_dict['app_id']=AppContactSerializer(appcontact).data['app_id']
                url_dict['site_name']=AppContactSerializer(appcontact).data['site_name']
                url_dict['app_name']=AppContactSerializer(appcontact).data['app_name']
                url_dict['domain_name']=AppContactSerializer(appcontact).data['domain_name']
                url_dict['p_user']=AppContactSerializer(appcontact).data['p_user']
                url_dict['p_no']=AppContactSerializer(appcontact).data['p_no']
                url_dict['b_user']=AppContactSerializer(appcontact).data['b_user']
                url_dict['b_no']=AppContactSerializer(appcontact).data['b_no']
                url_dict['department']=AppContactSerializer(appcontact).data['department']
                url_dict['head_user']=AppContactSerializer(appcontact).data['head_user']
                url_dict['head_no']=AppContactSerializer(appcontact).data['head_no']
                url_dict['sa_user']=AppContactSerializer(appcontact).data['sa_user']
                url_dict['sa_no']=AppContactSerializer(appcontact).data['sa_no']
                url_dict['sa_backup_user']=AppContactSerializer(appcontact).data['sa_backup_user']
                url_dict['sa_backup_no']=AppContactSerializer(appcontact).data['sa_backup_no']
                url_dict['domain_email']=AppContactSerializer(appcontact).data['domain_email']
                result.append(url_dict)
            except AppContact.DoesNotExist:
                appcontact = None
    if not path_beg:
        acl_name_domains = Pooltoacl.objects.using('urldatabase').filter(hdr=hdr).values('acl_name','hdr').distinct()
        acl_domains=[]

        for item in acl_name_domains:
            acl_domains.append(item['acl_name'])
        backendlist=Acltobackend.objects.using('urldatabase').filter(acl_domain__in=acl_domains).values('backend_name').distinct()

        for item in backendlist:
            url_dict=dict()
            url_dict['path_beg']='/'
            url_dict['hdr']=hdr
            site_pool = item['backend_name'].split('__')
            if len(site_pool) ==1:
                site_name = "yihaodian"
            else:
                site_name = site_pool[0]
            try:
                site_id=Site.objects.get(name=site_name).id
            except Site.DoesNotExist:
                site_id=None
            try:
                appcontact=AppContact.objects.get(pool_name=site_pool[-1],site_id=site_id,pool_status=0)
                url_dict['app_id']=AppContactSerializer(appcontact).data['app_id']
                url_dict['site_name']=AppContactSerializer(appcontact).data['site_name']
                url_dict['app_name']=AppContactSerializer(appcontact).data['app_name']
                url_dict['domain_name']=AppContactSerializer(appcontact).data['domain_name']
                url_dict['p_user']=AppContactSerializer(appcontact).data['p_user']
                url_dict['p_no']=AppContactSerializer(appcontact).data['p_no']
                url_dict['b_user']=AppContactSerializer(appcontact).data['b_user']
                url_dict['b_no']=AppContactSerializer(appcontact).data['b_no']
                url_dict['department']=AppContactSerializer(appcontact).data['department']
                url_dict['head_user']=AppContactSerializer(appcontact).data['head_user']
                url_dict['head_no']=AppContactSerializer(appcontact).data['head_no']
                url_dict['sa_user']=AppContactSerializer(appcontact).data['sa_user']
                url_dict['sa_no']=AppContactSerializer(appcontact).data['sa_no']
                url_dict['sa_backup_user']=AppContactSerializer(appcontact).data['sa_backup_user']
                url_dict['sa_backup_no']=AppContactSerializer(appcontact).data['sa_backup_no']
                url_dict['domain_email']=AppContactSerializer(appcontact).data['domain_email']
                result.append(url_dict)
            except AppContact.DoesNotExist:
                appcontact = None
    dict_total['results']=result
    dict_total['count']=len(result)
    return Response(status=status.HTTP_200_OK, data=dict_total)


class AppListV2(generics.ListAPIView):
    """
    APP(pool)列表接口.

    输入参数：

    输出参数：

    """
    queryset = AppV2.objects.select_related().filter(status=0).order_by('name')
    serializer_class = AppV2Serializer
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_fields = ('site__id', 'site__name', 'id', 'name', 'type', 'service_name')
    search_fields = ('name', 'site__name')

    def get_paginate_by(self):
        p = self.request.GET.get('page_size')
        return p if p else None


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_dbinstance_list(request):
    domian_port = request.QUERY_PARAMS.get('domian_port')
    idc = request.QUERY_PARAMS.get('idc')
    result = []
    if domian_port:
        domian_port = domian_port.split(':')
        domain = domian_port.pop(0)
        port = domian_port[0]
        config_db_instance = ConfigDbInstance.objects.filter(instance_url=domain, port=port, idc__id=idc)
        for db_int in config_db_instance:
            result.append({
                'id': db_int.id,
                'cname': db_int.cname,
                'idc': db_int.idc.id,
                'name_ch': db_int.idc.name_ch,
                'instance_type': db_int.instance_type
            })
    return Response(result)


@api_view(['POST'])
@permission_classes((AllowAny,))
def copy_db_instance(request):
    domian_port = request.DATA.get('domian_port')
    idc = request.DATA.get('idc')
    target_domian = request.DATA.get('target_domian')
    target_port = request.DATA.get('target_port')
    target_idc = request.DATA.get('target_idc')
    try:
        target_port = int(target_port)
        if target_port < 0 or target_port > 65535:
            return Response({'result': False, 'msg': '端口范围是0-65535'})
    except ValueError:
        return Response({'result': False, 'msg': '端口请输入数字'})
    create_list = []
    if ':' in domian_port:
        domian_port = domian_port.split(':')
        domain = domian_port.pop(0)
        port = domian_port[0]
        config_db_instance = ConfigDbInstance.objects.filter(instance_url=domain, port=port, idc__id=idc)
        flag = 0
        if config_db_instance.exists():
            for db_int in config_db_instance:
                temp_inst = ConfigDbInstance.objects.filter(
                    instance_url=target_domian,
                    port=target_port,
                    idc__id=target_idc,
                    username=db_int.username,
                    dbname=db_int.dbname,
                    db_type=db_int.db_type,
                    instance_type=db_int.instance_type
                )
                if not temp_inst.exists():
                    room = Room.objects.get(id=target_idc)
                    create_list.append(ConfigDbInstance(
                        instance_url=target_domian,
                        port=target_port,
                        idc=room,
                        username=db_int.username,
                        dbname=db_int.dbname,
                        db_type=db_int.db_type,
                        instance_type=db_int.instance_type,
                        password=db_int.password,
                        cname="id:%s://%s:%s/%s//%s" % (
                        db_int.db_type, target_domian, target_port, db_int.dbname, db_int.username)
                    ))
                else:
                    flag += 1
            if len(config_db_instance) == flag:
                return Response({'result': False, 'msg': '已复制，无需重复！'})
            if create_list:
                ConfigDbInstance.objects.bulk_create(create_list)
    else:
        return Response({'result': False, 'msg': '请选择复制源！'})
    result = {'result': True, 'msg': 'Finish'}
    return Response(result)
