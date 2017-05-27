from rest_framework import serializers
from models import *
from cmdb.serializers import AppSerializer

class ServerSerializer(serializers.ModelSerializer):
    site_id = serializers.ReadOnlyField(source='site.id')
    site_name = serializers.ReadOnlyField(source='site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    app_type_id = serializers.ReadOnlyField(source='app.type')
    server_status_name = serializers.ReadOnlyField(source='server_status.name')
    server_env_name = serializers.ReadOnlyField(source='server_env.name')
    server_type_name = serializers.ReadOnlyField(source='server_type.name')
    rack_name = serializers.ReadOnlyField(source='asset.rack.name')
    room = serializers.ReadOnlyField(source='asset.rack.room.name')
    rack_real_name = serializers.ReadOnlyField(source='asset.rack.real_name')
    server_os_template_name = serializers.ReadOnlyField(source='server_os_template.cname')
    server_app_template_name = serializers.ReadOnlyField(source='server_app_template.cname')
    room_comment = serializers.ReadOnlyField(source='asset.rack.room.comment')
    ycc_code = serializers.ReadOnlyField(source='ycc_zone.ycc_code')

    class Meta:
        model = Server
        fields = ('id', 'sn', 'mac', 'assetid', 'ip', 'site_id', 'site_name', 'app_id', 'app_type_id', 'app_name',
                  'tag_id', 'mgmt_ip', 'hostname', 'server_type_id', 'server_type_name', 'server_status_id',
                  'server_status_name', 'server_env_id', 'server_env_name', 'rack_name', 'room', 'rack_real_name',
                  'hostname', 'parent', 'comment', 'template_id', 'os_template', 'app_template', 'created_time',
                  'online_time', 'bond_mode', 'raid_change', 'server_owner', 'server_os_template_id',
                  'server_app_template_id', 'server_os_template_name', 'server_app_template_name', 'room_comment',
                  'ycc_code', 'ycc_zone', 'vm_count', 'ycc_idc')


class ServerInstallSerializer(serializers.ModelSerializer):
    server_status_name = serializers.ReadOnlyField(source='server_status.comment')
    server_env_name = serializers.ReadOnlyField(source='server_env.comment')
    server_type_name = serializers.ReadOnlyField(source='server_type.comment')
    room = serializers.ReadOnlyField(source='asset.rack.room.name')
    rack_name = serializers.ReadOnlyField(source='asset.rack.real_name')
    server_os_template_name = serializers.ReadOnlyField(source='server_os_template.show_name')
    server_os_template_identy = serializers.ReadOnlyField(source='server_os_template.cname')
    server_app_template_name = serializers.ReadOnlyField(source='server_app_template.show_name')
    server_app_template_identy = serializers.ReadOnlyField(source='server_app_template.cname')
    parent_app_name = serializers.ReadOnlyField(source='parent_server_obj.app.name')

    class Meta:
        model = Server
        fields = ('id', 'sn', 'mac', 'assetid', 'ip', 'mgmt_ip', 'server_os_template_id', 'server_os_template_name', 'server_os_template_identy',
                  'server_app_template_id', 'server_app_template_name', 'server_app_template_identy', 'server_type_id', 'server_type_name',
                  'server_status_id', 'server_status_name', 'server_env_id', 'server_env_name', 'room',
                  'rack_name', 'parent_app_name')


class ResourcesVmSerializer(serializers.ModelSerializer):

    class Meta:
        model = ResourcesVm
        fields = ('id', 'host_ip', 'hardware_id', 'available_num', 'used_num', 'script_num', 'total_num', 'status', 'created', 'updated',
                  'script_updated')


class ServerOsTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ServerOsTemplate


class ServerAppTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ServerAppTemplate


class ServerInfoForHybridSerializer(serializers.ModelSerializer):

    class Meta:
        model = Server
        fields = ('ip', 'hostname')


class ServerGroupSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source='room.name')
    room_id = serializers.ReadOnlyField(source='room.id')

    class Meta:
        model = ServerGroup
        fields = ('id', 'app_id', 'cname', 'room_id', 'room_name')


