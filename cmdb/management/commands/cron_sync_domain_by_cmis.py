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
from assetv2.settingscmdbv2 import CRON_DOMAIN_API
from cmdb.models import DdDomain
import HTMLParser


class Command(BaseCommand):
    args = ''
    help = 'sync domain info from cmis'

    def handle(self, *args, **options):
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
        print stamp2str(time.time()) + ':success'