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

        groupstatus = ConfigGroupStatus.objects.all()
        groupstatus_published = groupstatus.filter(status=4)
        groupstatus_edit = groupstatus.filter(status=0)
        configinfo_pro_published = ConfigInfo.objects.filter(env=7, group_status_id__status=4)
        configinfo_pro_edit =  ConfigInfo.objects.filter(env=7, group_status_id__status=0)

        current_time = int(time.time())
        print current_time

        for gsp in groupstatus_published:
            if not groupstatus_edit.filter(group_id=gsp.group_id).exists():
                print 'error-no gse in ' + gsp.group.group_id
                continue
            configinfo_pro_published_gsp = configinfo_pro_published.filter(group_status_id=gsp.id)
            if configinfo_pro_published_gsp.exists():
                gse = groupstatus_edit.get(group_id=gsp.group)
                configinfo_pro_published_gse = configinfo_pro_edit.filter(group_status_id=gse.id)
                if configinfo_pro_published_gse.exists():
                    print 'error-gse configinfo exists in ' + gsp.group.group_id
                    continue
                configinfos = []
                for cppg in configinfo_pro_published_gsp:
                    configinfos.append(ConfigInfo(data_id=cppg.data_id, group_status=gse, env=cppg.env, content=cppg.content,
                                                    content_md5=cppg.content_md5, created_time=current_time, modified_time=0,
                                                    created_by=cppg.created_by, modified_by='', remark='', file_type=cppg.file_type,
                                                    cmp=1, config_type=1))
                ConfigInfo.objects.bulk_create(configinfos)

        print stamp2str(time.time()) + ':success'

