# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from assetv2.settingsdeploy import RABBIT_MQ
import requests
from util.sendmail import sendmail_html

class Command(BaseCommand):
    args = ''
    help = 'get rabbitMQ queques data and send to monitoring system'

    def handle(self, *args, **options):
        base_url = 'http://%s:15672/api/queues/%%2f/' % RABBIT_MQ['HOST']
        url_list = [base_url + 'assetv2_change?lengths_age=150&lengths_incr=30',
                    base_url + 'assetv2_deploy?lengths_age=150&lengths_incr=30',
                    base_url + 'assetv2_stg_deploy?lengths_age=150&lengths_incr=30']
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
                        'messages_details': item['messages_details']['samples']
                    })
                    flag = 0
                    for detail in item['messages_details']['samples']:
                        if detail['sample'] >= 10:
                            flag = 1
                        else:
                            flag = 0
                    if flag:
                        sendmail_html(subject='报警：消息队列阻塞',
                                      html_content='<h1>消息队列' + item['name'] +'阻塞</h1><br><h2>消息数超过5</h2>',
                                        recipient_list=['liuyating1@yhd.com'])
                except Exception, e:
                    print('error:%s' % str(e))
            else:
                print('error:get rabbitMQ api error')
        print(len(queue_list))
        print(queue_list)
