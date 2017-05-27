# -*- coding: utf-8 -*-
from assetv2.settingsdeploy import *
from asset.models import Room
from django.contrib.auth.models import User
from celery import Celery
from django.conf import settings
from util.httplib import httpcall2
from deploy.models import *
from deploy.utils.DeployError import DeployError
from deploy.utils.Utils import *
from django.core.cache import get_cache
from datetime import datetime
# from change import tasks
import json
import redis
import urllib2
import stat
from assetv2.celeryapi import *
from change.utiltask import RL_all_deploy, RL_normal_deploy, RL_gray_deploy

cache_list = [get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION']+str(db)}) for db in range(3)]

def ie(key, log, db=0):
    i(key, log, error=True, db=db)
    raise DeployError(log)


def i(key, log, error=False, db=0):
    i2(cache_list[db], key, log, error)


def i2(cache, key, log, error=False):
        log_dict = {
            'create_time': int(time.time()),
            'log': log,
            'error': error
        }
        if cache.has_key(key):
            cache.incr(key, [log_dict])
        else:
            cache.set(key, [log_dict])


def trident_callback(deploy, status):
    is_webapp_deploy = False
    is_config_deploy = False

    if deploy.__class__.__name__ == 'DeployMain':
        is_webapp_deploy = True
    elif deploy.__class__.__name__ == 'DeployMainConfig':
        is_config_deploy = True

    deploy.status = status
    deploy.last_modified = int(time.time())
    deploy.save()

    username = User.objects.get(pk=deploy.uid).username
    index = deploy.depid
    app_id = deploy.app_id

    deploy_detail_url = DEPLOY_DETAIL_URL % (OMS_HOST, deploy.depid) if is_webapp_deploy else DEPLOY_YCC_DETAIL_URL % (OMS_HOST, deploy.depid)

    if is_webapp_deploy:
        deploy_type_msg = '-'.join(["程序发布", deploy.deptype_name, deploy.packtype_name]) 
    elif is_config_deploy:
        deploy_type_msg = '-'.join(['配置发布', deploy.zone.name_ch])

    message = """ 单号: <a href="%s" target="_blank">%s</a> 发布类型为: %s 更改状态为: %s """ % (deploy_detail_url, deploy.depid, deploy_type_msg, deploy.status_name)
    RL_all_deploy(username, index, message, app_id)

    if deploy.uid != 523:
        return
    depid = deploy.depid
    # depResult = TRIDENT['STATUS_MAPPING'].get(deploy.__class__.__name__, dict()).get(deploy.status, 0)
    # depResult = deploy.status
    if is_webapp_deploy:
        depResult = deploy.status
    elif is_config_deploy:
        depResult = {2: 4, 3: 5, 7: 7}.get(deploy.status, 0)
    checkcode = md5('{0}{1}OJIMRAS'.format(depid, depResult)).hexdigest()
    url = TRIDENT['PREFIX']+TRIDENT['CALLBACK_API'].format(depid, depResult, checkcode)
    code, data = httpcall2(url)
    i(deploy.depid, '调用trident接口的结果：%s|%s|%s' % (url, code, data))

def get_publish_server(depid, app_id, env_id=None):
    deploy = DeployMain.objects.get(depid=depid)
    server_list = []
    filters = dict()
    filters['app_id'] = app_id
    filters['server_env_id'] = env_id
    filters['server_status_id'] = 200
    if env_id == 1 and deploy.srcs:
        filters['ip__in'] = deploy.srcs.split(',')
    elif env_id == 2 and deploy.dets:
        filters['ip__in'] = deploy.dets.split(',')
    servers = Server.objects.filter(**filters)
    for srv in servers:
        if srv.ip:
            server_dict = dict()
            server_dict['ip'] = srv.ip
            room_obj = srv.asset.rack.room if srv.server_type_id == 1 else srv.parent_asset.rack.room
            server_dict['room'] = room_obj.id
            server_dict['idc'] = room_obj.area_id
            server_dict['deploy_host'] = DeployIDC.objects.get(id=room_obj.area_id).host
            server_dict['server_env_id'] = srv.server_env_id
            server_dict['server_status_id'] = srv.server_status_id
            server_list.append(server_dict)
    return server_list


def single_backup(deploy_detail):
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    if not path_exists(deploy.path, deploy_detail.host):
        status, cmd, output = mkdir(deploy.path, deploy_detail.host)
        if not status:
            unlock_it(deploy)
            ie(deploy.depid, '预发布：[%s]发布路径创建失败。执行命令：%s，执行结果：%s' % (deploy_detail.host, cmd, output))
    if deploy.last_ftpath:
        last_version = os.path.basename(deploy.last_ftpath)
        last_deprepath = os.path.join(os.path.dirname(deploy.deprepath), last_version)
        if path_exists(last_deprepath, deploy_detail.host):
            i(deploy.depid, '备份：[{0}]{1}已经存在，不需要备份'.format(deploy_detail.host, last_deprepath))
        else:
            _single_backup(deploy, deploy_detail, last_deprepath)
    else:
        _single_backup(deploy, deploy_detail, None)
    deploy_detail.has_backup = 1
    deploy_detail.backup_time = int(time.time())
    deploy_detail.save()


def _single_backup(deploy, deploy_detail, last_deprepath):
    src = deploy.path.rstrip('/') + '/'
    dst = last_deprepath if last_deprepath else deploy.backup
    if not path_exists(dst, deploy_detail.host):
        status, cmd, output = mkdir(dst, deploy_detail.host)
        if not status:
            unlock_it(deploy)
            ie(deploy.depid, '预发布：[%s]备份路径创建失败。执行命令：%s，执行结果：%s' % (deploy_detail.host, cmd, output))
    status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, remote_host=deploy_detail.host)
    msg = '预发布：[%s]备份代码%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        unlock_it(deploy)
        ie(deploy.depid, msg)
    else:
        i(deploy.depid, msg)


