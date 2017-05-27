# -*- coding: utf-8 -*-
from server.models import Server
from cmdb.models import App
from deploy.models import DeployPath, DeployVersionApp, DeployIDC
from deploy.utils.Utils import ssh, rsync4nocheck
from deploy.utils.DeployCommon import i, application_restart, change, i2, get_process_pattern_by_app_id
from deploy.utils.DeployError import DeployError
from deploy.utils.HedwigRegistration import HedwigRegistration
from assetv2.settingsdeploy import DEPLOY_VERSION_FILE, DEPLOY_CODE_HOST, STATUS_MAPPING, HC, ONLINE_REPORT, \
    DEPLOY_STATIC_APP_ID, CACHES, TICKET, OMS_HOST
from util.httplib import httpcall2
from django.core.cache import get_cache
import os
import time
import json


class SingleDeploy():
    def __init__(self, ip, task_id, restart, uniq_id):
        try:
            server_obj = Server.objects.exclude(server_status_id=400).get(ip=ip)
            if server_obj.app_id == DEPLOY_STATIC_APP_ID:
                self.ie('不支持对静态服务器的一键上架')
            self.server_obj = server_obj
        except Server.DoesNotExist:
            self.ie('找不到%s的对应的服务器!' % ip)
        except Server.MultipleObjectsReturned:
            self.ie('%s对应多个服务器!' % ip)
        room_obj = server_obj.asset.rack.room if server_obj.server_type_id == 1 else server_obj.parent_asset.rack.room
        self.deploy_host = DeployIDC.objects.get(id=room_obj.area_id).host
        self.app_id = server_obj.app_id
        self.app = App.objects.get(id=self.app_id)
        self.ip = ip
        self.task_id = task_id
        self.restart = restart
        self.cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION'] + '2'})
        self.pattern = get_process_pattern_by_app_id(self.app_id)
        self.uniq_id = uniq_id

    def auto_publish(self):
        # if self.server_obj.server_env_id == 1:
        #     self.i('staging没有版本信息')
        #     self.ticket()
        #     return 'staging没有版本信息，不需要重新发布'
        try:
            deploy_path_obj = DeployPath.objects.get(app_id=self.app_id)
        except DeployPath.DoesNotExist:
            self.i('找不到%s/%s的对应的发布路径!' % (self.app.site.name, self.app.name))
            # self.ticket()
            return '对应的发布路径不存在，认为不需要重新发布'
        except DeployPath.MultipleObjectsReturned:
            self.ie('%s/%s对应多个发布路径!' % (self.app.site.name, self.app.name))
        expected_version = self.get_expected_version()
        codepath = '/depot/deployv2/{0}/{1}/{2}/'.format(self.app.site.name, self.app.name, expected_version)
        if self.server_obj.server_env_id == 1:
            self.single_pre_deploy(src=codepath, dst='deploy@%s:%s' % (self.ip, deploy_path_obj.path), category='发布')
        else:
            real_version = self.get_real_version(deploy_path_obj.path)
            self.i('real_version:{0}<br>expected_version:{1}'.format(real_version, expected_version))
            if real_version == expected_version:
                self.i('版本相同，不需要重新发布')
            else:
                deprepath = '/depot/predeploy/{0}/'.format(expected_version)
                self.single_pre_deploy(src=codepath, dst='deploy@%s:%s' % (self.ip, deprepath), category='预发布')
                self.single_deploy(src=deprepath, dst=deploy_path_obj.path.rstrip('/'))
                self.i('成功执行发布')
        if self.restart == 0:
            self.i('不需要重启')
            # self.ticket()
            return '完成部署'
        hedwig_registration = HedwigRegistration(ip=self.ip, task_id=self.task_id)
        hedwig_registration.unregister()
        time.sleep(3)
        application_restart(self.ip, self.pattern, self.cache, self.task_id)
        health, msg = self.health_check()
        if health is None:
            self.ie('health_check失败，原因为%s' % msg)
        elif not health:
            self.ie('未通过health_check检查')
        else:
            # self.ticket()
            return '通过health_check检查'

    def get_real_version(self, path):
        cmd = 'cat %s' % os.path.join(path, DEPLOY_VERSION_FILE)
        status, cmd, output = ssh(cmd, self.ip)
        output_list = output.splitlines()
        return output_list[-1] if status else None

    def get_expected_version(self):
        try:
            # deploy_version_app_obj = DeployVersionApp.objects.get(app=self.app,
            #                                                       app_env_id=self.server_obj.server_env_id, pack_type=0)
            deploy_version_app_obj = DeployVersionApp.objects.get(app=self.app, app_env_id=2, pack_type=0)
            return os.path.basename(deploy_version_app_obj.ftp_path)
        except DeployVersionApp.DoesNotExist:
            self.ie('%s/%s的对应的期望版本不存在!' % (self.app.site.name, self.app.name))
        except DeployVersionApp.MultipleObjectsReturned:
            self.ie('%s/%s对应多个期望版本!' % (self.app.site.name, self.app.name))

    def single_pre_deploy(self, src, dst, category):
        remote_host = None if DEPLOY_CODE_HOST == self.deploy_host else self.deploy_host
        status, cmd, output = rsync4nocheck(src, dst, checksum=True, remote_host=remote_host)
        msg = '%s：[%s]代码传至目录%s。执行命令：%s 执行结果：%s' % (category, self.ip, STATUS_MAPPING[status], cmd, output)
        self.i(msg)
        if not status:
            self.ie('%s失败' % category)

    def single_deploy(self, src, dst):
        status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), self.ip)
        msg = '正式发布：[%s]代码切换到正式环境%s。执行命令：%s 执行结果：%s' % (self.ip, STATUS_MAPPING[status], cmd, output)
        self.i(msg)
        if not status:
            self.ie('正式发布失败')
        else:
            change(user='oms', action='single_deploy', index=self.ip, message=self.task_id)

    def health_check(self):
        health = False
        for retry in range(ONLINE_REPORT['TRIES']):
            url = HC['PREFIX'] + HC['PATH_API'].format(self.ip)
            status, data = httpcall2(url)
            self.i('%s|%s|%s' % (url, status, data))
            try:
                result = json.loads(data)
            except:
                return None, data
            if result['success'] and result['data']['status'] in (-1, 1):
                self.i('通过healthcheck检查，或者没有设置healthcheck')
                health = True
                break
            time.sleep(ONLINE_REPORT['WAIT'])
        return health, None

    def ie(self, log):
        self.i('修改服务器状态为预上线失败')
        self.server_obj.server_status_id = 230
        self.server_obj.save()
        self.i(log, error=True)
        # self.ticket(-1)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.task_id, log, error)

    # def ticket(self, status=1):
    #     if self.uniq_id is None:
    #         return
    #     url = TICKET['PREFIX'] + TICKET['EXPAND_API']
    #     body = {
    #         'uniq_id': self.uniq_id,
    #         'ip': self.ip,
    #         'status': status,
    #         'url': 'http://%s/deploy/single/detail/?task_id=%s&ip=%s' % (OMS_HOST, self.task_id, self.ip)
    #     }
    #     code, response = httpcall2(url, method='POST', body=body)
    #     self.i('|'.join([url, str(code), str(response)]))
