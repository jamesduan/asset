from django.db import models
from asset.models import Asset, Rack, Room
from cmdb.models import Site, App
from django.conf import settings


class ServerGroup(models.Model):
    id = models.AutoField(primary_key=True)
    app_id = models.IntegerField()
    room = models.ForeignKey(Room, db_column='room_id')
    cname = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'server_group'


class ServerAppTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    cname = models.CharField(max_length=100)
    show_name = models.CharField(max_length=100)
    type = models.IntegerField()
    status = models.IntegerField(default=0, blank=True)

    class Meta:
        managed = False
        db_table = 'server_app_template'


class ServerOsTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    cname = models.CharField(max_length=100)
    show_name = models.CharField(max_length=100)
    type = models.IntegerField()
    status = models.IntegerField(default=0, blank=True)

    class Meta:
        managed = False
        db_table = 'server_os_template'


class Server(models.Model):
    id = models.AutoField(primary_key=True)
    assetid = models.CharField(max_length=100, blank=True)
    sn = models.CharField(max_length=50, blank=True)
    mac = models.CharField(max_length=50, blank=True)
    ip = models.CharField(max_length=100, blank=True)
    app_id = models.IntegerField(blank=True, default=0)
    tag_id = models.IntegerField(blank=True, default=0)
    mgmt_ip = models.CharField(max_length=100, blank=True)
    hostname = models.CharField(max_length=100, blank=True)
    fqdn = models.CharField(max_length=100)
    server_type_id = models.IntegerField(blank=True, default=1)
    server_class_id = models.IntegerField(blank=True, default=0)
    server_status_id = models.IntegerField(blank=True, default=30)
    server_env_id = models.IntegerField(blank=True, default=2)
    parent = models.CharField(max_length=100, blank=True)
    comment = models.CharField(max_length=255, blank=True)
    template_id = models.CharField(max_length=50, blank=True)
    os_template = models.CharField(max_length=50, blank=True)
    app_template = models.CharField(max_length=50, blank=True)
    server_os_template_id = models.IntegerField(blank=True, default=0)
    server_app_template_id = models.IntegerField(blank=True, default=0)
    bond_mode = models.CharField(max_length=50, blank=True)
    raid_change = models.CharField(max_length=50, blank=True)
    created_time = models.IntegerField(blank=True)
    server_owner = models.IntegerField(blank=True, default=0)
    online_time = models.IntegerField(blank=True, default=0)
    parent_ip = models.CharField(max_length=20, blank=True)
    rack_id = models.IntegerField(blank=True, default=0)
    task_id = models.CharField(max_length=36, null=True, blank=True)
    ycc_zone = models.ForeignKey(Room, null=True)

    @property
    def app(self):
        try:
            app = App.objects.get(id=self.app_id)
        except App.DoesNotExist:
            app = None
        return app

    @property
    def site(self):
        if self.app is not None:
            try:
                site = Site.objects.get(id=self.app.site_id)
            except Site.DoesNotExist:
                site = None
        else:
            site = None
        return site

    @property
    def server_type(self):
        try:
            server_type = ServerType.objects.get(id=self.server_type_id)
        except ServerType.DoesNotExist:
            server_type = None
        return server_type

    @property
    def server_status(self):
        try:
            server_status = ServerStatus.objects.get(id=self.server_status_id)
        except ServerStatus.DoesNotExist:
            server_status = None
        return server_status

    @property
    def server_env(self):
        try:
            server_env = ServerEnv.objects.get(id=self.server_env_id)
        except ServerEnv.DoesNotExist:
            server_env = None
        return server_env

    @property
    def server_os_template(self):
        try:
            server_os_template = ServerOsTemplate.objects.get(id=self.server_os_template_id)
        except ServerOsTemplate.DoesNotExist:
            server_os_template = None
        return server_os_template

    @property
    def server_app_template(self):
        try:
            server_app_template = ServerAppTemplate.objects.get(id=self.server_app_template_id)
        except ServerAppTemplate.DoesNotExist:
            server_app_template = None
        return server_app_template

    @property
    def asset(self):
        if self.parent == "":
            try:
                asset = Asset.objects.get(assetid=self.assetid)
            except Asset.DoesNotExist:
                asset = None
        else:
            try:
                asset = Asset.objects.get(assetid=self.parent)
            except Asset.DoesNotExist:
                asset = None
        return asset

    @property
    def parent_asset(self):
        try:
            asset = Asset.objects.get(assetid=self.parent)
        except Asset.DoesNotExist:
            asset = None
        return asset

    @property
    def server_detail(self):
        detail = ServerDetail.objects.filter(server_id=self.id)
        if detail:
            detail = detail[0]
        else:
            detail = None
        return detail

    @property
    def vm_count(self):
        if self.app_id in settings.VM_HOST_APP_ID_LIST:
            return Server.objects.exclude(server_status_id=400).filter(server_type_id=0, parent=self.assetid).count()
        return None

    @property
    def parent_server_obj(self):
        if self.server_type_id == 1:
            return None
        return Server.objects.exclude(server_status_id=400).filter(assetid=self.parent).first()

    @property
    def ycc_idc(self):
        if self.ycc_zone is None:
            return None
        elif self.ycc_zone.parent is None:
            return self.ycc_zone.architecture_name
        else:
            return self.ycc_zone.parent.architecture_name

    class Meta:
        managed = False
        db_table = 'server'


