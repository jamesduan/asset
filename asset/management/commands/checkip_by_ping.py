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
        type = int(args[1])
        idc = int(args[0])
        is_need_delete = int(args[2])
        if is_need_delete == 1:
            IpFping.objects.all().delete()

        size = 10000
        for i in range(1, 20):
            bb = (i-1)*size
            cc = i*size
            if idc == 1: #南汇
                if type == 1: #DB
                    ip = IpTotal.objects.filter(type=3, status=1, idc=1, ip2=0)[bb:cc]
                else:
                    ip_list = [0,1,2,3,4,5,6,7,8,11,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,
                               35,36,37,38,39,40,41,42,43,44,225,248,249,250,251,252,253,254]
                    ip = IpTotal.objects.filter(type=3, status=1, idc=1, ip2=4, ip3__in=ip_list)[bb:cc]
            if idc == 4 or idc == 10:
                if type == 1:
                    ip = IpTotal.objects.filter(type=3, status=1, idc=4, ip3__gte=1, ip3__lte=46)[bb:cc]
                elif type == 3:
                    ip = IpTotal.objects.filter(type=3, status=1, idc=4, ip2=63, ip3__gte=12, ip3__lte=15)[bb:cc]
                else:
                    ip = IpTotal.objects.filter(type=3, status=1, idc=4, ip3=223)[bb:cc]

            for item in ip:
                response = os.system("ping -c 2 " + item.ip)
                if response == 0:
                    IpFping.objects.get_or_create(ip=item.ip)

        print stamp2str(time.time()) + ':success'