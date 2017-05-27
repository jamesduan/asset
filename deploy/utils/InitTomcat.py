# -*- coding: utf-8 -*-
from server.models import Server
from deploy.models import DeployPath
from assetv2.settingsdeploy import DEPLOY_STATIC_APP_ID, STATUS_MAPPING, BASE_DIR, CACHES
from deploy.utils.DeployCommon import i, ie, i2
from deploy.utils.DeployError import DeployError
from django.core.cache import get_cache
import commands
import os
import stat


class InitTomcat():
    def __init__(self, ip, task_id, require):
        self.ip = ip
        self.task_id = task_id
        self.require = require
        try:
            server_obj = Server.objects.exclude(server_status_id=400).get(ip=ip)
            if server_obj.app_id == DEPLOY_STATIC_APP_ID:
                self.ie('不支持对静态服务器的tomcat配置初始化')
            self.server_obj = server_obj
        except Server.DoesNotExist:
            self.ie(u'找不到%s的对应的服务器!' % ip)
        except Server.MultipleObjectsReturned:
            self.ie(u'%s对应多个服务器!' % ip)
        try:
            deploy_path_obj = DeployPath.objects.get(app_id=server_obj.app_id)
            self.path = deploy_path_obj.path
        except DeployPath.DoesNotExist:
            self.ie('找不到%s的对应的发布路径!' % self.app_id)
        except DeployPath.MultipleObjectsReturned:
            self.ie('%s对应多个发布路径!' % self.app_id)
        self.cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION']+'2'})

    def auto_publish(self):
        if self.require == 0:
            msg = '非tomcat的POOL，不需要进行tomcat配置初始化'
            self.i(msg)
            return {'exc_message': msg}
        # 检查初始化情况
        os.chdir(os.path.join(BASE_DIR, 'deploy/inittomcat/'))
        os.chmod('inittomcat', stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        status, output = commands.getstatusoutput('./inittomcat -d %s -i %s' % (self.path, self.ip))
        status = not bool(status)
        msg = u'初始化tomcat配置%s：%s' % (STATUS_MAPPING[status], output)
        if not status:
            self.ie(msg)
        else:
            self.i(msg)
            return {'exc_message': msg}

    def ie(self, log):
        self.i('修改服务器状态为预上线失败')
        self.server_obj.server_status_id = 230
        self.server_obj.save()
        self.i(log, error=True)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.task_id, log, error)