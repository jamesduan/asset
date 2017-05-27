# -*- coding: utf-8 -*-
from django.db import models
from util.timelib import stamp2datestr
from cmdb.models import App,DdDomain
import django.utils.timezone as timezone
import time

class Main(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.CharField(max_length=50)
    task_id = models.CharField(max_length=150, editable=False)
    type = models.CharField(max_length=60)
    action = models.CharField(max_length=60)
    index = models.CharField(max_length=150)
    level = models.CharField(max_length=30)
    message = models.TextField(blank=True)
    happen_time = models.DateTimeField(blank=True)
    created = models.DateTimeField(editable=False)
    action_id = models.IntegerField(max_length=11)
    app = models.ForeignKey(App, null=True, db_column='app_id')

    _database = 'change'

    @property
    def pool_name(self):
        if not self.app:
            return ''
        return self.app.site.name + '/' + self.app.name

    @property
    def happen_time_str(self):
        return self.happen_time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def action_ref(self):
        try:
            action = Action.objects.using('change').get(pk=self.action_id)
        except Action.DoesNotExist:
            action = None
        return action

    class Meta:
        db_table = u'main'

class Type(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=50, blank=True)
    desc = models.TextField(blank=True)

    _database = 'change'

    def __str__(self):
        return self.key

    class Meta:
        db_table = 'types'

# class Level(models.Model):
#     """
#     Description: Model Description
#     """
#     id = models.AutoField(primary_key=True)
#     name = models.CharField(max_length=50)
#     comment = models.TextField(blank=True)

#     _database = 'change'

#     class Meta:
#         db_table = 'levels'


class Action(models.Model):
    VL = (
        (1, "L1"),
        (2, "L2"),
        (3, "L3"),
        (4, "L4"),
        (5, "L5"),
    )
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=50, blank=True)
    type = models.ForeignKey(Type, null=False, db_column='type_id')
    desc = models.TextField(blank=True)
    level_id = models.IntegerField(max_length=11, choices=VL)

    _database = 'change'

    # @property
    # def get_type_action_name(self):
    #     return self.type.key + '/' + self.key

    @property
    def get_level_name(self):
        if not self.level_id:
            return ""
        return self.get_level_id_display()

    def __str__(self):
        return self.type.key + " -> " + self.key
    
    class Meta:
        db_table = 'actions'

class ExceptionReport(models.Model):
    TYPE=(
        (0,'CMDB'),
        (1,'YCC配置组'),
    )
    STATUS=(
        (0,'0'),
        (1,'1'),
    )
    LEVEL=(
        (100,'100(紧急)'),
        (200,'200(严重)'),
        (300,'300(重要)'),
        (350,'350(次要)'),
        (400,'400(警告)'),
        (500,'500(信息)'),
    )
    id = models.AutoField(primary_key=True)
    type=models.IntegerField(choices=TYPE,default=0)
    cname = models.CharField(max_length=255)
    cmdbsql = models.CharField(max_length=500,blank=True)
    api_url = models.CharField(max_length=500,null=True,blank=True)
    owner = models.CharField(max_length=30,blank=True)
    owner_domain = models.ForeignKey(DdDomain,db_column='owner_id',null=True,blank=True)
    status = models.IntegerField(max_length=4, choices=STATUS,default=1)
    fileds = models.CharField(max_length=500, blank=True)
    api_fields = models.CharField(max_length=500,null=True,blank=True)
    last_update = models.IntegerField(max_length=11)
    exception_count = models.IntegerField(max_length=11)
    use_db = models.CharField(max_length=50, blank=True)
    db_mail = models.CharField(max_length=255)
    frequency = models.IntegerField(null=True,blank=True)
    last_email_date =models.DateField(default=time.strftime('%Y-%m-%d',time.localtime()),null=True,blank=True)
    # level = models.ForeignKey(EventLevelMap,null=True,blank=True, on_delete=models.SET_NULL)
    level_id=models.IntegerField(choices=LEVEL,default=400)
    class Meta:
        db_table = u'exception_report'

    def __unicode__(self):
        return self.cname

class ExceptionReportDaily(models.Model):
    id = models.AutoField(primary_key=True)
    report_id = models.IntegerField()
    create_time = models.IntegerField()
    exception_count = models.IntegerField()

    @property
    def create_time_str(self):
        return stamp2datestr(self.create_time, formt='%Y-%m-%d')

    class Meta:
        db_table = u'exception_report_daily'

class ExceptionDetailComment(models.Model):
    id = models.AutoField(primary_key=True)
    exception_id = models.IntegerField()
    index = models.CharField(max_length=100)
    comment = models.CharField(max_length=50)

    class Meta:
        db_table = u'exception_detail_comment'