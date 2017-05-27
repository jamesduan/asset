# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from cmdb.models import AppV2
from server.models import ServerStandard
from ycc.models import ConfigPostInfoV2
import os
import datetime


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        if len(args) != 1:
            print 'invalid usage'
            exit(1)
        file_name = args[0]
        if not os.path.isfile(file_name):
            print '%s does not exist' % file_name
            exit(1)
        with open(file_name) as f:
            while True:
                pool_name = f.readline().rstrip()
                if not pool_name:
                    break
                try:
                    site_name, app_name = pool_name.split('/')
                except Exception, e:
                    print pool_name, e.args
                    continue
                app_obj = AppV2.objects.filter(site__name=site_name, name=app_name, status=0, type=0).first()
                if app_obj is None:
                    print '%s is invalid' % pool_name
                    continue
                filter_dict = {
                    'server_status_id': 200,
                    'server_env_id': 2,
                    'app_id': app_obj.id,
                    'rack__room': 1
                }
                server_queryset = ServerStandard.objects.filter(**filter_dict)
                if server_queryset.count() == 0:
                    filter_dict.update({'rack__room': 4})
                server_queryset = ServerStandard.objects.filter(**filter_dict)
                ip_list = [server_obj.ip for server_obj in server_queryset]
                if not ip_list:
                    print 'no servers in %s' % pool_name
                    continue
                config_post_queryset = ConfigPostInfoV2.objects.filter(ip__in=ip_list,
                                                                       update_time__gte=datetime.datetime.now() - datetime.timedelta(
                                                                           days=3))
                group_id_list = [group_id['group_id'].rstrip('_jq') for group_id in config_post_queryset.values('group_id').distinct()]
                print pool_name
                for group_id in group_id_list:
                    group_id = group_id.replace('_', '/', 1)
                    if pool_name == group_id:
                        continue
                    print '\t%s' % group_id
