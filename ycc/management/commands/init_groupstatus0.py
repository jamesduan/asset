# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import time
from util.timelib import stamp2str
from cmdb.models import Site, App
from asset.models import Room
from ycc.models import ConfigGroup, ConfigGroupStatus, ConfigInfo, OldConfigGroup, OldConfigInfo, ConfigEnv

class Command(BaseCommand):
    args = ''
    help = 'auto deploy'


    def handle(self, *args, **options):
        print stamp2str(time.time()) + ':begin'
        groups = ConfigGroup.objects.all()
        groupstatus = ConfigGroupStatus.objects.all()
        for g in groups:
            if not groupstatus.filter(group_id=g.id, status=0).exists():
                print g.group_id
                ConfigGroupStatus.objects.create(group=g, version=0, status=0, pre_version=10)
        print stamp2str(time.time()) + ':success'

