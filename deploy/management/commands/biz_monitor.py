# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
import requests


class Command(BaseCommand):
    args = ''
    help = 't'
    biz_url = settings.BIZ_MONITOR['PREFIX'] + settings.BIZ_MONITOR['BIZ_API']

    def handle(self, *args, **options):
        # queue
        for pool in settings.MONITORED_QUEUES:
            for queue in settings.MONITORED_QUEUES[pool]:
                url = 'http://%s:15672/api/queues/%%2f/%s' % (settings.RABBIT_MQ['HOST'], queue)
                auth = (settings.RABBIT_MQ['USER'], settings.RABBIT_MQ['PASSWORD'])
                code, data = Command.http_requests(url, 'get', None, auth)
                Command.http_requests(
                    Command.biz_url,
                    'post',
                    {
                        'pool': pool,
                        'key': 'queue_' + queue,
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
        print '|'.join([url, str(code), str(data)])
        return code, data