def single_pre_deploy(deploy_detail):
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    src = deploy.codepath.rstrip('/') + '/'
    dst = 'deploy@%s:%s' % (deploy_detail.host, deploy.deprepath)
    remote_host = None if DEPLOY_CODE_HOST == deploy_detail.deploy_host else deploy_detail.deploy_host
    status, cmd, output = rsync4nocheck(src, dst, checksum=True, remote_host=remote_host)
    msg = '预发布：[%s]代码传至预发布目录%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        unlock_it(deploy)
        ie(deploy.depid, set_color(msg))
    i(deploy.depid, msg)
    deploy_detail.has_pre = 1
    deploy_detail.pre_time = int(time.time())
    deploy_detail.save()


def single_deploy(deploy_detail):
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    src = deploy.deprepath.rstrip('/')
    dst = deploy.path.rstrip('/')
    if deploy.packtype == 0:
        status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), deploy_detail.host)
    else:
        src += '/'
        status, cmd, output = ssh('test -L %s && rm -f %s' % (dst, dst), deploy_detail.host)
        if status:
            i(deploy.depid, '正式发布：[%s]工作目录为软链接，需要删除。执行命令：%s 执行结果：%s###' %(deploy_detail.host, cmd, output))
            backup = os.path.join(os.path.dirname(deploy.deprepath), os.path.basename(deploy.last_ftpath)) if deploy.last_ftpath else deploy.backup
            backup += '/'
            status, cmd, output = rsync4nocheck(backup, dst, host_key_checking=False, checksum=True, remote_host=deploy_detail.host)
            msg = '正式发布：[%s]将备份还原到正式环境%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
            if not status:
                unlock_it(deploy)
                ie(deploy.depid, msg)
            i(deploy.depid, msg)
        status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, checksum=True, hotfix=True, remote_host=deploy_detail.host)
    msg = '正式发布：[%s]代码切换到正式环境%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        unlock_it(deploy)
        ie(deploy.depid, msg)
    i(deploy.depid, msg)
    deploy_detail.has_real = 1
    deploy_detail.real_time = int(time.time())
    deploy_detail.complete = 1
    deploy_detail.save()
    if deploy.restart:
        application_restart(deploy_detail.host, get_process_pattern_by_app_id(deploy.app_id), cache_list[0], deploy.depid)
    action = u'gray_deploy' if deploy.is_gray_release else u'normal_deploy'
    change(user=deploy.user.username if deploy.user else None, action=action, index=deploy_detail.host, message=deploy.depid)


