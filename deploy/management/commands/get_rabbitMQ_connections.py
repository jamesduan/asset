# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from assetv2.settingsdeploy import RABBIT_MQ
import json
import requests

class GetAPIExcept(Exception):
    pass

class Command(BaseCommand):
    args = ''
    help = 'get rabbitMQ connections data and send to monitoring system'

    def handle(self, *args, **options):
        url = 'http://%s:15672/api/connections' % RABBIT_MQ['HOST']
        req = requests.session()
        req.auth = (RABBIT_MQ['USER'], RABBIT_MQ['PASSWORD'])
        try:
            response = req.get(url)
            res = response.json()
        except Exception, e:
            raise GetAPIExcept('error:%s' % str(e))
        state_flag = True
        for item in res:
            if item['state'] != 'running' or item['timeout'] > 1:
                state_flag = False
        print('connections state:' + str(state_flag))