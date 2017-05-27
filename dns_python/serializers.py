from rest_framework import serializers
from dns_python.models import *


class DnsZoneSerializer(serializers.ModelSerializer):
    dns_zone_env__comment = serializers.ReadOnlyField(source='dns_zone_env.comment')
    dns_zone_env__id = serializers.ReadOnlyField(source='dns_zone_env.id')

    class Meta:
        model = DnsZoneV2
        fields = ('id', 'ip', 'ip2', 'name', 'serial', 'domain', 'path', 'ttl', 'origin', 'dns_zone_env', 'comment',
                  'dns_zone_env__comment', 'dns_zone_env__id')


class DnsRecordTempSerializer(serializers.ModelSerializer):
    class Meta:
        model = DnsRecordTempV2
        fields = ('id', 'dns_zone', 'domain', 'ttl', 'rrtype', 'rrdata', 'owner', 'status')
