# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json

from django.db import models
from cmdb.models import Site, App, DdUsers


class Father(object):
    _database = 'monitor'


class AlarmStatusMap(Father, models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'alarm_status_map'


class EventLevelMap(Father, models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=512)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_level_map'


class EventSourceMap(Father, models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    domain_id = models.IntegerField(blank=True, default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_source_map'


class EventTypeMap(Father, models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_type_map'


class Event(Father, models.Model):
    STATUS = (
        (0, ""),
        (1, "手动"),
        (2, "自动"),
    )
    SUB_TYPE = (
        (0, "非根源"),
        (1, "根源")
    )
    id = models.AutoField(primary_key=True)
    tag = models.CharField(max_length=3000, default='')
    tag_remark = models.TextField(blank=True)
    level = models.ForeignKey(EventLevelMap, blank=True, null=True, on_delete=models.SET_NULL)
    level_adjustment_id = models.IntegerField(blank=True, default=0)
    type = models.ForeignKey(EventTypeMap, blank=True, null=True, on_delete=models.SET_NULL)
    sub_type = models.IntegerField(choices=SUB_TYPE, default=0)
    source = models.ForeignKey(EventSourceMap, blank=True, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    send_to = models.CharField(max_length=3000, default='', blank=True)
    cc = models.CharField(max_length=3000, default='', blank=True)
    caller = models.CharField(max_length=3000, default='', blank=True)
    get_time = models.IntegerField(default=0)
    create_time = models.IntegerField(blank=True, default=0)
    cancel_time = models.IntegerField(blank=True, default=0)
    status = models.IntegerField(choices=STATUS, default=0)
    cancel_user = models.CharField(max_length=255, default='', blank=True)
    converge_id = models.IntegerField(blank=True, default=0)
    converge_rule_id = models.IntegerField(blank=True, default=0)
    comment = models.TextField(blank=True, default='')
    ignore = models.IntegerField(blank=True, default=0)
    # 0：正常处理；1:误报
    cancel_type = models.IntegerField(blank=True, default=0)
    _database = 'monitor'

    @property
    def event_detail(self):
        try:
            event_detail = EventDetail.objects.filter(event_id=self.id)
        except Exception, e:
            event_detail = None
        return event_detail

    class Meta:
        managed = False
        db_table = 'event'


class EventCreate(Father, models.Model):
    STATUS = (
        (0, ""),
        (1, "手动"),
        (2, "自动"),
    )
    SUB_TYPE = (
        (0, "非根源"),
        (1, "根源")
    )
    id = models.AutoField(primary_key=True)
    tag = models.CharField(max_length=3000, default='')
    tag_remark = models.TextField(blank=True)
    level_id = models.IntegerField(default=0)
    level_adjustment_id = models.IntegerField(blank=True, default=0)
    type_id = models.IntegerField(default=0)
    source_id = models.IntegerField(default=0)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    send_to = models.CharField(max_length=3000, default='')
    cc = models.CharField(max_length=3000, default='')
    caller = models.CharField(max_length=3000, default='')
    caller_message = models.CharField(max_length=400, default='')
    get_time = models.IntegerField(default=0)
    create_time = models.IntegerField(default=0)
    cancel_time = models.IntegerField(default=0)
    status = models.IntegerField(choices=STATUS, default=0)
    sub_type = models.IntegerField(choices=SUB_TYPE, default=0)
    cancel_user = models.CharField(max_length=255, default='')
    converge_id = models.IntegerField(blank=True, default=0)
    converge_rule_id = models.IntegerField(blank=True, default=0)
    comment = models.TextField(blank=True, default='')
    ignore = models.IntegerField(blank=True, default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event'


class Alarm(Father, models.Model):
    TYPE = (
        (1, "Email"),
        (2, "SMS"),
        (3, "Voice"),
        (4, "TTS"),
    )
    id = models.AutoField(primary_key=True)
    event = models.ForeignKey(Event, db_column='event_id')
    method_id = models.IntegerField(choices=TYPE)
    result = models.TextField()
    receiver = models.CharField(max_length=2000, default='')
    status_id = models.IntegerField(blank=True, default=1)  # 1是成功
    errorcode = models.IntegerField(blank=True, default=0)
    error = models.TextField(blank=True)
    senttimes = models.IntegerField(blank=True, default=0)
    badreceivers = models.TextField(blank=True)
    create_time = models.IntegerField()
    _database = 'monitor'

    @property
    def receiver_name(self):
        if self.method_id == 2:
            receiver_origin = self.receiver
            receiver_list = receiver_origin.split(',')

            for i in range(len(receiver_list)):
                phone = receiver_list[i].strip()
                try:
                    name = DdUsers.objects.get(telephone=phone).username
                except Exception:
                    name = phone
                receiver_list[i] = name
            return ",".join(receiver_list)
        else:
            return self.receiver

    class Meta:
        managed = False
        db_table = 'alarm'


class EventDetail(Father, models.Model):
    id = models.AutoField(primary_key=True)
    event = models.ForeignKey(Event, db_column='event_id')
    site = models.ForeignKey(Site, db_column='site_id', blank=True, null=True, on_delete=models.SET_NULL)
    pool = models.ForeignKey(App, db_column='pool_id',blank=True, null=True, on_delete=models.SET_NULL)
    group_id = models.IntegerField()
    ip = models.CharField(max_length=255)
    server_type = models.IntegerField()
    parent_ip = models.CharField(max_length=255)
    switch_ip = models.CharField(max_length=255)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_detail'


class EventDetailCreate(Father, models.Model):
    id = models.AutoField(primary_key=True)
    event_id = models.IntegerField(default=0)
    site_id = models.IntegerField(default=0)
    pool_id = models.IntegerField(default=0)
    group_id = models.IntegerField(default=0)
    ip = models.CharField(max_length=255)
    server_type = models.IntegerField(default=0)
    parent_ip = models.CharField(max_length=255)
    switch_ip = models.CharField(max_length=255)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_detail'


# 设置后，事件自动被处理(事件status设置为2), 事件不在未处理事件页面展示
class EventFilter(Father, models.Model):
    STATUS = (
        (0, "禁用"),
        (1, "启用"),
    )
    id = models.AutoField(primary_key=True)
    start_time = models.IntegerField(default=0)
    end_time = models.IntegerField(default=0)
    source = models.ForeignKey(EventSourceMap, db_column='source_id', blank=True, null=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(EventTypeMap, db_column='type_id', blank=True, null=True, on_delete=models.SET_NULL)
    pool = models.ForeignKey(App, db_column='pool_id', blank=True, null=True, on_delete=models.SET_NULL)
    ip = models.CharField(max_length=255, default='', blank=True)
    level = models.ForeignKey(EventLevelMap, db_column='level_id', blank=True, null=True, on_delete=models.SET_NULL)
    keyword = models.CharField(max_length=255, default='', blank=True)
    user = models.CharField(max_length=255, default='')
    status = models.IntegerField(default=0, choices=STATUS)
    create_time = models.IntegerField(default=0)
    # 0:告警; 1:屏蔽
    is_alarm = models.IntegerField(default=0)
    comment = models.TextField(blank=True, default='')
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_filter'


# 一定时间内的类似事件归为一类
class EventConvergenceRule(Father, models.Model):
    STATUS = (
        (0, "否"),
        (1, "是"),
    )
    id = models.AutoField(primary_key=True)
    source = models.ForeignKey(EventSourceMap, db_column='source_id')
    type = models.ForeignKey(EventTypeMap, db_column='type_id')
    pool = models.ForeignKey(App, db_column='pool_id',blank=True, null=True, on_delete=models.SET_NULL)
    same_ip = models.IntegerField(default=0, choices=STATUS)
    level = models.ForeignKey(EventLevelMap, db_column='level_id')
    key = models.CharField(max_length=255, default='', blank=True)
    interval = models.IntegerField(default=0)
    tmp_time = models.IntegerField(default=0)
    comment = models.TextField(blank=True, default='')
    user = models.CharField(max_length=255, default='')
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_convergence_rule'


class SendLog(Father, models.Model):
    id = models.AutoField(primary_key=True)
    event_id = models.IntegerField(default=0)
    return_id = models.CharField(max_length=255)
    receiver = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    method = models.CharField(max_length=255)
    send_time = models.IntegerField(default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'send_log'


class EventIntelligentCreate(Father, models.Model):
    id = models.AutoField(primary_key=True)
    interval_time = models.IntegerField(blank=True, default=0)
    reason = models.CharField(max_length=255, blank=True, default='')
    level_id = models.IntegerField(default=0)
    type_id = models.IntegerField(default=0)
    source_id = models.IntegerField(default=0)
    title = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    send_to = models.CharField(max_length=3000, default='', blank=True)
    caller = models.CharField(max_length=3000, default='', blank=True)
    create_time = models.IntegerField(blank=True, default=0)
    ip = models.CharField(max_length=255, blank=True, default='')
    parent_ip = models.CharField(max_length=255, blank=True, default='')
    switch_ip = models.CharField(max_length=255, blank=True, default='')
    pool_id = models.IntegerField(default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_intelligent'


class SwitchServer(models.Model):
    id = models.AutoField(primary_key=True)
    switch_ip = models.CharField(max_length=255)
    server_ip = models.CharField(max_length=255)
    _database = 'default'

    class Meta:
        managed = False
        db_table = 'switch_server'


class VoiceWarning(models.Model):
    id = models.AutoField(primary_key=True)
    content = models.TextField()
    md5_content = models.CharField(max_length=50)
    create_time = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    operator = models.CharField(max_length=255)
    operator_time = models.IntegerField(default=0)
    _database = 'db_warning'

    class Meta:
        managed = False
        db_table = 'voice_warning'


class T(models.Model):
    id = models.AutoField(primary_key=True)
    value = models.TextField()
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'test'


# 事件等级调整
class EventLevelAdjustment(Father, models.Model):
    id = models.AutoField(primary_key=True)
    start_time = models.IntegerField(default=0)
    end_time = models.IntegerField(default=0)
    source = models.ForeignKey(EventSourceMap, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(EventTypeMap, blank=True, null=True, on_delete=models.SET_NULL)
    pool = models.ForeignKey(App, blank=True, null=True, on_delete=models.SET_NULL)
    ip = models.CharField(max_length=255, default='', blank=True)
    keyword = models.TextField(max_length=255, default='', blank=True)
    origin_level = models.ForeignKey(EventLevelMap, related_name='origin_level', blank=True, null=True, on_delete=models.SET_NULL)
    new_level = models.ForeignKey(EventLevelMap, related_name='new_level', blank=True, null=True, on_delete=models.SET_NULL)
    operator = models.CharField(max_length=45, default='')
    create_time = models.IntegerField(default=0)
    comment = models.TextField(max_length=255, blank=True, default='')
    hit_time = models.IntegerField(default=0)
    # 0:valid, 1:logical deletion
    status = models.IntegerField(default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_level_adjustment'


# 屏蔽event，event不进MQ, 不保存到事件表
class EventMask(Father, models.Model):
    id = models.AutoField(primary_key=True)
    start_time = models.IntegerField(default=0)
    end_time = models.IntegerField(default=0)
    source = models.ForeignKey(EventSourceMap, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(EventTypeMap, blank=True, null=True, on_delete=models.SET_NULL)
    level = models.ForeignKey(EventLevelMap, blank=True, null=True, on_delete=models.SET_NULL)
    pool = models.ForeignKey(App, blank=True, null=True, on_delete=models.SET_NULL)
    ip = models.CharField(max_length=255, default='', blank=True)
    keyword = models.TextField(max_length=255, default='', blank=True)
    operator = models.CharField(max_length=45, default='')
    create_time = models.IntegerField(default=0)
    comment = models.TextField(max_length=255, blank=True, default='')
    hit_time = models.IntegerField(default=0)
    # 0:valid, 1:logical deletion
    status = models.IntegerField(default=0)
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_mask'


# 被屏蔽、被升降级的事件，保存到事件预处理表备查
class EventPreprocess(Father, models.Model):
    id = models.AutoField(primary_key=True)
    event_info = models.TextField(default='')
    alarm_content = models.TextField(default='')
    result = models.TextField(default='')
    receiver = models.CharField(max_length=1000, default='')
    errorcode = models.IntegerField(blank=True, default=0)
    error = models.TextField(blank=True)
    senttimes = models.IntegerField(blank=True, default=0)
    badreceivers = models.TextField(blank=True)
    create_time = models.IntegerField()
    _database = 'monitor'

    class Meta:
        managed = False
        db_table = 'event_preprocess'
