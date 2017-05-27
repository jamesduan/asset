# -*- coding: utf-8 -*-
from rest_framework import serializers

import utils
from models import *


class EventDetailSerializer(serializers.ModelSerializer):
    site_id = serializers.ReadOnlyField(source='site.id', read_only=True)
    site_name = serializers.ReadOnlyField(source='site.name', read_only=True)
    pool_id = serializers.ReadOnlyField(source='pool.id', read_only=True)
    pool_name = serializers.ReadOnlyField(source='pool.name', read_only=True)

    class Meta:
        model = EventDetail
        fields = ('id', 'site_id', 'site_name', 'pool_id','pool_name' , 'group_id', 'ip',
                  'server_type', 'parent_ip', 'switch_ip')


class EventSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return Event.objects.create(**validated_data)

    level_id = serializers.ReadOnlyField(source='level.id', read_only=True)
    level_name = serializers.ReadOnlyField(source='level.name', read_only=True)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    source_id = serializers.ReadOnlyField(source='source.id', read_only=True)
    source_name = serializers.ReadOnlyField(source='source.name', read_only=True)

    status_name = serializers.ReadOnlyField(source='get_status_display', read_only=True)
    sub_type_name = serializers.ReadOnlyField(source='get_sub_type_display', read_only=True)

    create_time = serializers.ReadOnlyField()
    cancel_time = serializers.ReadOnlyField()


    event_detail = EventDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = ('id', 'level_id', 'level_name', 'level_adjustment_id', 'type_name', 'source_id', 'source_name',
                  'title', 'message', 'send_to', 'caller', 'get_time',
                  'create_time', 'cancel_time', 'status', 'status_name', 'sub_type', 'sub_type_name',
                  'converge_rule_id', 'converge_id', 'cancel_user', 'event_detail', 'comment')


class AlarmSerializer(serializers.ModelSerializer):
    event_detail = EventDetailSerializer(source='event.event_detail', read_only=True, many=True)
    source_id = serializers.ReadOnlyField(source='event.source.id', read_only=True)
    source_name = serializers.ReadOnlyField(source='event.source.name', read_only=True)
    title = serializers.ReadOnlyField(source='event.title', read_only=True)
    message = serializers.ReadOnlyField(source='event.message', read_only=True)
    sendto = serializers.ReadOnlyField(source='event.send_to', read_only=True)
    caller = serializers.ReadOnlyField(source='event.caller', read_only=True)
    method_name = serializers.ReadOnlyField(source='get_method_id_display', read_only=True)
    type_name = serializers.ReadOnlyField(source='event.type.name', read_only=True)
    level_name = serializers.ReadOnlyField(source='event.level.name', read_only=True)
    level_id = serializers.ReadOnlyField(source='event.level.id', read_only=True)
    level_adjustment_id = serializers.ReadOnlyField(source='event.level_adjustment_id', read_only=True)

    class Meta:
        model = Alarm
        fields = ('id', 'method_id', 'method_name', 'result', 'create_time', 'receiver_name', 'source_id', 'source_name','title',
                  'message', 'sendto', 'caller', 'event_detail', 'type_name', 'level_name', 'level_id', 'status_id', 'error', 'level_adjustment_id')


class EventFilterSerializer(serializers.ModelSerializer):
    source_id = serializers.IntegerField()
    source_name = serializers.ReadOnlyField(source='source.name', read_only=True)
    type_id = serializers.IntegerField(default=-1)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    pool_id = serializers.IntegerField(default=-1)
    pool_name = serializers.ReadOnlyField(source='pool.name', read_only=True)
    site_name = serializers.ReadOnlyField(source='pool.site.name', read_only=True)
    level_id = serializers.IntegerField(default=-1)
    level_name = serializers.ReadOnlyField(source='level.name', read_only=True)
    status_name = serializers.ReadOnlyField(source='get_status_display', read_only=True)

    class Meta:
        model = EventFilter
        fields = ('id', 'start_time', 'end_time', 'source_id', 'source_name',
                  'type_id', 'type_name', 'pool_id', 'pool_name', 'site_name',
                  'ip', 'level_id', 'level_name', 'keyword', 'user', 'status',
                  'status_name', 'create_time', 'comment', 'is_alarm')


class EventConvergenceRuleSerializer(serializers.ModelSerializer):
    source_id = serializers.IntegerField()
    source_name = serializers.ReadOnlyField(source='source.name', read_only=True)
    type_id = serializers.IntegerField()
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    pool_id = serializers.IntegerField(default=-1)
    pool_name = serializers.ReadOnlyField(source='pool.name', read_only=True)
    site_name = serializers.ReadOnlyField(source='pool.site.name', read_only=True)
    same_ip_name = serializers.ReadOnlyField(source='get_same_ip_display', read_only=True)
    level_id = serializers.IntegerField(default=-1)
    level_name = serializers.ReadOnlyField(source='level.name', read_only=True)

    class Meta:
        model = EventConvergenceRule
        fields = ('id', 'source_id', 'source_name', 'type_id', 'type_name',
                  'pool_id', 'pool_name','site_name', 'same_ip', 'same_ip_name',
                  'level_id', 'level_name', 'key', 'interval', 'tmp_time', 'comment', 'user')


class SourceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSourceMap
        fields = ('id', 'name', 'domain_id')


class TypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTypeMap
        fields = ('id', 'name')


class LevelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLevelMap
        fields = ('id', 'name', 'description')


class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = T


class EventLevelAdjustmentSerializer(serializers.ModelSerializer):
    source_id = serializers.IntegerField()
    source_name = serializers.ReadOnlyField(source='source.name', read_only=True)
    type_id = serializers.IntegerField(default=-1)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    pool_id = serializers.IntegerField(default=-1)
    pool_name = serializers.ReadOnlyField(source='pool.name', read_only=True)
    site_name = serializers.ReadOnlyField(source='pool.site.name', read_only=True)
    origin_level_id = serializers.IntegerField(default=-1)
    origin_level_name = serializers.ReadOnlyField(source='origin_level.name', read_only=True)
    new_level_id = serializers.IntegerField(default=-1)
    new_level_name = serializers.ReadOnlyField(source='new_level.name', read_only=True)

    class Meta:
        model = EventLevelAdjustment
        fields = ('id', 'start_time', 'end_time', 'source_id', 'source_name',
                  'type_id', 'type_name', 'pool_id', 'pool_name', 'site_name',
                  'ip', 'keyword', 'origin_level_id', 'origin_level_name', 'new_level_id', 'new_level_name',
                  'operator', 'create_time', 'comment')


class EventMaskSerializer(serializers.ModelSerializer):
    source_id = serializers.IntegerField()
    source_name = serializers.ReadOnlyField(source='source.name', read_only=True)
    type_id = serializers.IntegerField(default=-1)
    type_name = serializers.ReadOnlyField(source='type.name', read_only=True)
    pool_id = serializers.IntegerField(default=-1)
    pool_name = serializers.ReadOnlyField(source='pool.name', read_only=True)
    site_name = serializers.ReadOnlyField(source='pool.site.name', read_only=True)
    level_id = serializers.IntegerField(default=-1)
    level_name = serializers.ReadOnlyField(source='level.name', read_only=True)

    class Meta:
        model = EventMask
        fields = ('id', 'start_time', 'end_time', 'source_id', 'source_name',
                  'type_id', 'type_name', 'pool_id', 'pool_name', 'site_name',
                  'ip', 'keyword', 'level_id', 'level_name', 'operator', 'create_time', 'comment')
