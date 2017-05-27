# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from accident.models import Accident, AccidentAction
import time
from util.timelib import stamp2str
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context
from cmdb.models import DdUsers
from assetv2.settingsaccident import ACCIDENT_CRON_MAILLIST


class Command(BaseCommand):
    args = ''
    help = 'action delay notice before 3 day'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            action_list = AccidentAction.objects.filter(accident_id__gte=2016010101, status=1)
            user_names = []
            for act in action_list:
                du = act.duty_users.split(',')
                if len(du) > 1:
                    for u in du:
                        user_names.append(u)
                elif len(du) == 1:
                    user_names.append(act.duty_users)

            user_names = list(set(user_names))
            for username in user_names:
                try:
                    user = DdUsers.objects.using('default').get(username=username, enable=0)
                except DdUsers.DoesNotExist:
                    user = None

                own_actions = AccidentAction.objects.filter(duty_users__contains=username, accident_id__gte=2016010101, status=1)
                act_list = []
                act_user_email = []
                for action in own_actions:
                    try:
                        accident = Accident.objects.get(accidentid=action.accident_id, is_accident=0)
                    except Accident.DoesNotExist, Accident.MultipleObjectsReturned:
                        accident = None
                    if accident:
                        act_list.append({
                            'level': accident.get_level_display,
                            'duty_manager_ch': accident.duty_manager_name_ch,
                            'accidentid': accident.accidentid,
                            'title': accident.title,
                            'action': action.action,
                            'duty_dept': action.dutydept_name,
                            'duty_users': action.duty_users,
                            'expect_time': action.expect_time_format
                        })
                        try:
                            act_user_email.append(DdUsers.objects.using('default').get(username=username, enable=0).email)
                        except DdUsers.DoesNotExist, DdUsers.MultipleObjectsReturned:
                            error = True
                            message.append('### duty user mail does not exist: username=%s' % username)
                act_user_email = list(set(act_user_email))
                # act_user_email = ['liuyating1@yhd.com']
                # 发送Action提醒邮件
                if act_list and act_user_email:
                    t = get_template('mail/accident/action_delay_notice.html')
                    html_content = t.render(Context(locals()))
                    try:
                        sendmail_html(u'【Action提醒】您还有未完成改进措施', html_content, act_user_email)
                    except Exception, e:
                        error = True
                        message.append('### send mail error: username=%s, detail: %s' % (username, str(e)))
                        break
            message.append(stamp2str(time.time()) + ':finish')
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        # 脚本报错邮件通知
        if error:
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【Action邮件提醒脚本失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, ACCIDENT_CRON_MAILLIST)


