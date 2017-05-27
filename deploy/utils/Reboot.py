# -*- coding: utf-8 -*-
from deploy.utils.DeployCommon import *
from deploy.models import DeployTicketCelery
from deploy.tasks import *
from assetv2.settingsdeploy import *
from util.timelib import *
from change import tasks
from django.core.cache import get_cache
from celery import group
import math
import json


class Reboot():
    def __init__(self, data, task_id):
        self.data = data
        self.task_id = task_id
        self.gray_dict = dict()
        self.restart_interval = data.get('interval', DEPLOY_INTERVAL)
        self.change_data = {'user': 'ticket', 'type': 'release', 'action': 'restart', 'level': 'change', 'message': data['jiraid']}
        self.server_obj_dict = dict()
        self.cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION']+'2'})
        self.pattern = get_process_pattern_by_app_id(data.get('app_id'))
        self.completed = 0
        self.deploy_ticket_celery, created = DeployTicketCelery.objects.get_or_create(
            ticket_id=data['jiraid'],
            defaults={
                'celery_task_id': task_id
            }
        )
        self.server_obj_queryset = Server.objects.filter(id__in=self.data['server_id_list'].split(',')).order_by('id')
        self.ip_list = [server_obj.ip for server_obj in self.server_obj_queryset]
        for server_obj in self.server_obj_queryset:
            self.server_obj_dict[server_obj] = False
        self.dump_id = data.get('dump_id')

    def auto_reboot(self):
        error_msg = None
        response_code = 1
        self.set_healthcheck(1)
        try:
            if self.data['grayDeployFlag'] == 1:
                server_dict = self.get_server_obj_group_by_room()
                self.init_gray(server_dict)
                if not self.gray_deploy():
                    error_msg = '部分机器重启失败'
            elif self.data['grayDeployFlag'] == 0:
                if not self.normal_deploy():
                    error_msg = '部分机器重启失败'
            elif self.data['grayDeployFlag'] == 2:
                if not self.parallel_deploy():
                    error_msg = '部分机器重启失败'
        except Exception, e:
            error_msg = e.args
            print error_msg
        self.i('重启结束，等待%s秒后开启HealthCheck' % HUDSON_DELAY)
        time.sleep(HUDSON_DELAY)
        self.set_healthcheck(0)
        log_list = self.cache.get(self.task_id)
        log_list = [' '.join([stamp2str(log_dict['create_time']), log_dict['log']]) for log_dict in log_list]
        if error_msg:
            response_code = -1
            log_list.append(str(error_msg))
        url = TICKET['PREFIX']+TICKET['API']
        body = {
            'uniq_id': self.data['jiraid'],
            'code': response_code,
            'detail': json.dumps(log_list)
        }
        code, response = httpcall2(url, method='POST', body=body)
        self.i('{0}|{1}|{2}'.format(url, code, response))
        self.i('流程结束')
        return error_msg or '重启成功'

    def ie(self, log):
        i(log, error=True)

    def i(self, log, error=False):
        i2(self.cache, self.task_id, log, error)

    def get_server_obj_group_by_room(self):
        server_dict = dict()
        for server_obj in self.server_obj_queryset:
            room_obj = get_room_obj_by_server_obj(server_obj)
            server_dict[room_obj] = server_dict.get(room_obj, [])
            server_dict[room_obj].append(server_obj)
        return server_dict

    def init_gray(self, server_dict):
        gray_stage = 0
        for percent in self.data['grayDetailInfo']['grayPercent'].split(','):
            if int(percent) == 0:
                continue
            gray_stage += 1
            for room_obj in server_dict:
                server_obj_list = server_dict[room_obj]
                for server_obj in server_obj_list[:int(math.ceil(len(server_obj_list)*int(percent)/float(100)))]:
                    if self.server_obj_dict.get(server_obj):
                        continue
                    self.gray_dict[gray_stage] = self.gray_dict.get(gray_stage, [])
                    self.gray_dict[gray_stage].append(server_obj)
                    self.server_obj_dict[server_obj] = True

    def gray_deploy(self):
        success = True
        gray_stage_list = self.gray_dict.keys()
        gray_stage_list.sort()
        for gray_stage in gray_stage_list:
            self.i('灰度第%s阶段开始' % gray_stage)
            for server_obj in self.gray_dict[gray_stage]:
                for log in detector_method(server_obj, 'disabled'):
                    self.i(log)
                if not application_restart(server_obj.ip, self.pattern, self.cache, self.task_id, server_obj.id == self.dump_id):
                    success = False
                self.completed += 1
                self.deploy_ticket_celery.percent = self.completed * 100 / len(self.server_obj_dict)
                self.deploy_ticket_celery.save()
                tasks.collect.apply_async((dict(self.change_data, **{'index': server_obj.ip, 'happen_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}),))
                if server_obj != self.gray_dict[gray_stage][-1]:
                    self.i('等待%s秒' % self.restart_interval)
                    time.sleep(self.restart_interval)
            self.i('灰度第%s阶段结束' % gray_stage)
            if gray_stage != gray_stage_list[-1]:
                stage_interval = self.data['grayDetailInfo']['stageInterval']
                self.i('等待%s分钟' % stage_interval)
                time.sleep(stage_interval*60)
        self.i('灰度结束')
        return success

    def normal_deploy(self):
        success = True
        for server_obj in self.server_obj_queryset:
            for log in detector_method(server_obj, 'disabled'):
                self.i(log)
            if not application_restart(server_obj.ip, self.pattern, self.cache, self.task_id, server_obj.id == self.dump_id):
                success = False
            self.completed += 1
            self.deploy_ticket_celery.percent = self.completed * 100 / len(self.server_obj_dict)
            self.deploy_ticket_celery.save()
            tasks.collect.apply_async((dict(self.change_data, **{'index': server_obj.ip, 'happen_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}),))
            if server_obj != self.server_obj_queryset.last():
                self.i('等待%s秒' % self.restart_interval)
                time.sleep(self.restart_interval)
        return success

    def parallel_deploy(self):
        kwargs = {
            'pattern': self.pattern,
            'ticket_id': self.data['jiraid'],
            'task_id': self.task_id,
            'weight': float(100) / self.server_obj_queryset.count()
        }
        result = group(parallel_reboot.s(dict(kwargs, **{'ip': server_obj.ip, 'dump': server_obj.id == self.dump_id})) for server_obj in self.server_obj_queryset)()
        result_list = result.get()
        self.deploy_ticket_celery.percent = 100
        self.deploy_ticket_celery.save()
        return all(result_list)

    def set_healthcheck(self, status=1):
        status, url, msg = set_healthcheck(self.ip_list, status)
        self.i(url)
        if status:
            self.i(msg)
        else:
            self.ie(msg)
