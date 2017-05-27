# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from deploy.models import DeployReboot
from deploy import tasks
import datetime
import time
import json


class Command(BaseCommand):
    args = ''
    help = 'auto reboot'

    def handle(self, *args, **options):
        task_id_list = []
        now = datetime.datetime.now()
        now_hour = datetime.datetime.strptime(now.strftime('%Y-%m-%d %H:%M'), '%Y-%m-%d %H:%M')
        now_hour_timestamp = long(time.mktime(now_hour.timetuple()))
        for deploy_reboot_obj in DeployReboot.objects.filter(reboot_time=now_hour_timestamp, is_auto_published=False):
            print json.loads(deploy_reboot_obj.data)
            result = tasks.auto_reboot.apply_async((json.loads(deploy_reboot_obj.data),))
            task_id_list.append(result.task_id)
            deploy_reboot_obj.is_auto_published = True
            deploy_reboot_obj.save()
        print task_id_list