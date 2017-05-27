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
from assetv2.settingscmdbv2 import CRON_DOMAIN_USERS_API
from cmdb.models import DdDomain, DdUsers, DdUsersDomains

class Command(BaseCommand):
    args = ''
    help = 'sync user and usersdomains info from cmis'

    def handle(self, *args, **options):
        domain = DdDomain.objects.filter(enable=0)
        # DdUsers.objects.all().delete()
        # DdUsersDomains.objects.all().delete()
        for item in domain:
            api_url = CRON_DOMAIN_USERS_API % item.id
            response = json.loads(urllib.urlopen(api_url).read())
            for item1 in response['response']:
                cmis_sync_user, created = DdUsers.objects.get_or_create(id=item1['id'], defaults={
                    'username':     item1['adAccount'],
                    'display_name': item1['displayName'],
                    'email':        item1['email'],
                    # 'enable':       item1['enable'],
                    'enable':       0,
                    'telephone':    item1['mobilePhoneNo'],
                    'username_ch': str(item1['displayName'][(item1['displayName'].rfind('_') + 1):-1]),
                })
                if not created:
                    cmis_sync_user.username = item1['adAccount']
                    cmis_sync_user.display_name = item1['displayName']
                    cmis_sync_user.email = item1['email']
                    # cmis_sync_user.enable = item1['enable']
                    cmis_sync_user.enable = 0
                    cmis_sync_user.telephone = item1['mobilePhoneNo']
                    cmis_sync_user.username_ch = str(item1['displayName'][(item1['displayName'].rfind('_') + 1):-1])
                    cmis_sync_user.save()
                cmis_sync_user.domains.add(item)
        print stamp2str(time.time()) + ':success'