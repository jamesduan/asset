# -*- coding: utf-8 -*-
from rest_framework import generics
from serializers import *
import uuid, time
from rest_framework import filters


class ApplyVmList(generics.ListCreateAPIView):
    """
    创建虚拟机流程创建/列表接口.

    输入参数：
    * site_id   -   按site_id筛选
    * app_id    -   按app_id筛选
    * apply_id  -   按流程编号筛选
    * status    -   按流程状态筛选
    * server_env_id -   按照申请服务器的环境筛选
    * zone_id   -   按申请的服务器zone区域申请

    输出参数：

    * id        -   pk
    * apply_id  -   唯一标识符
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_name  -   应用名称
    * hardware_config_id - 硬件配置ID
    * software_config_id - 软件配置ID
    * num       -   申请数量
    * server_env_id -   服务器环境
    * zone_id       -   可用区ID
    * status        -   状态
    * created       -   创建时间
    * approved_time -   创建成功时间
    """
    queryset = ApplyVm.objects.all()
    serializer_class = ApplyVmSerializer
    filter_fields = ('site_id', 'app_id', 'apply_id', 'status', 'server_env_id', 'zone_id')
    filter_backends = (filters.DjangoFilterBackend,)

    def perform_create(self, serializer):
        serializer.save(created=time.time(), apply_id=_create_apply_id('vm'))


class ApplyVmDetail(generics.RetrieveUpdateAPIView):
    """
    查看虚拟机申请流程接口.

    输入参数：

    输出参数：

    * id        -   pk
    * site_id   -   站点ID
    * site_name -   站点名称
    * app_id    -   应用ID
    * app_name  -   应用名称
    * hardware_config_id - 硬件配置ID
    * software_config_id - 软件配置ID
    * num       -   申请数量
    * server_env_id -   服务器环境
    * zone_id       -   可用区ID
    * status        -   状态
    * created       -   创建时间
    * approved_time -   创建成功时间
    """
    queryset = ApplyVm.objects.all()
    serializer_class = ApplyVmSerializer


def _create_apply_id(type1):
    if type1 == 'vm':
        return 'vm-%s' % uuid.uuid4()