def tomcat_restart(host, deploy, db=0):
    status, pid_list = _tomcat_pid_list(host)
    _tomcat_restart(host, deploy, db)
    times = 0
    while times < 15:
        time.sleep(2)
        status, new_pid_list = _tomcat_pid_list(host)
        if new_pid_list and all([pid not in pid_list for pid in new_pid_list]):
            return True
        times += 1
    _tomcat_restart(host, deploy, db)
    times = 0
    while times < 30:
        time.sleep(2)
        status, new_pid_list = _tomcat_pid_list(host)
        if new_pid_list and all([pid not in pid_list for pid in new_pid_list]):
            return True
        times += 1
    _tomcat_restart(host, deploy, db)


def _tomcat_restart(host, deploy, db):
    cmd = 'export LANG=en_US.UTF-8; /bin/bash /depot/boot.sh'
    status, cmd, output = ssh(cmd, host)
    i(deploy, '重启%s 结果：%s' % (cmd, output), db=db)


def _tomcat_pid_list(host):
    cmd = "ps -C java u --cols=1500|grep tomcat|awk '{print \$2}'"
    status, cmd, output = ssh(cmd, host)
    pid_list = []
    if status:
        pid_list = [pid.strip() for pid in output.split() if pid.strip().isdigit()]
    return status, pid_list


def deploy_detail_init(deploy):
    app_id = DEPLOY_PACKTYPE_APP_ID_MAPPING.get(deploy.packtype, deploy.app_id)
    src_server_list = get_publish_server(deploy.depid, app_id, 1)
    src_server_list = [src_server for src_server in src_server_list if src_server['idc'] == 1]
    dst_server_list = get_publish_server(deploy.depid, app_id, 2)
    for server in src_server_list + dst_server_list:
        if server['server_status_id'] == 200:
            DeployDetail.objects.get_or_create(
                depid=deploy.depid,
                host=server['ip'],
                defaults={
                    'deploy_host': server['deploy_host'],
                    'is_source': 1 if server['server_env_id'] == 1 else 0
                })
        else:
            DeployDetail.objects.filter(host=server['ip']).delete()


def deploy_detail_list(depid, is_source=0, has_real=None, has_rollback=None):
    filters = dict()
    filters['depid'] = depid
    filters['is_source'] = is_source
    if has_real is not None:
        filters['has_real'] = has_real
    if has_rollback is not None:
        filters['has_rollback'] = has_rollback
    return DeployDetail.objects.filter(**filters).order_by('id')


def is_locked(deploy):
    return deploy.in_progress


def lock_it(deploy):
    i(deploy.depid, set_color('对发布或者回滚进行加锁'))
    deploy.in_progress = True
    deploy.save()


def unlock_it(deploy):
    i(deploy.depid, set_color('对发布或者回滚进行解锁'))
    deploy.in_progress = False
    deploy.save()


def change(user=None, action=None, index=None, message=None, url=CHANGE_API['URL'], type="release", level="change"):
    happen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = {
        "user": user,
        "type": type,
        "action": action,
        "index": index,
        "message": message,
        "level": level,
        "happen_time": happen_time
    }
    httpcall2(url, method="POST", body=body, username=CHANGE_API["USERNAME"], password=CHANGE_API["PASSWORD"])


def latest_staging_version(deploy):
    latest_ftp_path = Deployv3StgMain.objects.filter(app_id=deploy.app_id, status=2, deploy_type=deploy.packtype).order_by('-id')[0].source_path
    return latest_ftp_path if deploy.ftpath != latest_ftp_path else None


def ycc_validate(deploy):
    url = YCC['PREFIX']+YCC['VALIDATE_API'].format(Room.objects.get(id=deploy.zone_id).ycc_code, deploy.app.site.name, deploy.app.name)
    code, response = httpcall2(url)
    i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, "有待发配置，可以继续发布")
        return True
    else:
        i(deploy.depid, '无待发配置，停止发布，原因为{0}'.format(response.get("msg")))
        trident_callback(deploy, 6)
        return False