class ServerType(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=30, default='')
    comment = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'server_type'

    def __unicode__(self):
        return self.name


class ServerStatus(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=30, default='')
    comment = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'server_status'

    def __unicode__(self):
        return self.name


class ServerEnv(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=30, default='')
    comment = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'server_env'

    def __unicode__(self):
        return self.name


class ResourcesVm(models.Model):
    id = models.AutoField(primary_key=True)
    host_ip = models.CharField(max_length=150)
    hardware_id = models.IntegerField(null=True, blank=True, default=0)
    available_num = models.IntegerField(null=True, blank=True, default=5)
    used_num = models.IntegerField(null=True, blank=True, default=0)
    script_num = models.IntegerField(null=True, blank=True, default=0)
    total_num = models.IntegerField(null=True, blank=True, default=5)
    status = models.IntegerField(null=True, blank=True, default=1)
    created = models.IntegerField(null=True, blank=True)
    updated = models.IntegerField(null=True, blank=True)
    script_updated = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = u'resources_vm'


class ServerStandard(models.Model):
    id = models.AutoField(primary_key=True)
    assetid = models.CharField(max_length=100, blank=True)
    sn = models.CharField(max_length=50, blank=True)
    ip = models.CharField(max_length=100, blank=True)
    app = models.ForeignKey(App, db_column='app_id', blank=True, default=0)
    mgmt_ip = models.CharField(max_length=100, blank=True)
    hostname = models.CharField(max_length=100, blank=True)
    server_type = models.ForeignKey(ServerType, db_column='server_type_id', blank=True, default=1)
    server_status = models.ForeignKey(ServerStatus, db_column='server_status_id', blank=True, default=30)
    server_env = models.ForeignKey(ServerEnv, db_column='server_env_id', blank=True, default=2)
    parent = models.CharField(max_length=100, blank=True)
    parent_ip = models.CharField(max_length=20, blank=True)
    comment = models.CharField(max_length=255, blank=True)
    template_id = models.CharField(max_length=50, blank=True)
    server_os_template = models.ForeignKey(ServerOsTemplate, db_column='server_os_template_id', blank=True, default=0)
    server_app_template = models.ForeignKey(ServerAppTemplate, db_column='server_app_template_id', blank=True, default=0)
    bond_mode = models.CharField(max_length=50, blank=True)
    raid_change = models.CharField(max_length=50, blank=True)
    created_time = models.IntegerField(blank=True)
    server_owner = models.IntegerField(blank=True, default=0)
    online_time = models.IntegerField(blank=True, default=0)
    rack = models.ForeignKey(Rack, blank=True, default=0, db_column='rack_id')
    groups = models.ManyToManyField(ServerGroup, db_table='server_group_bind')
    task_id = models.CharField(max_length=36, null=True, blank=True)
    ycc_zone = models.ForeignKey(Room, null=True)

    @property
    def parent_server_obj(self):
        if self.server_type_id == 1:
            return None
        return ServerStandard.objects.exclude(server_status_id=400).filter(assetid=self.parent).first()

    class Meta:
        managed = False
        db_table = 'server'


