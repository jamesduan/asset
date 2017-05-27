# -*- coding: utf-8 -*-
# 废弃
import os
import time
import monitor.assemble.tools as tool
from monitor.models import *


def dingwei(ip, parent_ip, switch_ip, port=0):
    remark = ''
    tag = ''
    line_tag = '@'
    if port:
        res = tool.sys_check(ip, way='nc', port=port)
        if res['code']:
            remark += res['stdout'] + line_tag
        else:
            return {'remark': remark, 'tag': tag}

    res = tool.sys_check(ip)
    if res['code']:
        remark += res['stdout'] + line_tag
        if parent_ip:
            res = tool.sys_check(parent_ip)
            if res['code']:
                remark += res['stdout'] + line_tag
                tag = 'father_alarm'
            else:
                tag = 'server_alarm'
        else:
            tag = 'server_alarm'

        if switch_ip:
            res = tool.sys_check(switch_ip)
            if res['code']:
                remark += res['stdout'] + line_tag
                tag = 'switch_alarm'
    else:
        if port:
            tag = 'tomcat_alarm'

    return {'remark': remark, 'tag': tag}


def process_convergence(queue, cfg):
    """"""
    tag_map = {
        'firewall_alarm': '防火墙有问题',
        'switch_alarm': '交换机有问题',
        'father_alarm': '服务器(宿主机)有问题',
        'server_alarm': '服务器有问题',
        'tomcat_alarm': 'tomcat有问题'
    }

    tmp_list = []
    tmp_time = time.time()
    interval = cfg['interval']
    while True:
        while not queue.empty():
            value = queue.get()
            tag = ''
            remark = ''
            type_id = int(value['type_id'])
            source_id = int(value['source_id'])
            message = value['message']
            title = value['title']
            detail_list = value['detail_list']
            if detail_list:
                pool_id = detail_list[0]['pool_id']
                ip = detail_list[0]['ip']
                parent_ip = detail_list[0]['parent_ip']
                switch_ip = detail_list[0]['switch_ip']

                if type_id == 5 and message.find(u'交换机') > -1:
                    tag = 'switch_alarm'
                # elif type_id == 4 and source_id == 3:  # 服务器|Zabbix 作为定位后的现象收敛
                elif type_id == 7 and source_id == 6:  # HC的
                    res = dingwei(ip, parent_ip, switch_ip)
                    tag, remark = res['tag'], res['remark']
                elif source_id == 2 and message.find(u'tomcat挂') > -1:
                    res = dingwei(ip, parent_ip, switch_ip, 8080)
                    tag, remark = res['tag'], res['remark']
            value['tag'] = tag
            value['remark'] = remark
            tmp_list.append(value)

        length = len(tmp_list)
        # print str(os.getpid()) + ': ' + str(length)

        if time.time() >= tmp_time + interval:
            # print '----' + str(length) + '-------'
            tmp_process = {}
            if length > 0:
                for i in tmp_list:
                    value = i
                    tag = value['tag'] if value['tag'] else '-'
                    # pool_id = value['detail_list'][0]['pool_id']
                    # ip = value['detail_list'][0]['ip']

                    tmp_process.setdefault(tag, []).append(value)

            if tmp_process:
                tmp_sql = []
                for i in tmp_process:
                    l = tmp_process[i]
                    reason = '' if i == '-' else tag_map[i]
                    for v in l:
                        detail_list = v['detail_list']
                        tmp_sql.append(EventIntelligentCreate(
                            interval_time=tmp_time,
                            reason=reason,
                            level_id=v['level_id'],
                            type_id=v['type_id'],
                            source_id=v['source_id'],
                            title=v['title'],
                            message=v['message'],
                            send_to=v['send_to'],
                            caller=v['caller'],
                            create_time=v['create_time'],
                            ip=detail_list[0]['ip'] if detail_list else '',
                            parent_ip=detail_list[0]['parent_ip'] if detail_list else '',
                            switch_ip=detail_list[0]['switch_ip'] if detail_list else '',
                            pool_id=detail_list[0]['pool_id'] if detail_list else 0,
                        ))
                if tmp_sql:
                    EventIntelligentCreate.objects.bulk_create(tmp_sql)

            tmp_time = time.time()
            tmp_list = []
        time.sleep(1)