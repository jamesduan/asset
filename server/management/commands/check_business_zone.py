# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from threading import Thread, Lock
from Queue import Queue
from server.models import ServerStandard,ExceptionBusinessZone
from deploy.utils.DeployCommon import ssh
from util.timelib import *
import commands
import re

class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        status, output=commands.getstatusoutput('ps -ef --sort=start_time|grep -v grep|grep -v "sh -c"| grep "manage-deploy.py check_business_zone"')
        cmd=output.split('\n')
        if not status and len(cmd)>=2:
            detail=re.sub(' +', ' ', cmd[0]).split(' ')
            commands.getstatusoutput('kill -9 %s' %detail[1])
        now=time.time()
        current_format=stamp2str(now,formt='%Y-%m-%d %H:%M:%S')
        queue = Queue()
        lock = Lock()
        initial_id = [obj.id for obj in ExceptionBusinessZone.objects.all()]
        update_id = []
        for i in range(40):
            worker = Thread(target=self.business_config, args=(queue, lock,update_id))
            worker.setDaemon(True)
            worker.start()
        for server_obj in ServerStandard.objects.filter(server_env_id=2, server_status_id__in=[200, 210],app__status=0).exclude(ip='10.17.4.206'):
            queue.put(server_obj)
        queue.join()
        diff_id = list(set(initial_id).difference(set(update_id)))
        ExceptionBusinessZone.objects.filter(id__in=diff_id).delete()
        print 'Done ' + current_format

    @classmethod
    def business_config(cls, queue, lock, update_id):
        while True:
            server_obj = queue.get()
            server_zone = server_obj.ycc_zone.ycc_code if server_obj.ycc_zone else None
            status, cmd, output = ssh('grep zone= /var/www/webapps/config/env.ini', server_obj.ip)
            if status:
                business_zone = output.split('=')[1]
            else:
                business_zone=None
            if business_zone !=server_zone:
                obj,created = ExceptionBusinessZone.objects.get_or_create(server_id=server_obj.id,defaults={'business_zone':business_zone,})
                if not created:
                    obj.business_zone=business_zone
                    obj.save()
                    update_id.append(obj.id)
            queue.task_done()

