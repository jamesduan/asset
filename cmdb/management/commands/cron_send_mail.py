# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json
from util.httplib import *
from util.timelib import *
from util.sendmail import *
import time
from cmdb.models import Rota,DdUsers,RotaMan,RotaBackup,ShiftTime,RotaActivity,DdDomain
from assetv2.settingscmdbv2 import DOMAIN_HEAD_ID

class Command(BaseCommand):
    args = ''
    help = 'sync user and usersdomains info from cmis'

    def handle(self, *args, **options):
        now = time.time()
        now_7=now+2*24*60*60
        now_8=now+3*24*60*60
        now_7_formt=stamp2str(now_7, formt='%Y-%m-%d')
        now_8_formt=stamp2str(now_8, formt='%Y-%m-%d')
        activities=RotaActivity.objects.filter(start_time__gte=now_7_formt,start_time__lt=now_8_formt,promotion=1)
        for activity in activities:
            shifts=activity.shift_times.count()
            domains=activity.domains.all()
            unfinished=[]
            for domain in domains:
                if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()<shifts:
                    unfinished.append(domain.domainemailgroup)

            subject=activity.name+'值班表录入提醒'
            recipient_list=unfinished
            if recipient_list:
                recipient_list.extend(['huangyijing1@yhd.com'])
            print recipient_list
            html_content='Hi: 您Domain的值班信息还未完整录入，请尽快录入,链接：http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)

            for i in range(0,len(recipient_list),15):
                sendmail_co(subject, html_content, recipient_list[i:i+15], 0,"yihaodian/techdep-yellowpages")
            # if recipient_list:
            #     sendmail_co(subject, html_content, recipient_list, 0,"yihaodian/techdep-yellowpages")

        # subject='值班表录入提醒'
        # html_content="""Hi:
        # 您Domain的值班信息还未录入，请尽快录入（若无需录入，请忽略本次邮件）,链接：http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id=25"""
        # recipient_list=['chenyu5@yhd.com']
        # sendmail_co(subject, html_content, recipient_list, 0,"yihaodian/techdep-yellowpages")
        # print recipient_list
        print stamp2str(time.time()) + ':success--' + '邮件'
