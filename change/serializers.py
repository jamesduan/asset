# -*- coding: utf-8 -*-
from rest_framework import serializers
from models import *

class ChangeMainSerializer(serializers.ModelSerializer):

    action_name = serializers.ReadOnlyField(source='action_ref.name')	
    action_desc = serializers.ReadOnlyField(source='action_ref.desc')	
    action_type_name = serializers.ReadOnlyField(source='action_ref.type.name')
    action_type_desc = serializers.ReadOnlyField(source='action_ref.type.desc')

    level_id = serializers.ReadOnlyField(source='action_ref.level_id')
    level_name = serializers.ReadOnlyField(source='action_ref.get_level_name')
    app_id = serializers.ReadOnlyField(source='app.id')

    def create(self, validated_data):
        return Main.objects.using('change').create(**validated_data)

    class Meta:
        model = Main
        fields = ('id', 'user', 'task_id', 'type', 'action',
        	      'action_name', 'action_desc',
        	      'action_type_name', 'action_type_desc',
        	      'index', 'message', 'happen_time', 'level_id', 
                  'level_name', 'happen_time_str','created', 'app_id',
                  'pool_name')


class ChangeTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Type
        fields = ('id', 'key', 'name', 'desc')


class ChangeActionSerializer(serializers.ModelSerializer):
    """docstring for ChangeActionSerializer"""
    # type_action_name = serializers.ReadOnlyField(source='get_type_action_name')
    type_id = serializers.ReadOnlyField(source='type.id')
    type_name = serializers.ReadOnlyField(source='type.name')

    class Meta:
        model = Action
        # fields = ('id', 'key', 'name')
        fields = ('id', 'key', 'name', 'type_id', 'type_name')


class ExceptionReportSerializer(serializers.ModelSerializer):
    type_name=serializers.ReadOnlyField(source='get_type_display')
    owner_domain_name=serializers.ReadOnlyField(source='owner_domain.domainname')
    class Meta:
        model = ExceptionReport
        fields = ('id', 'cname','type','type_name', 'cmdbsql','api_url', 'owner','owner_domain_name' ,'status', 'api_fields','fileds',
                  'last_update', 'exception_count', 'use_db', 'db_mail','frequency','last_email_date','level_id')