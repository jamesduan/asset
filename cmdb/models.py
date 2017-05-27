# -*- coding: utf-8 -*-
from django.db import models
from asset.models import Room

class Site(models.Model):
    id = models.AutoField(primary_key=True)
    cmis_id = models.IntegerField(default=0)
    name = models.CharField(max_length=100, default='')
    comment = models.CharField(max_length=255, default='')
    created = models.IntegerField(default=0)
    status = models.IntegerField(default=0)

    @property
    def app_total(self):
        return App.objects.filter(site_id=self.id).count()

    class Meta:
        managed = False
        db_table = 'site'


class App(models.Model):
    TYPE = (
        (0, '应用'),
        (1, '基础服务'),
    )
    id = models.AutoField(primary_key=True)
    cmis_id = models.IntegerField(default=0)
    cmis_site_id = models.IntegerField(default=0)
    name = models.CharField(max_length=100, default='')
    site_id = models.IntegerField(default=0)
    type = models.IntegerField(default=1, choices=TYPE)
    level = models.CharField(max_length=50, default='')
    hudson_job = models.CharField(max_length=50, default='', blank=True)
    comment = models.TextField(default='')
    ctime = models.IntegerField(default=0)
    info = models.CharField(max_length=765)
    status = models.IntegerField(default=0)
    is_cmis_sync = models.IntegerField(default=0)
    domainid = models.IntegerField(default=0)
    offline_type = models.IntegerField(default=0)
    service_name = models.CharField(max_length=50, blank=True)
    test_status = models.IntegerField(max_length=2, default=0)

    @property
    def site(self):
        try:
            site = Site.objects.get(pk=self.site_id)
        except Site.DoesNotExist:
            site = None
        return site

    @property
    def domain(self):
        try:
            domain = DdDomain.objects.get(id=self.domainid)
        except DdDomain.DoesNotExist:
            domain = None
        return domain

    @property
    def server_total(self):
        from server.models import Server
        return Server.objects.filter(app_id=self.id).exclude(server_status_id = 400).count()

    @property
    def groups(self):
        from server.models import ServerGroup
        sg = ServerGroup.objects.filter(app_id = self.id)
        if sg:
            return [g.cname+ '_' + g.room.name for g in sg]
        else:
            return None

    @property
    def appcontact(self):
        try:
            appcontact=AppContact.objects.get(pool_id=self.id, pool_status=0)
        except (AppContact.DoesNotExist, AppContact.MultipleObjectsReturned):
            appcontact=None
        return appcontact

    class Meta:
        managed = False
        db_table = 'app'

    def __unicode__(self):
        return self.name

class AppWeb(models.Model):
    TYPE = (
        (0, '应用'),
        (1, '基础服务'),
    )
    id = models.AutoField(primary_key=True)
    cmis_id = models.IntegerField(default=0)
    cmis_site_id = models.IntegerField(default=0)
    name = models.CharField(max_length=100, default='')
    site_id = models.IntegerField(default=0)
    type = models.IntegerField(default=1, choices=TYPE)
    level = models.CharField(max_length=50, default='')
    hudson_job = models.CharField(max_length=50, default='', blank=True)
    comment = models.CharField(max_length=255, default='')
    ctime = models.IntegerField(default=0)
    info = models.CharField(max_length=765)
    status = models.IntegerField(default=0)
    is_cmis_sync = models.IntegerField(default=0)
    domainid = models.IntegerField(default=0)
    offline_type = models.IntegerField(default=0)
    service_name = models.CharField(max_length=50, blank=True)
    test_status = models.IntegerField(max_length=2, default=0)

    @property
    def site(self):
        try:
            site = Site.objects.get(pk=self.site_id)
        except Site.DoesNotExist:
            site = None
        return site

    @property
    def servers(self):
        from server.models import Server
        return Server.objects.filter(app_id=self.id).exclude(server_status_id = 400)

    @property
    def server_total(self):
        return self.servers.count()

    @property
    def server_stg_total(self):
        return self.servers.filter(server_env_id=1).count()

    @property
    def server_pro_total(self):
        return self.servers.filter(server_env_id=2).count()

    @property
    def JQ_pro_total(self):
        from asset.models import Rack, Room
        rack_ids = Rack.objects.filter(room_id__in = [4,10])
        return self.servers.filter(server_env_id=2, rack_id__in=[rack.id for rack in rack_ids]).count()

    @property
    def NH_pro_total(self):
        from asset.models import Rack, Room
        rack_ids = Rack.objects.filter(room_id=1)
        return self.servers.filter(server_env_id=2, rack_id__in=[rack.id for rack in rack_ids]).count()

    @property
    def groups(self):
        from server.models import ServerGroup
        sg = ServerGroup.objects.filter(app_id = self.id)
        if sg:
            return [g.cname+ '_' + g.room.name for g in sg]
        else:
            return None

    class Meta:
        managed = False
        db_table = 'app'

    def __unicode__(self):
        return self.name

