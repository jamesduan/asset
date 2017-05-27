# -*- coding: utf-8 -*-

from rest_framework import serializers
from models import *


class RegSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return Reg.objects.using('logplatform').create(**validated_data)

    class Meta:
        model = Reg
        fields = ('id', 'title', 'type', 'query', 'interval_type',
                  'interval_value', 'comparison', 'count', 'group_by',
                  'is_influence', 'enable', 'remark', 'applicant',
                  'apply_date', 'updater', 'update_time')