def ycc_deploy(deploy, true_list, false_list):
    i(deploy.depid, 'ycc发布开始')
    url = YCC['PREFIX']+YCC['DEPLOY_API'].format(Room.objects.get(id=deploy.zone_id).ycc_code, deploy.app.site.name, deploy.app.name)
    if true_list or false_list:
        body = {
            'ipList': ','.join(['{0}:true'.format(ip) for ip in true_list] + ['{0}:false'.format(ip) for ip in false_list])
        }
        code, response = httpcall2(url, method='POST', body=body)
        i(deploy.depid, "{0}|{1}|{2}|{3}".format(url, body['ipList'], code, response))
    else:
        code, response = httpcall2(url)
        i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, 'ycc发布结束')
        trident_callback(deploy, 2)
        return True
    else:
        i(deploy.depid, 'ycc发布失败，失败原因为{0}，请联系liushuansheng'.format(response.get("msg")))
        trident_callback(deploy, 4)
        return False


def ycc_rollback(deploy):
    i(deploy.depid, 'ycc回滚开始')
    url = YCC['PREFIX']+YCC['ROLLBACK_API'].format(Room.objects.get(id=deploy.zone_id).ycc_code, deploy.app.site.name, deploy.app.name)
    code, response = httpcall2(url)
    i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, 'ycc回滚结束')
        trident_callback(deploy, 3)
        return True
    else:
        i(deploy.depid, 'ycc回滚失败，失败原因为{0}，请联系请联系liushuansheng'.format(response.get("msg")))
        trident_callback(deploy, 5)
        return False


def ycc_black(deploy, black_list, white_list):
    i(deploy.depid, '设置YCC黑白名单')
    url = YCC2['PREFIX']+YCC2['BLACK_API']
    body = {
        'iplist': json.dumps({'black': black_list, 'white': white_list})
    }
    code, response = httpcall2(url, method='POST', body=body)
    i(deploy.depid, "{0}|{1}|{2}|{3}".format(url, code, response, str(body)))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, "设置黑白名单成功")
        return True
    else:
        i(deploy.depid, '设置黑白名单失败，原因为{0}'.format(response.get("detail")))
        trident_callback(deploy, 4)
        return False


def ycc_deploy2(deploy):
    i(deploy.depid, 'ycc发布开始')
    ycc_code = TRIDENT_YCC_IDC_MAPPING.get(deploy.idc) if deploy.idc else Room.objects.get(id=deploy.zone_id).ycc_code
    url = YCC2['PREFIX']+YCC2['DEPLOY_API'].format(ycc_code, deploy.app.site.name, deploy.app.name)
    code, response = httpcall2(url)
    i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, 'ycc发布结束')
        trident_callback(deploy, 2)
        return True
    else:
        i(deploy.depid, 'ycc发布失败，失败原因为{0}'.format(response.get("detail")))
        trident_callback(deploy, 4)
        return False


def ycc_rollback2(deploy):
    room_ids = []
    if deploy.idc:
        room_ids = TRIDENT_CMDB_IDC_MAPPING[deploy.idc]
    else:
        room_ids = [deploy.zone_id]
    # white_list = [obj.ip for obj in Server.objects.filter(app_id=deploy.app_id) ]
    white_list = [obj.server.ip for obj in DeployDetailConfig.objects.filter(depid=deploy.depid) if obj.room.id in room_ids]
    if not ycc_black(deploy, None, white_list):
        return False
    i(deploy.depid, 'ycc回滚开始')
    ycc_code = TRIDENT_YCC_IDC_MAPPING.get(deploy.idc) if deploy.idc else Room.objects.get(id=deploy.zone_id).ycc_code
    url = YCC2['PREFIX']+YCC2['ROLLBACK_API'].format(ycc_code, deploy.app.site.name, deploy.app.name)
    code, response = httpcall2(url)
    i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, 'ycc回滚结束')
        trident_callback(deploy, 3)
        return True
    else:
        i(deploy.depid, 'ycc回滚失败，失败原因为{0}'.format(response.get("detail")))
        trident_callback(deploy, 5)
        return False


def get_room_obj_by_server_obj(server_obj):
    asset_obj = server_obj.asset if server_obj.server_type_id == 1 else server_obj.parent_asset
    return asset_obj.rack.room


def application_restart(host, pattern, cache, key, dump=False):
    if dump:
        status, output = jvm_heap_dump(host)
        i2(cache, key, '点击<a href="%s">此处</a>下载%s的dump.hprof' % (output, host) if status else '生成%s的dump.hprof失败，原因为：%s' % (host, output))
    status, pid_list = _application_pid_list(host, pattern)
    for retries in [15, 30, 60]:
        status, cmd, output = _application_restart(host)
        msg = '重启%s 结果：%s' % (cmd, output)
        i2(cache, key, msg)
        for retry in range(retries):
            time.sleep(2)
            status, new_pid_list = _application_pid_list(host, pattern)
            if new_pid_list and all([pid not in pid_list for pid in new_pid_list]):
                return True
    i2(cache, key, '重启%s失败' % host)
    return False


