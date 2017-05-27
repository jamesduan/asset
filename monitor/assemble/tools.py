# -*- coding:utf-8 -*-
import subprocess
import os
import json
import urllib2
import time


def command(cmdstr):
    proc = subprocess.Popen(cmdstr, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    code = proc.returncode
    return code, stdout, stderr


def http_request(url):
    try:
        req = urllib2.Request(url=url)
        res = urllib2.urlopen(req, timeout=2)
        return res.getcode(), res.read()
    except Exception as e:
        return 500, e


def sys_check(ip, c_time=2, way='ping', port=8080):
    if way == 'ping':
        cmdstr = r'''ping -c 2 ''' + ip
    elif way == 'nc':
        cmdstr = r'''nc -z -vv -w 2 ''' + ip + ''' ''' + str(port)

    for i in range(0, c_time):
        code, stdout, stderr = command(cmdstr)
        if code != 1:
            break
        time.sleep(0.1)
    return {'way': way, 'code': code, 'stdout': stdout, 'stderr': stderr}


def hc_check(ip):
    """:status: 1 - 陈功 0 - 失败 -1 - 未设置 """
    url = "http://oms.yihaodian.com.cn/itil/api/?action=health_check&method=healthcheck&ip="
    url += ip
    try:
        req = urllib2.Request(url=url)
        res = urllib2.urlopen(req, timeout=2)
        return res.getcode(), res.read()
    except Exception as e:
        return 500, {}