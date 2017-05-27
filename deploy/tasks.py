# -*- coding: utf-8 -*-
from __future__ import absolute_import
from assetv2.celeryapi import app as celery_app
from celery import shared_task, current_task
from django.template import loader
from django.core.cache import get_cache
from deploy.utils.ConfigDeploy import ConfigDeploy
from deploy.utils.SingleDeploy import SingleDeploy
from deploy.utils.InitTomcat import InitTomcat
from deploy.utils.InitTomcatV2 import InitTomcatV2
from deploy.utils.HaproxyRegistration import HaproxyRegistration
from deploy.utils.Utils import *
from deploy.utils.DeployCommon import i, application_restart, single_backup, single_pre_deploy, get_url_by_depid, single_rollback_v2, i2
from deploy.models import DeployMain, DeployMainConfig, DeployTicketCelery, DeployDetail
from assetv2.settingsdeploy import OMS_HOST, ONLINE_REPORT, ZABBIX, CACHES, EVENT, CMDBAPI_URL, CACHES, TICKET, ADD_SERVERS_TIME_OUT, GitLab_Deploy_Mail,LEDAO_POOL_ID
from server.models import Server
from cmdb.models import App
from change import tasks
from util.timelib import stamp2str
from util.httplib import httpcall2
from util.sendmail import sendmail_v2
from datetime import datetime
import time, cgi
import urllib2, urllib
import json
from deploy.utils.DeployError import DeployError
from ycc.models import ConfigInfo
import logging
from ycc.views_api import add_servers, get_service_reg_realtime
from celery.exceptions import Reject


@shared_task()
def parallel_pre_deploy(deploy_detail_id):
    deploy_detail = DeployDetail.objects.get(id=deploy_detail_id)
    success = True
    try:
        if not deploy_detail.has_backup:
            single_backup(deploy_detail)
        if not deploy_detail.has_pre:
            single_pre_deploy(deploy_detail)
    except Exception, e:
        print e.args
        success = False
    return success


@shared_task()
def auto_pre_deploy(depid):
    from deploy.utils.PreDeploy import PreDeploy
    pre_deploy = PreDeploy(depid=depid)
    pre_deploy.auto_publish()


@shared_task()
def auto_publish(depid, interval=0):
    from deploy.utils.Publish import Publish
    publish = Publish(depid=depid, interval=int(interval))
    publish.auto_publish()


@shared_task()
def rollback(depid, interval=0, parallel=False):
    from deploy.utils.Publish import Publish
    publish = Publish(depid=depid, interval=int(interval), parallel=parallel)
    publish.rollback()


@shared_task()
def parallel_rollback(deploy_detail_id, pattern):
    deploy_detail = DeployDetail.objects.get(id=deploy_detail_id)
    success = True
    try:
        single_rollback_v2(deploy_detail, pattern)
    except Exception, e:
        print e.args
        success = False
    return success


@shared_task()
def config_auto_publish(depid):
    config_deploy = ConfigDeploy(depid=depid)
    config_deploy.auto_publish()


@shared_task()
def config_rollback(depid, interval=0):
    config_deploy = ConfigDeploy(depid=depid, interval=int(interval))
    config_deploy.rollback()