def _application_restart(host):
    cmd = 'export LANG=en_US.UTF-8; /bin/bash /depot/boot.sh'
    return ssh(cmd, host)


def _application_pid_list(host, pattern):
    cmd = 'pgrep -f %s' % pattern
    status, cmd, output = ssh(cmd, host)
    pid_list = [pid.strip() for pid in output.split() if pid.strip().isdigit()] if status else []
    return status, pid_list


def get_process_pattern_by_app_id(app_id):
    try:
        app = App.objects.get(id=app_id)
    except App.DoesNotExist:
        return None
    return app.deployprocesspattern.pattern if hasattr(app, 'deployprocesspattern') else DEPLOY_DEFAULT_PROCESS_PATTERN


def celery_report(celery_task_id):
    app = Celery("assetv2")
    app.config_from_object("django.conf:settings")
    async_result = app.AsyncResult(celery_task_id)
    cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION']+'2'})
    task_dict = dict()
    task_dict['ready'] = async_result.ready()
    task_dict['status'] = async_result.status
    task_dict['result'] = str(async_result.result)
    log_list = cache.get(celery_task_id, [])
    log_list.reverse()
    task_dict['logs'] = log_list
    return task_dict


def set_healthcheck(ip_list=[], status=1):
    status_dict = {0: '开启', 1: '关闭'}
    ip_str = '&' + '&'.join(['ip[]=%s' % ip for ip in ip_list])
    url = HC['PREFIX']+HC['SET_API'].format(ip_str, status)
    try:
        fp = urllib2.urlopen(url)
    except Exception as e:
        return False, url, '设置HealthCheck为{0}状态出错, 错误信息: {1}'.format(status_dict[status], str(e))
    else:
        return True, url, '设置HealthCheck为{0}状态成功'.format(status_dict[status])


def detector_method(server_obj, method):
    room = get_room_obj_by_server_obj(server_obj)
    log_list = []
    for i in range(3):
        code, response = httpcall2(DETECTOR['PREFIX']+DETECTOR['METHOD_API'] % (CMDB_DETECTOR_IDC_MAPPING.get(room.id), DETECTOR['SECRET'], DETECTOR['SECRET'], server_obj.ip, method))
        log_list.append('服务%s：detector|%s|%s|%s' % (method, DETECTOR['PREFIX']+DETECTOR['METHOD_API'] % (CMDB_DETECTOR_IDC_MAPPING.get(room.id), '*' * 32, '*' * 32, server_obj.ip, method), code, response))
        try:
            response = json.loads(response)
        except:
            response = dict()
        if isinstance(response, dict) and response.get('result') != '-3':
            break
    return log_list


def get_url_by_depid(depid_list):
    url_list = []
    category = None
    for depid in depid_list:
        if depid[-1] == 'C':
            category = 'ycc'
        elif depid[-1] in ('S', 'W'):
            # deploy_main = DeployMain.objects.get(depid=depid)
            # if deploy_main.is_gray_release == 0:
            #     category = 'normal'
            # elif deploy_main.is_gray_release == 1:
            #     category = 'gray'
            category = 'prod'
        url_list.append('<a href="http://{0}/deploy/{1}/detail/?depid={2}">{3}</a>'.format(OMS_HOST, category, depid, depid))
    return url_list


def get_recursive_node_dict(menu_obj):
    node_dict = {
        'name': menu_obj.name,
        'url': menu_obj.url,
        'type': menu_obj.type
    }
    deploy_center_menu_queryset = DeployCenterMenu.objects.filter(parent=menu_obj.id)
    if deploy_center_menu_queryset.exists():
        node_dict['children'] = [get_recursive_node_dict(deploy_center_menu_obj) for deploy_center_menu_obj in deploy_center_menu_queryset]
    return node_dict


