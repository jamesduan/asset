# -*- coding: utf-8 -*-
from rest_framework import serializers
from models import *
from cmdb.serializers import DdDomainV2Serializer, DdDepartmentSerializer


class AccidentParentTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = AccidentParentType
        fields = ('id', 'name',  'define', 'enable')


class AccidentTypeSerializer(serializers.ModelSerializer):

    ptype = AccidentParentTypeSerializer(read_only=True,)

    class Meta:
        model = AccidentType
        fields = ('id', 'ptype', 'name', 'enable',)


class AccidentDomainSerializer(serializers.ModelSerializer):

    # domain = DdDomainV2Serializer(read_only=True,)
    # domainid = serializers.ReadOnlyField(source='domain.id')
    domainname = serializers.ReadOnlyField()
    # deptid = serializers.ReadOnlyField(source='domain.department_level2.id')
    deptname = serializers.ReadOnlyField()
    accident_id = serializers.ReadOnlyField(source='accident.accidentid')

    class Meta:
        model = AccidentDomain
        fields = ('id', 'accident_id', 'domainid', 'domainname', 'deptname', 'departmentid')


class AccidentActionSerializer(serializers.ModelSerializer):

    status_name = serializers.ReadOnlyField(source='get_status_display')
    dutydept_name = serializers.ReadOnlyField()
    # dutydept = DdDepartmentSerializer(many=True, read_only=True)
    expect_time_format = serializers.ReadOnlyField()
    accident_id = serializers.ReadOnlyField(source='accident.accidentid')

    class Meta:
        model = AccidentAction
        fields = ('id', 'accident_id', 'action', 'dutydept_name', 'duty_users', 'create_time', 'expect_time', 'expect_time_format', 'finish_time', 'trident_id', 'status', 'status_name', 'comment')


class AccidentPoolSerializer(serializers.ModelSerializer):

    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')

    class Meta:
        model = AccidentPool
        fields = ('id', 'accident_id', 'app_id', 'site_name', 'app_name', 'create_time', 'enable')


class AccidentSerializer(serializers.ModelSerializer):

    duty_manager_name_ch = serializers.ReadOnlyField()
    type_parent_id = serializers.ReadOnlyField(source='type.ptype.id', read_only=True)
    type_parent_name = serializers.ReadOnlyField(source='type.ptype.name', read_only=True)
    type_id = serializers.ReadOnlyField(source='type.id', read_only=True)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    status_name = serializers.ReadOnlyField(source='status.name', read_only=True)
    # duty_domains = AccidentDomainSerializer(many=True, read_only=True)
    duty_dept_ids = serializers.ReadOnlyField()
    duty_dept_names = serializers.ReadOnlyField()
    duty_domain_ids = serializers.ReadOnlyField()
    duty_domain_names = serializers.ReadOnlyField()
    # log = AccidentLogSerializer(many=True,)
    action = AccidentActionSerializer(many=True, read_only=True)
    find_user_department = serializers.ReadOnlyField()
    level_name = serializers.ReadOnlyField(source='get_level_display', read_only=True)
    time_length = serializers.ReadOnlyField()
    basic_sla = serializers.ReadOnlyField()
    detail_sla = serializers.ReadOnlyField()
    # type_parent_id = serializers.SerializerMethodField()

    class Meta:
        model = Accident
        fields = ('id', 'accidentid', 'title', 'status_name', 'is_accident', 'level', 'level_name',  'find_user_name',
                  'find_user_department',  'duty_manager_name', 'duty_manager_name_ch', 'duty_users',
                  'happened_time',  'finish_time', 'time_length', 'reason', 'process', 'comment', 'affect', 'is_online','is_online_str', 'health', 'is_available',
                  'type_id', 'type_name', 'type_parent_id', 'type_parent_name', 'is_punish',
                  'basicinfo_time', 'detailinfo_time', 'duty_dept_ids', 'duty_dept_names', 'duty_domain_ids', 'duty_domain_names',
                  'mantis_id', 'basic_sla', 'detail_sla', 'punish_users', 'punish_content', 'action')

    # def get_type_parent_id(self, obj):
    #     return obj.site_apps.all().count()


class AccidentListSerializer(serializers.ModelSerializer):

    duty_manager_name_ch = serializers.ReadOnlyField()
    type_parent_name = serializers.ReadOnlyField(source='type.ptype.name', read_only=True)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    status_name = serializers.ReadOnlyField(source='status.name', read_only=True)
    duty_dept_names = serializers.ReadOnlyField()
    duty_domain_names = serializers.ReadOnlyField()
    find_user_department = serializers.ReadOnlyField(source='find_user.dept_level2.deptname', read_only=True)
    level_name = serializers.ReadOnlyField(source='get_level_display', read_only=True)
    time_length = serializers.ReadOnlyField()

    class Meta:
        model = Accident
        fields = ('id', 'accidentid', 'title','status_name', 'is_accident', 'level', 'level_name',  'find_user_name',
                  'find_user_department',  'duty_manager_name', 'duty_manager_name_ch', 'duty_users', 'happened_time',  'finish_time', 'time_length', 'reason',  'comment',
                   'type_name', 'type_parent_name', 'is_punish', 'duty_dept_names', 'duty_domain_names', 'mantis_id')


class AccidentLogImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = AccidentLogImage

        fields = ('id', 'accident_log_id', 'image', 'create_time')


class AccidentLogSerializer(serializers.ModelSerializer):

    source_name = serializers.ReadOnlyField(source='get_source_display', read_only=True)
    level_name = serializers.ReadOnlyField()
    images = AccidentLogImageSerializer(read_only=True, many=True)
    create_time_format = serializers.ReadOnlyField()
    # source_name = serializers.SerializerMethodField()

    class Meta:
        model = AccidentLog

        fields = ('id', 'accident_id', 'username',  'source', 'from_id', 'app_id', 'ip',
                  'source_name',  'level_id', 'message', 'create_time', 'is_process',
                  'level_name', 'images', 'create_time_format', 'happened_time', 'happened_time_format')

    # def get_source_name(self, obj):
    #     return '123'