@shared_task()
def all_auto_publish(jiraid, pool, deploy_dict, recipient_list, deploy_interval):
    from deploy.utils.Publish import Publish
    config_depid_list = deploy_dict.get("config", [])
    static_depid_list = deploy_dict.get("static", [])
    webapps_depid_list = deploy_dict.get("webapps", [])
    event_dict = {
                     "sendType": "email",
                     "receivers": 'noreplay@cmdbapi.yihaodian.com.cn',
                     "warningMessage": None,
                     "warningTopic": None,
                     "warningType": 1
    }
    #静态发布
    if static_depid_list:
        error = False
        try:
            publish = Publish(depid=static_depid_list[0], interval=deploy_interval)
            publish.auto_publish()
        except Exception, e:
            print e.message
            error = True
        static_status = DeployMain.objects.get(depid=static_depid_list[0]).status
        if error or static_status != 4:
            subject = u"无人发布|{0}|{1}|静态发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/static/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'static_depid_url': get_url_by_depid(static_depid_list),
            })
            # body = list()
            # body.append(u"<span style='color: red'>静态发布异常的发布单:{0}</span>".format(get_url_by_depid(static_depid_list)))
            # body.append(u"YCC待发布的发布单:{0}".format(get_url_by_depid(config_depid_list)))
            # body.append(u"程序待发布的发布单:{0}".format(get_url_by_depid(webapps_depid_list)))
            # body.append(u"请正确处理已发布的发布单和待发布的发布单")
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
            print httpcall2(EVENT['PREFIX']+EVENT['API'], 'POST', body={
                'apiType': 'Deploy',
                'param': json.dumps(dict(event_dict, **{
                    'warningMessage': ','.join(static_depid_list),
                    'warningTopic': subject
                }))
            })
            return False
    #配置发布
    if config_depid_list:
        error = False
        try:
            for config_depid in config_depid_list:
                config_deploy = ConfigDeploy(config_depid)
                config_deploy.auto_publish()
        except Exception, e:
            print e.message
            error = True
        config_failure_list = [str(deploy.depid) for deploy in DeployMainConfig.objects.filter(depid__in=config_depid_list) if deploy.status != 2]
        if error or config_failure_list:
            config_success_list = [str(deploy.depid) for deploy in DeployMainConfig.objects.filter(depid__in=config_depid_list) if deploy.status == 2]
            subject = u"无人发布|{0}|{1}|YCC发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/ycc/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'config_success_url': get_url_by_depid(config_success_list),
            })
            # body = list()
            # body.append(u"静态已发布的发布单:{0}".format(get_url_by_depid(static_depid_list)))
            # body.append(u"<span style='color: red'>YCC发布异常的发布单:{0}</span>".format(get_url_by_depid(config_failure_list)))
            # body.append(u"YCC已发布的发布单:{0}".format(get_url_by_depid(config_success_list)))
            # body.append(u"程序待发布的发布单:{0}".format(get_url_by_depid(webapps_depid_list)))
            # body.append(u"请正确处理已发布的发布单和待发布的发布单")
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
            print httpcall2(EVENT['PREFIX']+EVENT['API'], 'POST', body={
                'apiType': 'Deploy',
                'param': json.dumps(dict(event_dict, **{
                    'warningMessage': ','.join(config_failure_list),
                    'warningTopic': subject
                }))
            })
            return False
    #程序发布
    if webapps_depid_list:
        error = False
        try:
            publish = Publish(depid=webapps_depid_list[0], interval=deploy_interval)
            publish.auto_publish()
        except Exception, e:
            print e.args
            error = True
        webapps_status = DeployMain.objects.get(depid=webapps_depid_list[0]).status
        if error or webapps_status != 4:
            subject = u"无人发布|{0}|{1}|程序发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/webapps/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'webapps_dept_url': get_url_by_depid(webapps_depid_list),
            })
            # body = list()
            # body.append(u"静态已发布的发布单:{0}".format(get_url_by_depid(static_depid_list)))
            # body.append(u"YCC已发布的发布单:{0}".format(get_url_by_depid(config_depid_list)))
            # body.append(u"<span style='color: red'>程序发布异常的发布单:{0}</span>".format(get_url_by_depid(webapps_depid_list)))
            # body.append(u"请正确处理已发布的发布单和待发布的发布单")
            # send_email(subject=subject, content="<br>".join(body).encode("utf8"), recipient_list=recipient_list)
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
            print httpcall2(EVENT['PREFIX']+EVENT['API'], 'POST', body={
                'apiType': 'Deploy',
                'param': json.dumps(dict(event_dict, **{
                    'warningMessage': ','.join(webapps_depid_list),
                    'warningTopic': subject
                }))
            })
            return False
    subject = u"无人发布|{0}|{1}|发布正常".format(jiraid, pool)
    body = loader.render_to_string('mail/deploy/auto/publish_success.html', {
        'jiraid': jiraid,
        'pool': cgi.escape(pool),
        'static_depid_url': get_url_by_depid(static_depid_list),
        'config_success_url': get_url_by_depid(config_success_list),
        'webapps_dept_url': get_url_by_depid(webapps_depid_list),
    })
    # body = list()
    # body.append(u"静态已发布的发布单:{0}".format(get_url_by_depid(static_depid_list)))
    # body.append(u"YCC已发布的发布单:{0}".format(get_url_by_depid(config_depid_list)))
    # body.append(u"程序已发布的发布单:{0}".format(get_url_by_depid(webapps_depid_list)))
    # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
    sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
    return True