def single_rollback(deploy_detail, pattern):
    server_obj = Server.objects.filter(server_status_id=200, ip=deploy_detail.host).first()
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    if server_obj is None:
        i(deploy.depid, '回滚：[%s]代码回滚忽略，该机器处于非使用中状态' % deploy_detail.host)
        return
    src = os.path.join(os.path.dirname(deploy.deprepath), os.path.basename(deploy.last_ftpath)) if deploy.last_ftpath else deploy.backup
    dst = deploy.path.rstrip('/')
    # if not path_exists(src, deploy_detail.host):
    #     single_pre_deploy(deploy_detail)
    if deploy.packtype == 0:
        status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), deploy_detail.host)
    else:
        src += '/'
        status, cmd, output = ssh('test -L %s && rm -f %s' % (dst, dst), deploy_detail.host)
        if status:
            i(deploy_detail.depid, '回滚：[%s]工作目录为软链接，需要删除。执行命令：%s 执行结果：%s###' %(deploy_detail.host, cmd, output))
        status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, checksum=True, remote_host=deploy_detail.host)
    msg = '回滚：[%s]代码回滚%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        unlock_it(deploy)
        ie(deploy.depid, msg)
    i(deploy.depid, msg)
    deploy_detail.has_rollback = 1
    deploy_detail.rollback_time = int(time.time())
    deploy_detail.complete = 1
    deploy_detail.save()
    if deploy.restart:
        application_restart(deploy_detail.host, pattern, cache_list[0], deploy.depid)
    action = u"gray_rollback" if deploy.is_gray_release else u"normal_rollback"
    change(user=deploy.user.username if deploy.user else None, action=action, index=deploy_detail.host, message=deploy.depid)


def ycc_rmvpublish(deploy):
    ycc_code = TRIDENT_YCC_IDC_MAPPING.get(deploy.idc) if deploy.idc else Room.objects.get(id=deploy.zone_id).ycc_code
    url = YCC2['PREFIX']+YCC2['RMVPUBLISH_API'].format(ycc_code, deploy.app.site.name, deploy.app.name)
    code, response = httpcall2(url)
    i(deploy.depid, "{0}|{1}|{2}".format(url, code, response))
    response = json.loads(response) if response else {}
    if response.get("result"):
        i(deploy.depid, "成功删除配置组待发布状态")
        return True
    else:
        i(deploy.depid, '无法删除配置组待发布状态，原因为{0}'.format(response.get("detail")))
        return False


def is_locked_v2(deploy):
    return deploy.status in (9, 11)


def deploy_detail_init_v2(deploy):
    filters = dict()
    app_id = DEPLOY_PACKTYPE_APP_ID_MAPPING.get(deploy.packtype, deploy.app_id)
    filters['app_id'] = app_id
    filters['server_status_id'] = 200
    filters['server_env_id'] = 2
    if deploy.dets:
        filters['ip__in'] = deploy.dets.split(',')

    for server in Server4Deploy.objects.filter(**filters):
        deploy_detail, created = DeployDetailV2.objects.get_or_create(
            depid=deploy.depid,
            host=server.ip,
            defaults={
                'deploy_host': DeployIDC.objects.get(id=server.rack.room.area.id).host,
            }
        )
        deploy_detail.server = server
        deploy_detail.save()

def get_room_group_by_server_queryset(server_queryset):
    room_dict = dict()
    for server in server_queryset:
        room_obj = server.rack.room
        room_dict[room_obj] = room_dict.get(room_obj, [])
        room_dict[room_obj].append(server)
    return room_dict


