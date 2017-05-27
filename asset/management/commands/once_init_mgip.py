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
from asset.models import TmpFpingIp, TmpFpingIpJq, TmpFpingIpNh, IpTotal
from server.models import Server
from util.timelib import stamp2str
import time

class Command(BaseCommand):
    args = ''
    help = 'sync department info from cmis'

    def handle(self, *args, **options):
        ip = TmpFpingIpJq.objects.filter()
        for item in ip:
            try:
                server = Server.objects.exclude(server_status_id=400).get(mgmt_ip=item.ip)
            except Server.MultipleObjectsReturned:
                print item.ip
            except Server.DoesNotExist:
                print item.ip
            new_ip = IpTotal.objects.get(ip=item.ip)
            new_ip.asset_info = server.assetid
            new_ip.is_used = 1
            new_ip.save()
        print stamp2str(time.time()) + ':success'