from django.db import models


# Create your models here.
class DnsZone(models.Model):
    ip = models.CharField(max_length=15, default='')
    ip2 = models.CharField(max_length=15, default='', blank=True)
    name = models.CharField(max_length=50, default='')
    serial = models.CharField(max_length=50, default='')
    domain = models.CharField(max_length=50, default='')
    path = models.CharField(max_length=100, default='')
    temp = models.CharField(max_length=100, default='', blank=True)
    ttl = models.CharField(max_length=20, default='', blank=True)
    origin = models.CharField(max_length=50, default='')
    dns_zone_env_id = models.IntegerField(default=0)
    comment = models.CharField(max_length=255, default='', blank=True)

    class Meta:
        db_table = 'dns_zone'


class DnsApiZone(models.Model):
    key = models.CharField(max_length=15, default='')
    dns_zone_id = models.IntegerField(default=0)

    @property
    def zone(self):
        try:
            zone = DnsZone.objects.get(pk=self.dns_zone_id)
        except DnsZone.DoesNotExist:
            zone = None
        return zone

    class Meta:
        db_table = 'dns_api_zone'


class DnsZoneHistory(models.Model):
    dns_zone_id = models.IntegerField(default=0)
    serial = models.CharField(max_length=50, default='')
    path = models.CharField(max_length=100, default='')
    ctime = models.IntegerField(default=0)

    class Meta:
        db_table = 'dns_zone_history'


class DnsOwner(models.Model):
    owner = models.IntegerField(default=0)
    dns_zone_id = models.IntegerField(default=0)
    name = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'dns_owner'


class DnsRecord(models.Model):
    dns_zone_id = models.IntegerField(default=0)
    domain = models.CharField(max_length=200, default='')
    ttl = models.CharField(max_length=20, default='')
    rrtype = models.CharField(max_length=10, default='')
    rrdata = models.CharField(max_length=255, default='')
    owner = models.IntegerField(default=0)
    ctime = models.IntegerField(default=0)

    @property
    def dns_zone(self):
        try:
            item = DnsZone.objects.get(pk=self.dns_zone_id)
        except DnsZone.DoesNotExist:
            item = None
        return item

    class Meta:
        db_table = 'dns_record'
        unique_together = ('dns_zone_id', 'domain', 'rrtype', 'rrdata')


class DnsRecordTemp(models.Model):
    dns_zone_id = models.IntegerField(default=0)
    domain = models.CharField(max_length=200, default='')
    ttl = models.CharField(max_length=20, default='')
    rrtype = models.CharField(max_length=10, default='')
    rrdata = models.CharField(max_length=255, default='')
    owner = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    ctime = models.IntegerField(default=0)
    username = models.CharField(max_length=30, default='')

    @property
    def record(self):
        try:
            item = DnsRecord.objects.get(pk=self.id)
        except DnsRecord.DoesNotExist:
            item = None
        return item

    class Meta:
        db_table = 'dns_record_temp'
        unique_together = ('dns_zone_id', 'domain', 'rrtype', 'rrdata')


class DnsRecordHistory(models.Model):
    dns_record_id = models.IntegerField(default=0)
    dns_zone_id = models.IntegerField(default=0)
    old_data = models.TextField(default='')
    new_data = models.TextField(default='')
    action = models.CharField(max_length=1, default='')
    owner = models.IntegerField(default=0)
    username = models.CharField(max_length=30, default='')
    ctime = models.IntegerField(default=0)

    @property
    def record(self):
        try:
            item = DnsRecord.objects.get(pk=self.dns_record_id)
        except DnsRecord.DoesNotExist:
            item = None
        return item

    class Meta:
        db_table = 'dns_record_history'


class DnsZoneEnv(models.Model):
    name = models.CharField(max_length=30, default='')
    comment = models.CharField(max_length=100, default='')

    class Meta:
        db_table = 'dns_zone_env'


class Download(models.Model):
    key = models.CharField(max_length=50, default='')
    name = models.CharField(max_length=200, default='')
    path = models.CharField(max_length=100, default='')
    file_type = models.CharField(max_length=30, default='')

    class Meta:
        db_table = 'download'


class DnsZoneV2(models.Model):
    ip = models.CharField(max_length=15, default='')
    ip2 = models.CharField(max_length=15, default='', blank=True)
    name = models.CharField(max_length=50, default='')
    serial = models.CharField(max_length=50, default='')
    domain = models.CharField(max_length=50, default='')
    path = models.CharField(max_length=100, default='')
    temp = models.CharField(max_length=100, default='')
    ttl = models.CharField(max_length=20, default='', blank=True)
    origin = models.CharField(max_length=50, default='')
    dns_zone_env = models.ForeignKey(DnsZoneEnv)
    comment = models.CharField(max_length=255, default='', blank=True)

    class Meta:
        db_table = 'dns_zone'


class DnsApiZoneV2(models.Model):
    key = models.CharField(max_length=15, default='')
    dns_zone = models.ForeignKey(DnsZoneV2)

    class Meta:
        db_table = 'dns_api_zone'


class DnsZoneHistoryV2(models.Model):
    dns_zone = models.ForeignKey(DnsZoneV2)
    serial = models.CharField(max_length=50, default='')
    path = models.CharField(max_length=100, default='')
    ctime = models.IntegerField(default=0)

    class Meta:
        db_table = 'dns_zone_history'


class DnsOwnerV2(models.Model):
    owner = models.IntegerField(default=0)
    dns_zone = models.ForeignKey(DnsZoneV2)
    name = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'dns_owner'


class DnsRecordV2(models.Model):
    dns_zone = models.ForeignKey(DnsZoneV2)
    domain = models.CharField(max_length=200, default='')
    ttl = models.CharField(max_length=20, default='')
    rrtype = models.CharField(max_length=10, default='')
    rrdata = models.CharField(max_length=255, default='')
    owner = models.IntegerField(default=0)
    ctime = models.IntegerField(default=0)

    class Meta:
        db_table = 'dns_record'
        unique_together = ('dns_zone_id', 'domain', 'rrtype', 'rrdata')


class DnsRecordTempV2(models.Model):
    dns_zone = models.ForeignKey(DnsZoneV2)
    domain = models.CharField(max_length=200, default='')
    ttl = models.CharField(max_length=20, default='')
    rrtype = models.CharField(max_length=10, default='')
    rrdata = models.CharField(max_length=255, default='')
    owner = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    ctime = models.IntegerField(default=0)
    username = models.CharField(max_length=30, default='')

    @property
    def record(self):
        return DnsRecordV2.objects.filter(pk=self.id).first()

    class Meta:
        db_table = 'dns_record_temp'
        unique_together = ('dns_zone_id', 'domain', 'rrtype', 'rrdata')


class DnsRecordHistoryV2(models.Model):
    dns_record = models.ForeignKey(DnsRecordV2)
    dns_zone = models.ForeignKey(DnsZoneV2)
    old_data = models.TextField(default='')
    new_data = models.TextField(default='')
    action = models.CharField(max_length=1, default='')
    owner = models.IntegerField(default=0)
    username = models.CharField(max_length=30, default='')
    ctime = models.IntegerField(default=0)

    class Meta:
        db_table = 'dns_record_history'
