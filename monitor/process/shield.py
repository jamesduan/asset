# -*- coding: utf-8 -*-
from django.db import connections
from server.models import Server
from monitor.models import EventFilter
from django.db.models import Q
import time


class Shield(object):
    def filter(self):
        pass


class NotificationShield(Shield):
    def filter(self, _ip, _message, _source_id, _type_id, _level_id, _pool_id):
        # -_- 没必要，肯定有参数是填了的
        # r = map(lambda x: True if x else False, [ip, message, source_id, type_id, level_id, pool_id])
        # if True not in r:
        #     return False

        now = int(time.time())

        res = EventFilter.objects.filter(
            Q(status=1, end_time__gte=now, start_time__lte=now) |
            Q(status=1, end_time__lte=-1, start_time__lte=now)
        )
        if not res:
            return False
        else:
            try:
                if _ip:
                    tmp_ip = _ip.split(',')[0]
                    tmp_res = Server.objects.filter(ip=tmp_ip).exclude(server_status_id=400)
                    if tmp_res:
                        _pool_id = tmp_res[0].app_id
                for i in res:
                    filter_count = 0
                    keyword = i.keyword
                    ip = i.ip
                    source_id = i.source_id
                    pool_id = i.pool_id
                    type_id = i.type_id
                    level_id = i.level_id
                    is_alarm = i.is_alarm

                    if keyword:
                        filter_count += 1
                    if ip:
                        filter_count += 1
                    if source_id > 0:
                        filter_count += 1
                    if pool_id > 0:
                        filter_count += 1
                    if type_id > 0:
                        filter_count += 1
                    if level_id > 0:
                        filter_count += 1

                    if filter_count == 0:
                        continue

                    find_count = 0
                    if ip and _ip and _ip.find(ip) > -1:
                        find_count += 1

                    if keyword and _message and _message.find(keyword) > -1:
                        find_count += 1
                    if _source_id == source_id:
                        find_count += 1
                    if _pool_id == pool_id:
                        find_count += 1
                    if _type_id == type_id:
                        find_count += 1
                    if _level_id == level_id:
                        find_count += 1

                    if filter_count == find_count:
                        return True, is_alarm

                return False
            except Exception, e:
                raise e