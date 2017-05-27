# -*- coding: utf-8 -*-
'''
    @description:   方法级的调用

    @copyright:     ©2013 yihaodian.com
    @author:        jackie
    @since:         13-12-23
    @version:       0.1
    @author:        jackie
'''
from assetv2.celeryapi import *
import tasks
import time, logging
import json

logger = logging.getLogger('django')

#基础方法
def collect_data(data):
    try:
        logger.info("getting data -> " + json.dumps(data))
        result = tasks.collect.delay(data)
        logger.info("wrote changes to broker done.")
        logger.info("task_id : " + result.id + " task_name: " + result.task_name)
    except Exception as e:
        print e
        logger.error(__name__ + ": " + str(e))

#主机管理相关
def CB_server_createvm(ip, username, message):
    _collect('server', 'createvm', ip, message, username)


#IP库管理相关
def CB_ip_createip_bycreatevm(ip, username, message):
    _collect('ip', 'createip_createvm', ip, message, username)


def CB_ip_deleteip_bychangevm(ip, username):
    _collect('ip', 'deleteip_changeserver', ip, 'IP库->修改服务器IP引起的删除操作', username)


def CB_ip_createmgip_bychangevm(ip, username):
    _collect('ip', 'createmgip_changeserver', ip, 'IP库->修改服务器管理IP引起的新增操作', username)


def CB_ip_createip_by_createasset(ip, username):
    _collect('ip', 'createip_createasset', ip, 'IP库->新增IP', username)


def CB_ip_unbind_by_changeasset(assetid, username, message):
    _collect('ip', 'unbind_changeasset', assetid, message, username)


def CB_ip_bind_by_changeasset(assetid, username, message):
    _collect('ip', 'bind_changeasset', assetid, message, username)


def CB_mgip_unbind_by_changeasset(assetid, username, message):
    _collect('mgip', 'unbind_changeasset', assetid, message, username)


def CB_mgip_bind_by_changeasset(assetid, username, message):
    _collect('mgip', 'bind_changeasset', assetid, message, username)


def CB_ip_unbind_by_deleteasset(assetid, username, message):
    _collect('ip', 'unbind_deleteasset', assetid, message, username)


def CB_mgip_unbind_by_deleteasset(assetid, username, message):
    _collect('mgip', 'unbind_deleteasset', assetid, message, username)


def CB_ip_bindip_by_initasset(ip, username, message):
    _collect('ip', 'bind_initasset', ip, message, username)

def CB_mgip_bindip_by_initasset(ip, username, message):
    _collect('mgip', 'bind_initasset', ip, message, username)

def CB_ip_unbind_by_scrapserver(ip, username, message):
    _collect('ip', 'unbind_scrapserver', ip, message, username)

def CB_ip_unbind_by_scrapoffserver(ip, username, message):
    _collect('ip', 'unbind_scrapoffserver', ip, message, username)

#主机管理相关
def CB_server_predeploy(ip, username, message, app_id=0):
    logger.info("excuting CB_server_predeploy...")
    _collect('server', 'predeploy', ip, message, username, app_id=app_id)

def CB_server_deploy(ip, username, message, app_id=0):
    logger.info("excuting CB_server_deploy...")
    _collect('server', 'deploy', ip, message, username, app_id=app_id)

def CB_server_predeployfail_to_using(ip, username, message, app_id=0):
    logger.info("excuting CB_server_predeployfail_to_using...")
    _collect('server', 'deployfail_to_using', ip, message, username, app_id=app_id)

def CB_server_predeployfail_to_maintain(ip, username, message, app_id=0):
    logger.info("excuting CB_server_predeployfail_to_maintain...")
    _collect('server', 'deployfail_to_maintain', ip, message, username, app_id=app_id)

def CB_server_redeploy(ip, username, message):
    logger.info("excuting CB_server_redeploy...")
    _collect('server', 'redeploy', ip, message, username)

def CB_zabbix_add(ip, username, app_id=0):
    logger.info("excuting CB_zabbix_add...")
    _collect('zabbix', 'add', ip, 'zabbix->上架成功，开启监控', username, app_id=app_id)

def CB_zabbix_enable(ip, username):
    logger.info("excuting CB_zabbix_enable..")
    _collect('zabbix', 'enable', ip, 'zabbix->开启监控', username)

def CB_zabbix_disable(ip, username, app_id=0):
    logger.info("excuting CB_zabbix_disable...")
    _collect('zabbix', 'disable', ip, 'zabbix->屏蔽监控', username, app_id=app_id)

def CB_zabbix_delete(ip, username):
    logger.info("excuting CB_zabbix_delete...")
    _collect('zabbix', 'delete', ip, 'zabbix->删除监控', username)

def CB_zabbix_free(ip, username):
    logger.info("excuting CB_zabbix_free...")
    _collect('zabbix', 'free', ip, 'zabbix->主机空闲，开启监控', username)

def CB_server_trash(ip, username, message):
    _collect('server', 'trash', ip, message, username)

def CB_server_maintain(ip, username, message, app_id=0):
    logger.info("excuting CB_server_maintain...")
    _collect('server', 'maintain', ip, message , username, app_id=app_id)

