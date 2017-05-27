# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from assetv2.settingsdeploy import RABBIT_MQ
import requests

class Command(BaseCommand):
    args = ''
    help = 'get rabbitMQ queques data and send to monitoring system'

    def handle(self, *args, **options):
        base_url = 'http://%s:15672/api/queues/%%2f/' % RABBIT_MQ['HOST']
        url_list = [base_url + 'assetv2_change',
                    base_url + 'assetv2_deploy',
                    base_url + 'assetv2_stg_deploy']
        req = requests.session()
        req.auth = (RABBIT_MQ['USER'], RABBIT_MQ['PASSWORD'])

        queue_list = []
        for url in url_list:
            response = req.get(url)
            if(response.status_code == 200):
                try:
                    item = response.json()
                    queue_list.append({
                        'name': item['name'],
                        'messages': item['messages'] if item.has_key('messages') else 0,
                        'messages_unack': item['messages_unacknowledged'] if item.has_key('messages_unacknowledged') else 0,
                    })
                except Exception, e:
                    print('error:%s' % str(e))
            else:
                print('error:get rabbitMQ api error')
        print(len(queue_list))
        print(queue_list)
