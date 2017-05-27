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
from asset.models import IpTotal
from util.timelib import stamp2str
import time

class Command(BaseCommand):
    args = ''
    help = 'sync department info from cmis'

    def handle(self, *args, **options):
        ip = IpTotal.objects.all()
        for item in ip:
            arr = item.ip.split('.')
            item.ip1 = arr[0]
            item.ip2 = arr[1]
            item.ip3 = arr[2]
            item.ip4 = arr[3]
            item.save()
        print stamp2str(time.time()) + ':success'