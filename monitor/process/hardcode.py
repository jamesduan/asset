# -*- coding:utf-8 -*-
from monitor.models import *
import time
import re
import urllib2
import json


def curl(url, data=None):
    r = urllib2.Request(url)
    try:
        f = urllib2.urlopen(r, data, timeout=2)
        return json.loads(f.read())
    except Exception, e:
        return e.message


def hardcode_process(*args, **kwargs):
    """所有source是zabbix的都走一遍monitor的特殊逻辑处理"""
    hc_url = "http://oms.yihaodian.com.cn/itil/api/?action=health_check&method=healthcheck&ip="

    source_id = kwargs['source_id']
    message = kwargs['message']
    ip = kwargs['ip']

    # 如果是zabbix来源的
    if source_id == 3:
        if message.find('mon_la') > -1:
            res = Event.objects.filter(
                source_id=3,
                create_time__gt=time.time()-600,
                message__contains='mon_flume_la'
            )
            if res:
                # 如果10分钟前有mon_flume_la 则跳出
                return True

        # tomcat挂掉的报警，先检查hc是否正常，hc正常则忽略该报警
        if message.find('tomcat_stats[alive]') > -1:
            reg = r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'
            ip_list = re.findall(reg, ip)
            if ip_list:
                fail_ips = []
                for i in ip_list:
                    result = curl(hc_url + i)
                    status = result['data']['status']
                    if status < 1:
                        fail_ips.append(i)
                        break

                if not fail_ips:
                    return True