@shared_task()
def deploy_by_gitlab(ips, code_path, branch, deploy_type):
    result_list = []
    prefix = "http://oms.yihaodian.com.cn/itil/api/?action=check&method=isDeploy&deploy="
    healthcheck_close_url = prefix + "1"
    healthcheck_open_url = prefix + "0"

    for ip in ips:
        healthcheck_close_url += "&ip[]=" + ip
        healthcheck_open_url += "&ip[]=" + ip

    # close healthcheck
    logging.info(__name__ + ": prepare close healthcheck url -> " + healthcheck_close_url)
    status_code, response = httpcall2(healthcheck_close_url)
    logging.info(__name__ + ": healthcheck close request complet -> " + str(status_code) + ", response -> " + response)

    for item in ips:
        if deploy_type == 'python':
            status, cmd, output = ssh('/depot/boot.sh', item)
            result_list.append([item, status, '<br>'.join(output.splitlines())])
            time.sleep(10)
        elif deploy_type == 'manual-docs':
            command = 'cd %s;git pull origin %s:%s;rm -rf /data/manual/manual/ledao/;/data/python-virtualenv/manual/bin/sphinx-build /data/manual/_source/docs /data/manual/manual/ledao' %(code_path, branch, branch)
            ssh(command, item)
        elif deploy_type == 'manual-docs-office':
            command = 'cd %s;git pull origin %s:%s;/data/python-virtualenv/manual/bin/sphinx-build /data/manual/_source/docs-office /data/manual/manual/ledao-office' %(code_path, branch, branch)
            ssh(command, item)
        elif deploy_type == 'ledao_app':
            command = 'cd %s;git pull origin %s:%s' % (code_path, branch, branch)
            ssh(command, item)
        else:
            command = 'cd %s;git pull origin %s:%s' % (code_path, branch, branch)
            ssh(command, item)
            time.sleep(10)

    if deploy_type == 'python':
        title = u'代码发布' + ('成功' if all([result[1] for result in result_list]) else '失败')
        send_email(subject=title, content=loader.render_to_string('deploy/assetv2_result.html', {'result_list': result_list}), recipient_list=GitLab_Deploy_Mail)

    # open healthcheck.
    time.sleep(400)
    logging.info(__name__ + ": prepare open healthcheck url -> " + healthcheck_open_url)
    status_code, response = httpcall2(healthcheck_open_url)
    logging.info(__name__ + ": healthcheck open request complete -> " + str(status_code) + ", response -> " + response)

    return True


def write_redis_for_log(task_id, log, error=False):
    cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION'] + '2'})
    i2(cache, task_id, log)


def ticket(uniq_id, ip, task_id, status=1):
    if uniq_id is None:
        return
    url = TICKET['PREFIX'] + TICKET['EXPAND_API']
    body = {
        'uniq_id': uniq_id,
        'ip': ip,
        'status': status,
        'url': 'http://%s/deploy/single/detail/?task_id=%s&ip=%s' % (OMS_HOST, task_id, ip)
    }
    code, response = httpcall2(url, method='POST', body=body)
    # cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION'] + '2'})
    log = '|'.join([url, str(code), str(response)])
    # i2(cache, task_id, log)
    write_redis_for_log(task_id, log)


def change_server_status(ip, status_id):
    server_obj = Server.objects.exclude(server_status_id=400).get(ip=ip)
    server_obj.server_status_id = status_id
    server_obj.save()


