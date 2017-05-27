# -*- coding: utf-8 -*-

import os
import time
import json
import monitor.assemble.tools as tool


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
    if ip:
        res = tool.sys_check(ip)
        if res['code']:
            remark += res['stdout'] + line_tag
            if parent_ip:
                res = tool.sys_check(parent_ip)
                if res['code']:
                    remark += res['stdout'] + line_tag
                    tag = '宿主机问题'
                else:
                    tag = '机器问题'
            else:
                tag = '机器问题'

            if switch_ip:
                res = tool.sys_check(switch_ip)
                if res['code']:
                    remark += res['stdout'] + line_tag
                    tag = '交换机问题'
        else:
            if port:
                tag = 'tomcat问题'

    return {'remark': remark, 'tag': tag}


def get_params(**kwargs):
    # type_id = int(value['type_id'])
    # source_id = int(value['source_id'])
    # message = value['message']
    # title = value['title']
    detail_list = kwargs.get('detail_list', None)
    pool_id = 0
    ip = ''
    parent_ip = ''
    switch_ip = ''
    if detail_list:
        pool_id = detail_list[0].get('pool_id', 0)
        ip = detail_list[0].get('ip')
        parent_ip = detail_list[0].get('parent_ip')
        switch_ip = detail_list[0].get('switch_ip')

    return{'ip': ip, 'pool_id': pool_id, 'parent_ip': parent_ip, 'switch_ip': switch_ip}


def switch_convergence(**kwargs):
    remark = ''
    tag = '交换机问题'
    return {'tag': tag, 'remark': remark}


def ocean_convergence(**kwargs):
    remark = ''
    tag = '海洋合并'
    return {'tag': tag, 'remark': remark}


def hc_convergence(**kwargs):
    p = get_params(**kwargs)
    ip = p.get('ip')
    hc_code, hc_dict = tool.hc_check(ip)
    if hc_code == 200:
        hc_status = json.loads(hc_dict).get('data', {}).get('status')
        if hc_status == 1:
            return {'remark': '', 'tag': 'HC合并'}
        else:
            res = dingwei(ip, p.get('parent_ip'), p.get('switch_ip'))
            if not res['tag']:
                return {'remark': '', 'tag': 'HC合并'}
            else:
                return res
    else:
        return {'remark': 'http错误', 'tag': 'HC合并'}


def tomcat_convergence(**kwargs):
    p = get_params(**kwargs)
    return dingwei(p.get('ip'), p.get('parent_ip'), p.get('switch_ip'), 8080)