# -*- coding: utf-8 -*-
from django.db import models
from asset.models import Room
from server.models import Server, ServerStandard, ServerEnv
from cmdb.models import App,Site,DdDomain
from django.conf import settings
import re
from cmdb.models import AppV2


# Create your models here.
class ConfigGroup(models.Model):
    TYPE = (
        (1, '应用类'),
        (2, '公共组件类'),
    )
    id = models.AutoField(primary_key=True)
    site_id = models.IntegerField(default=0)
    site_name = models.CharField(max_length=50, blank=True)
    app_id = models.IntegerField(default=0)
    app_name = models.CharField(max_length=100, blank=True)
    group_id = models.CharField(max_length=100, blank=True)
    type = models.IntegerField(choices=TYPE)
    old_pool = models.CharField(max_length=100, blank=True)
    idc = models.ForeignKey(Room, db_column='idc')
    created = models.IntegerField(blank=True)
    updated = models.IntegerField(blank=True)
    status = models.IntegerField(default=1)

    @property
    def group_status(self):
        return ConfigGroupStatus.objects.get(group_id=self.id, status=0)

    @property
    def published_group_status(self):
        return ConfigGroupStatus.objects.get(group_id=self.id, status=4)

    @property
    def all_status(self):
        return ConfigGroupStatus.objects.filter(group_id=self.id).values("status").distinct()

    @property
    def app_status(self):
        if self.app_id == 0:
            return 0
        app = App.objects.filter(id=self.app_id).first()
        if app:
            return app.status if settings.YCC_ENV == 'production' else app.test_status
        else:
            return 1

    @property
    def to_be_committed(self):
        def md5_list(status):
            return [config_info_obj.content_md5 for config_info_obj in
                    ConfigInfo.objects.filter(group_status__group__id=self.id, env=7, group_status__status=status)]
        edit_md5_list = md5_list(0)
        edit_md5_list.sort()
        published_md5_list = md5_list(4)
        published_md5_list.sort()
        return edit_md5_list != published_md5_list

    class Meta:
        managed = False
        db_table = 'configgroup'


