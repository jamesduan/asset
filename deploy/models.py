# -*- coding: utf-8 -*-
from django.db import models
from cmdb.models import App, Site, AuthUser
from asset.models import Room
from server.models import ServerEnv, Server, ServerStatus, ServerType
from asset.models import Rack
from util.timelib import *
from django.contrib.auth.models import User
import time
import os
import HTMLParser


class DeployLog(models.Model):
    depid = models.CharField(max_length=30, default='')
    host = models.CharField(max_length=30, default='')
    error = models.IntegerField(default=0)
    log = models.TextField(default='')
    create_time = models.IntegerField(default=0)

    @property
    def create_time_str(self):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.create_time))

    class Meta:
        db_table = 'deploy_log'

    def __unicode__(self):
        return '%s: [%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.create_time)), self.host, self.log)


# class Deployv3VersionApp(models.Model):
#     id = models.AutoField(primary_key=True)
#     site_id = models.IntegerField()
#     site_name = models.CharField(max_length=50)
#     app_id = models.IntegerField()
#     app_name = models.CharField(max_length=100)
#     app_env = models.IntegerField()
#     app_version = models.CharField(max_length=500)
#     version_package = models.CharField(max_length=500)
#     created_time = models.DateTimeField(blank=True)
#     updated_time = models.DateTimeField(blank=True)
#
#     class Meta:
#         managed = False
#         db_table = 'deployv3_version_app'


class Deployv3VersionServer(models.Model):
    id = models.IntegerField(primary_key=True)
    ip = models.CharField(max_length=50)
    server_version = models.CharField(max_length=500)
    healthcheck_server_version = models.CharField(max_length=500)
    created_time = models.DateTimeField(blank=True, null=True)
    updated_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'deployv3_version_server'


class Deployv3Detail(models.Model):
    id = models.AutoField(primary_key=True)
    depid = models.CharField(max_length=90)
    target_host = models.CharField(max_length=90)
    deploy_host = models.CharField(max_length=90)

    class Meta:
        db_table = u'deployv3_detail'


