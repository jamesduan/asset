# -*- coding: utf-8 -*-
from django.db import models
from cmdb.models import DdDomainV2, DdUsers,  DdDepartmentNew
from util.timelib import timelength_format, stamp2str
from monitor.models import EventLevelMap
from cmdb.models import AppWeb
from change.models import Action


class AccidentParentType(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True,)
    name = models.CharField(max_length=50,)                                     #事故类型
    define = models.TextField()                                                 #类型定义
    enable = models.IntegerField(max_length=4, default=0)                       #类型标记

    class Meta:
        managed = False
        db_table = 'accident_parent_type'


class AccidentType(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True,)
    ptype = models.ForeignKey(AccidentParentType, db_column='ptype_id')         #上级类型
    name = models.CharField(max_length=50,)                                     #事故类型
    enable = models.IntegerField(max_length=4, default=0)                       #类型标记

    class Meta:
        managed = False
        db_table = 'accident_type'


class AccidentStatus(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True,)
    name = models.CharField(max_length=50,)                                     #事故状态

    class Meta:
        managed = False
        db_table = 'accident_status'


class AccidentOtherDomain(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True,)
    domainname = models.CharField(max_length=150)
    deptid = models.IntegerField(max_length=11)
    deptname = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'accident_other_domain'


class Accident(models.Model):
    _database = 'accident'

    LEVEL_NAME = (
        (0, '未定义'),
        (1, 'S1'),
        (2, 'S2'),
        (3, 'S3'),
        (4, 'S4')
    )

    id = models.AutoField(primary_key=True)
    accidentid = models.IntegerField(max_length=11, unique=True, blank=True)        #事故编号
    title = models.CharField(max_length=255)                                        #事故名称
    level = models.IntegerField(max_length=4, choices=LEVEL_NAME, default=0, blank=True)       #事故等级
    find_user_name = models.CharField(max_length=50, blank=True)                    #事故发现人
    duty_manager_name = models.CharField(max_length=50, blank=True)                 #值班经理
    happened_time = models.IntegerField(max_length=12, blank=True)                  #事故发生时间
    finish_time = models.IntegerField(max_length=12,blank=True, default=0)          #事故恢复时间
    reason = models.TextField(blank=True)                                           #事故原因
    is_accident = models.IntegerField(max_length=4, default=0)                      #是否事故
    status = models.ForeignKey(AccidentStatus, db_column='status_id',blank=True, null=True, on_delete=models.SET_NULL)  #事故跟进状态，默认事故中

    process = models.TextField(blank=True)                                          #事故经过
    comment = models.CharField(max_length=255, blank=True)                          #事故备注

    duty_users = models.CharField(max_length=150, blank=True)                       #责任报告人
    type = models.ForeignKey(AccidentType, db_column='type_id', blank=True, null=True, on_delete=models.SET_NULL)    #事故根源类型

    affect = models.TextField(blank=True)                                           #影响（范围及程度、订单量、销售额）
    is_available = models.IntegerField(max_length=4, default=0)                     #是否影响可用性
    root_reason = models.TextField(blank=True)                                      #事故根本原因
    is_punish = models.IntegerField(max_length=4, default=0)                        #是否 处罚，默认不处罚
    punish_users = models.CharField(max_length=150,blank=True)                      #惩罚人（多个）
    punish_content = models.TextField(blank=True)                                   #惩罚内容
    basicinfo_time = models.IntegerField(max_length=12,blank=True)                  #基础信息录入时间
    detailinfo_time = models.IntegerField(max_length=12,blank=True)                 #详细信息录入时间
    mantis_id = models.IntegerField(max_length=11,default=0)                        #mantis编号，默认为0，不提交mantis
    is_online = models.IntegerField(max_length=4, default=0, blank=True)            # 是否电商系统
    health = models.FloatField(max_length=10, default=1, blank=True)                # 调校系数-业务健康度

    @property
    def time_length(self):        # 事故影响时长
        return timelength_format(self.happened_time, self.finish_time)

    @property
    def duty_manager_name_ch(self):
        if self.duty_manager_name != '' and self.duty_manager_name is not None:
            try:
                user = DdUsers.objects.using('default').get(username=self.duty_manager_name, enable=0)
            except DdUsers.DoesNotExist:
                user = None
            username = user.username_ch if user else ''
        else:
            username = ''
        return username

    @property
    def find_user_department(self):
        if self.find_user_name != '' and self.find_user_name is not None:
            try:
                find_user = DdUsers.objects.using('default').get(username=self.find_user_name, enable=0)
            except DdUsers.DoesNotExist:
                find_user = None
            find_user_department = find_user.dept_level2.deptname
        else:
            find_user_department = ''
        return find_user_department

    @property
    def duty_domains(self):
        return self.accident_domain.using('accident').all()

    @property
    def duty_dept_ids(self):
        dm_ids = [a_dm.domainid for a_dm in self.duty_domains]
        dept_ids = [str(dm.department_level2.id) for dm in DdDomainV2.objects.filter(id__in=dm_ids) if
                      dm.department_level2]
        others = [str(other.deptid) for other in AccidentOtherDomain.objects.filter(id__in=dm_ids)]
        return (',').join(list(set(dept_ids)) + others)

    @property
    def duty_dept_names(self):
        dm_ids = [a_dm.domainid for a_dm in self.duty_domains]
        duty_depts = [dm.department_level2.deptname for dm in DdDomainV2.objects.filter(id__in=dm_ids) if dm.department_level2 and dm.department_level2.deptname]
        others = [other.deptname for other in AccidentOtherDomain.objects.filter(id__in = dm_ids)]
        return (',').join(list(set(duty_depts)) + others)

    @property
    def duty_domain_ids(self):
        dm_ids = [str(a_dm.domainid) for a_dm in self.duty_domains]
        return (',').join(dm_ids)

    @property
    def duty_domain_names(self):
        dm_ids = [a_dm.domainid for a_dm in self.duty_domains]
        duty_dms = [dm.domainname for dm in DdDomainV2.objects.filter(id__in=dm_ids)]
        others = [other.domainname for other in AccidentOtherDomain.objects.filter(id__in=dm_ids)]
        return (',').join(duty_dms + others)

    @property
    def logs(self):
        return AccidentLog.objects.using('accident').filter(accident_id=self.accidentid).order_by('-create_time')

    @property
    def logs_happened(self):
        return AccidentLog.objects.using('accident').filter(accident_id=self.accidentid).order_by('happened_time')

    @property
    def action(self):
        return self.accident_action.using('accident').all().select_related()

    @property
    def happened_time_str(self):
        return stamp2str(self.happened_time, formt='%Y-%m-%d %H:%M:%S')

    @property
    def finish_time_str(self):
        return stamp2str(self.finish_time, formt='%Y-%m-%d %H:%M:%S')

    @property
    def basic_sla(self):        # 基本信息填写SLA,精确到分钟
        return timelength_format(self.finish_time, self.basicinfo_time, unit='m')

    @property
    def detail_sla(self):        # 详细信息填写SLA，精确到分钟
        return timelength_format(self.finish_time, self.detailinfo_time, unit='m')

    @property
    def is_online_str(self):
        if self.is_online == 1:
            return u'电商系统'
        elif self.is_online == 2:
            return u'办公系统'
        else:
            return u'未定义'

    class Meta:
        managed = False
        db_table = 'accident'


