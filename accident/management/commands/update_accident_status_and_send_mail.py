# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from accident.models import Accident, AccidentAction
import time
from datetime import date
from util.timelib import stamp2str, str2stamp
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context
from cmdb.models import Rota, RotaMan, RotaBackup
from assetv2.settingsaccident import ACCIDENT_DAILY_MAIL, ACCIDENT_DAILY_MAIL_CC, ACCIDENT_CRON_MAILLIST, DOMAIN_HEAD_ID
from cmdb.models import DdUsers


class Command(BaseCommand):
    args = ''
    help = 'update accident action status per day'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            action_list = AccidentAction.objects.using('accident').filter(status=1)     #进行中的action
            today = str2stamp(date.today().strftime("%Y-%m-%d"), formt='%Y-%m-%d')

            for action in action_list:
                if action.expect_time < today:
                    action.status = 2
                    action.save()

            accident_list = Accident.objects.using('accident').filter(is_accident=0, status_id=5) #改进措施进行中的事故列表
            for accident in accident_list:
                cur_actions = AccidentAction.objects.using('accident').filter(accident_id=accident.accidentid)
                action_status = [c_act.status for c_act in cur_actions]
                if 2 in action_status:
                    accident.status_id = 6
                    accident.save()

            #发送值班日报邮件
            lastday_str = stamp2str(today - 86400)
            try:
                cur_rota = Rota.objects.using('default').get(promotion=0, duty_domain=DOMAIN_HEAD_ID, duty_date_start__lt=lastday_str, duty_date_end__gte=lastday_str)
                duty_manager = RotaMan.objects.using('default').get(rota_id=cur_rota.id).man
                back_duty_manager = RotaBackup.objects.using('default').get(rota_id=cur_rota.id).backup

                cur_duty_manager = duty_manager.username
                cur_back_duty_manager = back_duty_manager.username

                if duty_manager.display_name != '':
                    cur_duty_manager_ch = str(duty_manager.display_name[(duty_manager.display_name.rfind('_') + 1):-1])
                else:
                    cur_duty_manager_ch = '无'
                if back_duty_manager.display_name != '':
                    cur_back_duty_manager_ch = str(back_duty_manager.display_name[(back_duty_manager.display_name.rfind('_') + 1):-1])
                else:
                    cur_back_duty_manager_ch = '无'

                if cur_rota is not None:
                    duty_date_start = cur_rota.duty_date_start.strftime('%Y-%m-%d %H:%M:%S')
                    duty_date_end = cur_rota.duty_date_end.strftime('%Y-%m-%d %H:%M:%S')

            except Exception, e:
                cur_duty_manager = ''
                cur_back_duty_manager = ''
                cur_duty_manager_ch = ''
                cur_back_duty_manager_ch = ''

            acc = Accident.objects.using('accident').exclude(status=1).filter(is_accident=0, happened_time__lt=today-14400, happened_time__gte=today-100800)
            accidents = []
            for accident in acc:
                accidents.append({
                    'level': accident.get_level_display,
                    'title': accident.title,
                    'happened_time': stamp2str(accident.happened_time, formt='%Y-%m-%d %H:%M'),
                    'finish_time': stamp2str(accident.finish_time, formt='%Y-%m-%d %H:%M'),
                    'affect': accident.affect,
                    'reason': accident.reason,
                    'duty_dept_names': accident.duty_dept_names,
                    'process': accident.process,
                    'action': accident.action
                })
            delay_actions = AccidentAction.objects.using('accident').filter(accident_id__gte=2016010101, expect_time__gte=1451577600, status=2)
            delay_action = []
            delay_action_users = []
            for da in delay_actions:
                try:
                    act = Accident.objects.using('accident').get(accidentid=da.accident_id, is_accident=0)
                except Accident.DoesNotExist:
                    act = None
                if act:
                    delay_action.append({
                        'level': act.get_level_display,
                        'duty_manager_ch': act.duty_manager_name_ch,
                        'accidentid': act.accidentid,
                        'title': act.title,
                        'action': da.action,
                        'duty_dept': da.dutydept_name,
                        'duty_users': da.duty_users,
                        'expect_time': da.expect_time_format
                    })
                    for user in da.duty_users.split(','):
                        try:
                            delay_action_users.append(DdUsers.objects.using('default').get(username=user, enable=0).email)
                        except DdUsers.DoesNotExist, DdUsers.MultipleObjectsReturned:
                            error = True
                            message.append('### duty user mail does not exist: username=%s' % user)

            t = get_template('mail/accident/daily_on_build.html')
            html_content = t.render(Context(locals()))
            cc = ACCIDENT_DAILY_MAIL_CC + list(set(delay_action_users))
            # cc = ['liuyating1@yhd.com']
            try:
                sendmail_html(u'【值班日报】昨日事故汇总与延迟Action通告', html_content, ACCIDENT_DAILY_MAIL, cc=cc)
            except Exception, e:
                error = True
                message.append('### send mail error: detail: %s' % str(e))

            message.append(stamp2str(time.time()) + ':finish')
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        # 脚本报错邮件通知
        if error:
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【值班日报邮件脚本执行失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, ACCIDENT_CRON_MAILLIST)

