# -*- coding: utf-8 -*-
from server.models import Server
from deploy.models import DeployPath
from git_python.models import GitBootShApp
from django.conf import settings
from deploy.utils.DeployCommon import i2, rsync4nocheck, ssh
from deploy.utils.DeployError import DeployError
from deploy.utils.Utils import mkdir
from django.core.cache import get_cache
import os


class InitTomcatV2:
    def __init__(self, ip, task_id, require):
        self.ip = ip
        self.task_id = task_id
        self.require = require
        server_obj = Server.objects.exclude(server_status_id=400).filter(ip=ip).first()
        if server_obj is None:
            self.ie(u'找不到%s的对应的服务器!' % ip)
        self.server_obj = server_obj

    def auto_publish(self):
        if self.require == 0:
            msg = '非tomcat的POOL，不需要进行tomcat配置初始化'
            self.i(msg)
            return {'exc_message': msg}
        deploy_path_obj = DeployPath.objects.filter(app_id=self.server_obj.app_id).first()
        if deploy_path_obj is None:
            self.ie(u'找不到%s的对应的发布路径!' % self.app_id)
        path4webapps = deploy_path_obj.path
        path4config = '/var/www/webapps/config'
        server_xml = '/usr/local/tomcat6/conf/server.xml'
        catalina_sh = '/usr/local/tomcat6/bin/catalina.sh'
        # env_ini = '/var/www/webapps/config/env.ini'
        app_obj = self.server_obj.app
        full_path = os.path.join('/depot/tomcat', app_obj.site.name, app_obj.name)
        # boot_sh = '/depot/boot.sh'
        # boot_sh_path = '/depot/boot.git/deploy/'
        # if GitBootShApp.objects.filter(app=app_obj).first():
        #     boot_sh_path = os.path.join(boot_sh_path, app_obj.site.name, app_obj.name)
        self.create_directory(path4webapps)
        self.create_directory(path4config)
        self.create_file(os.path.join(full_path, 'server.xml'), 'deploy@%s:%s' % (self.ip, server_xml))
        self.create_file(os.path.join(full_path, 'catalina.sh'), 'deploy@%s:%s' % (self.ip, catalina_sh))
        # self.create_file(os.path.join(full_path, self.server_obj.rack.room.name + '_env.ini'), 'deploy@%s:%s' % (self.ip, env_ini))
        # self.create_file(os.path.join(boot_sh_path, 'boot.sh'), 'deploy@%s:%s' % (self.ip, boot_sh))
        self.puppet()

    def ie(self, log):
        self.i('修改服务器状态为预上线失败')
        self.server_obj.server_status_id = 230
        self.server_obj.save()
        self.i(log, error=True)
        raise DeployError(log)

    def i(self, log, error=False):
        cache = get_cache('deploy', **{'LOCATION': settings.CACHES['deploy']['LOCATION'] + '2'})
        i2(cache, self.task_id, log, error)

    def create_directory(self, directory):
        status, cmd, output = mkdir(directory, self.ip)
        if not status:
            self.ie('创建目录%s失败，原因为：%s' % (directory, output))
        self.i('创建目录%s成功' % directory)

    def create_file(self, src, dst):
        status, cmd, output = rsync4nocheck(src, dst, checksum=True)
        if not status:
            self.ie('创建文件%s失败，原因为：%s' % (dst, output))
        self.i('创建文件%s成功' % dst)

    def puppet(self):
        status, cmd, output = ssh('sudo /usr/bin/puppet agent -t --logdest /var/log/puppet/puppet_runtime.log', self.ip)
        # status, cmd, output = ssh('hostname', self.ip)
        # if not status:
        #     self.ie('执行puppet失败，原因为：%s' % output)
        self.i('执行puppet成功，详情为：%s' % output)
