# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from cmdb.models import AppV2
from server.models import ServerStandard
import os
import json
import requests


class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        if len(args) != 2:
            print 'param is missing'
            exit(1)
        file_name, room_id = args
        if not os.path.isfile(file_name):
            print 'file does not exist'
            exit(1)
        url = 'http://%s/api/server/vmexpand/' % settings.OMS_HOST
        headers = {
            'Authorization': 'Basic dGlja2V0OnYwQihVeG1ZNDhNKSpeYl4=',
            'content-type': 'application/json'
        }
        data = {
            'env_id': 2,
            'room_id': int(room_id),
            'num': 1,
            'is_init_tomcat': 1,
            'is_one_click': 1,
            'ycc_zone_id': int(room_id),
            'from_user': 'lihaowei'
        }
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
                free_server_obj = ServerStandard.objects.filter(rack__room__id=room_id, server_type_id=0,
                                                                server_status_id=100, server_env_id=2).first()
                if free_server_obj is None:
                    print '无空闲机器'
                    break
                existing_server_obj = ServerStandard.objects.filter(rack__room__id=room_id, server_type_id=0,
                                                                    server_status_id__gte=200, server_env_id=2,
                                                                    app_id=app_obj.id).first()
                if existing_server_obj:
                    print '%s，已存在，略过' % pool_name
                    continue
                data['app_id'] = app_obj.id
                r = requests.post(url, data=json.dumps(data), headers=headers)
                print pool_name, r.status_code, r.json()
