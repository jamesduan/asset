# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from util.httplib import *
from util.timelib import *
import time
from util.sendmail import *
from cmdb.models import Rota,DdUsers,RotaActivity,DdDomain,DailyDutyConfig
from django.template import loader
from assetv2.settingscmdbv2 import DOMAIN_HEAD_ID
from monitor.process.process import process_notification
import json

class Command(BaseCommand):
    args = ''
    help = 'sync user and usersdomains info from cmis'

    def handle(self, *args, **options):
        now = time.localtime()
        year = now.tm_year
        month = now.tm_mon
        day = now.tm_mday
        if month==12:
            start_year = str(year + 1)
            start_month = str(1)
            end_year = start_year
            end_month = str(2)
        else:
            start_year = str(year)
            start_month = str(month +1)
            end_year = start_year
            end_month = str(month +2)
            if month ==11:
                end_year = str(year+1)
                end_month = str(1)

        # acname=['值班经理','值班监控','问题诊断专家']
        # domainid=[800,106,49]
        # recipient_list=[['huangyijing1@yhd.com','chenyu5@yhd.com'],['it_ops_monitor@yhd.com','chenyu5@yhd.com'],['chenyu5@yhd.com']]
        # error=[]
        for obj in DailyDutyConfig.objects.filter(enable=1):
        # for i in range(3):

            activity, created = RotaActivity.objects.get_or_create(name = start_year+'年'+ start_month+'月'+ obj.name, defaults={
                'name':     start_year+'年'+ start_month+ '月' + obj.name,
                'start_time':    start_year + '-'+start_month+'-01 00:00',
                'end_time':     end_year+ '-'+end_month+'-01 00:00',
                'promotion': 0,
                })
            if created:
                activity.domains.add(obj.domain)
                subject=activity.name+'值班录入提醒'
                message=activity.name+'值班活动已创建，请及时录入值班信息。链接：http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
                html_content = loader.render_to_string('cmdbv2/cmdb/text_mail.html', {
                'content': activity.name+'值班活动已创建，请及时录入值班信息。链接：',
                'url': 'http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
                })
                if obj.domain_id==DOMAIN_HEAD_ID:
                    recipient_list=['huangyijing1@yhd.com','chenyu5@yhd.com']
                else:
                     recipient_list=[obj.domain.domainemailgroup,'chenyu5@yhd.com']
                if obj.sendmail==1:
                    # sendmail_co(subject, html_content, recipient_list, 0,"yihaodian/techdep-yellowpages")
                    # None
                    datas={'level_id': 500,'title': subject,'message': message,'send_to': ','.join(recipient_list),
                                  'get_time': time.time()}
                    process_notification(json.dumps(datas),template= html_content)



        print stamp2str(time.time()) + ':success'