# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from ycc.models import ConfigInfo
import xml.etree.ElementTree as ET


class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        for obj in ConfigInfo.objects.filter(data_id__contains='cache', env_id=7, group_status__status=4).filter(data_id__contains='.xml'):
            try:
                root = ET.fromstring(obj.content)
            except Exception, e:
                continue
            for pool in root.findall('pool'):
                servers = pool.find('servers')
                if pool.get('id') == 'data_pool' or (servers is not None and servers.findall('server')):
                    continue
                print obj.group_status.group.group_id, obj.group_status.group.idc.name, pool.get('id')