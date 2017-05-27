# -*- coding: utf-8 -*-

from django.db import models


class Reg(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, default='')
    type = models.IntegerField(default=1)
    query = models.CharField(max_length=500)
    interval_type = models.IntegerField(default=1)
    interval_value = models.IntegerField(default=60)
    comparison = models.CharField(max_length=255, default='>')
    count = models.IntegerField(default=0)
    group_by = models.CharField(max_length=255, default='access_ip')
    is_influence = models.IntegerField(default=0)
    enable = models.IntegerField(default=1)
    remark = models.CharField(max_length=255, default='', blank=True)
    applicant = models.CharField(max_length=255, default='')
    apply_date = models.DateField(blank=True)
    updater = models.CharField(max_length=255, default='')
    update_time = models.DateTimeField(blank=True)
    _database = "logplatform"

    class Meta:
        db_table = 'reg'


class Log(models.Model):
    id = models.AutoField(primary_key=True)
    reg_id = models.IntegerField(default=0)
    content = models.TextField(default='')
    update_time = models.DateTimeField(blank=True)
    _database = "logplatform"

    class Meta:
        managed = False
        db_table = 'log'
