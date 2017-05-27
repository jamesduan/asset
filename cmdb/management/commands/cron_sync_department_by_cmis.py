# -*- coding: utf-8 -*-
'''
    @description:

    @copyright:     ©2013 yihaodian.com
    @author:        jackie
    @since:         15-03-24
    @version:       1.0
    @author:        jackie
'''
from django.core.management.base import BaseCommand
import json
from util.httplib import *
from util.timelib import *
from assetv2.settingscmdbv2 import CRON_DEPARTMENT_API, CMDB_CRON_MAILLIST
from cmdb.models import DdDepartmentNew
import HTMLParser
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context
import time


class Command(BaseCommand):
    args = ''
    help = 'sync department info from cmis'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            response = json.loads(urllib.urlopen(CRON_DEPARTMENT_API).read())
            for item in response['response']:
                try:
                    item['pid'] = item.get('pid', 0)
                    deptleaderaccount = item.get('deptLeaderAccount', '')
                    item['deptEmailGroup'] = item.get('deptEmailGroup', None)
                    cmis_sync_depart, created = DdDepartmentNew.objects.get_or_create(id=item['id'], defaults={
                        'deptcode':     HTMLParser.HTMLParser().unescape(item['deptCode']),
                        'deptname':     HTMLParser.HTMLParser().unescape(item['deptName']),
                        'deptemailgroup':     item['deptEmailGroup'],
                        'deptleaderaccount':     deptleaderaccount,
                        'deptlevel':     item['deptLevel'],
                        'enable':     item['enable'],
                        'pid':     item['pid'],
                    })
                    if not created:
                        cmis_sync_depart.deptcode = HTMLParser.HTMLParser().unescape(item['deptCode'])
                        cmis_sync_depart.deptname = HTMLParser.HTMLParser().unescape(item['deptName'])
                        cmis_sync_depart.deptemailgroup = item['deptEmailGroup']
                        cmis_sync_depart.deptleaderaccount = deptleaderaccount
                        cmis_sync_depart.deptlevel = item['deptLevel']
                        cmis_sync_depart.enable = item['enable']
                        cmis_sync_depart.pid = item['pid']
                        cmis_sync_depart.save()
                except Exception, e:
                    error = True
                    message.append('error: id=%d, detail: %s' % (item['id'], str(e)))
                    continue
            message.append(stamp2str(time.time()) + ':finish')
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        # 邮件通知
        if error:
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【同步部门信息失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, CMDB_CRON_MAILLIST)
