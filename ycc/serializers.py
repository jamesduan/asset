from rest_framework import serializers
from models import *
from server.serializers import ServerSerializer
from asset.serializers import ZoneSerializer
from cmdb.serializers import AppV2Serializer

class GroupSerializer(serializers.ModelSerializer):
    type_name = serializers.ReadOnlyField(source='get_type_display')
    idc_name = serializers.ReadOnlyField(source='idc.name_ch')
    ycc_code = serializers.ReadOnlyField(source='idc.ycc_code')
    all_status = serializers.ReadOnlyField()

    class Meta:
        model = ConfigGroup
        fields = ('id', 'site_id', 'site_name', 'app_id', 'app_name', 'group_id', 'type', 'type_name', 'old_pool',
                  'idc', 'idc_name', 'created', 'updated', 'status', 'all_status', 'ycc_code', 'app_status',
                  'to_be_committed')


class ConfigInfoSerializer(serializers.ModelSerializer):
    group_id = serializers.ReadOnlyField(source='group_status.group.group_id')
    idc = serializers.ReadOnlyField(source='group_status.group.idc.name_ch')
    idc_id = serializers.ReadOnlyField(source='group_status.group.idc.id')
    status = serializers.ReadOnlyField(source='group_status.status')
    version = serializers.ReadOnlyField(source='group_status.version')
    env_name = serializers.ReadOnlyField(source='env.name')
    db_instance_id = serializers.ReadOnlyField(source='db_info.config_db_instance_id')
    app_id = serializers.ReadOnlyField(source='group_status.group.app_id')
    status_cn = serializers.ReadOnlyField(source='group_status.get_status_display')
    app_status = serializers.ReadOnlyField(source='group_status.group.app_status')
    is_cmp = serializers.ReadOnlyField()
    is_cmp_type = serializers.ReadOnlyField()
    config_type_name = serializers.ReadOnlyField()
    is_group_status = serializers.ReadOnlyField()

    class Meta:
        model = ConfigInfoV3
        fields = ('id', 'data_id', 'group_status', 'group_id', 'idc', 'env', 'env_name', 'content', 'created_time',
                  'modified_time', 'created_by', 'modified_by', 'remark', 'file_type', 'cmp', 'status', 'version',
                  'config_type', 'db_instance_id', 'idc_id', 'app_id', 'status_cn', 'app_status', 'is_cmp',
                  'is_cmp_type', 'config_type_name', 'is_group_status')


class ConfigInfoTmpSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConfigInfoTmp
        fields = ('id', 'configinfo_id', 'content')

class ProConfigInfoSerializer(serializers.ModelSerializer):
    group_id = serializers.ReadOnlyField(source='group_status.group.group_id')
    idc = serializers.ReadOnlyField(source='group_status.group.idc.name_ch')
    idc_id = serializers.ReadOnlyField(source='group_status.group.idc.id')
    status = serializers.ReadOnlyField(source='group_status.status')
    version = serializers.ReadOnlyField(source='group_status.version')
    env_name = serializers.ReadOnlyField(source='env.name')
    db_instance_id = serializers.ReadOnlyField(source='db_info.config_db_instance_id')
    app_id = serializers.ReadOnlyField(source='group_status.group.app_id')
    status_cn = serializers.ReadOnlyField(source='group_status.get_status_display')
    app_status = serializers.ReadOnlyField(source='group_status.group.app_status')
    is_cmp = serializers.ReadOnlyField()
    is_cmp_type = serializers.ReadOnlyField()
    config_type_name = serializers.ReadOnlyField()

    class Meta:
        model = ConfigInfo
        fields = (
            'id', 'data_id', 'group_status', 'group_id', 'idc', 'env', 'env_name', 'content_nopwd', 'created_time',
            'modified_time', 'created_by', 'modified_by', 'remark', 'file_type', 'cmp', 'status', 'version',
            'config_type', 'db_instance_id', 'idc_id', 'app_id', 'status_cn', 'app_status', 'is_cmp', 'is_cmp_type',
            'config_type_name')


class ConfigGroupStatusSerializer(serializers.ModelSerializer):
    group_id = serializers.ReadOnlyField(source='group.id')
    group_id_desc = serializers.ReadOnlyField(source='group.group_id')
    idc = serializers.ReadOnlyField(source='group.idc.id')
    status_desc = serializers.ReadOnlyField(source='get_status_display')
    app_id = serializers.ReadOnlyField(source='group.app_id')

    class Meta:
        model = ConfigGroupStatus
        fields = ('id', 'group_id', 'group_id_desc', 'idc', 'remark', 'version', 'status', 'status_desc', 'pre_version', 'app_id')


class OldConfigGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = OldConfigGroup
        #fileds = ('group_id', 'pool', 'remark', 'status', 'env', 'pemail', 'bemail', 'semail', 'idc')
        fileds = ('group_id', 'pool', 'idc')


class blackipSerializer(serializers.ModelSerializer):
    created_time = serializers.ReadOnlyField()
    ip = serializers.ReadOnlyField()

    class Meta:
        model = GrayReleaseBlackip
        fileds = ('id', 'ip', 'create_time')


class ConfigSubscribeLogSerializer(serializers.ModelSerializer):
    app_name = serializers.ReadOnlyField(source='server.app.name')
    site_name = serializers.ReadOnlyField(source='server.app.site.name')

    class Meta:
        model = ConfigSubscribeLog
        fileds = ('id', 'server', 'ip', 'group_id', 'config_file', 'status_code', 'update_time', 'site_name', 'app_name')


class ConfigHostSerializer(serializers.ModelSerializer):
    server_ip = serializers.ReadOnlyField(source='server.ip')
    main_group_name = serializers.ReadOnlyField(source='main_group.group_id')

    class Meta:
        model = ConfigHost
        fileds = ('id', 'server', 'server_ip', 'ori_pool_name', 'pool_name', 'ori_main_group_id', 'main_group', 'main_group_name', 'create_time')


class RoomAppsSerializer(serializers.ModelSerializer):
    room= ZoneSerializer(read_only=True,)
    app=AppV2Serializer(read_only=True,)

    class Meta:
        model = RoomApps
        fileds = ('room', 'app')


class SoaServiceSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source='room.name_ch')
    room_id = serializers.ReadOnlyField(source='room.id')
    app_id = serializers.ReadOnlyField(source='app.id')
    app_name = serializers.ReadOnlyField(source='app.name')
    site_name = serializers.ReadOnlyField(source='app.site.name')
    env_name = serializers.ReadOnlyField(source='env.name')
    # group_servers = serializers.ReadOnlyField()
    count_groups = serializers.ReadOnlyField()
    count_servers = serializers.ReadOnlyField()
    server_env_id = serializers.ReadOnlyField()

    class Meta:
        model = SoaService
        fields = ('id', 'app', 'service_path', 'room', 'type',
                  'room_name', 'room_id', 'app_id', 'app_name', 'site_name', 'count_groups',
                  'count_servers', 'env', 'env_name', 'server_env_id')


class SoaServiceGroupRegisterSerializer(serializers.ModelSerializer):
    server_ip = serializers.ReadOnlyField(source='serverstandard.ip')

    class Meta:
        model = SoaServiceGroupRegister
        fields = ('id', 'serverstandard', 'soa_service', 'port', 'server_ip')


class SoaServiceGroupSerializer(serializers.ModelSerializer):
    soa_service_id = serializers.ReadOnlyField(source='soa_service.id')

    class Meta:
        model = SoaServiceGroup
        fields = ('id', 'cname', 'status', 'soa_service', 'soa_service_id')


class SoaServiceGroupBindSerializer(serializers.ModelSerializer):
    server_ip = serializers.ReadOnlyField(source='serverstandard.ip')

    class Meta:
        model = SoaServiceGroupBind
        fields = ('id', 'soa_service_group', 'type', 'server_ip')

class ExceptionConfigAccessDetailSerializer(serializers.ModelSerializer):
    error_name=serializers.ReadOnlyField(source='get_error_display')
    site_name=serializers.ReadOnlyField(source='site.name')
    app_name=serializers.ReadOnlyField(source='app.name')
    domain_name=serializers.ReadOnlyField(source='domain.domainname')
    # domain_email=serializers.ReadOnlyField(source='domain.domainemailgroup')
    site_app = serializers.ReadOnlyField(source='site_app_def')
    lastupdate_format=serializers.DateTimeField(source='lastupdate',format='%Y-%m-%d %H:%M')
    class Meta:
        model = ExceptionConfigAccessDetail
        fields = ('error_name','group_id','data_id','ip','site_name','app_name','domain_name','frequency','lastupdate_format','standardgroup_id','site_app')