class ConfigEnv(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'config_env'

    def __unicode__(self):
        return self.name


class ConfigGroupStatus(models.Model):
    STATUS = (
        # (0, 'edit'),
        # (1, 'commited'),
        # (2, 'approved'),
        # (3, 'rejected'),
        # (4, 'published'),
        # (5, 'history'),
        # (6, 'rollback'),
        # (7, 'rmvpublish'),
        # (8, 'rmvaudit'),
        (0, '编辑'),
        (1, '已提交'),
        (2, '已审核'),
        (3, '已拒绝'),
        (4, '已发布'),
        (5, '历史发布'),
        (6, '已回滚'),
        (7, '待发布作废'),
        (8, '待审核作废'),
    )

    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(ConfigGroup)
    remark = models.CharField(max_length=100, blank=True)
    version = models.IntegerField()
    status = models.IntegerField(choices=STATUS)
    pre_version = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'configgroupstatus'

    def __unicode__(self):
        return self.group.group_id


class ConfigInfo(models.Model):
    id = models.AutoField(primary_key=True)
    data_id = models.CharField(max_length=255)
    group_status = models.ForeignKey(ConfigGroupStatus, db_column='group_status_id')
    env = models.ForeignKey(ConfigEnv, db_column='env_id')
    content = models.TextField(blank=True)
    content_md5 = models.CharField(max_length=32)
    created_time = models.IntegerField(blank=True)
    modified_time = models.IntegerField(blank=True)
    created_by = models.CharField(max_length=100, blank=True)
    modified_by = models.CharField(max_length=100, blank=True)
    remark = models.CharField(max_length=100, blank=True)
    file_type = models.CharField(max_length=20, blank=True)
    cmp = models.IntegerField(blank=True)
    config_type = models.IntegerField()

    @property
    def db_info(self):
        try:
            db_info = ConfigDbConfiginfo.objects.get(config_info_id=self.id)
        except ConfigDbConfiginfo.DoesNotExist:
            db_info = None
        return db_info

    @property
    def content_nopwd(self):
        # pwdkey = 'jdbc.password.encrypt'
        # tobereplaced = re.compile(pwdkey + '[  ]*=.*\n')
        # content_nopwd = tobereplaced.sub(pwdkey + '=******\n', self.content)
        # tobereplaced = re.compile(pwdkey + '[  ]*=.*')
        # content_nopwd = tobereplaced.sub(pwdkey + '=******', content_nopwd)
        # if content_nopwd == self.content:
        #     pwdkey = 'jdbc.password'
        #     tobereplaced = re.compile(pwdkey + '[  ]*=.*\n')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******\n', content_nopwd)
        #     tobereplaced = re.compile(pwdkey + '[  ]*=.*')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******', content_nopwd)
        # if content_nopwd == self.content:
        #     pwdkey = 'password'
        #     tobereplaced = re.compile(pwdkey + '[  ]*=.*\n')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******\n', content_nopwd)
        #     tobereplaced = re.compile(pwdkey + '[  ]*=.*')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******', content_nopwd)
        # if content_nopwd == self.content:
        #     pwdkey = '[a-zA-Z0-9.-_]*password[a-zA-Z0-9.-_]'
        #     tobereplaced = re.compile('.*' + pwdkey + '.*=.*\n')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******\n', content_nopwd)
        #     tobereplaced = re.compile('.*' + pwdkey + '.*=.*')
        #     content_nopwd = tobereplaced.sub(pwdkey + '=******', content_nopwd)
        if self.config_type == 1:
            return self.content
        pwdkey = 'password'
        tmp_arr = []
        for cn in self.content.split('\n'):
            if pwdkey in cn.split('=', 1)[0]:
                tmp_arr.append('%s=%s' % (cn.split('=', 1)[0], '******'))
            else:
                tmp_arr.append(cn)
        content_nopwd = '\n'.join(tmp_arr)
        return content_nopwd

    class Meta:
        managed = False
        db_table = 'configinfo'


class ConfigInfoTmp(models.Model):
    id = models.AutoField(primary_key=True)
    configinfo_id = models.IntegerField(blank=False)
    content = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = 'configinfo_tmp'


class OldConfigInfo(models.Model):
    id = models.BigIntegerField(primary_key=True)
    data_id = models.CharField(max_length=255)
    group_id = models.CharField(max_length=255)
    content = models.TextField()
    md5 = models.CharField(max_length=32)
    gmt_create = models.DateTimeField()
    gmt_modified = models.DateTimeField()
    environment = models.CharField(max_length=20, blank=True)
    gmt_expired = models.DateTimeField(blank=True, null=True)
    group_version = models.IntegerField()
    status = models.CharField(max_length=50)
    created_by = models.CharField(max_length=100, blank=True)
    updated_by = models.CharField(max_length=100, blank=True)
    remark = models.CharField(max_length=100, blank=True)
    file_type = models.CharField(max_length=20, blank=True)
    release_type = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'config_info'


class OldConfigGroup(models.Model):
    group_id = models.CharField(primary_key=True, max_length=100)
    pool = models.CharField(max_length=100)
    remark = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, blank=True)
    # env = models.CharField(max_length=20, blank=True)
    idc = models.CharField(max_length=30, blank=True)
    pemail = models.CharField(max_length=100, blank=True)
    bemail = models.CharField(max_length=100, blank=True)
    semail = models.CharField(max_length=200, blank=True)

    class Meta:
        managed = False
        db_table = 'config_group'


class ConfigDbConfiginfo(models.Model):
    id = models.AutoField(primary_key=True)
    config_info_id = models.IntegerField()
    config_db_instance_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'config_db_configinfo'


