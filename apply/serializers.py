from rest_framework import serializers
from models import *


class ApplyVmSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplyVm
        fields = ('id', 'apply_id', 'site_id', 'site_name', 'app_id', 'app_name', 'hardware_config_id', 'software_config_id',
        'num', 'server_env_id', 'zone_id', 'status', 'created', 'approved_time')