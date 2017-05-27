# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from assetv2.settingsdeploy import RABBIT_MQ
import requests

class GetAPIExcept(Exception):
    pass

class Command(BaseCommand):
    args = ''
    help = 'get rabbitMQ node data and send to monitoring system'

    def handle(self, *args, **options):
        url = 'http://%s:15672/api/nodes/rabbit@db-2-3' % RABBIT_MQ['HOST']
        req = requests.session()
        req.auth = (RABBIT_MQ['USER'], RABBIT_MQ['PASSWORD'])
        try:
            response = req.get(url)
            item = response.json()
        except Exception, e:
            raise GetAPIExcept('error:%s' % str(e))
        node = {
            'node_name': item['name'],
            'node_state': item['running'],
            'mem_used_percent': float(item['mem_used'])/item['mem_limit'],
            'disk_free': item['disk_free'],
            'disk_free_max': int(item['disk_free_limit'] * 1.5)
        }
        print(node)
