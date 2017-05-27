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
from asset.models import IpTotal, IpFping
from util.timelib import stamp2str
import time
import os


class Command(BaseCommand):
    args = ''
    help = 'sync department info from cmis'

    def handle(self, *args, **options):
        size = 10000
        for i in range(1, 20):
            bb = (i-1)*size
            cc = i*size
            ip = IpTotal.objects.filter(type=args[0])[bb:cc]
            for item in ip:
                response = os.system("ping -c 2 " + item.ip)
                if response == 0:
                    IpFping.objects.get_or_create(ip=item.ip)

        print stamp2str(time.time()) + ':success'