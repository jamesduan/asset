# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from deploy.models import Deployv3StgMain
from assetv2.settingsdeploy import OMS_HOST
import requests
import json
from deploy.tasks import stg_deploy, stg_rollback
import time

class Command(BaseCommand):
    args = ''
    help = 'test stg deploy and rollback'

    def handle(self, *args, **options):
        web_stg = Deployv3StgMain.objects.filter(app_id=1, status=2, deploy_type=0).order_by('-depid')[0]
        base_url = 'http://%s/api/deploy/' % OMS_HOST
        headers = {'content-type': 'application/json',
                    'Authorization': 'Basic amVua2luczp2MEIoVXhtWTQ4TSkqXmJe'}

        url = base_url + 'stg/list/'
        data = {}
        data['app_id'] = web_stg.app_id
        data['deploy_type'] = web_stg.deploy_type
        data['is_restart'] = web_stg.is_restart
        data['source_path'] = web_stg.source_path
        data['uid'] = 'test'
        data['is_test'] =1

        response = requests.post(url, data=json.dumps(data), headers=headers)
        if response.status_code == 201:
            res = response.json()
            depid = res['depid']
            print('create stg success,depid=%s' % str(depid))
            res1 = stg_deploy.apply_async((depid, 1))
            stg_result = res1.get()
            print('stg deploy result:%s' % stg_result)
            if stg_result:
                time.sleep(5)
                res2 = stg_rollback.apply_async((depid,))
                roll_result = res2.get()
                print('stg rollback result:%s' % roll_result)

