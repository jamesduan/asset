# -*- coding: utf-8 -*-
from deploy.utils.DeployCommon import *
from assetv2.settingsdeploy import *
from datetime import datetime
import math
import time


class ConfigDeploy():
    def __init__(self, depid=None, interval=DEPLOY_INTERVAL):
        self.room_ids = []
        self.depid = depid
        self.deploy = DeployMainConfig.objects.get(depid=depid)
        self.app = self.deploy.app
        self.site = self.app.site if self.app else None
        self.alone = not DeployMain.objects.filter(jiraid=self.deploy.jiraid, app_id=self.deploy.app_id, packtype=0).exists()
        self.cache = get_cache('deploy')
        self.pattern = get_process_pattern_by_app_id(self.deploy.app_id)
        self.interval = interval
        self.ip_list = []

        if self.deploy.idc:
            self.room_ids = TRIDENT_CMDB_IDC_MAPPING[self.deploy.idc]
        else:
            self.room_ids = [self.deploy.zone_id]

    def health_check(self):
        self.i('检查HealthCheck是否设置')
        url = HC['PREFIX'] + HC['API'].format(self.deploy.app_id)
        fp = urllib2.urlopen(url)
        result = json.loads(fp.read())
        return result['data']['isSetHealthCheck']

    def set_healthcheck(self, status=1):
        status, url, msg = set_healthcheck(self.ip_list, status)
        output = ':'.join([msg, url])
        if status:
            self.i(output)
        else:
            self.ie(output)

    def auto_publish(self):
        # 检查HealthCheck是否设置
        if not self.health_check():
            self.ie('HealthCheck有问题，请检查是否设置HealthCheck')
        if self.deploy.status != 1:
            self.i(set_color('不是待发布状态，不能发布'))
            return False
        if is_locked(self.deploy):
            self.i(set_color('当前发布或者回滚被锁住'))
            return False
        lock_it(self.deploy)
        time.sleep(3)
        # if not ycc_validate(self.deploy):
        #     return False
        if self.deploy.gray_release_info:
            self.deploy_detail_init_gray()
            return self.gray_deploy()
        else:
            self.deploy_detail_init_normal()
            return self.normal_deploy()

    def rollback(self):
        if self.deploy.status != 2:
            self.i(set_color('不是已发布状态，不能回滚'))
            return False
        if is_locked(self.deploy):
            self.i(set_color('当前发布或者回滚被锁住'))
            return False
        else:
            lock_it(self.deploy)
        time.sleep(3)
        if not ycc_rollback2(self.deploy):
            unlock_it(self.deploy)
            return False
        if self.deploy.restart and self.alone:
            obj_queryset = DeployDetailConfig.objects.filter(depid=self.depid, real_time__isnull=False).order_by('id')
            last_obj_id = obj_queryset.last().id
            for obj in obj_queryset:
                self.service_restart(obj.server.ip)
                obj.rollback_time = datetime.now()
                obj.save()
                if obj.id != last_obj_id:
                    self.i('等待%s秒' % self.interval)
                    time.sleep(self.interval)
        self.deploy.status = 3
        self.deploy.save()
        unlock_it(self.deploy)

    def ie(self, log):
        self.i(log, error=True)
        unlock_it(self.deploy)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.depid, log, error)

    def deploy_detail_init_gray(self):
        gray_stage = 0
        for percent in self.deploy.gray_release_info.split(','):
            if int(percent) == 0:
                continue
            gray_stage += 1
            server_obj_queryset = Server.objects.filter(app_id=self.deploy.app_id, server_status_id=200, server_env_id=2)
            server_obj_queryset = filter(lambda x: get_room_obj_by_server_obj(x).id in self.room_ids, server_obj_queryset)
            for server_obj in server_obj_queryset[:int(math.ceil(len(server_obj_queryset)*int(percent)/float(100)))]:
                DeployDetailConfig.objects.get_or_create(
                    depid=self.depid,
                    server=server_obj,
                    defaults={
                        'gray_stage': gray_stage
                    })

    def deploy_detail_init_normal(self):
        server_obj_queryset = Server.objects.filter(app_id=self.deploy.app_id, server_status_id=200, server_env_id=2)
        server_obj_queryset = filter(lambda x: get_room_obj_by_server_obj(x).id in self.room_ids, server_obj_queryset)
        for server_obj in server_obj_queryset:
            DeployDetailConfig.objects.get_or_create(
                depid=self.depid,
                server=server_obj
            )

    def gray_deploy(self):
        black_list = [obj.server.ip for obj in DeployDetailConfig.objects.filter(depid=self.depid) if obj.room.id in self.room_ids]
        if not ycc_black(self.deploy, black_list, None):
            unlock_it(self.deploy)
            return False
        if not ycc_deploy2(self.deploy):
            unlock_it(self.deploy)
            return False
        if not self.alone:
            self.deploy.status = 2
            self.deploy.save()
            unlock_it(self.deploy)
            return True
        gray_stage_list = [obj['gray_stage'] for obj in DeployDetailConfig.objects.filter(depid=self.depid, real_time__isnull=True).values('gray_stage').distinct()]
        gray_stage_list.sort()
        for gray_stage in gray_stage_list:
            self.i('灰度第%s阶段开始' % gray_stage)
            white_list = [obj.server.ip for obj in DeployDetailConfig.objects.filter(depid=self.depid, gray_stage__lte=gray_stage) if obj.room.id in self.room_ids]
            black_list = [obj.server.ip for obj in DeployDetailConfig.objects.filter(depid=self.depid, gray_stage__gt=gray_stage) if obj.room.id in self.room_ids]
            if not ycc_black(self.deploy, black_list, white_list):
                unlock_it(self.deploy)
                return False
            if self.deploy.restart:
                self.ip_list = white_list
                self.set_healthcheck(1)
                obj_queryset = DeployDetailConfig.objects.filter(depid=self.depid, gray_stage=gray_stage, real_time__isnull=True).order_by('id')
                for obj in obj_queryset:
                    self.service_restart(obj.server.ip)
                    obj.real_time = datetime.now()
                    obj.save()
                    if DeployDetailConfig.objects.filter(depid=self.depid, gray_stage=gray_stage, real_time__isnull=True):
                        self.i('等待%s秒' % self.deploy.restart_interval)
                        time.sleep(self.deploy.restart_interval)
            self.i('灰度第%s阶段结束' % gray_stage)
            if gray_stage != gray_stage_list[-1]:
                unlock_it(self.deploy)
                self.i('等待%s分钟' % self.deploy.gray_stage_interval)
                time.sleep(self.deploy.gray_stage_interval*60)
                lock_it(self.deploy)
        self.i('灰度结束')
        self.deploy.status = 2
        self.deploy.save()
        if self.deploy.restart and self.alone:
            time.sleep(HUDSON_DELAY)
            self.set_healthcheck(0)
        unlock_it(self.deploy)
        return True

    def normal_deploy(self):
        white_list = [obj.server.ip for obj in DeployDetailConfig.objects.filter(depid=self.depid) if obj.room.id in self.room_ids]
        if not ycc_black(self.deploy, None, white_list):
            unlock_it(self.deploy)
            return False
        if not ycc_deploy2(self.deploy):
            unlock_it(self.deploy)
            return False
        if self.deploy.restart and self.alone:
            self.ip_list = white_list
            self.set_healthcheck(1)
            obj_queryset = DeployDetailConfig.objects.filter(depid=self.depid, real_time__isnull=True).order_by('id')
            for obj in obj_queryset:
                self.service_restart(obj.server.ip)
                obj.real_time = datetime.now()
                obj.save()
                if DeployDetailConfig.objects.filter(depid=self.depid, real_time__isnull=True):
                    self.i('等待%s秒' % self.deploy.restart_interval)
                    time.sleep(self.deploy.restart_interval)
        self.deploy.status = 2
        self.deploy.save()
        if self.deploy.restart and self.alone:
            time.sleep(HUDSON_DELAY)
            self.set_healthcheck(0)
        unlock_it(self.deploy)
        return True

    def service_restart(self, ip):
        server_obj = Server.objects.filter(server_status_id=200, ip=ip).first()
        if server_obj is None:
            self.i('重启：[%s]重启忽略，该机器处于非使用中状态' % ip)
            return
        # 回滚前将服务下线
        for log in detector_method(server_obj, 'disabled'):
            self.i(log)
        application_restart(ip, self.pattern, self.cache, self.depid)
