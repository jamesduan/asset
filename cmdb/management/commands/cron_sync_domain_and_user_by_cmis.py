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
from django.db.models import Count

class Command(BaseCommand):

    args = ''
    help = 'sync domain info from cmis'

    def handle(self, *args, **options):
        error = False
        message = []
        try:
            head_users_domains = DdUsersDomains.objects.filter(dddomain_id=DOMAIN_HEAD_ID)
            head_user_ids = [uu.ddusers_id for uu in head_users_domains]

            response = json.loads(urllib.urlopen(CRON_DOMAIN_API).read())
            for item in response['response']:
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
                if cmis_sync_domain.enable == 0:    # Domain可用，同步Domain下的用户
                    user_domain = DdUsersDomains.objects.filter(dddomain=cmis_sync_domain.id)
                    user_ids = [uu.ddusers_id for uu in user_domain]

                    res = json.loads(urllib.urlopen(CRON_DOMAIN_USERS_API % cmis_sync_domain.id).read())
                    new_user_ids = [nu['id'] for nu in res['response']]
                    for item1 in res['response']:
                        display_name = item1['displayName'].strip()
                        cmis_sync_user, created = DdUsers.objects.get_or_create(id=item1['id'], username=item1['adAccount'], defaults={
                            # 'username':     item1['adAccount'],
                            'display_name': display_name,
                            'email':        item1['email'],
                            # 'enable':       item1['enable'],
                            'enable':       0,
                            'telephone':    item1['mobilePhoneNo'],
                            'username_ch': str(display_name[(display_name.rfind('_') + 1):-1]),
                        })
                        if not created:
                            # cmis_sync_user.username = item1['adAccount']
                            cmis_sync_user.display_name = item1['displayName']
                            cmis_sync_user.email = item1['email']
                            # cmis_sync_user.enable = item1['enable']
                            cmis_sync_user.enable = 0
                            cmis_sync_user.telephone = item1['mobilePhoneNo']
                            cmis_sync_user.username_ch = str(display_name[(display_name.rfind('_') + 1):-1])
                            cmis_sync_user.save()
                        cmis_sync_user.domains.add(cmis_sync_domain)

                        # for head in DdUsers.objects.filter(username=item1['adAccount']):
                        #     if head.id in head_user_ids:  # 如果是乐道自建的head，废弃用户重新写入
                        #         head.enable = 1
                        #         head.save()
                        #         head_users_domains.filter(ddusers=head.id).update(ddusers=item1['id'])

                    # user_domain.exclude(ddusers__in=new_user_ids).delete()  # 删除已不在该Domain的用户对应关系
                    # DdUsers.objects.filter(id__in=user_ids, enable=0).exclude(id__in=new_user_ids).update(enable=1)   # 废弃已不在该Domain的用户
                else:   # Domain已废弃，删除该Domain下的用户
                    DdUsersDomains.objects.filter(dddomain=cmis_sync_domain.id).delete()

            message.append(stamp2str(time.time()) + ':finish')
        except Exception, e:
            error = True
            message.append('error: %s' % str(e))
        print('\n'.join(message))
        if error:
            # 邮件通知
            t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
            title = '【同步Domain和用户信息失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
            html_content = t.render(Context(locals()))
            sendmail_html(title, html_content, CMDB_CRON_MAILLIST)