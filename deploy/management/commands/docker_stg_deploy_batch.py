# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from cmdb.models import Site, App
from server.models import Server
from deploy.models import Deployv3StgMain
from assetv2.settingsdeploy import CMDBAPI_URL
from util.timelib import stamp2str
import requests
import time
import random

class Command(BaseCommand):
    args = ''
    help = 'Batch create stg deploy form and release automatically'

    def handle(self, *args, **options):
        #pool list
        appname_list = ['yihaodian/ad-dolphin-go', 'yihaodian/contract', 'yihaodian/advertise-open-service',
                        'yihaodian/backend-zeus-app', 'yihaodian/front-cms', 'yihaodian/promotion',
                        'yihaodian/backend-price-web', 'ops/sre', 'yihaodian/tracker-related',
                        'yihaodian/security-antifraud', 'samsclub/lab-pe-front', 'shareservice/tracker-flume',
                        'yihaodian/front-homepage', 'yihaodian/brain', 'shareservice/order-gds',
                        'yihaodian/front-union-click', 'yihaodian/mingpin-backend', 'yihaodian/jingpin',
                        'yihaodian/front-myyhd-backend', 'yihaodian/ad-dolphin-bidding', 'yihaodian/backend-finance-invoice',
                        'yihaodian/search-mars-platform', 'yihaodian/lab_pe_front']
        for appname in appname_list:
            print('%s start' % appname)
            site_app = appname.split('/')
            #get param
            try:
                site = Site.objects.get(name=site_app[0].strip())
                app = App.objects.get(name=site_app[1].strip(), site_id=site.id)
            except (Site.DoesNotExist, App.DoesNotExist):
                print('error: %s  site or app does not exist!' % appname)
                continue

            servers = Server.objects.filter(app_id=app.id, server_type_id=3)
            ids = ','.join([str(s.id) for s in servers])
            last_stg_list = Deployv3StgMain.objects.filter(app_id=app.id, deploy_type=0, status=2).order_by('-success_update')
            if len(last_stg_list)== 0:
                print('error: %s  last stg deploy does not exist!' % appname)
                continue

            last_stg = last_stg_list[0]
            postdata = {
                'app_id': int(app.id),
                'depid': stamp2str(int(time.time()), '%Y%m%d%H%M%S') + str(random.randint(100000,999999)),
                'uid': 'liuyating1',
                'source_path': str(last_stg.source_path),
                'deploy_type': 0,
                'is_restart': 0,
                'is_need_deploy': 1,
                'server_ids': str(ids)
            }
            #post stg deploy
            url = '%sdeploy/stg/list/' % CMDBAPI_URL

            headers = {'Authorization':'Basic amVua2luczp2MEIoVXhtWTQ4TSkqXmJe'}
            response = requests.post(url, data=postdata, headers=headers)
            if response.status_code == 201:
                print('%s create stg deploy success!')
            else:
                print(u'error: %s create stg deploy error：%s' % (appname, str(response.text)))
        print('end')