class AccidentDomain(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True)
    accident = models.ForeignKey(Accident, related_name='accident_domain', db_column='accident_id', db_index=True, to_field='accidentid', on_delete=models.SET_NULL, null=True)            #事故ID
    # accident_id = models.IntegerField(max_length=11)            # 事故ID
    # domain = models.ForeignKey(DdDomainV2, db_column='domainid', blank=True, on_delete=models.SET_NULL, null=True)
    domainid = models.IntegerField(max_length=11)               # 责任DomainID
    departmentid = models.IntegerField(max_length=11)           # 责任部门ID

    @property
    def domainname(self):
        try:
            domainname = DdDomainV2.objects.using('default').get(id=self.domainid).domainname
        except DdDomainV2.DoesNotExist:
            try:
                domainname = AccidentOtherDomain.objects.get(id=self.domainid).domainname
            except AccidentOtherDomain.DoesNotExist:
                domainname = ''
        return domainname

    @property
    def deptname(self):
        try:
            deptname = DdDepartmentNew.objects.using('default').get(id=self.departmentid).deptname
        except DdDepartmentNew.DoesNotExist:
            try:
                deptname = AccidentOtherDomain.objects.get(id=self.departmentid).deptname
            except AccidentOtherDomain.DoesNotExist:
                deptname = ''
        return deptname

    class Meta:
        managed = False
        db_table = 'accident_domain'


