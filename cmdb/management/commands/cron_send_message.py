# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json
from util.httplib import *
from util.timelib import *
from util.sendmessage import *
import time
from cmdb.models import Rota,DdUsers,RotaMan,RotaBackup,ShiftTime,RotaActivity,DdDomain
from assetv2.settingscmdbv2 import DOMAIN_HEAD_ID
from monitor.process.process import process_notification

class Command(BaseCommand):
    args = ''
    help = 'sync user and usersdomains info from cmis'

    def handle(self, *args, **options):
        now = time.localtime()
        now_hour_Tuple = (now.tm_year,now.tm_mon,now.tm_mday,now.tm_hour,00,00,now.tm_wday,now.tm_yday,now.tm_isdst)
        intnow_hour = time.mktime(now_hour_Tuple)
        intnow_hour_8p = intnow_hour + 8*60*60
        intnow_hour_9p = intnow_hour + 9*60*60
        formatnow_hour_8p = stamp2str(intnow_hour_8p, formt='%Y-%m-%d %H:%M')
        formatnow_hour_9p = stamp2str(intnow_hour_9p, formt='%Y-%m-%d %H:%M')

        if now.tm_hour >=16:
            day = '明日'
        else:
            day = '今日'

        duty_rota = Rota.objects.filter(duty_date_start__gte=formatnow_hour_8p,duty_date_start__lt = formatnow_hour_9p)

        if duty_rota:
            for item in duty_rota:
                # if item.rota_activity_id !=11:
                #     continue
                activity=RotaActivity.objects.get(id=item.rota_activity_id)
                promotion=item.promotion
                if ([object.id for object in activity.domains.all()]!=[DOMAIN_HEAD_ID] and promotion==0) or promotion!=0:
                    continue
                duty_start = item.duty_date_start.strftime('%Y-%m-%d %H:%M')
                duty_end = item.duty_date_end.strftime('%Y-%m-%d %H:%M')
                duty_domain_id = item.duty_domain_id
                duty_domain_name = DdDomain.objects.get(id=duty_domain_id).domainname
                duty_mans = item.duty_man.all()
                duty_man_names=[man.username_ch+'('+man.telephone+')' for man in duty_mans]
                duty_man_names=','.join(duty_man_names)
                duty_man_tels = [man.telephone for man in duty_mans]
                way=['on call','on site','at home']
                duty_way = item.duty_way
                duty_backups = item.duty_backup.all()
                duty_backup_names=[man.username_ch+'('+man.telephone+')' for man in duty_backups]
                duty_backup_names=','.join(duty_backup_names)
                duty_backup_tels = [man.telephone for man in duty_backups]

                if [object.id for object in activity.domains.all()]==[DOMAIN_HEAD_ID] and promotion==0:
                    head='IT_OndutyManager值班提醒: '
                    message_content=  head + 'IT_OndutyManager值班人员:'+duty_man_names+ '; 后备人员:'+duty_backup_names + '; 值班时间:'+duty_start +' 至 '+duty_end
                else:
                    head=activity.name+'值班提醒: '
                    message_content=  head + duty_domain_name +'值班人员:'+duty_man_names+ '; 后备人员:'+duty_backup_names + '; 值班时间:'+duty_start +' 至 '+duty_end +'; 值班方式:'+way[duty_way]
                # for tel in duty_man_tels:
                #     sendmessage_v2(0,"yihaodian/techdep-yellowpages",message_content,tel)
                # for tel in duty_backup_tels:
                #     sendmessage_v2(0,"yihaodian/techdep-yellowpages",message_content,tel)
                duty_man_tels.extend(duty_backup_tels)
                datas={'level_id': 500,'message':message_content ,'caller': ','.join(duty_man_tels),'caller_message':  message_content,
                                  'get_time': time.time()}
                process_notification(json.dumps(datas))

        print stamp2str(time.time()) + ':success--' + '值班短信'
