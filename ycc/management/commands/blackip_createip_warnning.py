# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import time
import datetime
from util.timelib import stamp2str
from cmdb.models import Site, App
from asset.models import Room
from util.sendmail import *
from ycc.models import ConfigGroup, ConfigGroupStatus, ConfigInfo, OldConfigGroup, OldConfigInfo, ConfigEnv, GrayReleaseBlackip

class Command(BaseCommand):
    args = ''
    help = 'gray release black ip create time over one day warnning'

    def handle(self, *args, **options):
        now_time = datetime.datetime.now()
        blackip = GrayReleaseBlackip.objects.all()
        subject = '灰度发布黑名单IP超时报警'
        html_content = '黑名单里的IP创建时间超过一天，管理页面地址是http://oms.yihaodian.com.cn/deploy/yccv2/grayrelease/blackip/'
        recipient_list = ['It_base_dev@yhd.com']
        for ctime in blackip:
            start_time = ctime.create_time
            if (now_time - start_time).days >= 1 :
                sendmail_co(subject, html_content, recipient_list, '', '')





