class AccidentAction(models.Model):
    _database = 'accident'

    STATUS_NAME = (
        (1, '进行中'),
        (2, '延迟'),
        (200, '已完成'),
        (400, '已取消')
    )
    id = models.AutoField(primary_key=True)
    accident = models.ForeignKey(Accident, related_name='accident_action', db_column='accident_id', to_field='accidentid')            #事故ID
    # accident_id = models.IntegerField(max_length=11)            #事故ID
    action = models.CharField(max_length=255)                   #action内容
    duty_users = models.CharField(max_length=150)               #action负责人ID
    create_time = models.IntegerField(max_length=12, blank=True, default=0)            #录入时间
    expect_time = models.IntegerField(max_length=12)            #预期完成时间
    finish_time = models.IntegerField(max_length=12, blank=True, default=0)            #实际完成时间
    trident_id = models.CharField(max_length=30,  blank=True, default='')    #tridentID（预期完成时间超过两周的action需关联）
    status = models.IntegerField(max_length=4, choices=STATUS_NAME, default=1)                  #action状态
    comment = models.CharField(max_length=255, blank=True)

    @property
    def dutydept_name(self):
        if self.duty_users != '' and self.duty_users is not None:
            users = DdUsers.objects.filter(username__in=self.duty_users.split(','), enable=0)
            if users.exists():
                return (',').join(list(set([user.dept_level2.deptname for user in users if user.dept_level2])))
            else:
                return ''
        else:
            return ''

    # @property
    # def dutydept(self):
    #     users = DdUsers.objects.filter(username__in = self.duty_users.split(','), enable=0)
    #     dept_ids = list(set([user.dept_level2.id for user in users]))
    #     depts = DdDepartmentNew.objects.filter(id__in = dept_ids, enable = 0)
    #     if depts:
    #         return depts
    #     else:
    #         return []

    @property
    def expect_time_format(self):
        return stamp2str(self.expect_time, formt='%Y-%m-%d')

    class Meta:
        managed = False
        db_table = 'accident_action'


class AccidentPool(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True)
    accident_id = models.IntegerField(max_length=11)            # 事故ID
    app_id = models.IntegerField(max_length=11)                 # 应用ID
    enable = models.IntegerField(max_length=4, default=0)       # 状态 1代表废弃
    create_time = models.IntegerField(max_length=12)            # 录入时间

    @property
    def app(self):
        try:
            app = AppWeb.objects.using('default').get(id=self.app_id)
        except AppWeb.DoesNotExist:
            app = None
        return app

    class Meta:
        managed = False
        db_table = 'accident_pool'


class AccidentLog(models.Model):
    _database = 'accident'

    SOURCE_NAME = (
        (0, '事故中心'),
        (1, '配置变更'),
        (2, '告警事件'),
    )
    FROM_ACCIDENT_CHOICE = (
        (0, '默认'),
        (1, '事故发生'),
        (2, '事故恢复'),
    )
    id = models.AutoField(primary_key=True)
    accident_id = models.IntegerField(max_length=11, default=0, blank=True)                            #事故ID
    username = models.CharField(max_length=150)                                 #录入员工
    source = models.IntegerField(max_length=4, choices=SOURCE_NAME, default=0)            #系统来源
    from_id = models.IntegerField(max_length=11, default=0)                     #配置变更或告警事件表的ID
    app_id = models.IntegerField(max_length=4, default=0, blank=True)            #受影响应用ID
    ip = models.CharField(max_length=255, blank=True)                             #IP
    level_id = models.IntegerField(max_length=4, default=0, blank=True)                     #log重要性等级
    message = models.TextField()                                                 #log内容
    create_time = models.IntegerField(max_length=12, blank=True, default=0)                 #log系统写入时间
    happened_time = models.IntegerField(max_length=12, blank=True, default=0)               #log描述的发生时间
    from_accident = models.IntegerField(max_length=4, default=0, choices=FROM_ACCIDENT_CHOICE)  #事故发生和恢复时间记录，需同步事故表
    is_process = models.IntegerField(max_length=4, default=0, blank=True)        #是否同步至事故处理经过,预留

    @property
    def level_name(self):
        if self.source == 0:
            level_name = 'L5'
        elif self.source == 1:
            actions = Action.objects.using('change').filter(level_id=self.level_id)
            if actions.count() > 1:
                level_name = actions.first().get_level_name
            else:
                level_name = ''
        elif self.source == 2:
            try:
                level_name = EventLevelMap.objects.using('monitor').get(id=self.level_id).name
            except EventLevelMap.DoesNotExist:
                level_name = '未定义'
        else:
            level_name = '未定义'
        return level_name

    @property
    def create_time_format(self):
        return stamp2str(self.create_time, formt='%Y-%m-%d %H:%M:%S')

    @property
    def happened_time_format(self):
        return stamp2str(self.happened_time, formt='%Y/%m/%d %H:%M:%S')

    @property
    def images(self):
        return AccidentLogImage.objects.filter(accident_log_id=self.id)

    class Meta:
        managed = False
        ordering = ('-create_time',)
        db_table = 'accident_log'


class AccidentLogImage(models.Model):
    _database = 'accident'

    id = models.AutoField(primary_key=True)
    accident_log_id = models.IntegerField(max_length=11, default=None)              #事故log信息ID
    image = models.ImageField(upload_to='image/accident/%Y/%m/%d', db_column='image_path', max_length=255)   #log图片存储路径
    create_time = models.IntegerField(max_length=12, blank=True, default=0)  # 事故log上传图片时间

    class Meta:
        managed = False
        db_table = 'accident_log_image'