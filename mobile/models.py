# -*- coding:utf-8 -*-

from django.db import models
from cmdb.models import DdUsers

class TOrderMin(models.Model):
    order_count = models.IntegerField(default=0,db_column='count')
    time_position = models.IntegerField(default=0)
    create_time = models.IntegerField(default=0)

    class Meta:
        db_table = 't_order_min'


class AuthUser(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=30, default='')
    email = models.CharField(max_length=75, default='')
    is_app = models.IntegerField(default=0)

    class Meta:
        db_table = 'auth_user'

class SearchUserHistory(models.Model):
 
    id = models.AutoField(primary_key=True)
    dd_user = models.ForeignKey(DdUsers, db_column='user_id')
    owner_id = models.IntegerField(max_length=11)

    class Meta:
        db_table = 'mobile_search_user_history'