class AppContact(models.Model):
    id = models.IntegerField(primary_key=True)
    site_id = models.IntegerField(default=0, max_length=11)
    site_name = models.CharField(max_length=50)
    pool_id = models.IntegerField(default=0, max_length=11)
    pool_name = models.CharField(max_length=50)
    pool_status = models.IntegerField(default=0, max_length=11)
    department_id = models.IntegerField(default=0, max_length=11)
    p_user = models.CharField(max_length=255)
    p_email = models.CharField(max_length=255)
    p_no = models.CharField(max_length=255)
    domain_email = models.CharField(max_length=255)
    sa_user = models.CharField(max_length=255)
    sa_email = models.CharField(max_length=255)
    sa_no = models.CharField(max_length=255)
    b_user = models.CharField(max_length=255)
    b_email = models.CharField(max_length=255)
    b_no = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    domain_id = models.IntegerField(default=0, max_length=11)
    domain_code = models.CharField(max_length=100, blank=True)
    domain_name = models.CharField(max_length=100, blank=True)
    domain_leader = models.CharField(max_length=100, blank=True)
    domain_account = models.CharField(max_length=100, blank=True)
    sa_backup_user = models.CharField(max_length=100, blank=True)
    sa_backup_email = models.CharField(max_length=100, blank=True)
    sa_backup_no = models.CharField(max_length=100, blank=True)
    head_user = models.CharField(max_length=100, blank=True)
    head_email = models.CharField(max_length=100, blank=True)
    head_no = models.CharField(max_length=100, blank=True)

    @property
    def pool(self):
        try:
            item = App.objects.get(pk=self.pool_id)
        except App.DoesNotExist:
            item = None
        return item

    @property
    def server_total(self):
        from server.models import Server
        return Server.objects.filter(app_id = self.pool_id).exclude(server_status_id = 400).count()

    class Meta:
        db_table = u'app_contact'


class DdDepartmentNew(models.Model):
    id = models.AutoField(primary_key=True)
    deptcode = models.CharField(max_length=150, db_column='deptCode', blank=True)
    deptname = models.CharField(max_length=150, db_column='deptName', blank=True)
    deptemailgroup = models.CharField(max_length=150, db_column='deptEmailGroup', blank=True)
    deptleaderaccount = models.CharField(max_length=150, db_column='deptLeaderAccount', blank=True)
    deptlevel = models.IntegerField(db_column='deptLevel')
    enable = models.IntegerField()
    pid = models.IntegerField()

    @property
    def telephone(self):
        try:
            telephone = DdUsers.objects.get(username=self.deptleaderaccount, enable=0)
        except DdUsers.DoesNotExist:
            telephone = None
        return telephone

    class Meta:
        db_table = u'dd_department_new'


# class DdDomainUsers(models.Model):
#     id = models.AutoField(primary_key=True)
#     domain_id = models.IntegerField()
#     user_id = models.IntegerField()
#
#     class Meta:
#         managed = False
#         db_table = 'dd_domain_users'