@shared_task()
def auto_single_deploy(ip, is_one_click, init_tomcat, change_server_data={}, change_zabbix_data={}, uniq_id=None, haproxy=dict(),
                        id=None, service_id=None, ports=None, group_id=None, from_user='unknown'):
    try:
        if init_tomcat is not None:
            init_tomcat = InitTomcatV2(ip=ip, task_id=auto_single_deploy.request.id, require=int(init_tomcat))
            result = init_tomcat.auto_publish()
        if is_one_click is not None:
            single_deploy = SingleDeploy(ip=ip, task_id=auto_single_deploy.request.id, restart=int(is_one_click), uniq_id=uniq_id)
            result = single_deploy.auto_publish()
    except DeployError, msg:
        ticket(uniq_id, ip, auto_single_deploy.request.id, -1)
        raise DeployError(msg)

    if group_id and service_id:
        ports = ports.split(',')
        ip_ports = set([str(ip) + ':' + port.strip() for port in ports])
        is_all_reg = False

        now = datetime.now()
        while (datetime.now() - now).seconds <= ADD_SERVERS_TIME_OUT+1:
            result = get_service_reg_realtime(service_id)
            if result['result']:
                status_220 = set(result['detail']['status_220'])
                is_all_reg = ip_ports <= status_220
                if is_all_reg:
                    break
            else:
                change_server_status(ip, 230)
                ticket(uniq_id, ip, auto_single_deploy.request.id, -1)
                write_redis_for_log(auto_single_deploy.request.id, '检测ZK是否注册失败')
                return '检测ZK是否注册失败'

        if is_all_reg:
            id_ports = [str(id) + ':' + port.strip() for port in ports]
            result = add_servers(id_ports, group_id, from_user)

            if result['result']:
                ticket(uniq_id, ip, auto_single_deploy.request.id, 1)
                write_redis_for_log(auto_single_deploy.request.id, 'add_servers() 成功' + result['msg'])
            else:
                change_server_status(ip, 230)
                ticket(uniq_id, ip, auto_single_deploy.request.id, -1)
                write_redis_for_log(auto_single_deploy.request.id, 'add_servers() 失败' + result['msg'])
                return 'add_servers() 失败'
        else:
            change_server_status(ip, 230)
            not_reg_ip_ports = ''.join(list(ip_ports - status_220))
            write_redis_for_log(auto_single_deploy.request.id, 'ZK未注册' + not_reg_ip_ports)
            ticket(uniq_id, ip, auto_single_deploy.request.id, -1)
            return 'ZK未注册' + not_reg_ip_ports
    else:
        write_redis_for_log(auto_single_deploy.request.id, '非hedwig, 无需add_servers().')
        ticket(uniq_id, ip, auto_single_deploy.request.id, 1)

    for haproxy_room in haproxy.get('group_dict', {}):
        for haproxy_group in haproxy['group_dict'].get(haproxy_room, []):
            haproxy_registration = HaproxyRegistration(ip=ip, haproxy_room=haproxy_room, haproxy_group=haproxy_group, task_id=auto_single_deploy.request.id)
            result = eval('haproxy_registration.' + haproxy.get('method'))()
    server_obj = Server.objects.exclude(server_status_id=400).get(ip=ip)
    server_obj.server_status_id = 200
    server_obj.save()
    if change_server_data or change_zabbix_data:
        happen_time = datetime.now().strftime("%Y-%m-%d %X")
        url = ZABBIX['PREFIX']+ZABBIX['API'] % (change_zabbix_data.get('auth_id'), change_zabbix_data.get('action'), ip)
        if server_obj.server_type_id == 3:
            url += '&v_type=1'
        req = urllib2.Request(url)
        try:
            response = urllib2.urlopen(req)
            code = response.getcode()
            data = response.read()
            try:
                if json.loads(data)['success']:
                    change_zabbix_data['happen_time'] = happen_time
                    tasks.collect.apply_async((change_zabbix_data,))
            except ValueError:
                pass
        except urllib2.HTTPError, e:
            code = e.code
            data = e.read()
        except urllib2.URLError, e:
            code = None
            data = e.args
        i(auto_single_deploy.request.id, '%s|%s|%s' % (url, code, data), db=2)
        change_server_data['message'] = json.dumps(change_server_data['message'])
        change_server_data['happen_time'] = happen_time
        tasks.collect.apply_async((change_server_data,))
    return result


