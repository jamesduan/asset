# -*- coding: utf-8 -*-
from rest_framework import serializers
from models import *
from cmdb.models import DdUsers, DdDomain

class TOrderMinSerializer(serializers.ModelSerializer):

    class Meta:
        model = TOrderMin
        fields = ('order_count', 'time_position', 'create_time')

class DdDomainSerializer(serializers.ModelSerializer):
    # app = AppSerializer(many=True, read_only=True)
    #department_name = serializers.ReadOnlyField(source='department.deptName')
    department_leader = serializers.ReadOnlyField(source='department.deptleaderaccount')

    class Meta:
        model = DdDomain
        fields = ('id', 'domainname', 'domainemailgroup', 'domainleaderaccount',
                  'backupdomainleaderaccount', 'departmentname', 'department_leader')

class DdUsersSerializer(serializers.ModelSerializer):
    domains = DdDomainSerializer(many=True, read_only=True)

    class Meta:
        model = DdUsers
        fields = ('id', 'username', 'username_ch', 'display_name', 'email', 'domains','telephone')

class SearchUserHistorySerializer(serializers.ModelSerializer):
    dd_user = DdUsersSerializer(read_only=True)

    class Meta:
        model = SearchUserHistory
        fields = ('id', 'dd_user', 'owner_id')