class DdDomain(models.Model):
    id = models.AutoField(primary_key=True)
    domaincode = models.CharField(max_length=150, db_column='domainCode')
    domainname = models.CharField(max_length=150, db_column='domainName')
    domainemailgroup = models.CharField(max_length=150, db_column='domainEmailGroup')
    domainleaderaccount = models.CharField(max_length=150, db_column='domainLeaderAccount')
    backupdomainleaderaccount = models.CharField(max_length=150, db_column='backupDomainLeaderAccount')
    departmentid = models.IntegerField(db_column='departmentId')
    departmentname = models.CharField(max_length=150, db_column='departmentName')
    enable = models.IntegerField()

    @property
    def app(self):
        return App.objects.filter(domainid=self.id, status=0)

    @property
    def department(self):
        try:
            dept = DdDepartmentNew.objects.get(id=self.departmentid)
        except DdDepartmentNew.DoesNotExist:
            dept = None
        return dept

    @property
    def department_level2(self):
        try:
            dept = DdDepartmentNew.objects.get(id= self.departmentid)
            if dept.deptlevel == 2:
                return dept
            dept_v2 = DdDepartmentNew.objects.get(id= dept.pid, deptlevel=2)
        except DdDepartmentNew.DoesNotExist:
            dept_v2 = None
        return dept_v2

    @property
    def telephone(self):
        try:
            telephone=DdUsers.objects.get(username=self.domainleaderaccount, enable=0)
        except DdUsers.DoesNotExist:
            telephone = None
        return telephone

    @property
    def backuptelephone(self):
        try:
            backuptelephone=DdUsers.objects.get(username=self.backupdomainleaderaccount, enable=0)
        except DdUsers.DoesNotExist:
            backuptelephone = None
        return backuptelephone

    class Meta:
        db_table = u'dd_domain'

    def __unicode__(self):
        return self.domaincode+' '+self.domainname


class DdDomainV2(models.Model):
    id = models.AutoField(primary_key=True)
    domaincode = models.CharField(max_length=150, db_column='domainCode')
    domainname = models.CharField(max_length=150, db_column='domainName')
    domainemailgroup = models.CharField(max_length=150, db_column='domainEmailGroup')
    domainleaderaccount = models.CharField(max_length=150, db_column='domainLeaderAccount')
    backupdomainleaderaccount = models.CharField(max_length=150, db_column='backupDomainLeaderAccount')
    department = models.ForeignKey(DdDepartmentNew, db_column='departmentId')
    # departmentid = models.IntegerField(db_column='departmentId')
    departmentname = models.CharField(max_length=150, db_column='departmentName')
    enable = models.IntegerField()

    all_depts = {}

    def __init_global(self):
        for d in DdDepartmentNew.objects.select_related().filter(deptlevel=2):
            self.all_depts[d.id] = d

    @property
    def department_level2(self):
        dept = self.department
        if dept:
            if dept.deptlevel == 2:
                return dept
            # dept_v2 = self.all_depts.setdefault(dept.pid, None)
            try:
                dept_v2 = DdDepartmentNew.objects.get(deptlevel=2, id=dept.pid, enable=0)
            except DdDepartmentNew.DoesNotExist:
                dept_v2 = None
        else:
            dept_v2 = None
        return dept_v2

    class Meta:
        managed = False
        db_table = u'dd_domain'

    def __unicode__(self):
        return self.domainname


class DdUsers(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50)
    display_name = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=100)
    enable = models.IntegerField()
    telephone = models.CharField(max_length=20)
    username_ch = models.CharField(max_length=255)
    domains = models.ManyToManyField(DdDomain)

    @property
    def dept_level2(self):
        if self.domains.all():
            dept_ids = list(set([dm.department_level2.id for dm in self.domains.all() if dm.department_level2]))
            dept = DdDepartmentNew.objects.filter(id__in=dept_ids, enable=0) if dept_ids else None
            dept2 = dept[0] if dept else None
        else:
            dept2 = None
        return dept2

    class Meta:
        managed = False
        db_table = 'dd_users'

    def __unicode__(self):
        return self.username


class DdUsersDomains(models.Model):
    id = models.AutoField(primary_key=True)
    ddusers = models.ForeignKey(DdUsers, db_column='ddusers_id')
    dddomain = models.ForeignKey(DdDomain, db_column='dddomain_id')

    class Meta:
        managed = False
        db_table = 'dd_users_domains'