class Deployv3StgMain(models.Model):
    id = models.AutoField(primary_key=True)
    depid = models.CharField(max_length=30, unique=True, blank=True)
    uid = models.CharField(max_length=20)
    site_id = models.IntegerField(blank=True)
    app_id = models.IntegerField(blank=True)
    deploy_type = models.IntegerField(blank=True, default=0)
    status = models.IntegerField(blank=True, max_length=2)
    source_path = models.CharField(max_length=255, blank=True)
    version = models.CharField(max_length=255, blank=True)
    is_restart = models.IntegerField()
    bz = models.CharField(max_length=1000, blank=True)
    created = models.IntegerField(blank=True, max_length=12)
    success_update = models.IntegerField(blank=True, default=0, max_length=12)
    rollback_update = models.IntegerField(blank=True, default=0, max_length=12)
    is_process = models.IntegerField(blank=True, default=0, max_length=4)
    process = models.FloatField(blank=True, default=0)
    is_autocreated = models.IntegerField(blank=True, default=0, max_length=4)

    @property
    def app(self):
        try:
            app = App.objects.get(id=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    @property
    def site(self):
        try:
            site = Site.objects.get(id=self.site_id)
        except Site.DoesNotExist:
            site = None
        return site

    @property
    def detail(self):
        return Deployv3Detail.objects.filter(depid=self.depid)

    @property
    def created_time(self):
        return stamp2str(self.created)

    @property
    def success_time(self):
        return stamp2str(self.success_update)

    @property
    def rollback_time(self):
        return stamp2str(self.rollback_update)

    @property
    def status_name(self):
        if self.status == 1:
            return '待发布'
        elif self.status == 2:
            return '已发布'
        elif self.status == 3:
            return '已回滚'
        elif self.status == 4:
            return '发布异常'
        elif self.status == 5:
            return '已作废'

    @property
    def deploy_type_name(self):
        if self.deploy_type == 0:
            return 'webapps'
        elif self.deploy_type == 3:
            return 'static'
        else:
            return '未定义'

    @property
    def logs(self):
        return DeployLog.objects.filter(depid=self.depid).order_by('-id')

    @property
    def ips(self):
        return ''

    @property
    def bz_safe(self):
        return HTMLParser.HTMLParser().unescape(self.bz)

    class Meta:
        db_table = u'deployv3_stg_main'

class Deployv3StgMaxtime(models.Model):
    id = models.AutoField(primary_key=True)
    app = models.ForeignKey(App, db_column="app_id", blank=True, default=0)
    deploy_maxtime = models.IntegerField(max_length=11)
    deploy_type = models.IntegerField(max_length=4, default=0, db_column='deploy_type_id')

    @property
    def deploy_type_name(self):
        if self.deploy_type == 0:
            return 'webapps'
        elif self.deploy_type == 3:
            return 'static'
        else:
            return '未定义'

    class Meta:
        db_table = u'deployv3_stg_maxtime'

class DeployFtp(models.Model):
    app_id = models.IntegerField(default=0, unique=True)
    ftp = models.CharField(max_length=255, default='')
    path = models.CharField(max_length=255, default='')
    user = models.CharField(max_length=50, default='')
    passwd = models.CharField(max_length=50, default='')
    active = models.IntegerField(default=1)

    @property
    def app(self):
        try:
            app = App.objects.get(pk=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    class Meta:
        db_table = 'deploy_ftp'


class DeployPath(models.Model):
    app_id = models.IntegerField(default=0)
    name = models.CharField(max_length=50, default='')
    path = models.CharField(max_length=255, default='')
    temp = models.CharField(max_length=255, default='')
    sub = models.CharField(max_length=50, default='')
    active = models.IntegerField(default=1)

    @property
    def app(self):
        try:
            app = App.objects.get(pk=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    class Meta:
        db_table = 'deploy_path'
        unique_together = (('app_id', 'name'),)


class HudsonJob(models.Model):
    JOB_TYPE = (
        (0, 'Common'),
        (1, 'Staging'),
        (2, 'Production'),
    )
    app_id = models.IntegerField(default=0)
    jobtype = models.IntegerField(default=0, choices=JOB_TYPE)
    name = models.CharField(max_length=100, default='')
    url = models.CharField(max_length=200, default='')
    token = models.CharField(max_length=100, default='')

    @property
    def app(self):
        try:
            app = App.objects.get(pk=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    class Meta:
        db_table = 'hudson_job'
        unique_together = (('app_id', 'jobtype'),)


class DeployMain(models.Model):
    STATUS = (
        (0, '初始值'),
        (1, '待发布'),
        (2, '待发布'),
        (3, '待发布'),
        (4, '发布成功'),
        (5, '已回滚'),
        (6, '阶段N已发布'),
        (7, '已作废'),
        (8, '待回滚'),
        (9, '发布中'),
        (10, '发布暂停'),
        (11, '回滚中'),
        (12, '回滚暂停'),
    )
    DEPLOY_TYPE = (
        # (0, 'Ftp2Stag'),
        (1, 'Stag2Product'),
        (2, 'Ftp2Product')
    )
    PACK_TYPE = (
        (0, 'webapps'),
        # (1, 'Hotfix'),
        # (2, '整包Hotfix'),
        (3, 'static'),
        # (4, 'hadoop'),
    )
    BOOLEAN = (
        (0, '否'),
        (1, '是')
    )
    GRAY_ROLL_TYPE = (
        (0, '自动判断回滚'),
        (1, '人工判断回滚')
    )
    SIGNAL = (
        (0, '继续'),
        (1, '暂停')
    )
    depid = models.CharField(max_length=30, default='', blank=True)
    uid = models.IntegerField(default=0)
    app_id = models.IntegerField(default=0)
    status = models.IntegerField(default=0, choices=STATUS)
    gray_status = models.IntegerField(default=0)
    deptype = models.IntegerField(default=0, choices=DEPLOY_TYPE)
    packtype = models.IntegerField(default=0, choices=PACK_TYPE)
    deploypathid = models.IntegerField(default=0)
    ftpath = models.CharField(max_length=255, default='', blank=True)
    codepath = models.CharField(max_length=255, default='')
    deprepath = models.CharField(max_length=255, default='')
    backup = models.CharField(max_length=255, default='')
    path = models.CharField(max_length=255, default='')
    path_src = models.CharField(max_length=255, default='')
    version = models.CharField(max_length=255, default='')
    srcs = models.CharField(max_length=255, default='')
    dets = models.TextField(default='')
    deploy_hosts = models.CharField(max_length=255, default='')
    restart = models.IntegerField(default=0, choices=BOOLEAN)
    comment = models.TextField(default='', blank=True)
    jiraid = models.CharField(max_length=30, default='', blank=True)
    create_time = models.IntegerField(default=0)
    last_modified = models.IntegerField(default=0)
    valid = models.IntegerField(default=0)
    is_gray_release = models.IntegerField(default=0)
    rela_pool = models.CharField(max_length=255, default='')
    publishdatetimefrom = models.IntegerField(default=0)
    publishdatetimeto = models.IntegerField(default=0)
    is_auto_published = models.IntegerField(default=0)
    gray_offset_start = models.CharField(max_length=255, default='')
    gray_release_info = models.CharField(max_length=255, default='')
    idc = models.CharField(max_length=255, default='')
    ycc_codes = models.CharField(max_length=255, default='')
    publishtimetype = models.IntegerField(default=0)
    gray_stage_interval = models.IntegerField(default=0)
    colony_surplus = models.IntegerField(default=0)
    recover_time = models.IntegerField(default=0)
    gray_rollback_type = models.IntegerField(choices=GRAY_ROLL_TYPE)
    last_ftpath = models.CharField(max_length=255, default='', blank=True)
    in_progress = models.BooleanField(default=False)
    restart_interval = models.IntegerField(default=15)
    signal = models.SmallIntegerField(default=0, choices=SIGNAL)

    @property
    def user(self):
        try:
            user = User.objects.get(pk=self.uid)
        except User.DoesNotExist:
            user = None
        return user

    @property
    def app(self):
        try:
            app = App.objects.get(id=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    @property
    def deploypath1(self):
        try:
            path = DeployPath.objects.get(id=self.deploypathid)
        except DeployPath.DoesNotExist:
            path = None
        return path

    @property
    def deptype_name(self):
        return self.get_deptype_display()

    @property
    def packtype_name(self):
        return self.get_packtype_display()

    @property
    def status_name(self):
        return self.get_status_display() if self.status != 6 else '阶段%s已完成' % self.gray_status

    @property
    def gray_rollback_type_name(self):
        return self.get_gray_rollback_type_display() if self.is_gray_release == 1 else ''

    @property
    def pre_deploy_progress(self):
        deploy_detail_queryset = DeployDetailV2.objects.filter(depid=self.depid, is_source=0)
        return int(len(deploy_detail_queryset.filter(has_pre=1))*100.0/len(deploy_detail_queryset)) if deploy_detail_queryset.count() else 0

    @property
    def deploy_progress(self):
        deploy_detail_queryset = DeployDetailV2.objects.filter(depid=self.depid, is_source=0)
        return int(len(deploy_detail_queryset.filter(has_real=1))*100.0/len(deploy_detail_queryset)) if deploy_detail_queryset.count() else 0

    @property
    def rollback_progress(self):
        deploy_detail_queryset = DeployDetailV2.objects.filter(depid=self.depid, is_source=0, has_real=1)
        return int(len(deploy_detail_queryset.filter(has_rollback=1))*100.0/len(deploy_detail_queryset)) if deploy_detail_queryset.count() else 0

    class Meta:
        db_table = 'deploy_main'


class DeployDetail(models.Model):
    depid = models.CharField(max_length=30, default='')
    host = models.CharField(max_length=30, default='')
    deploy_host = models.CharField(max_length=30, default='')
    is_source = models.IntegerField(default=0)
    has_pre = models.IntegerField(default=0)
    has_backup = models.IntegerField(default=0)
    has_real = models.IntegerField(default=0)
    has_rollback = models.IntegerField(default=0)
    backup_time = models.IntegerField(default=0)
    pre_time = models.IntegerField(default=0)
    real_time = models.IntegerField(default=0)
    rollback_time = models.IntegerField(default=0)
    has_error = models.IntegerField(default=0)
    error_msg = models.TextField(default='')
    complete = models.IntegerField(default=0)
    gray_stage = models.PositiveSmallIntegerField(default=0)

    @property
    def room(self):
        try:
            server = Server.objects.exclude(server_status_id=400).get(ip=self.host)
            asset = server.asset if server.server_type_id == 1 else server.parent_asset
            return asset.rack.room
        except Server.DoesNotExist:
            return None
        except Server.MultipleObjectsReturned:
            return None

    class Meta:
        db_table = 'deploy_detail'


class DeployMainConfig(models.Model):
    STATUS = (
        (0, '初始值'),
        (1, '待发布'),
        (2, '发布成功'),
        (3, '已回滚'),
        (4, '发布异常'),
        (5, '回滚异常'),
        (6, '无待发配置'),
        (7, '已作废'),
    )
    IDC = (
        (0, '未知'),
        (1, '南汇'),
        (2, '北京'),
        (3, '金桥'),
    )
    GRAY_ROLL_TYPE = (
        (0, '自动判断回滚'),
        (1, '人工判断回滚')
    )
    depid = models.CharField(max_length=30, default='', blank=True)
    uid = models.IntegerField(default=0)
    app_id = models.IntegerField(default=0)
    status = models.IntegerField(default=0, choices=STATUS)
    version = models.CharField(max_length=255, default='')
    comment = models.TextField(default='', blank=True)
    jiraid = models.CharField(max_length=30, default='', blank=True)
    create_time = models.IntegerField(default=0)
    last_modified = models.IntegerField(default=0)
    idc = models.IntegerField(default=0, choices=IDC)
    is_auto_published = models.IntegerField(default=0)
    publishdatetimefrom = models.IntegerField(default=0)
    publishdatetimeto = models.IntegerField(default=0)
    restart = models.IntegerField(default=0)
    publishtimetype = models.IntegerField(default=0)
    restart_interval = models.IntegerField(default=0)
    gray_release_info = models.CharField(max_length=255, null=True)
    gray_stage_interval = models.IntegerField(null=True)
    colony_surplus = models.IntegerField(null=True)
    recover_time = models.IntegerField(null=True)
    gray_rollback_type = models.SmallIntegerField(choices=GRAY_ROLL_TYPE, null=True)
    in_progress = models.BooleanField(default=False)
    zone = models.ForeignKey(Room, null=True, db_column='zone')

    @property
    def user(self):
        try:
            user = User.objects.get(pk=self.uid)
        except User.DoesNotExist:
            user = None
        return user

    # @property
    # def area(self):
    #     try:
    #         item = Area.objects.get(pk=self.idc)
    #     except Area.DoesNotExist:
    #         item = None
    #     return item

    @property
    def app(self):
        try:
            app = App.objects.get(id=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    @property
    def status_name(self):
        return self.get_status_display()

    @property
    def idc_name(self):

        if self.idc == 0 and self.zone is None:
            return self.get_idc_display()

        try:
            return self.get_idc_display() if self.idc else Room.objects.get(id=self.zone_id).name_ch
        except Room.DoesNotExist:
            return self.get_idc_display()

    @property
    def deploy_progress(self):
        if DeployMain.objects.filter(jiraid=self.jiraid, app_id=self.app_id, packtype=0).exists():
            return 100 if self.status in [2, 3, 5] else 0
        deploy_detail_queryset = DeployDetailConfig.objects.filter(depid=self.depid)
        return int(len(deploy_detail_queryset.filter(real_time__isnull=False))*100.0/len(deploy_detail_queryset)) if deploy_detail_queryset.count() else 0

    @property
    def rollback_progress(self):
        if DeployMain.objects.filter(jiraid=self.jiraid, app_id=self.app_id, packtype=0).exists():
            return 100 if self.status == 3 else 0
        deploy_detail_queryset = DeployDetailConfig.objects.filter(depid=self.depid, real_time__isnull=False)
        return int(len(deploy_detail_queryset.filter(rollback_time__isnull=False))*100.0/len(deploy_detail_queryset)) if deploy_detail_queryset.count() else 0

    class Meta:
        db_table = 'deploy_main_config'


class DeployGrayData(models.Model):
    id = models.AutoField(primary_key=True)
    depid = models.CharField(max_length=90, blank=True)
    corder = models.IntegerField()
    percent = models.CharField(max_length=30, blank=True)
    hosts = models.TextField()
    class Meta:
        db_table = u'deploy_gray_data'


class DeployIDC(models.Model):
    name = models.CharField(max_length=50, default='')
    host = models.CharField(max_length=100, default='')
    comment = models.CharField(max_length=255, default='')

    class Meta:
        db_table = 'deploy_idc'


class DeployVersionApp(models.Model):
    APP_ENV = (
        (0, 'unknown'),
        (1, 'stagging'),
        (2, 'production')
    )
    id = models.AutoField(primary_key=True)
    app = models.ForeignKey(App)
    app_env_id = models.SmallIntegerField(choices=APP_ENV)
    ftp_path = models.CharField(max_length=500)
    pack_type = models.SmallIntegerField()
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)

    @property
    def app_version(self):
        return os.path.basename(self.ftpath)

    @property
    def app_env_name(self):
        return self.get_app_env_id_display()

    class Meta:
        db_table = 'deploy_version_app'


class DeployIDC(models.Model):
    name = models.CharField(max_length=50, default='')
    host = models.CharField(max_length=100, default='')
    comment = models.CharField(max_length=255, default='')

    class Meta:
        db_table = 'deploy_idc'


class DeployRollbackReason(models.Model):
    CATEGORY = (
        (0, 'Domain自身问题'),
        (1, '发布系统问题'),
        (2, '其他')
    )
    id = models.AutoField(primary_key=True)
    uid = models.ForeignKey(AuthUser, db_column="uid")
    depid = models.CharField(max_length=90, blank=True)
    verifier = models.CharField(max_length=150, blank=True)
    reason = models.CharField(max_length=765, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    category = models.SmallIntegerField(choices=CATEGORY)

    class Meta:
        db_table = u'deploy_rollback_reason'


class DeployDetailConfig(models.Model):
    depid = models.CharField(max_length=30, default='')
    server = models.ForeignKey(Server)
    real_time = models.DateTimeField(null=True)
    rollback_time = models.DateTimeField(null=True)
    gray_stage = models.SmallIntegerField(null=True)

    @property
    def room(self):
        try:
            asset = self.server.asset if self.server.server_type_id == 1 else self.server.parent_asset
            return asset.rack.room
        except Server.DoesNotExist:
            return None
        except Server.MultipleObjectsReturned:
            return None

    class Meta:
        db_table = 'deploy_detail_config'


class DeployReboot(models.Model):
    reboot_time = models.IntegerField()
    data = models.TextField()
    is_auto_published = models.BooleanField(default=False)

    class Meta:
        db_table = 'deploy_reboot'


class DeployProcessPattern(models.Model):
    app = models.OneToOneField(App, parent_link=True, null=False)
    pattern = models.CharField(max_length=50, null=False, blank=False)

    class Meta:
        db_table = u'deploy_process_pattern'


class DeployTicketCelery(models.Model):
    ticket_id = models.CharField(max_length=32, null=False, blank=False, unique=True)
    celery_task_id = models.CharField(max_length=36, null=False, blank=False)
    percent = models.FloatField(default=0)

    class Meta:
        db_table = u'deploy_ticket_celery'


class DeployCenterMenu(models.Model):
    TYPE = (
        (0, 'internal'),
        (1, 'external')
    )
    name = models.CharField(max_length=100, null=False, blank=False)
    url = models.CharField(max_length=200, null=True, blank=True)
    type = models.SmallIntegerField(default=0, choices=TYPE)
    parent = models.ForeignKey('self', null=True, blank=True)

    class Meta:
        db_table = u'deploy_center_menu'

    def __unicode__(self):
        menu_list = [self.name]
        parent = self.parent
        while True:
            if not parent:
                break
            else:
                menu_list.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(menu_list)


class DeployJenkinsJob(models.Model):
    app = models.ForeignKey(App)
    url = models.URLField(max_length=500, null=False, blank=False)
    updated = models.DateTimeField(auto_now=True, auto_now_add=True)
    owner = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = u'deploy_jenkins_job'


class CheckUrl(models.Model):
    id = models.IntegerField(primary_key=True)
    site_id = models.IntegerField()
    pool_id = models.IntegerField()
    warning = models.TextField(blank=True)
    description = models.CharField(max_length=255)
    status = models.IntegerField()
    send_type = models.IntegerField()
    email = models.TextField(blank=True)
    cell_phone = models.TextField(blank=True)
    url = models.CharField(max_length=255)
    check_type = models.IntegerField()
    check_times = models.IntegerField()
    check_content = models.TextField(blank=True)
    user_name = models.CharField(max_length=30)
    create_time = models.IntegerField()
    port = models.IntegerField()
    interval_time = models.IntegerField()
    last_time = models.IntegerField()
    warning_interval = models.IntegerField()
    special_ip = models.TextField(blank=True)
    is_check_staging = models.IntegerField()
    is_deploy = models.IntegerField()
    level = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'check_url'


class NeednotCheck(models.Model):
    site_id = models.IntegerField(primary_key=True)
    pool_id = models.IntegerField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'neednot_check'


class DisableIp(models.Model):
    ip = models.BigIntegerField(primary_key=True)
    create_time = models.IntegerField()
    expiration_time = models.IntegerField()
    level = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'disable_ip'


class Server4Deploy(models.Model):
    id = models.AutoField(primary_key=True)
    ip = models.CharField(max_length=100, blank=True)
    app = models.ForeignKey(App)
    server_type = models.ForeignKey(ServerType)
    server_status = models.ForeignKey(ServerStatus)
    server_env = models.ForeignKey(ServerEnv)
    rack = models.ForeignKey(Rack)

    class Meta:
        managed = False
        db_table = 'server'


class DeployDetailV2(models.Model):
    depid = models.CharField(max_length=30, default='')
    host = models.CharField(max_length=30, default='')
    deploy_host = models.CharField(max_length=30, default='')
    is_source = models.IntegerField(default=0)
    has_pre = models.IntegerField(default=0)
    has_backup = models.IntegerField(default=0)
    has_real = models.IntegerField(default=0)
    has_rollback = models.IntegerField(default=0)
    backup_time = models.IntegerField(default=0)
    pre_time = models.IntegerField(default=0)
    real_time = models.IntegerField(default=0)
    rollback_time = models.IntegerField(default=0)
    has_error = models.IntegerField(default=0)
    error_msg = models.TextField(default='')
    complete = models.IntegerField(default=0)
    server = models.ForeignKey(Server4Deploy, null=True)
    gray_stage = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'deploy_detail'


class TNewPool(models.Model):
    uniq_id = models.CharField(max_length=32, default='')
    activity_id = models.IntegerField(default=0)
    ticket_type_id = models.IntegerField(default=0)
    pool_id = models.IntegerField(default=0)
    env_id = models.IntegerField(default=0)
    idc_id = models.IntegerField(default=0)
    num = models.IntegerField(default=0)
    ip = models.TextField()
    reason = models.TextField()
    status = models.IntegerField(max_length=11, default=0)
    create_time = models.IntegerField(max_length=11, default=0)
    _database = 'db_ticket'

    class Meta:
        db_table = 't_new_pool'


class TDockerIp(models.Model):
    uniq_id = models.CharField(max_length=32, default='')
    ip = models.CharField(max_length=100, default='')
    start_status = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    log_time = models.IntegerField(default=0)
    _database = 'db_ticket'

    class Meta:
        db_table = 't_docker_ip'