def single_deploy_v2(deploy_detail):
    server_obj = Server.objects.filter(server_status_id=200, ip=deploy_detail.host).first()
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    if server_obj is None:
        i(deploy.depid, '发布：[%s]代码发布忽略，该机器处于非使用中状态' % deploy_detail.host)
        return
    # 回滚前将服务下线
    if deploy.packtype == 0 and deploy.restart:
        for log in detector_method(server_obj, 'disabled'):
            i(deploy.depid, log)
    time.sleep(OFFLINE_DELAY)
    src = deploy.deprepath.rstrip('/')
    dst = deploy.path.rstrip('/')
    if deploy.packtype == 0:
        status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), deploy_detail.host)
    else:
        src += '/'
        status, cmd, output = ssh('test -L %s && rm -f %s' % (dst, dst), deploy_detail.host)
        if status:
            i(deploy.depid, '正式发布：[%s]工作目录为软链接，需要删除。执行命令：%s 执行结果：%s###' %(deploy_detail.host, cmd, output))
            backup = os.path.join(os.path.dirname(deploy.deprepath), os.path.basename(deploy.last_ftpath)) if deploy.last_ftpath else deploy.backup
            backup += '/'
            status, cmd, output = rsync4nocheck(backup, dst, host_key_checking=False, checksum=True, remote_host=deploy_detail.host)
            msg = '正式发布：[%s]将备份还原到正式环境%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
            if not status:
                unlock_it(deploy)
                ie(deploy.depid, msg)
            i(deploy.depid, msg)
        status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, checksum=True, hotfix=True, remote_host=deploy_detail.host)
    msg = '正式发布：[%s]代码切换到正式环境%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        raise DeployError(msg)
    i(deploy.depid, msg)
    deploy_detail.has_real = 1
    deploy_detail.real_time = int(time.time())
    deploy_detail.complete = 1
    deploy_detail.save()
    if deploy.restart:
        application_restart(deploy_detail.host, get_process_pattern_by_app_id(deploy.app_id), cache_list[0], deploy.depid)
    action = u'gray_deploy' if deploy.is_gray_release else u'normal_deploy'
    change(user=deploy.user.username if deploy.user else None, action=action, index=deploy_detail.host, message=deploy.depid)
    # username = deploy.user.username if deploy.user else None
    # index = deploy_detail.host
    # deploy_detail_url = DEPLOY_DETAIL_URL % (OMS_HOST, deploy.depid) 
    # message = """<a href="%s">%s</a>"""%(deploy_detail_url, deploy.depid)
    # RL_normal_deploy(username, index, message, deploy.app_id)

def single_rollback_v2(deploy_detail, pattern):
    server_obj = Server.objects.filter(server_status_id=200, ip=deploy_detail.host).first()
    deploy = DeployMain.objects.get(depid=deploy_detail.depid)
    if server_obj is None:
        i(deploy.depid, '回滚：[%s]代码回滚忽略，该机器处于非使用中状态' % deploy_detail.host)
        return
    # 回滚前将服务下线
    if deploy.packtype == 0 and deploy.restart:
        for log in detector_method(server_obj, 'disabled'):
            i(deploy.depid, log)
    src = os.path.join(os.path.dirname(deploy.deprepath), os.path.basename(deploy.last_ftpath)) if deploy.last_ftpath else deploy.backup
    dst = deploy.path.rstrip('/')
    # if not path_exists(src, deploy_detail.host):
    #     single_pre_deploy(deploy_detail)
    if deploy.packtype == 0:
        status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), deploy_detail.host)
    else:
        src += '/'
        status, cmd, output = ssh('test -L %s && rm -f %s' % (dst, dst), deploy_detail.host)
        if status:
            i(deploy_detail.depid, '回滚：[%s]工作目录为软链接，需要删除。执行命令：%s 执行结果：%s###' %(deploy_detail.host, cmd, output))
        status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, checksum=True, remote_host=deploy_detail.host)
    msg = '回滚：[%s]代码回滚%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
    if not status:
        raise DeployError(msg)
    i(deploy.depid, msg)
    deploy_detail.has_rollback = 1
    deploy_detail.rollback_time = int(time.time())
    deploy_detail.complete = 1
    deploy_detail.save()
    if deploy.restart:
        application_restart(deploy_detail.host, pattern, cache_list[0], deploy.depid)
    action = u"gray_rollback" if deploy.is_gray_release else u"normal_rollback"
    change(user=deploy.user.username if deploy.user else None, action=action, index=deploy_detail.host, message=deploy.depid)


def jvm_heap_dump(host):
    hprof = '/tmp/heap.hprof'
    cmd = '/usr/j2sdk/bin/jmap -dump:format=b,file=%s \`ls /tmp/hsperfdata_deploy\`' % hprof
    status, cmd, output = ssh(cmd, host)
    if status:
        src = 'deploy@%s:%s' % (host, hprof)
        dst = '/depot/download/%s_%s.hrof' % (host, int(time.time()))
        status, cmd, output = rsync4nocheck(src, dst, checksum=True)
        os.chmod(dst, stat.S_IRUSR + stat.S_IRGRP + stat.S_IROTH)
        return status, 'http://%s/staticv2/download/%s' % (OMS_HOST, os.path.basename(dst)) if status else output
    return status, output
