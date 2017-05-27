# -*- coding: utf-8 -*-
from server.models import Server
from util.httplib import httpcall2
from django.conf import settings
from django.core.cache import get_cache
from deploy.utils.DeployError import DeployError
from deploy.utils.DeployCommon import i2
import json


class HaproxyRegistration:
    def __init__(self, ip, haproxy_room, haproxy_group, task_id):
        self.ip = ip
        self.server_obj = Server.objects.exclude(server_status_id=400).get(ip=ip)
        self.app_obj = self.server_obj.app
        self.haproxy_room = haproxy_room
        self.haproxy_group = haproxy_group
        self.task_id = task_id
        self.cache = get_cache('deploy', **{'LOCATION': settings.CACHES['deploy']['LOCATION'] + '2'})

    def register(self):
        self.haproxy(True, 'online', '上架')

    def annotate(self):
        self.haproxy(False, 'update', '临时下架')

    def deannotate(self):
        self.haproxy(True, 'update', '重新上架')

    def unregister(self):
        self.haproxy(None, 'offline', '下架')

    def haproxy(self, in_use, method, action):
        body = {
            'site': self.app_obj.site.name,
            'app': self.app_obj.name,
            'idc': self.haproxy_room,
            'group': self.haproxy_group,
            'ips': [{self.ip: {'inter': '10000', 'maxconn': '500', 'port': '8080', 'weight': 1, 'check': True,
                               'in_use': in_use}}],
            'method': method
        }
        code, response = httpcall2(settings.HAPROXY_REGISTRATION_API, method='POST', body=body)
        if code == 200:
            msg = 'haproxy%s成功(%s:%s)' % (action, self.haproxy_room, self.haproxy_group)
            self.i(msg)
            return msg
        elif code == 503:
            msg = 'haproxy%s失败(%s:%s)，原因为%s' % (action, self.haproxy_room, self.haproxy_group, json.loads(response).get('output'))
            self.ie(msg)
        else:
            msg = 'haproxy%s失败(%s:%s)，原因%s|%s' % (action, self.haproxy_room, self.haproxy_group, code, response)
            self.ie(msg)

    def ie(self, log):
        self.i('修改服务器状态为预上线失败')
        self.server_obj.server_status_id = 230
        self.server_obj.save()
        self.i(log, error=True)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.task_id, log, error)
