# -*- coding: utf-8 -*-
from server.models import ServerStandard
from util.httplib import httpcall2
from django.conf import settings
from django.core.cache import get_cache
from deploy.utils.DeployError import DeployError
from deploy.utils.DeployCommon import i2
import json


class HedwigRegistration:
    def __init__(self, ip, task_id):
        self.ip = ip
        self.server_obj = ServerStandard.objects.exclude(server_status_id=400).get(ip=ip)
        self.app_obj = self.server_obj.app
        self.task_id = task_id
        self.cache = get_cache('deploy', **{'LOCATION': settings.CACHES['deploy']['LOCATION'] + '2'})

    def unregister(self):
        self.hedwig('disabled', '下架')

    def hedwig(self, method, action):
        code, response = httpcall2(settings.DETECTOR['PREFIX'] + settings.DETECTOR['METHOD_API'] % (
            settings.CMDB_DETECTOR_IDC_MAPPING.get(self.server_obj.rack.room_id),
            settings.DETECTOR['SECRET'],
            settings.DETECTOR['SECRET'], self.ip, method))
        if code == 200:
            print code, response
            response = json.loads(response)
            if response.get('result') == '0':
                msg = 'hedwig%s成功' % action
            else:
                msg = 'hedwig%s失败，原因为%s' % (action, response.get('warn'))
            self.i(msg)
            return msg
        else:
            msg = 'hedwig%s失败，原因%s|%s' % (action, code, response)
            self.ie(msg)

    def ie(self, log):
        self.i('修改服务器状态为预上线失败')
        self.server_obj.server_status_id = 230
        self.server_obj.save()
        self.i(log, error=True)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.task_id, log, error)
