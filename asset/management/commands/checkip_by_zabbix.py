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
from asset.models import IpTotal, IpFping, IpZabbix
from util.timelib import stamp2str
import time
import os
from django.db import connections


class Command(BaseCommand):
    args = ''
    help = 'sync department info from cmis'

    def handle(self, *args, **options):
        IpZabbix.objects.all().delete()
        cursor = connections['zabbix_jq_new'].cursor()
        cursor.execute('select distinct ip from interface where hostid in (select hostid from hosts where status=0)')
        data = cursor.fetchall()
        for item in data:
            IpZabbix.objects.get_or_create(ip=item[0])
        connections['zabbix_jq_new'].close()

        cursor = connections['zabbix_nh_new'].cursor()
        cursor.execute('select distinct ip from interface where hostid in (select hostid from hosts where status=0)')
        data = cursor.fetchall()
        for item in data:
            IpZabbix.objects.get_or_create(ip=item[0])
        connections['zabbix_nh_new'].close()

        cursor = connections['zabbix_jq'].cursor()
        cursor.execute('select distinct ip from interface where hostid in (select hostid from hosts where status=0)')
        data = cursor.fetchall()
        for item in data:
            IpZabbix.objects.get_or_create(ip=item[0])
        connections['zabbix_jq'].close()

        cursor = connections['zabbix_nh'].cursor()
        cursor.execute('select distinct ip from interface where hostid in (select hostid from hosts where status=0)')
        data = cursor.fetchall()
        for item in data:
            IpZabbix.objects.get_or_create(ip=item[0])
        connections['zabbix_nh'].close()

        print stamp2str(time.time()) + ':success'