@shared_task()
def online_report(redis_host, redis_port, task_dict, action, username, server_change_content, email, poolname, sitename):
    action_time = stamp2str(time.time(), '%Y%m%d')
    for i in range(ONLINE_REPORT['TRIES']):
        if all([task_report(redis_host, redis_port, task_id)['ready'] for ip, task_id in task_dict.items()]):
            break
        time.sleep(ONLINE_REPORT['WAIT'])
    failure_ip_list = [ip for ip, task_id in task_dict.items() if task_report(redis_host, redis_port, task_id)['status'] == 'FAILURE']
    ip_list = ','.join([ip for ip, task_id in task_dict.items()])
    subject = '(%s)主机变更提醒：%s %s' % ('失败' if failure_ip_list else '成功', ip_list, action)
    html = loader.render_to_string('deploy/online_report.html', {
        'task_list': [task_report(redis_host, redis_port, task_id, ip) for ip, task_id in task_dict.items()],
        'oms_host': OMS_HOST,
        'action': action,
        'action_time': action_time,
        'username': username,
        'server_change_content': server_change_content,
        'poolname': poolname,
        'sitename': sitename,
        'ips': ip_list
    })
    send_email(subject=subject, content=html.encode('utf8'), recipient_list=email)


@shared_task()
def parallel_reboot(kwargs):
    cache = get_cache('deploy', **{'LOCATION': CACHES['deploy']['LOCATION']+'2'})
    success = application_restart(kwargs['ip'], kwargs['pattern'], cache, kwargs['task_id'], kwargs['dump'])
    deploy_ticket_celery = DeployTicketCelery.objects.get(ticket_id=kwargs['ticket_id'])
    print deploy_ticket_celery.percent
    deploy_ticket_celery.percent += kwargs['weight']
    deploy_ticket_celery.save()
    return success


@shared_task()
def auto_reboot(data):
    from deploy.utils.Reboot import Reboot
    reboot = Reboot(data=data, task_id=current_task.request.id)
    return reboot.auto_reboot()

@shared_task()
def stg_deploy(depid, is_save_process=None):
    from deploy.utils.StgPublish import Publish
    publish = Publish(depid)
    return publish.deploy_stg(is_save_process)

@shared_task()
def stg_rollback(depid):
    from deploy.utils.StgPublish import Publish
    publish = Publish(depid)
    return publish.rollback_stg()


@shared_task()
def auto_publish_v2(depid, from_scratch):
    from deploy.utils.PublishV2 import Publish
    publish = Publish(depid=depid, from_scratch=from_scratch)
    publish.auto_publish()


@shared_task()
def rollback_v2(depid, rollback_type):
    from deploy.utils.PublishV2 import Publish
    publish = Publish(depid=depid, rollback_type=rollback_type)
    publish.rollback()


