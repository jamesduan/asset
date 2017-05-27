# -*- coding: utf-8 -*-
'''
    @description:   

    @copyright:     ©2013 yihaodian.com
    @author:        jackie
    @since:         14-8-29
    @version:       0.1
    @author:        jackie
'''
from rest_framework import serializers
from models import *


class HybridRequirementSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField(source='get_status_display')
    is_long_name = serializers.ReadOnlyField(source='get_is_long_display')

    class Meta:
        model = HybridRequirement
        fields = ('id', 'cname', 'total', 'real_total', 'machine_config', 'server_template', 'idc', 'start_time',
                  'end_time', 'task_id', 'status', 'status_name', 'is_long', 'is_long_name')


class HybridRequirementDetailSerializer(serializers.ModelSerializer):
    requirement_id = serializers.ReadOnlyField(source='requirement.id')
    requirement_name = serializers.ReadOnlyField(source='requirement.cname')
    requirement_type_name = serializers.ReadOnlyField(source='requirement.get_is_long_display')
    status_name = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = HybridRequirementDetail
        fields = ('id', 'requirement_id', 'requirement_name','requirement_type_name', 'ip', 'status', 'status_name')
