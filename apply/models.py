from django.db import models


class ApplyVm(models.Model):
    id = models.AutoField(primary_key=True)
    apply_id = models.CharField(max_length=255, unique=True, editable=False)
    site_id = models.IntegerField()
    site_name = models.CharField(max_length=150, blank=True)
    app_id = models.IntegerField()
    app_name = models.CharField(max_length=300, blank=True)
    hardware_config_id = models.IntegerField(null=True, blank=True)
    software_config_id = models.IntegerField(null=True, blank=True)
    num = models.IntegerField()
    server_env_id = models.IntegerField()
    zone_id = models.IntegerField()
    status = models.IntegerField(blank=True, default=1)
    created = models.IntegerField(blank=True)
    approved_time = models.IntegerField(blank=True)

    class Meta:
        db_table = u'apply_vm'
