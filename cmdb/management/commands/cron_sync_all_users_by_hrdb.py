# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from util.timelib import *
from assetv2.settingscmdbv2 import CMDB_CRON_MAILLIST, CRON_ALL_USERS_API
from cmdb.models import DdUsers
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context
import time
from pyhessian.client import HessianProxy


class Command(BaseCommand):
    args = ''
    help = 'sync domain info from cmis'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            dept_list = ['780>781>6>', '780>782>2567>']
            url = CRON_ALL_USERS_API
            hr_users = []
            for dept in dept_list:
                res = HessianProxy(url, timeout=300).findEmpInfoListByDepRel(dept)
                if len(res):
                    for item in res:
                        hr_users.append(item.ad)
                        try:
                            cmis_sync_user, created = DdUsers.objects.filter(enable=0).get_or_create(username=item.ad, defaults={
                                'display_name': item.displayName if item.displayName else '',
                                'email':        item.email,
                                'enable':       0,
                                'telephone':    item.phone,
                                'username_ch': str(item.displayName[(item.displayName.rfind('_') + 1):-1]) if item.displayName else '',
                            })
                            if not created:
                                cmis_sync_user.display_name = item.displayName if item.displayName else ''
                                cmis_sync_user.email = item.email
                                cmis_sync_user.enable = 0
                                cmis_sync_user.telephone = item.phone
                                cmis_sync_user.username_ch = str(item.displayName[(item.displayName.rfind('_') + 1):-1]) if item.displayName else ''
                                cmis_sync_user.save()
                        except Exception, e:
                            error = True
                            message.append('error: id=%d, detail: %s' % (item['id'], str(e)))
                            break
                    message.append(stamp2str(time.time()) + ':finish')
            # 反向查询更新已离职人员状态
            DdUsers.objects.filter(enable=0).exclude(username__in=hr_users).update(enable=1)
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        # 邮件通知
        if error:
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【同步用户信息失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, CMDB_CRON_MAILLIST)