class ServerStandardSerializer(serializers.ModelSerializer):
    site_id = serializers.ReadOnlyField(source='app.site.id')
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    app_id = serializers.ReadOnlyField(source='app.id')
    app_type_id = serializers.ReadOnlyField(source='app.type')
    server_status_name = serializers.ReadOnlyField(source='server_status.comment')
    server_status_id = serializers.ReadOnlyField(source='server_status.id')
    server_env_name = serializers.ReadOnlyField(source='server_env.name')
    server_env_id = serializers.ReadOnlyField(source='server_env.id')
    server_type_name = serializers.ReadOnlyField(source='server_type.name')
    server_type_comment = serializers.ReadOnlyField(source='server_type.comment')
    server_type_id = serializers.ReadOnlyField(source='server_type.id')
    server_os_template_name = serializers.ReadOnlyField(source='server_os_template.cname')
    server_app_template_name = serializers.ReadOnlyField(source='server_app_template.cname')
    server_os_template_id = serializers.ReadOnlyField(source='server_os_template.id')
    server_app_template_id = serializers.ReadOnlyField(source='server_app_template.id')
    rack_name = serializers.ReadOnlyField(source='rack.name')
    rack_id = serializers.ReadOnlyField(source='rack.id')
    room = serializers.ReadOnlyField(source='rack.room.name')
    ycc_code = serializers.ReadOnlyField(source='ycc_zone.ycc_code')
    # rack_real_name = serializers.ReadOnlyField(source='rack.real_name')
    groups = ServerGroupSerializer(many=True, read_only=True)
    parent_app_name = serializers.ReadOnlyField(source='parent_server_obj.app.name')

    class Meta:
        model = ServerStandard
        fields = (
            'id', 'sn', 'assetid', 'ip', 'site_id', 'site_name', 'app', 'app_id', 'server_type', 'app_type_id',
            'app_name',
            'mgmt_ip', 'hostname', 'server_type_id', 'server_type_name', 'server_type_comment', 'server_status',
            'server_status_id',
            'server_status_name', 'server_env', 'server_env_id', 'server_env_name',
            'parent', 'parent_ip', 'comment', 'template_id', 'created_time', 'rack_id', 'rack_name', 'room',
            'online_time', 'bond_mode', 'raid_change', 'server_owner', 'server_os_template_id',
            'server_app_template_id', 'server_os_template_name', 'server_app_template_name', 'groups', 'ycc_code',
            'ycc_zone', 'parent_app_name')


# class LBGroupSerializer(serializers.ModelSerializer):
#     site_name = serializers.ReadOnlyField(source='app.site.name')
#     app_name = serializers.ReadOnlyField(source='app.name')
#
#     class Meta:
#         model = LBGroup
#         fileds = ('app', 'name')


class ServerDetailSerializer(serializers.ModelSerializer):

    app = AppSerializer(read_only=True,)
    server_status_name = serializers.ReadOnlyField(source='server_status.comment')
    server_env_name = serializers.ReadOnlyField(source='server_env.comment')
    server_type_name = serializers.ReadOnlyField(source='server_type.comment')
    rack_name = serializers.ReadOnlyField(source='asset.rack.name')
    room = serializers.ReadOnlyField(source='asset.rack.room.name')
    rack_real_name = serializers.ReadOnlyField(source='asset.rack.real_name')
    server_os_template_name = serializers.ReadOnlyField(source='server_os_template.cname')
    server_app_template_name = serializers.ReadOnlyField(source='server_app_template.cname')
    room_comment = serializers.ReadOnlyField(source='asset.rack.room.comment')

    class Meta:
        model = Server
        fields = ('id', 'sn', 'mac', 'assetid', 'ip', 'app_id',
                  'tag_id', 'mgmt_ip', 'hostname', 'server_type_id', 'server_type_name', 'server_status_id',
                  'server_status_name', 'server_env_id', 'server_env_name', 'rack_name', 'room', 'rack_real_name',
                  'parent', 'comment', 'template_id', 'created_time',
                  'online_time', 'bond_mode', 'raid_change', 'server_owner', 'server_os_template_id',
                  'server_app_template_id', 'server_os_template_name', 'server_app_template_name', 'room_comment', 'app')

class VirtualLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogMain
        fields = ('id', 'is_error', 'type', 'action', 'index', 'content','created','happen_time')