class GrayReleaseBlackip(models.Model):
    id = models.AutoField(primary_key=True)
    ip = models.CharField( max_length=100)
    create_time = models.DateTimeField(auto_now=True, auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'gray_release_blackip'


class ConfigLog(models.Model):
    id = models.BigIntegerField(primary_key=True, max_length=20)
    log_operator = models.CharField(max_length=50)
    log_time = models.DateTimeField()
    log_type = models.CharField(max_length=50)
    log_level = models.CharField(max_length=255)
    log_detail = models.TextField()

    class Meta:
        managed = False
        db_table = 'config_log'


class ConfigHost(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    server = models.ForeignKey(Server, db_column='server_id')
    ori_pool_name = models.CharField(max_length=100)
    ori_validated_pool_name = models.CharField(max_length=100)
    pool_name = models.CharField(max_length=100)
    ori_main_group_id = models.CharField(max_length=100)
    main_group = models.ForeignKey(ConfigGroup, db_column='main_group_id')
    #main_group_id = models.IntegerField(default=0, max_length=11)
    create_time = models.IntegerField(default=0, max_length=12)

    class Meta:
        managed = False
        db_table = 'config_host'

    # @property
    # def main_group(self):
    #     try:
    #         main_group = ConfigGroup.objects.get(id = self.main_group_id)
    #     except ConfigGroup.DoesNotExist:
    #         main_group = None
    #     return main_group

class ConfigDependGroup(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    config_host = models.ForeignKey(ConfigHost, default=0, db_column='config_host_id')
    ori_depend_group_id = models.CharField(max_length=100)
    depend_group_id = models.IntegerField(default=0, max_length=11, blank=True)

    class Meta:
        managed = False
        db_table = 'config_depend_group'


class ConfigJar(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    config_jar = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'config_jar'


class ConfigJarVersion(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    config_jar_version = models.CharField(max_length=200)
    config_jar = models.ForeignKey(ConfigJar, default=0, db_column='config_jar_id')
    create_time = models.IntegerField(default=0, max_length=12)

    class Meta:
        managed = False
        db_table = 'config_jar_version'


class ConfigHostJarVersion(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    config_host = models.ForeignKey(ConfigHost, default=0, db_column='config_host_id')
    config_jar_version = models.ForeignKey(ConfigJarVersion, default=0, db_column='config_jar_version_id')
    create_time = models.IntegerField(default=0, max_length=12)

    class Meta:
        managed = False
        db_table = 'config_host_jar_version'


class ConfigSubscribeLog(models.Model):
    id = models.AutoField(primary_key=True)
    server = models.ForeignKey(Server, db_column='server_id', default=None)
    ip = models.CharField(max_length=30)
    group_id = models.CharField(max_length=200)
    config_file = models.CharField(max_length=200)
    status_code = models.IntegerField()
    update_time = models.IntegerField()

    # @property
    # def server(self):
    #     try:
    #         server = Server.objects.get(ip=self.ip)
    #     except Server.DoesNotExist:
    #         server = None
    #     return server

    class Meta:
        managed = False
        db_table = 'config_subscribe_log'


class ConfiginfoCmp(models.Model):
    id = models.AutoField(primary_key=True)
    group_id = models.CharField(max_length=100)
    data_id = models.CharField(max_length=100)
    cmp = models.IntegerField(default=0)
    type = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'configinfocmp'


class ConfigType(models.Model):
    id = models.IntegerField(primary_key=True)
    type_name = models.CharField(max_length=45)

    class Meta:
        managed = False
        db_table = 'configtype'


class ConfigInfoV3(models.Model):
    id = models.AutoField(primary_key=True)
    data_id = models.CharField(max_length=255)
    group_status = models.ForeignKey(ConfigGroupStatus, db_column='group_status_id')
    env = models.ForeignKey(ConfigEnv, db_column='env_id')
    content = models.TextField(blank=True)
    content_md5 = models.CharField(max_length=32)
    created_time = models.IntegerField(blank=True)
    modified_time = models.IntegerField(blank=True)
    created_by = models.CharField(max_length=100, blank=True)
    modified_by = models.CharField(max_length=100, blank=True)
    remark = models.CharField(max_length=100, blank=True)
    file_type = models.CharField(max_length=20, blank=True)
    cmp = models.IntegerField(blank=True)
    config_type = models.IntegerField(ConfigType, db_column='config_type')

    @property
    def is_cmp(self):
        configinfo_cmp = ConfiginfoCmp.objects.get(group_id=self.group_status.group.group_id, data_id=self.data_id)
        return configinfo_cmp.cmp

    @property
    def is_cmp_type(self):
        configomfp_cmp = ConfiginfoCmp.objects.get(group_id=self.group_status.group.group_id, data_id=self.data_id)
        return configomfp_cmp.type

    @property
    def config_type_name(self):
        config_type = ConfigType.objects.get(id=self.config_type)
        return config_type.type_name

    @property
    def db_info(self):
        try:
            db_info = ConfigDbConfiginfo.objects.get(config_info_id=self.id)
        except ConfigDbConfiginfo.DoesNotExist:
            db_info = None
        return db_info

    @property
    def content_nopwd(self):
        if self.config_type == 1:
            return self.content
        pwdkey = 'password'
        tmp_arr = []
        for cn in self.content.split('\n'):
            if pwdkey in cn.split('=', 1)[0]:
                tmp_arr.append('%s=%s' % (cn.split('=', 1)[0], '******'))
            else:
                tmp_arr.append(cn)
        content_nopwd = '\n'.join(tmp_arr)
        return content_nopwd

    @property
    def is_group_status(self):
        configinfo = ConfigInfo.objects.filter(group_status__group__group_id=self.group_status.group.group_id,
                                               group_status__group__status=1, group_status__status__in=[1, 2])
        if configinfo.exists():
            return True
        else:
            return False

    class Meta:
        managed = False
        db_table = 'configinfo'


class RandomGetProbeRsp(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    #ip = models.CharField(max_length=30)
    server = models.ForeignKey(Server, db_column='server_id', default=None)
    group_id = models.CharField(max_length=200)
    data_id = models.CharField(max_length=200)
    create_time = models.DateTimeField(auto_now=True,auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'random_getprobersp'


class ConfigPostInfo(models.Model):
    id = models.AutoField(primary_key=True, max_length=11)
    server = models.ForeignKey(Server, db_column='server_id', default=None)
    group_id = models.CharField(max_length=200)
    data_id = models.CharField(max_length=200)
    create_time = models.DateTimeField(auto_now=True, auto_now_add=True)
    update_time = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'config_post_info'


class ConfigPostInfoV2(models.Model):
    ip = models.CharField(max_length=15)
    group_id = models.CharField(max_length=200)
    data_id = models.CharField(max_length=200)
    update_time = models.DateTimeField(auto_now=True, auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'config_post_info_v2'


class RoomApps(models.Model):
    room=models.ForeignKey(Room,db_column='room_id')
    app=models.ForeignKey(AppV2,db_column='app_id')

    class Meta:
        managed = True
        db_table='room_apps'


class SoaEnv(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=45)
    name_ch = models.CharField(max_length=45)
    server_env_id = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'soa_env'


class SoaService(models.Model):
    id = models.AutoField(primary_key=True)
    app = models.ForeignKey(App, db_column='app_id')
    service_path = models.CharField(max_length=100)
    room = models.ForeignKey(Room, db_column='room_id')
    type = models.IntegerField(default=1)
    env = models.ForeignKey(SoaEnv, db_column='env_id')

    def group_servers(self):
        result_list = []
        groups = SoaServiceGroup.objects.filter(status=1, soa_service__id=self.id)
        for group in groups:
            servers = SoaServiceGroupBind.objects.filter(soa_service_group=group.id)
            servers_tmp = []
            for server in servers:
                servers_tmp.append('"%s:%s"' % (server.serverstandard.ip, server.port))
            show_tmp = '"%s": {%s}' % (group.cname, ', '.join(servers_tmp))
            result_list.append(show_tmp)
        return ' || '.join(result_list)

    def count_groups(self):
        groups = SoaServiceGroup.objects.filter(status=1, soa_service__id=self.id)
        return len(groups)

    def count_servers(self):
        result_list = []
        count_total = 0
        groups = SoaServiceGroup.objects.filter(status=1, soa_service__id=self.id)
        for group in groups:
            servers = SoaServiceGroupBind.objects.filter(soa_service_group=group.id)
            count_total += len(servers)
        return count_total

    def server_env_id(self):
        try:
            soa_env = SoaEnv.objects.get(id=self.env.id)
            return ServerEnv.objects.get(id=soa_env.server_env_id).id
        except SoaEnv.DoesNotExist:
            return 0
        except SoaEnv.MultipleObjectsReturned:
            return 0
        except ServerEnv.DoesNotExist:
            return 0
        except ServerEnv.MultipleObjectsReturned:
            return 0

    class Meta:
        managed = False
        db_table = 'soa_service'


class SoaServiceGroup(models.Model):
    id = models.AutoField(primary_key=True)
    soa_service = models.ForeignKey(SoaService, db_column='soa_service_id')
    cname = models.CharField(max_length=50)
    status = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'soa_service_group'


class SoaServiceGroupBind(models.Model):
    id = models.AutoField(primary_key=True)
    serverstandard = models.ForeignKey(ServerStandard, db_column='serverstandard_id')
    soa_service_group = models.ForeignKey(SoaServiceGroup, db_column='soa_service_group_id')
    port = models.IntegerField()
    type = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'soa_service_group_bind'


class SoaServiceGroupRegister(models.Model):
    id = models.AutoField(primary_key=True)
    serverstandard = models.ForeignKey(ServerStandard, db_column='serverstandard_id')
    soa_service = models.ForeignKey(SoaService, db_column='soa_service_id')
    port = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'soa_service_group_register'


class SoaDomain(models.Model):
    id = models.AutoField(primary_key=True)
    idc = models.ForeignKey(Room, db_column='idc_id')
    env = models.ForeignKey(SoaEnv, db_column='env_id')
    domain = models.CharField(max_length=45)
    zone_code = models.CharField(max_length=45)
    status = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'soa_domain'


class ExceptionDetailSoaBind(models.Model):
    id = models.AutoField(primary_key=True)
    type = models.IntegerField()
    zone = models.CharField(max_length=45)
    path = models.CharField(max_length=200)
    group = models.CharField(max_length=45)
    content = models.CharField(max_length=250)
    port = models.IntegerField()
    time = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'exception_detail_soa_bind'


class ExceptionConfigAccessDetail(models.Model):
    ERROR=(
        (0,'配置组无对应Pool'),
        (1,'配置组对应Pool被禁用'),
        (2,'配置组名不规范'),
        (3,'404'),
    )
    id= models.AutoField(primary_key=True)
    error=models.IntegerField(choices=ERROR)
    group_id=models.CharField(max_length=150)
    data_id=models.CharField(max_length=150)
    ip=models.CharField(max_length=60)
    site=models.ForeignKey(Site,db_column='site_id',null=True)
    app=models.ForeignKey(AppV2,db_column='app_id')
    domain=models.ForeignKey(DdDomain,db_column='domain_id',null=True)
    # domain_id=models.IntegerField()
    # exception_export =models.ForeignKey(ExceptionReport,db_column='exception_export_id')
    frequency=models.IntegerField()
    lastupdate=models.DateTimeField()
    standardgroup_id=models.CharField(max_length=150,null=True)

    @property
    def site_app_def(self):
        return  self.site.name + '/'+self.app.name

    class Meta:
        db_table = u'exception_config_access_detail'