def CB_server_maintainfinish(ip, username, message, app_id=0):
    logger.info("excuting CB_server_maintainfinish...")
    _collect('server', 'maintainfinish', ip, message , username, app_id=app_id)

def CB_server_recycle(ip, username, messages):
    logger.info("excuting CB_server_recycle...")
    _collect('server', 'recycle', ip, messages, username)

def CB_server_resetinstall(ip, username):
    logger.info("excuting CB_server_resetinstall...") 
    _collect('server', 'resetinstall', ip, '服务器->置为待装机', username)

def CB_server_installing(ip, username):
    logger.info("excuting CB_server_installing...") 
    _collect('server', 'installing', ip, '服务器->安装中', username)

def CB_server_installed(ip, username):
    logger.info("excuting CB_server_installed...") 
    _collect('server', 'installed', ip, '服务器->成功安装', username)

def CB_server_installfailure(ip, username):
    logger.info("excuting CB_server_installfailure...") 
    _collect('server', 'installfailure', ip, '服务器->安装失败', username)

def CB_server_bindpuppetmodule(ip, username):
    logger.info("excuting CB_server_bindpuppetmodule...") 
    message = "服务器->新增PUPPET模块"
    _collect('server', 'bindpuppetmodule', ip, message, username)


def CB_server_bindtag(ip, username):
    _collect('server', 'bindtag', ip, '服务器->打标记', username)


def CB_server_changetemplate(ip, username):
    _collect('server', 'changetemplate', ip, '服务器->改变装机模板', username)


def CB_server_deleterecord(ip, username):
    _collect('server', 'deleterecord', ip, '服务器->删除虚拟机记录', username)


def CB_server_deletemachine(ip, username):
    _collect('server', 'deletermachine', ip, '服务器->删除虚拟机服务器', username)


def CB_server_restartvm(ip, username):
    _collect('server', 'restartvm', ip, '服务器->重启服务器', username)


def CB_server_create_bycreateasset(ip, username, message):
    _collect('server', 'create', ip, message, username)


def CB_server_edit_byeditasset(ip, username, message):
    _collect('server', 'edit', ip, message, username)


def CB_server_bindip_by_changeasset(assetid, username, message):
    _collect('server', 'bindip', assetid, message, username)

def CB_server_unbindip_by_changeasset(assetid, username, message):
    _collect('server', 'unbindip', assetid, message, username)

def CB_server_bindmgip_by_changeasset(assetid, username, message):
    _collect('server', 'bindmgip', assetid, message, username)

def CB_server_unbindmgip_by_changeasset(assetid, username, message):
    _collect('server', 'unbindmgip', assetid, message, username)

#设备管理相关


def CB_asset_create(assetid, username, message):
    _collect('asset', 'create', assetid, message, username)


def CB_asset_delete(assetid, username, message):
    _collect('asset', 'delete', assetid, message, username)


def CB_asset_change(assetid, username, message):
    _collect('asset', 'change', assetid, message, username)


def CB_rack_deletasset(assetid, username, message):
    _collect('rack', 'clearunitno', assetid, message, username)


def CB_rack_deploy(assetid, username, message):
    _collect('rack', 'deploy', assetid, message, username)


def CB_rack_move(assetid, username, message):
    _collect('rack', 'move', assetid, message, username)


# 站点/应用
def CB_site_create(siteid, username, message, action='create'):
    if action == 'create':
        _collect('site', 'create', siteid, message, username)
    else:
        _collect('site', 'change', siteid, message, username)


def CB_site_delete(siteid, username, message):
    _collect('site', 'delete', siteid, message, username)


def CB_app_create(appid, username, message, action='create'):
    if action == 'create':
        _collect('app', 'create', appid, message, username, app_id=appid)
    else:
        _collect('app', 'change', appid, message, username, app_id=appid)


def CB_app_delete(appid, username, message):
    _collect('app', 'delete', appid, message, username, app_id=appid)

def block_cc_create(username, index, message):
    _collect('block_cc', 'create',  index, message, username)

def block_cc_change(username, index, message):
    _collect('block_cc', 'change', index, message, username)


def soa_group_add(username, index, message, app_id):
    _collect('soa_group', 'create', index, message, username, app_id)


def soa_group_del(username, index, message, app_id):
    _collect('soa_group', 'delete', index, message, username, app_id)


def soa_server_add(username, index, message, app_id):
    _collect('soa_server', 'create', index, message, username, app_id)


def soa_server_del(username, index, message, app_id):
    _collect('soa_server', 'delete', index, message, username, app_id)

def RL_all_deploy(username, index, message, app_id):
    _collect('release', 'all_deploy', index, message, username, app_id)

def RL_normal_deploy(username, index, message, app_id):
    _collect('release', 'normal_deploy', index, message, username, app_id)

def RL_gray_deploy(username, index, message, app_id):
    _collect('release', 'gray_deploy', index, message, username, app_id)

# 私有方法
def _collect(type, action, index, message, user, level='change', app_id=0):
    collect_data({
        'type':  type,
        'action': action,
        'index': index,
        'level': level,
        'message': message,
        'happen_time': time.strftime("%Y-%m-%d %X", time.localtime()),
        'user': user,
        'app_id': app_id
    })