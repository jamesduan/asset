# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
import requests


class Command(BaseCommand):
    args = ''
    help = 't'
    biz_url = "http://oms.yihaodian.com.cn/itil/api/?action=business&method=pushData"

    def handle(self, *args, **options):
        url = 'http://%s:15672/api/queues/%%2f/%s' % (settings.RABBIT_MQ['HOST'], "assetv2_monitor")
        auth = (settings.RABBIT_MQ['USER'], settings.RABBIT_MQ['PASSWORD'])
        code, data = Command.http_requests(url, 'get', None, auth)
        # print code, data
        Command.http_requests(
            Command.biz_url,
            'post',
            {
                'pool': "yihaodian/LeDao-biz",
                'key': 'queue_assetv2_monitor',
                'value': data.get('backing_queue_status', dict()).get('len', -1) if code == 200 else -1
            },
            None
        )

    @staticmethod
    def http_requests(url, method, data, auth):
        try:
            if method == 'get':
                r = requests.get(url, data=data, auth=auth)
            elif method == 'post':
                r = requests.post(url, data=data, auth=auth)
        except Exception, e:
            code, data = None, e.args
        else:
            code, data = r.status_code, r.json()
        # print '|'.join([url, str(code), str(data)])
        return code, data
