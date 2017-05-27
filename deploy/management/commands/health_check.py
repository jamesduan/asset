# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from cmdb.models import AppV2
from server.models import ServerStandard
from threading import Thread, Lock
from Queue import Queue
from deploy.utils.DeployCommon import ssh
import requests
import os
import json


class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        if len(args) != 4:
            print 'param is missing'
            exit(1)
        file_name, room_name, thread, restart = args
        if not os.path.isfile(file_name):
            print 'file does not exist'
            exit(1)
        queue = Queue()
        lock = Lock()
        for i in range(int(thread)):
            worker = Thread(target=self.cell, args=(queue, lock, json.loads(restart)))
            worker.setDaemon(True)
            worker.start()
        with open(file_name) as f:
            while True:
                pool_name = f.readline().rstrip()
                if not pool_name:
                    break
                try:
                    site_name, app_name = pool_name.split('/')
                except Exception, e:
                    print pool_name, e.args
                    continue
                app_obj = AppV2.objects.filter(site__name=site_name, name=app_name, status=0, type=0).first()
                if app_obj is None:
                    print '%s is invalid' % pool_name
                    continue
                server_queryset = ServerStandard.objects.filter(rack__room__name=room_name, app_id=app_obj.id,
                                                                server_type_id=0,
                                                                server_status_id__in=[200, 210, 220, 230],
                                                                server_env_id=2)
                server_obj = server_queryset.first()
                if server_obj:
                    queue.put((pool_name, server_obj))
            queue.join()
            print 'Done'

    @staticmethod
    def cell(q, l, restart):
        while True:
            pool_name, server_obj = q.get()
            url = settings.HC['PREFIX'] + settings.HC['PATH_API'].format(server_obj.ip)
            r = requests.get(url)
            j = r.json()
            status = j.get('data', dict).get('status')
            l.acquire()
            print '\t'.join([pool_name, server_obj.ip, str(status)])
            l.release()
            if restart and status == 0:
                ssh('/depot/boot.sh', server_obj.ip)
                status, cmd, output = ssh('/depot/boot.sh', server_obj.ip)
                print output
                # # 开始部署
                # if server_queryset.first():
                #     print '%s|已经有至少一台虚拟机了|%s' % (pool_name, server_queryset.first().server_status_id)
                #     continue
                # free_server_obj = ServerStandard.objects.filter(rack__room__name=room_name, server_type_id=0,
                #                                                 server_status_id=100, server_env_id=2).first()
                # if free_server_obj is None:
                #     print '无空闲机器'
                #     break
                # url = 'http://%s/api/server/serverstandard/%s/' % (settings.OMS_HOST, free_server_obj.id)
                # payload = {
                #     'action': 'predeploy',
                #     'app_id': app_obj.id,
                #     'comment': '',
                #     'ycc_zone': 10,
                #     'is_init_tomcat': '1',
                #     'is_one_click': '1',
                #     'haproxy': False,
                # }
                # headers = {
                #     'Authorization': 'Basic %s' % base64.encodestring('%s:%s' % ('deployv3', 'w@rKt0yccDJT&jNs')).rstrip(),
                #     'Content-Type': 'application/json'
                # }
                # r = requests.patch(url=url, data=json.dumps(payload), headers=headers)
                # r.close()
                # if r.status_code != 200:
                #     print '%s|%s|调用接口失败|%s' % (pool_name, free_server_obj.ip, r.status_code)
                #     continue
                # else:
                #     print '%s|%s|调用接口成功|%s' % (pool_name, free_server_obj.ip, r.status_code)

                # while True:
                #     server_obj = ServerStandard.objects.get(id=free_server_obj.id)
                #     if server_obj.server_status_id in [100, 220]:
                #         continue
                #     elif server_obj.server_status_id == 200:
                #         print '%s|%s|使用中' % (pool_name, free_server_obj.ip)
                #         # payload = {
                #         #     'action': 'maintain',
                #         #     'haproxy': False,
                #         #     'hedwig': False
                #         # }
                #         # r = requests.patch(url=url, data=json.dumps(payload), headers=headers)
                #         # r.close()
                #         # if r.status_code == 200:
                #         #     print '%s|%s|切维护成功' % (pool_name, free_server_obj.ip)
                #         # else:
                #         #     print '%s|%s|切维护失败|%s' % (pool_name, free_server_obj.ip, r.status_code)
                #     elif server_obj.server_status_id == 230:
                #         print '%s|%s|预上架失败' % (pool_name, free_server_obj.ip)
                #     else:
                #         print '%s|%s|状态异常' % (pool_name, free_server_obj.ip)
                #     break
            q.task_done()