class ConfigDbInstance(models.Model):
    id = models.AutoField(primary_key=True)
    cname = models.CharField(max_length=255, blank=True)
    dbname = models.CharField(max_length=255)
    db_type = models.CharField(max_length=30)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    instance_url = models.CharField(max_length=500)
    port = models.CharField(max_length=10)
    instance_type = models.CharField(max_length=50)
    idc = models.ForeignKey(Room, db_column='idc')

    class Meta:
        managed = False
        db_table = 'config_db_instance'

class ConfigDbKvDefault(models.Model):
    id = models.AutoField(primary_key=True)
    dbtype = models.CharField(max_length=50)
    jdbckey = models.CharField(max_length=200)
    jdbcval = models.CharField(max_length=200)
    jdbctype = models.IntegerField()
    jdbcdescribe = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'config_db_kv_default'

class ConfigDbKvCustom(models.Model):
    id = models.AutoField(primary_key=True)
    configinfo_id = models.IntegerField()
    # dbkv = models.ForeignKey(ConfigDbKvDefault, db_column="kv_id")
    dbtype = models.CharField(max_length=10)
    jdbckey = models.CharField(max_length=45)
    jdbcval = models.CharField(max_length=200)
    jdbctype = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'config_db_kv_custom'

class News(models.Model):
    id = models.IntegerField(primary_key=True)
    type = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    url = models.CharField(max_length=255)
    created = models.DateField()
    status = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'news'


class AuthUser(models.Model):
    id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=30)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.CharField(max_length=75)
    password = models.CharField(max_length=128)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    is_superuser = models.IntegerField()
    last_login = models.DateTimeField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

class AuthGroup(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=80)

    class Meta:
        managed = False
        db_table = 'auth_group'

class AuthUserGroups(models.Model):
    id = models.IntegerField(primary_key=True)
    user_id = models.IntegerField()
    group_id = models.IntegerField()
    # user_id = models.ForeignKey(AuthUser)
    # group_id = models.ForeignKey(AuthGroup)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'

class RotaActivity(models.Model):
    PROMOTION = (
        (0, '日常'),
        (1, '大促'),
        (2, '反馈'),
    )
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255,default='',blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    promotion = models.IntegerField(choices=PROMOTION)
    domains = models.ManyToManyField(DdDomain)

    class Meta:
        managed = False
        db_table = 'rota_activity'

    @property
    def shift_times(self):
        return ShiftTime.objects.filter(activity=self.id).order_by("id")


