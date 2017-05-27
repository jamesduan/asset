# -*- coding:utf-8 -*-
from django.db import models


class HybridRequirement(models.Model):
    STATUS = (
        (1, '未申请'),
        (2, '申请中'),
        (3, '申请成功'),
    )
    LONG = (
        (0, '短期'),
        (1, '长期')
    )
    id = models.AutoField(primary_key=True)
    cname = models.CharField(max_length=255)
    total = models.IntegerField()
    real_total = models.IntegerField(default=0, blank=True)
    machine_config = models.CharField(max_length=150)
    server_template = models.CharField(max_length=150)
    idc = models.CharField(max_length=150)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(max_length=300, blank=True)
    status = models.IntegerField(default=1, choices=STATUS)
    is_long = models.IntegerField(default=0, choices=LONG)

    class Meta:
        db_table = u'hybrid_requirement'


class HybridRequirementDetail(models.Model):
    STATUS = (
        (1, '申请成功'),
        (2, '已确认'),
        (3, '确认失败'),
        (4, '已加白名单'),
        (5, '已导入'),
        (6, '已废弃'),
    )
    id = models.AutoField(primary_key=True)
    requirement = models.ForeignKey(HybridRequirement, db_column='requirement_id')
    ip = models.CharField(max_length=150)
    index = models.CharField(max_length=300, blank=True)
    status = models.IntegerField(choices=STATUS, default=1)
    created = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = u'hybrid_requirement_detail'