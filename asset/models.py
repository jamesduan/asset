# -*- coding: utf-8 -*-
from django.db import models


class AssetIp(models.Model):
    id = models.IntegerField(primary_key=True)
    assetid = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    ip = models.CharField(max_length=15)
    usage = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'asset_ip'


class AssetModel(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        managed = False
        db_table = 'asset_model'

    def __unicode__(self):
        return self.name


class AssetPort(models.Model):
    id = models.IntegerField(primary_key=True)
    assetid = models.CharField(max_length=100)
    port = models.CharField(max_length=100)
    related_id = models.IntegerField()
    cable = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'asset_port'


class AssetPre(models.Model):
    id = models.IntegerField(primary_key=True)
    assetid = models.CharField(max_length=100)
    cname = models.CharField(max_length=100, blank=True)
    asset_type_id = models.IntegerField()
    is_used = models.IntegerField()
    created = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'asset_pre'


class AssetType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    comment = models.CharField(max_length=255)
    short_name = models.CharField(max_length=30, blank=True)

    class Meta:
        managed = False
        db_table = 'asset_type'

    def __unicode__(self):
        return self.comment

class Area(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    name_cn = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'area'

    def __unicode__(self):
        return self.name


class Room(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    #area_id = models.IntegerField()
    area = models.ForeignKey(Area, blank=True, db_column='area_id')
    comment = models.CharField(max_length=255)
    points = models.CharField(max_length=100)
    ycc_code = models.CharField(max_length=100)
    zk_cluster = models.CharField(max_length=255)
    name_ch = models.CharField(max_length=20)
    status = models.IntegerField(default=1)
    haproxy_zk_cluster = models.CharField(max_length=255, null=True, blank=True)
    ycc_display = models.BooleanField(default=False)
    ycc_sync = models.IntegerField(default=0)
    parent = models.ForeignKey('self', null=True, blank=True)
    architecture_name = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'room'

    @property
    def rack_total(self):
        return Rack.objects.filter(room_id=self.id).count()

    @property
    def rack_blade_total(self):
        return Rack.objects.filter(room_id=self.id, valid=0).count()

    @property
    def rack_real_total(self):
        return Rack.objects.filter(room_id=self.id, valid=1).count()

    def __unicode__(self):
        return self.name


class Rack(models.Model):
    TYPE = (
        (0, '刀片笼子'),
        (1, '机柜'),
    )
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    height = models.IntegerField()
    valid = models.IntegerField(choices=TYPE)
    room = models.ForeignKey(Room, db_column='room_id')
    comment = models.CharField(max_length=255, blank=True)
    ctime = models.IntegerField()
    ip_min = models.IntegerField(default=0)
    ip_max = models.IntegerField(default=0)

    @property
    def real_name(self):
        if self.valid:
            return self.name
        else:
            try:
                asset = Asset.objects.get(assetid=self.name)
                return asset.rack.name
            except Exception:
                return None

    class Meta:
        managed = False
        db_table = 'rack'

    def __unicode__(self):
        return self.name


class RackSpace(models.Model):
    id = models.IntegerField(primary_key=True)
    rack_id = models.IntegerField()
    unit_no = models.IntegerField()
    assetid = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'rack_space'


class IpSegment(models.Model):
    STATUS = (
        (1, '有效'),
        (0, '无效'),
    )
    TYPE = (
        (1, '外网'),
        (2, '管理'),
        (3, '内网'),
    )
    OWNER = (
        ('1', '中国电信'),
        ('2', '中国联通'),
        ('3', 'BGP'),
        ('5', '内网'),
        ('6', '管理内网'),
    )
    IDC = (
        (1, 'DCB'),
        (3, 'DCA'),
        (4, 'DCD'),
        (8, 'DCF'),
    )
    id = models.AutoField(primary_key=True)
    ip = models.CharField(max_length=20)
    type = models.IntegerField(choices=TYPE)
    mask = models.IntegerField()
    idc = models.IntegerField(choices=IDC)
    owner = models.CharField(max_length=150, choices=OWNER)
    comment = models.CharField(max_length=765, blank=True)
    created = models.DateTimeField(editable=False)
    status = models.IntegerField(choices=STATUS, default=1)

    class Meta:
        db_table = u'ip_segment'

    @property
    def room(self):
        try:
            room = Room.objects.get(pk=self.idc)
        except Room.DoesNotExist:
            room = None
        return room


class IpTotal(models.Model):
    STATUS = (
        (1, '有效'),
        (0, '无效'),
    )
    IS_VIRTUAL = (
        (1, '虚IP'),
        (0, '实IP'),
    )
    IS_USED = (
        (1, '使用'),
        (0, '空闲'),
    )
    ASSET_TYPE = (
        (0, '暂无'),
        (1, '路由器'),
        (2, '交换机'),
        (3, '防火墙'),
        (4, 'A10'),
        (5, 'NETSCALER'),
        (6, 'HAPROXY'),
        (7, '临时设备'),
        (8, '软路由'),
        (9, 'VPN设备'),
        (10, '服务器'),
    )
    TYPE = (
        (0, '暂无'),
        (1, '外网'),
        (2, '管理'),
        (3, '内网'),
    )
    IDC = (
        (0, '暂无'),
        (1, 'DCB'),
        (3, 'DCA'),
        (4, 'DCD'),
        (8, 'DCF'),
    )
    id = models.AutoField(primary_key=True)
    ip_segment_id = models.IntegerField()
    type = models.IntegerField(choices=TYPE)
    idc = models.IntegerField(choices=IDC)
    ip = models.CharField(max_length=60)
    ip1 = models.IntegerField(blank=True, default=0)
    ip2 = models.IntegerField(blank=True, default=0)
    ip3 = models.IntegerField(blank=True, default=0)
    ip4 = models.IntegerField(blank=True, default=0)
    asset_type = models.IntegerField(blank=True, default=0, choices=ASSET_TYPE)
    asset_info = models.CharField(max_length=765, blank=True)
    business_info = models.CharField(max_length=765, blank=True)
    is_used = models.IntegerField(blank=True, default=0, choices=IS_USED)
    is_virtual = models.IntegerField(blank=True, default=0, choices=IS_VIRTUAL)
    status = models.IntegerField(blank=True, default=1, choices=STATUS)

    @property
    def ipsegment(self):
        try:
            ipsegment = IpSegment.objects.get(pk=self.ip_segment_id)
        except IpSegment.DoesNotExist:
            ipsegment = None
        return ipsegment

    @property
    def room(self):
        try:
            room = Room.objects.get(pk=self.idc)
        except Room.DoesNotExist:
            room = None
        return room

    class Meta:
        db_table = u'ip_total'

class IpTotal2(models.Model):
    STATUS = (
        (1, '有效'),
        (0, '无效'),
    )
    IS_VIRTUAL = (
        (1, '虚IP'),
        (0, '实IP'),
    )
    IS_USED = (
        (1, '使用'),
        (0, '空闲'),
    )
    ASSET_TYPE = (
        (0, '暂无'),
        (1, '路由器'),
        (2, '交换机'),
        (3, '防火墙'),
        (4, 'A10'),
        (5, 'NETSCALER'),
        (6, 'HAPROXY'),
        (7, '临时设备'),
        (8, '软路由'),
        (9, 'VPN设备'),
        (10, '服务器'),
    )
    TYPE = (
        (0, '暂无'),
        (1, '外网'),
        (2, '管理'),
        (3, '内网'),
    )
    IDC = (
        (0, '暂无'),
        (1, 'DCB'),
        (3, 'DCA'),
        (4, 'DCD'),
        (8, 'DCF'),
    )
    id = models.AutoField(primary_key=True)
    ip_segment = models.ForeignKey(IpSegment, db_column='ip_segment_id')
    type = models.IntegerField(choices=TYPE)
    idc = models.IntegerField(choices=IDC)
    ip = models.CharField(max_length=60)
    ip1 = models.IntegerField(blank=True, default=0)
    ip2 = models.IntegerField(blank=True, default=0)
    ip3 = models.IntegerField(blank=True, default=0)
    ip4 = models.IntegerField(blank=True, default=0)
    asset_type = models.IntegerField(blank=True, default=0, choices=ASSET_TYPE)
    asset_info = models.CharField(max_length=765, blank=True)
    business_info = models.CharField(max_length=765, blank=True)
    is_used = models.IntegerField(blank=True, default=0, choices=IS_USED)
    is_virtual = models.IntegerField(blank=True, default=0, choices=IS_VIRTUAL)
    status = models.IntegerField(blank=True, default=1, choices=STATUS)

    @property
    def room(self):
        try:
            room = Room.objects.get(pk=self.idc)
        except Room.DoesNotExist:
            room = None
        return room

    class Meta:
        db_table = u'ip_total'

class Asset(models.Model):
    STATUS_NAME = (
        (0, '未交付'),
        (1, '已申请'),
        (2, '已交付'),
        (3, '已报修'),
    )
    id = models.AutoField(primary_key=True)
    service_tag = models.CharField(unique=True, max_length=50)
    mac = models.CharField(max_length=50, blank=True)
    assetid = models.CharField(unique=True, max_length=100, blank=True)
    asset_type = models.ForeignKey(AssetType, db_column='asset_type_id')
    status = models.IntegerField(blank=True, default=0)
    rack = models.ForeignKey(Rack, blank=True, default=0, db_column='rack_id')
    asset_model = models.ForeignKey(AssetModel, db_column='asset_model_id')
    position = models.CharField(max_length=100)
    detail = models.TextField(blank=True)
    comment = models.CharField(max_length=255, blank=True)
    expiration_time = models.IntegerField()
    create_time = models.IntegerField(blank=True, default=0)
    last_modified = models.IntegerField(blank=True, default=0)
    come_from = models.IntegerField(blank=True, default=0)
    inventory = models.DateField(blank=True, null=True)
    new_status = models.IntegerField(blank=True, default=0, choices=STATUS_NAME)

    @property
    def rack_space(self):
        return RackSpace.objects.filter(rack_id=self.rack_id, assetid=self.assetid)

    @property
    def ip_info(self):
        return IpTotal.objects.filter(asset_info=self.assetid, is_used=1, status=1)

    class Meta:
        managed = False
        db_table = 'asset'

    def __unicode__(self):
        return self.assetid


class UniqueAsset(models.Model):
    id = models.AutoField(primary_key=True)
    cname = models.CharField(max_length=30, unique=True, blank=True)

    class Meta:
        db_table = u'unique_asset'


class TmpFpingIp(models.Model):
    ip = models.CharField(max_length=100, primary_key=True)

    class Meta:
        managed = False
        db_table = 'tmp_fping_ip'


class TmpFpingIpJq(models.Model):
    ip = models.CharField(max_length=100, primary_key=True)

    class Meta:
        managed = False
        db_table = 'tmp_fping_ip_jq'


class TmpFpingIpNh(models.Model):
    ip = models.CharField(max_length=100, primary_key=True)

    class Meta:
        managed = False
        db_table = 'tmp_fping_ip_nh'


class TmpIp63(models.Model):
    ip = models.CharField(max_length=100, primary_key=True)

    class Meta:
        managed = False
        db_table = 'tmp_ip_63'


class IpFping(models.Model):
    id = models.AutoField(primary_key=True)
    ip = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'ip_fping'


class IpZabbix(models.Model):
    id = models.AutoField(primary_key=True)
    ip = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'ip_zabbix'


class AssetRepair(models.Model):
    TYPE_NAME = (
        (0, '未定义'),
        (1, '主板故障'),
        (2, '内存故障'),
        (3, '硬盘故障'),
        (4, '电源故障'),
        (5, '电池故障'),
        (6, 'CPU故障'),
        (7, 'raid卡故障'),
        (8, '风扇故障'),
        (9, '交换机故障'),
    )
    id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, db_column='asset_id')
    type = models.IntegerField(choices=TYPE_NAME)
    reson_user = models.CharField(max_length=50, blank=True)
    reson = models.CharField(max_length=500, blank=True)
    result_user = models.CharField(max_length=50, blank=True)
    result = models.CharField(max_length=500, blank=True)
    reson_time = models.IntegerField(blank=True, null=True)
    result_time = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'asset_repair'