class ServerDetail(models.Model):
    id = models.IntegerField(primary_key=True,verbose_name="ID")
    server_id = models.IntegerField(verbose_name="server_id")
    architecture = models.CharField(max_length=20L, blank=True)
    boardmanufacturer = models.CharField(max_length=50L, blank=True)
    boardserialnumber = models.CharField(max_length=50L, blank=True)
    facterversion = models.CharField(max_length=50L, blank=True)
    fqdn = models.CharField(max_length=100L, blank=True)
    hardwareisa = models.CharField(max_length=50L, blank=True)
    hostname = models.CharField(max_length=50L, blank=True)
    ipaddress = models.CharField(max_length=50L, blank=True)
    nicinfo = models.TextField(blank=True)
    is_virtual = models.CharField(max_length=10L, blank=True)
    kernelrelease = models.CharField(max_length=50L, blank=True)
    kernelversion = models.CharField(max_length=50L, blank=True)
    fact_date = models.DateTimeField(null=True, blank=True)
    lsbdistdescription = models.CharField(max_length=255L, blank=True)
    lsbmajdistrelease = models.CharField(max_length=10L, blank=True)
    lsbdistid = models.CharField(max_length=50L, blank=True)
    lsbdistrelease = models.CharField(max_length=50L, blank=True)
    manufacturer = models.CharField(max_length=50L, blank=True)
    memorysize = models.CharField(max_length=50L, blank=True)
    operatingsystem = models.CharField(max_length=50L, blank=True)
    physicalprocessorcount = models.CharField(max_length=50L, blank=True)
    processorcount = models.CharField(max_length=50L, blank=True)
    processorinfo = models.TextField(blank=True)
    productname = models.CharField(max_length=100L, blank=True)
    puppetversion = models.CharField(max_length=50L, blank=True)
    rubyversion = models.CharField(max_length=50L, blank=True)
    serialnumber = models.CharField(max_length=50L, blank=True)
    swapsize = models.CharField(max_length=50L, blank=True)
    timezone = models.CharField(max_length=50L, blank=True)
    uptime = models.CharField(max_length=50L, blank=True)
    created = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(null=True, blank=True)
    macaddress = models.CharField(max_length=50L, blank=True)
    netmask = models.CharField(max_length=50L, blank=True)
    pythonversion = models.CharField(max_length=50L, blank=True)

    class Meta:
        db_table = 'server_detail'

class LogMain(models.Model):
    id = models.AutoField(primary_key=True)
    is_error = models.IntegerField()
    happen_time = models.DateTimeField(blank=True)
    type = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=150, blank=True)
    index = models.CharField(max_length=300, blank=True)
    content = models.TextField(blank=True)
    created = models.DateTimeField(blank=True)
    class Meta:
        db_table = u'log_main'

# class LBGroup(models.Model):
#     app = models.ForeignKey(App)
#     name = models.CharField(max_length=100L)
#     members = models.ManyToManyField(ServerStandard, through='Membership')
#
#     class Meta:
#         unique_together = (('app', 'name'),)
#
#
# class Membership(models.Model):
#     server = models.ForeignKey(ServerStandard)
#     lb_group = models.ForeignKey(LBGroup)
#     port = models.PositiveSmallIntegerField(default=8080)

class ExceptionBusinessZone(models.Model):
    business_zone=models.CharField(max_length=30,null=True)
    server=models.ForeignKey(Server,db_column="server_id")

    class Meta:
        db_table = 'exception_business_zone'
