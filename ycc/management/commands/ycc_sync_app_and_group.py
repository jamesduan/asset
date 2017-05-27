# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import time
from util.timelib import stamp2str
from cmdb.models import App
from asset.models import Room
from ycc.models import ConfigGroup, ConfigGroupStatus, RoomApps
from django.conf import settings


class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        app_filter = dict()
        app_filter['type'] = 0
        if settings.YCC_ENV == 'production':
            app_filter['status'] = 0
        elif settings.YCC_ENV == 'test':
            app_filter['test_status'] = 0
        else:
            app_filter['id'] = 0
        app = App.objects.filter(**app_filter)
        idc = Room.objects.filter(status=1, ycc_sync=1)
        for item in idc:
            for item_app in app:
                # if item.id not in [1, 4] and not RoomApps.objects.filter(room=item.id, app=item_app.id).exists():
                #     continue
                group_name = '%s_%s' % (item_app.site.name, item_app.name)
                old_pool = '%s/%s' % (item_app.site.name, item_app.name)
                group, created = ConfigGroup.objects.get_or_create(site_id=item_app.site_id, app_id=item_app.id,
                                                                   group_id=group_name, idc=item, status=1, defaults={
                    'site_name': item_app.site.name,
                    'app_name': item_app.name,
                    'type': 1,
                    'old_pool': old_pool,
                    'created': int(time.time()),
                    'updated': int(time.time()),
                    'status': 1,
                })
                if not created:
                    group.site_name = item_app.site.name
                    group.app_name = item_app.name
                    group.save()
                else:
                    ConfigGroupStatus.objects.get_or_create(group=group, version=0, status=0, pre_version=0)
                    ConfigGroupStatus.objects.get_or_create(group=group, version=1, status=4, pre_version=0)

        print stamp2str(time.time()) + ':success'

def retmsg():
    app = App.objects.filter(type=0, status=0)
    idc = Room.objects.filter(id__in=[1, 4])
    for item in idc:
        for item_app in app:
            group_name = '%s_%s' % (item_app.site.name, item_app.name)
            old_pool = '%s/%s' % (item_app.site.name, item_app.name)
            group, created = ConfigGroup.objects.get_or_create(site_id=item_app.site_id, app_id=item_app.id, group_id=group_name, idc=item, defaults={
                'site_name': item_app.site.name,
                'app_name': item_app.name,
                'type': 1,
                'old_pool': old_pool,
                'created': int(time.time()),
                'updated': int(time.time()),
                'status': 1,
            })
            if not created:
                group.site_name = item_app.site.name
                group.app_name = item_app.name
                group.save()
            else:
                ConfigGroupStatus.objects.get_or_create(group=group, version=0, status=0, pre_version=0)
                ConfigGroupStatus.objects.get_or_create(group=group, version=1, status=4, pre_version=0)
    response = {'success': True, 'msg': u'同步成功!!!！'}
    return response