@shared_task()
def all_auto_publish_v2(jiraid, pool, deploy_dict, recipient_list):
    # 异常事件处理
    event_url_v2 = EVENT['PREFIX'] + EVENT['API_V2']

    from deploy.utils.PublishV2 import Publish
    config_depid_list = deploy_dict.get("config", [])
    static_depid_list = deploy_dict.get("static", [])
    webapps_depid_list = deploy_dict.get("webapps", [])
    
    #静态发布
    if static_depid_list:
        error = False
        try:
            publish = Publish(depid=static_depid_list[0])
            publish.auto_publish()
        except Exception, e:
            print e.message
            error = True
        static_status = DeployMain.objects.get(depid=static_depid_list[0]).status
        if error or static_status != 4:
            subject = u"无人发布|{0}|{1}|静态发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/static/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'static_depid_url': get_url_by_depid(static_depid_list),
            })
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
            event_dict_v2 = {
                'title' : subject,
                'level_id' : 300,
                'type_id' : 3,
                'source_id' : 16,
                'pool_id' : LEDAO_POOL_ID,
                'message' : '静态程序发布异常: ' + ','.join(static_depid_list),
                'send_to' : ','.join(recipient_list)
            }
            print httpcall2(event_url_v2, 'POST', body=event_dict_v2)
            return False
    #配置发布
    if config_depid_list:
        error = False
        try:
            for config_depid in config_depid_list:
                config_deploy = ConfigDeploy(config_depid)
                config_deploy.auto_publish()
        except Exception, e:
            print e.message
            error = True
        config_failure_list = [str(deploy.depid) for deploy in DeployMainConfig.objects.filter(depid__in=config_depid_list) if deploy.status != 2]
        if error or config_failure_list:
            config_success_list = [str(deploy.depid) for deploy in DeployMainConfig.objects.filter(depid__in=config_depid_list) if deploy.status == 2]
            subject = u"无人发布|{0}|{1}|YCC发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/ycc/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'config_failure_url': get_url_by_depid(config_failure_list),
            })
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
           
            event_dict_v2 = {
                'title' : subject,
                'level_id' : 300,
                'type_id' : 3,
                'source_id' : 16,
                'pool_id' : LEDAO_POOL_ID,
                'message' : '配置发布异常: ' + ','.join(config_failure_list),
                'send_to' : ','.join(recipient_list)
            }
            print httpcall2(event_url_v2, 'POST', body=event_dict_v2)
            return False
    #程序发布
    if webapps_depid_list:
        error = False
        try:
            publish = Publish(depid=webapps_depid_list[0])
            publish.auto_publish()
        except Exception, e:
            print e.args
            error = True
        webapps_status = DeployMain.objects.get(depid=webapps_depid_list[0]).status
        if error or webapps_status != 4:
            subject = u"无人发布|{0}|{1}|程序发布异常".format(jiraid, pool)
            body = loader.render_to_string('mail/deploy/auto/webapps/error_report.html', {
                'jiraid': jiraid,
                'pool': cgi.escape(pool),
                'webapps_dept_url': get_url_by_depid(webapps_depid_list),
            })
            # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
            sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
            event_dict_v2 = {
                'title' : subject,
                'level_id' : 300,
                'type_id' : 3,
                'source_id' : 16,
                'pool_id' : LEDAO_POOL_ID,
                'message' : '程序发布异常: ' + ','.join(webapps_depid_list),
                'send_to' : ','.join(recipient_list)
            }
            print httpcall2(event_url_v2, 'POST', body=event_dict_v2)
            return False
    subject = u"无人发布|{0}|{1}|发布正常".format(jiraid, pool)
    body = loader.render_to_string('mail/deploy/auto/publish_success.html', {
        'jiraid': jiraid,
        'pool': pool,
        'static_depid_url': get_url_by_depid(static_depid_list),
        'config_success_url': get_url_by_depid(config_depid_list),
        'webapps_dept_url': get_url_by_depid(webapps_depid_list),
    })
    # send_email(subject=subject, content=body.encode("utf8"), recipient_list=recipient_list)
    sendmail_v2(subject, body.encode("utf8"), recipient_list, None)
    return True


@shared_task()
def bulk_rollback(app_id, jiraid_list):
    jiraid_dict = dict()
    for jiraid in jiraid_list:
        deploy_main_config_obj = DeployMainConfig.objects.filter(jiraid=jiraid).first()
        if deploy_main_config_obj is not None:
            jiraid_dict[jiraid] = deploy_main_config_obj.publishdatetimefrom
            continue
        deploy_main_obj = DeployMain.objects.filter(jiraid=jiraid).first()
        jiraid_dict[jiraid] = deploy_main_obj.publishdatetimefrom
    for jiraid, publishdatetimefrom in sorted(jiraid_dict.iteritems(), key=lambda x : x[1], reverse=True):
        deploy_main_obj = DeployMain.objects.filter(jiraid=jiraid, app_id=app_id, packtype=3).first()
        if deploy_main_obj is not None:
            from deploy.utils.PublishV2 import Publish
            publish = Publish(depid=deploy_main_obj.depid)
            publish.rollback()
        for deploy_main_config_obj in DeployMainConfig.objects.filter(jiraid=jiraid, app_id=app_id):
            config_deploy = ConfigDeploy(depid=deploy_main_config_obj.depid)
            config_deploy.rollback()
        deploy_main_obj = DeployMain.objects.filter(jiraid=jiraid, app_id=app_id, packtype=0).first()
        if deploy_main_obj is not None:
            from deploy.utils.PublishV2 import Publish
            publish = Publish(depid=deploy_main_obj.depid)
            publish.rollback()

