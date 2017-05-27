# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from cmdb.models import App
from server.models import ServerStandard
from deploy.utils.Utils import rsync4nocheck
import os


class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        base_path = '/depot/tomcat'
        tomcat_base = '/usr/local/tomcat6'
        env_ini = '/var/www/webapps/config/env.ini'
        for app_obj in App.objects.exclude(id__in=[73, 930, 934]).filter(status=0, type=0, service_name='tomcat'):
            filters = {
                'app': app_obj.id,
                'server_status_id': 200,
                'server_env_id': 2,
                'rack__room__in': [1, 4]
            }
            server1_obj = ServerStandard.objects.exclude(server_status_id=400).filter(**filters).first()
            if server1_obj is None:
                continue
            dst = os.path.join(base_path, app_obj.site.name, app_obj.name)
            if not os.path.isdir(dst):
                os.makedirs(dst)
            src = 'deploy@%s:%s' % (server1_obj.ip, os.path.join(tomcat_base, 'conf/server.xml'))
            self.run(src, dst)
            src = 'deploy@%s:%s' % (server1_obj.ip, os.path.join(tomcat_base, 'bin/catalina.sh'))
            self.run(src, dst)
            # src = 'deploy@%s:%s' % (server1_obj.ip, env_ini)
            # self.run(src, os.path.join(dst, server1_obj.rack.room.name + '_env.ini'))
            # filters['rack__room'] = 4
            # server4_obj = ServerStandard.objects.exclude(server_status_id=400).filter(**filters).first()
            # if server4_obj is None:
            #     continue
            # src = 'deploy@%s:%s' % (server4_obj.ip, env_ini)
            # self.run(src, os.path.join(dst, server4_obj.rack.room.name + '_env.ini'))

    def run(self, src, dst):
        status, cmd, output = rsync4nocheck(src, dst, checksum=True)
        print [str(status), cmd, output]
