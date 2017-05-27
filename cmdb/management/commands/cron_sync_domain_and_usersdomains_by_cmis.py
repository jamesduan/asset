# -*- coding: utf-8 -*-

__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
import json
from util.httplib import *
from util.timelib import *
from assetv2.settingscmdbv2 import CRON_DOMAIN_API, CRON_DOMAIN_USERS_API, CMDB_CRON_MAILLIST, DOMAIN_HEAD_ID
from cmdb.models import DdDomain, DdUsers, DdUsersDomains
import HTMLParser
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context


class Command(BaseCommand):

    args = ''
    help = 'sync domain and domainsusers info from cmis'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            # 获取所有Domain
            response = json.loads(urllib.urlopen(CRON_DOMAIN_API).read())
            for item in response['response']:
                if item['id'] == DOMAIN_HEAD_ID:
                    message.append(u'domainid=800 repeated error, update failure')
                    continue
                if item['id'] in [187,188,189,190]:
                    continue
                cmis_sync_domain, created = DdDomain.objects.get_or_create(id=item['id'], defaults={
                    'domaincode':     HTMLParser.HTMLParser().unescape(item['domainCode']),
                    'domainname':     HTMLParser.HTMLParser().unescape(item['domainName']),
                    'domainemailgroup':     item['domainEmailGroup'],
                    'domainleaderaccount':     item['domainLeaderAccount'],
                    'backupdomainleaderaccount':     item['backupDomainLeaderAccount'],
                    'enable':     item['enable'],
                    'departmentid':     item['departmentId'],
                    'departmentname':       item['departmentName'],
                })
                if not created:
                    cmis_sync_domain.domaincode = HTMLParser.HTMLParser().unescape(item['domainCode'])
                    cmis_sync_domain.domainname = HTMLParser.HTMLParser().unescape(item['domainName'])
                    cmis_sync_domain.domainemailgroup = item['domainEmailGroup']
                    cmis_sync_domain.domainleaderaccount = item['domainLeaderAccount']
                    cmis_sync_domain.backupdomainleaderaccount = item['backupDomainLeaderAccount']
                    cmis_sync_domain.enable = item['enable']
                    cmis_sync_domain.departmentid = item['departmentId']
                    cmis_sync_domain.departmentname = item['departmentName']
                    cmis_sync_domain.save()
                # Domain可用，同步Domain下的用户对应关系
                user_domain = DdUsersDomains.objects.filter(dddomain=cmis_sync_domain.id)
                if cmis_sync_domain.enable == 0:
                    res = json.loads(urllib.urlopen(CRON_DOMAIN_USERS_API % cmis_sync_domain.id).read())
                    new_user_ids = []
                    for item1 in res['response']:
                        try:
                            hrdb_user = DdUsers.objects.get(username=item1['adAccount'])
                        except (DdUsers.DoesNotExist, DdUsers.MultipleObjectsReturned), e:
                            if not item1['adAccount'].endswith('-ext'):
                                error = True
                                message.append(u'user does not exist or multiple returned error: domainid=%d, username=%s, detail: %s' % (item['id'], item1['adAccount'], str(e)))
                            continue
                        new_user_ids.append(hrdb_user.id)
                        hrdb_user.domains.add(cmis_sync_domain)
                    # 删除已不在该Domain的用户对应关系
                    user_domain.exclude(ddusers__in=new_user_ids).delete()
                else:   # Domain已废弃，删除该Domain下的用户关系
                    user_domain.delete()

            message.append(stamp2str(time.time()) + ':finish')
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        if error:
            # 邮件通知
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【同步Domain和Domain与用户关系信息失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, CMDB_CRON_MAILLIST)