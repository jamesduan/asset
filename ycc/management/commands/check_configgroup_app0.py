# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from ycc.models import ConfigGroup
from cmdb.models import App,Site
class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        abandon=['abandon']
        exist=['exist']
        forbidden=['forbidden']
        group=ConfigGroup.objects.filter(app_id=0,status=1).values('group_id').distinct()
        for obj in group:
            try:
                site=obj['group_id'].split('_')[0]
                appname='_'.join(obj['group_id'].split('_')[1:])
            except Exception,e:
                abandon.append(obj['group_id'])
                continue
            try:
                site_id=Site.objects.get(name=site).id
            except Site.DoesNotExist:
                abandon.append(obj['group_id'])
                continue

            app=App.objects.filter(name=appname,site_id=site_id)
            if not app:
                 abandon.append(obj['group_id'])
            else:
                if app.filter(status=0):
                    exist.append(obj['group_id'])
                else:
                    forbidden.append(obj['group_id'])

        print abandon
        print forbidden
        print exist
        # print groupiddistinct
        print 'success'