class ShiftTime(models.Model):
    id = models.AutoField(primary_key=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    activity = models.ForeignKey(RotaActivity,db_column="activity_id")

    class Meta:
        managed = True
        db_table = 'shift_time'

class Rota(models.Model):
    WAY = (
        (0, 'on call'),
        (1, 'on site'),
        (2, 'at home'),
    )
    id = models.AutoField(primary_key=True)
    duty_domain = models.ForeignKey(DdDomain,db_column="duty_domain_id")
    rota_activity = models.ForeignKey(RotaActivity,db_column="rota_activity_id")
    promotion = models.IntegerField()
    duty_man = models.ManyToManyField(DdUsers,related_name='man',through='RotaMan')
    duty_way = models.IntegerField(choices=WAY)
    duty_backup = models.ManyToManyField(DdUsers,related_name='backup',through='RotaBackup')
    duty_date_start = models.DateTimeField(null=True)
    duty_date_end = models.DateTimeField(null=True)
    shift_time = models.ForeignKey(ShiftTime,db_column="shift_time_id" ,null=True)
    comment = models.CharField(max_length=255,blank=True,default='')

    class Meta:
        managed = False
        db_table = 'rota'

class RotaMan(models.Model):
    rota = models.ForeignKey(Rota,db_column="rota_id")
    man = models.ForeignKey(DdUsers,db_column="ddusers_id",on_delete=models.DO_NOTHING)
    class Meta:
        managed = False
        db_table = 'rota_man'

class RotaBackup(models.Model):
    rota = models.ForeignKey(Rota,db_column="rota_id")
    backup = models.ForeignKey(DdUsers,db_column="ddusers_id",on_delete=models.DO_NOTHING)
    class Meta:
        managed = False
        db_table = 'rota_backup'

class DailyDutyConfig(models.Model):
    name=models.CharField(max_length=255)
    domain=models.ForeignKey(DdDomain,db_column="domain_id")
    dailyfrequency=models.IntegerField()
    cycle=models.IntegerField()
    startdate=models.DateTimeField(null=True)
    startwday=models.IntegerField(null=True)
    entryintoforce=models.DateTimeField()
    sendmail=models.IntegerField(default=1)
    enable=models.IntegerField(default=1)

    class Meta:
        managed =True
        db_table = 'daily_duty_config'

    @property
    def dailydutytime(self):
        return DailyDutyTime.objects.filter(dailydutyconfig=self.id).order_by('id')

    def __unicode__(self):
        return self.domain_id

class DailyDutyTime(models.Model):
    id= models.AutoField(primary_key=True)
    starttime=models.TimeField()
    addday=models.IntegerField()
    endtime=models.TimeField()
    dailydutyconfig=models.ForeignKey(DailyDutyConfig,db_column="dailydutyconfig_id")
    class Meta:
        managed =False
        db_table = 'daily_duty_time'

class SelectDomain(models.Model):
    id=models.AutoField(primary_key=True)
    domain=models.ForeignKey(DdDomain,db_column="domain_id")
    class Meta:
        managed = True
        db_table = 'select_domain'
    def __unicode__(self):
        return self.domain.domainname

class Pooltoacl(models.Model):
    id = models.AutoField(primary_key=True)
    ha_ip = models.CharField(max_length=20)
    acl_name = models.CharField(max_length=50)
    hdr = models.CharField(max_length=50,null=True)
    path_beg = models.CharField(max_length=50,null=True)
    class Meta:
        managed = False
        db_table = 'pooltoacl'

class Acltobackend(models.Model):
    id = models.AutoField(primary_key=True)
    ha_ip = models.CharField(max_length=40)
    acl_domain = models.CharField(max_length=50 ,null=True)
    acl_url = models.CharField(max_length=50 ,null=True)
    backend_name = models.CharField(max_length=50)
    class Meta:
        managed = False
        db_table = 'acltobackend'


class WebMenu(models.Model):
    TYPE = (
        (0, 'disable'),
        (1, 'enable'),
        (2, 'invisible'),
    )

    # glyphicon icon for main menu
    ICONS = (
        (0, '-------------'),
        (1, 'signal'),
        (2, 'credit-card'),
        (3, 'duplicate'),
        (4, 'blackboard'),
        (5, 'list'),
        (6, 'exclamation-sign'),
        (7, 'cog'),
        (8, 'hdd'),
        (9, 'wrench'),
        (10, 'plane'),
        (11, 'search'),
        (12, 'question-sign'),
        (13, 'oil'),
        (14, 'usd'),
        (15, 'cutlery'),
        (16, 'book'),
        (17, 'fire'),
        (18, 'flag'),
        (19, 'th'),
    )

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=45, default='')
    url = models.URLField(max_length=9000, blank=True)
    top = models.ForeignKey('self', null=True, blank=True)

    status = models.IntegerField(choices=TYPE, default=1)
    weight = models.IntegerField(default=0)
    icon = models.IntegerField(choices=ICONS, default=0)
    new_tab = models.IntegerField(choices=TYPE, default=0)
    doc_url = models.CharField(max_length=9000, blank=True)

    class Meta:
        managed = False
        db_table = 'web_menu'
        unique_together = (('name', 'top'),)

    def __unicode__(self):
        menu_list = [self.name]
        try:
            father = self.top
        except self.DoesNotExist:
            father = None

        while father:
            menu_list.insert(0, father.name)
            try:
                father = father.top
            except self.DoesNotExist:
                father = None

        return '>'.join(menu_list)


class AppV2(models.Model):
    TYPE = (
        (0, '应用'),
        (1, '基础服务'),
    )
    name = models.CharField(max_length=100, default='')
    site = models.ForeignKey(Site, related_name='site_apps')
    type = models.IntegerField(default=1, choices=TYPE)
    status = models.IntegerField(default=0)
    test_status = models.IntegerField(max_length=2, default=0)
    level = models.CharField(max_length=50, default='')
    service_name = models.CharField(max_length=50, blank=True)

    class Meta:
        managed = False
        db_table = 'app'
