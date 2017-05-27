# -*- coding: utf-8 -*-
from __future__ import division
from django.template import loader
from kazoo.client import KazooClient
from kazoo.exceptions import KazooException
from threading import Thread
from cmdb.models import *
from deploy.utils.DeployCommon import *
from deploy.utils.Utils import *
from deploy.utils.PreDeploy import PreDeploy
from deploy.tasks import parallel_rollback
from util.httplib import httpcall2
from assetv2.settingsdeploy import *
from Queue import Queue
from celery import group
import time
import math
import os
import urllib2
import json
import random
import datetime
import shutil


class Publish():
    def __init__(self, depid, interval=DEPLOY_INTERVAL, parallel=False):
        self.depid = depid
        self.deploy = DeployMain.objects.get(depid=depid)
        app = self.deploy.app
        site = app.site if app else None
        self.full_app_name = '{0}#{1}'.format(site.name if site else '', app.name if app else '')
        site = self.deploy.app.site if app else None
        self.interval = interval
        self.cache = get_cache('deploy')
        self.pattern = get_process_pattern_by_app_id(self.deploy.app_id)
        self.ip_list = [deploy_detail.host for deploy_detail in deploy_detail_list(depid)]
        self.parallel = parallel
        self.cache.set(self.depid, [dict(log_dict, **{'error': False}) for log_dict in self.cache.get(self.depid)])

    def ie(self, log):
        self.i(log, error=True)
        self.deploy = DeployMain.objects.get(depid=self.depid)
        unlock_it(self.deploy)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.depid, log, error)

    def health_check(self):
        if self.deploy.packtype != 0:
            return True
        self.i('检查HealthCheck是否设置')
        url = HC['PREFIX']+HC['API'].format(self.deploy.app_id)
        fp = urllib2.urlopen(url)
        result = json.loads(fp.read())
        return result['data']['isSetHealthCheck']

    def set_healthcheck(self, status=1):
        if self.deploy.packtype != 0:
            return
        status, url, msg = set_healthcheck(self.ip_list, status)
        self.i(url)
        if status:
            self.i(msg)
        else:
            self.ie(msg)

    def reset_error_info(self):
        if self.depid is not None:
            DeployLog.objects.filter(depid=self.depid).update(error=0)

    def deploy_email(self):
        if self.deploy.deptype == 0:
            return None
        app_id = self.deploy.app_id
        try:
            contact = AppContact.objects.get(pool_id=app_id)
        except AppContact.DoesNotExist:
            self.i('POOL联系人信息没有设置，请在itil的pool联系人中设置(不影响正常发布)。')
        mails = [contact.domain_email]+contact.p_email.split(',')
        mails += MAIL_RECIPIENT
        to = [item.strip() for item in mails if item.strip()]
        app = self.deploy.app
        site = app.site if app else None
        pool = '%s/%s' % (app.site.name if site else '', app.name if app else '')
        jiraid = self.deploy.jiraid
        subject = '%s-%s-%s-%s上线结果' % (contact.domain_name, pool, self.deploy.get_packtype_display(), stamp2str(time.time(), formt='%Y-%m-%d'))
        cmdstr, status, output = self.catalina()
        if not status:
            self.i('取Tomcat日志时报错，无法发送邮件(不影响正常发布)。')
        log = output
        import cgi
        html = loader.render_to_string('deploy/deploy_mail.html', {
            'jiraid': jiraid,
            'pool': cgi.escape(pool),
            'log': cgi.escape(log)}) if self.deploy.packtype == 0 else '发布完成'
        if self.deploy.deptype == 1:
            latest_ftp_path = latest_staging_version(self.deploy)
            if latest_ftp_path:
                extra_list = ['检测到发布的版本和当前Stg版本不同']
                extra_list.append('发布的版本：%s' % os.path.basename(self.deploy.ftpath))
                extra_list.append('Stg的版本：%s' % os.path.basename(latest_ftp_path))
                html = '<br>'.join(extra_list) + html
        maintained_server_obj_list = Server.objects.filter(app_id=self.deploy.app_id, server_status_id=210, server_env_id=2)
        if maintained_server_obj_list.exists():
            html = '维护中的主机没有发布，请知悉:%s<br>' % ','.join([server_obj.ip for server_obj in maintained_server_obj_list]) + html
            to.append('IT_OPS_SA@yhd.com')
        self.i('邮件发送给%s' % to)
        if not to:
            self.i('domain的email没有设置，请在itil的pool联系人中设置(不影响正常发布)。')
        send_email(subject=subject, content=html.encode('utf8'), recipient_list=to)

    # 开始发布
    def auto_publish(self):
        time.sleep(random.random()*5)
        if is_locked(self.deploy):
            self.i(set_color('当前发布或者回滚被锁住'))
            return False
        if self.deploy.status < 3:
            pre_deploy = PreDeploy(depid=self.deploy.depid)
            pre_deploy.auto_publish()
            self.deploy = DeployMain.objects.get(depid=self.depid)
        # if self.deploy.status != 3:
        #     self.ie(set_color('预发布出现问题'))
        # 如果是staging2production，判断staging版本是否发生变化，如果是则重新预发布
        # if self.deploy.deptype == 1:
        #     latest_ftp_path = latest_staging_version(self.deploy)
        #     if latest_ftp_path:
        #         self.i('staging版本发生变化，需要重新预发布')
        #         pre_deploy = PreDeploy(depid=self.deploy.depid)
        #         pre_deploy.auto_publish()
        #         self.deploy = DeployMain.objects.get(depid=self.depid)
        lock_it(self.deploy)
        if not self.health_check():
            self.ie('HealthCheck有问题，请检查是否设置HealthCheck')
        self.reset_error_info()
        if self.deploy.deptype > 0:
            self.check_interval()
        self.set_healthcheck(1)
        deploy_detail_init(self.deploy)
        deploy_type = '灰度' if self.deploy.is_gray_release == 1 else '常规'
        self.i('开始%s发布' % deploy_type)
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            self.gray_deploy()
        else:
            self.normal_deploy()
        self.deploy.last_modified = int(time.time())
        self.deploy.save()
        unlock_it(self.deploy)
        trident_callback(self.deploy, 4)
        self.i('%s发布完成' % deploy_type)
        # 更新版本信息表
        self.update_version(self.deploy.ftpath)
        # 清理版本
        if self.deploy.packtype == 0:
            cleanup_list = self.cleanup_version()
            if cleanup_list:
                self.i('清理了这些版本%s' % cleanup_list)
        # 发送邮件
        if self.deploy.deptype != 0:
            self.i('开始发送发布完成邮件')
            self.deploy_email()
            self.i('结束发送发布完成邮件')
        time.sleep(HUDSON_DELAY)
        self.set_healthcheck(0)
        self.hudson_hook()

    def normal_deploy(self):
        deploy_detail_queryset = deploy_detail_list(self.depid)
        last_deploy_detail_id = deploy_detail_queryset.last().id
        for deploy_detail in deploy_detail_queryset:
            if not deploy_detail.has_backup:
                single_backup(deploy_detail)
            if not deploy_detail.has_pre:
                single_pre_deploy(deploy_detail)
            if not deploy_detail.has_real:
                # 发布前将服务下线
                if self.deploy.packtype == 0 and self.deploy.restart:
                    server_obj = Server.objects.exclude(server_status_id=400).get(ip=deploy_detail.host)
                    for log in detector_method(server_obj, 'disabled'):
                        self.i(log)
                single_deploy(deploy_detail)
                if self.deploy.packtype == 0 and self.deploy.restart_interval and deploy_detail.id != last_deploy_detail_id:
                    self.i(u'等待{0}秒'.format(self.deploy.restart_interval))
                    time.sleep(self.deploy.restart_interval)

    def gray_deploy(self):
        room_dict = self.get_room_group_by_host_list([deploy_detail.host for deploy_detail in deploy_detail_list(self.depid)])
        self.room_delay_dict = dict()
        for room in room_dict:
            self.room_delay_dict[room] = (self.deploy.recover_time/(len(room_dict[room])*(1-self.deploy.colony_surplus/100)))
        self.deploy.gray_offset_start = str(random.randint(0, 999999))
        self.deploy.save()
        self.i(set_color('偏移量:%s' % self.deploy.gray_offset_start))
        # 初始化DeployGrayData
        dst_list = [deploy_detail.host for deploy_detail in deploy_detail_list(self.depid)]
        flag, gray_data = self._format_gray_data(self.deploy.gray_release_info, dst_list)
        if not flag:
            self.ie(u'错误信息：%s' % gray_data)
        for each in gray_data:
            hosts = ','.join(each['hosts'])
            DeployGrayData.objects.get_or_create(
                depid=self.deploy.depid,
                corder=each['order'],
                defaults={
                    'percent': each['percent'],
                    'hosts': hosts
                })
        # 循环发布直到所有阶段完毕，或者需要回滚
        while self._gray_deploy():
            pass

    def _gray_deploy(self):
        deploy = DeployMain.objects.get(depid=self.depid)
        if deploy.status == 5 or (deploy.status == 8 and deploy.in_progress):
            self.ie('检测到已经回滚或者正在回滚，灰度发布被终止')
        lock_it(self.deploy)
        self.current_gray_status = self.deploy.gray_status + 1
        self.i(u'灰度第%s次开始' % self.current_gray_status)
        # ycc发布
        deploy_gray_data = DeployGrayData.objects.get(depid=self.deploy.depid, corder=self.current_gray_status)
        current_host_list = deploy_gray_data.hosts.split(',')
        deploy_gray_data_last = DeployGrayData.objects.filter(depid=self.deploy.depid).last()
        all_host_list = deploy_gray_data_last.hosts.split(',')
        for deploy4ycc in self.deploy4ycc_queryset(status=2):
            white_list = [ip for ip in current_host_list if self.get_room_by_ip(ip).id in TRIDENT_CMDB_IDC_MAPPING[deploy4ycc.idc]]
            black_list = [ip for ip in set(all_host_list) - set(current_host_list) if self.get_room_by_ip(ip).id in TRIDENT_CMDB_IDC_MAPPING[deploy4ycc.idc]]
            self.i('<a href="/deploy/ycc/detail/?depid=%s">%s的ycc发布详情</a>' % (deploy4ycc.depid, TRIDENT_YCC_IDC_MAPPING[deploy4ycc.idc]))
            if not ycc_black(deploy4ycc, black_list, white_list):
                self.ie('异常退出')
        # 正式发布
        for deploy_detail in deploy_detail_list(self.depid, has_real=0):
            if deploy_detail.host in current_host_list:
                if DeployMain.objects.get(depid=self.depid).status == 8:
                    unlock_it(self.deploy)
                    self.rollback()
                    self.rollback_exception_handling()
                if not deploy_detail.has_backup:
                    single_backup(deploy_detail)
                if not deploy_detail.has_pre:
                    single_pre_deploy(deploy_detail)
                if self.deploy.restart:
                    server_obj = Server.objects.exclude(server_status_id=400).get(ip=deploy_detail.host)
                    for log in detector_method(server_obj, 'disabled'):
                        self.i(log)
                single_deploy(deploy_detail)
                room = self.get_room_by_ip(deploy_detail.host)
                delay = self.room_delay_dict[room]
                deploy_detail_queryset = DeployDetail.objects.filter(depid=self.depid, host__in=current_host_list)
                if not all([deploy_detail_obj.has_real == 1 for deploy_detail_obj in deploy_detail_queryset]):
                    self.i('{0}的机器，等待{1}秒'.format(room.comment[:4], int(delay)))
                    time.sleep(delay)
        # zookeeper - 创建监听器
        offset_start = self.deploy.gray_offset_start
        offset_end = 10000 * int(deploy_gray_data.percent)
        self.i(u'开始监听zk回写，等待{0}秒后，会更新节点，监听超时时间为{1}秒'.format(ZOOKEEPER['WATCHER_DELAY'], ZOOKEEPER['WATCHER_TIMEOUT']))
        self.service_dict = dict()
        q = Queue()
        room_dict = self.get_room_group_by_host_list(current_host_list)
        for room in room_dict:
            for service in ZOOKEEPER['SERVICE_LIST']:
                # listen to /FlagsCenter/<siteName#poolName>/gray_hedwig/gray_hedwig.result
                worker = Thread(target=self.zookeeper_watcher, args=(q, room))
                worker.setDaemon(True)
                worker.start()
                q.put(service)
        time.sleep(ZOOKEEPER['WATCHER_DELAY'])
        # zookeeper - 更新节点
        for room in room_dict:
            for service in ZOOKEEPER['SERVICE_LIST']:
                # update /FlagsCenter/<siteName#poolName>/gray_hedwig
                path = '/FlagsCenter/%s/gray_%s' % (self.full_app_name, service)
                depid_zk = '%s_%s' % (self.depid, self.current_gray_status)
                if service == 'haproxy':
                    data = '%s;%s;%s,%s;%s' % (self.full_app_name, depid_zk, offset_start, offset_end, ','.join(room_dict[room]))
                elif service == 'squid':
                    data = '%s;%s;%s,%s' % (self.full_app_name, depid_zk, offset_start, offset_end)
                elif service == 'hedwig':
                    data = '%s;%s,%s;%s' % (depid_zk, offset_start, offset_end, ','.join(room_dict[room]))
                data = '' if deploy_gray_data.percent == '100' else data
                if not self.zookeeper_crud(operation='update', path=path, data=data, room=room):
                    self.i(set_color('更新zk失败，准备回退'))
                    unlock_it(self.deploy)
                    self.rollback()
                    self.rollback_exception_handling()
        # zookeeper - 判断返回结果
        q.join()
        rollback_bool = False
        for room in self.service_dict:
            room_cn_name = room.comment[:4]
            for service in self.service_dict[room]:
                if isinstance(self.service_dict[room][service], str):
                    self.i('%s|%s|%s' % (room_cn_name, service, self.service_dict[room][service]))
                    continue
                name = self.service_dict[room][service]['name']
                data = self.service_dict[room][service]['data']
                if data:
                    status, extra_info = self.check_znode_data(data, name)
                    if status:
                        if extra_info:
                            self.i(set_color('%s，warning:%s回写数据有点异常：%s，数据为%s' % (room_cn_name, name, extra_info, data), 'green'))
                        else:
                            self.i(u'%s，%s回写数据正常，数据为%s' % (room_cn_name, name, data))
                    else:
                        self.i(u'%s，%s回写数据异常，数据为%s' % (room_cn_name, name, data))
                        # rollback_bool = True
                else:
                    self.i(u'%s，%s没有回写数据' % (room_cn_name, name))
        if rollback_bool:
            self.i(set_color('zk回写检测失败，准备回退'))
            unlock_it(self.deploy)
            self.rollback()
            self.rollback_exception_handling()
        # 发布状态更新
        self.deploy.status = 4 if deploy_gray_data.percent == '100' else 6
        self.deploy.gray_status += 1
        self.deploy.save()
        self.i(u'灰度发布第%s步完成' % self.deploy.gray_status)
        unlock_it(self.deploy)
        # detector检测
        self.i('等待%s分钟' % self.deploy.gray_stage_interval)
        time.sleep(self.deploy.gray_stage_interval*60)
        deploy = DeployMain.objects.get(depid=self.depid)
        if deploy.status == 5 or (deploy.status == 8 and deploy.in_progress):
            self.ie('检测到已经回滚或者正在回滚，灰度发布被终止')
        detector_dict = dict()
        for host in current_host_list:
            server_obj = Server.objects.exclude(server_status_id=400).get(ip=host)
            room = self.get_room_by_ip(host)
            if server_obj.server_status_id == 200 and room.id not in DETECTOR['EXCLUDE_IDC']:
                detector_dict[host] = self.detector_check(host)
        if self.deploy.gray_rollback_type:
            self.i('忽略detector检测')
        else:
            if all(detector_dict.values()):
                self.i('detector检测成功')
            else:
                self.i(set_color('detector检测失败，准备回退|%s</span' % detector_dict))
                unlock_it(self.deploy)
                self.rollback()
                self.rollback_exception_handling()
                # return False
        # 判断是否退出循环
        return False if deploy_gray_data.percent == '100' else True

    def detector_check(self, ip):
        start_time = datetime.datetime.now()-datetime.timedelta(seconds=int(self.deploy.gray_stage_interval*60*0.7))
        start_timestamp = int(time.mktime(start_time.timetuple())) * 1000
        url = DETECTOR['PREFIX']+DETECTOR['HEALTH_API'] % (self.deploy.app.site.name, self.deploy.app.name, ip, start_timestamp)
        code, result = httpcall2(url)
        self.i('detector|%s|%s|%s' % (url, code, result))
        try:
            health_detail_dict = json.loads(result)
        except Exception, e:
            health_detail_dict = {}
        return True if health_detail_dict.get('status') == 1 else False

    def detector_method(self, ip, method):
        time.sleep(OFFLINE_DELAY)
        room = self.get_room_by_ip(ip)
        code, response = httpcall2(DETECTOR['PREFIX']+DETECTOR['METHOD_API'] % (CMDB_DETECTOR_IDC_MAPPING.get(room.id), DETECTOR['SECRET'], DETECTOR['SECRET'], ip, method))
        if code is not None and code >= 400:
            response = None
        self.i(u'服务%s：detector|%s|%s|%s' % (method, DETECTOR['PREFIX']+DETECTOR['METHOD_API'] % (CMDB_DETECTOR_IDC_MAPPING.get(room.id), '*' * 32, '*' * 32, ip, method), code, response))
        if response:
            try:
                response = json.loads(response)
            except:
                response = dict()
            if isinstance(response, dict) and response.get('result') == '0':
                return True
        return False

    def zookeeper_crud(self, **kwargs):
        operation = kwargs['operation']
        room = kwargs['room']
        room_cn_name = room.comment[:4]
        try:
            zk = KazooClient(hosts=room.zk_cluster)
            zk.start()
            if operation == 'retrieve':
                path = kwargs['path']
                zk.ensure_path(path)
                data, stat = zk.get(path)
                self.i(u'%s，获取节点%s数据成功，值为%s' % (room_cn_name, path, data))
                return data
            elif operation == 'update':
                path = kwargs['path']
                data = kwargs['data']
                zk.ensure_path(path)
                zk.set(path, bytes(data))
                self.i(u'%s，更新节点%s成功，值为%s' % (room_cn_name, path, data))
                return True
        except KazooException, e:
            self.i(u'%s，%s操作失败，原因为%s' % (room_cn_name, operation, e.message))
            return e.message
        except Exception, e:
            self.i(u'%s，%s操作失败，原因为%s' % (room_cn_name, operation, str(e)))
            return str(e)
        finally:
            zk.stop()

    def zookeeper_watcher(self, q, room):
        service = q.get()
        try:
            zk = KazooClient(hosts=room.zk_cluster)
            zk.start()
            count = 0
            path = '/FlagsCenter/%s/gray_%s/gray_%s.result' % (self.full_app_name, service, service)
            zk.ensure_path(path)

            @zk.DataWatch(path)
            def watch_node(data, stat):
                if count == 0:
                    self.service_dict[room] = self.service_dict.get(room, dict())
                    self.service_dict[room][stat.pzxid] = self.service_dict[room].get(stat.pzxid, dict())
                    self.service_dict[room][stat.pzxid]['name'] = service
                    self.service_dict[room][stat.pzxid]['data'] = False
                else:
                    self.service_dict[room][stat.pzxid]['data'] = data
            while count < (ZOOKEEPER['WATCHER_TIMEOUT'] + ZOOKEEPER['WATCHER_DELAY']) * ZOOKEEPER['WATCHER_TIMES']:
                if all([self.service_dict[room][pzxid]['data'] for pzxid in self.service_dict[room]]):
                    q.task_done()
                    return
                count += 1
                time.sleep(1.0 / ZOOKEEPER['WATCHER_TIMES'])
            q.task_done()
            return
        except KazooException, e:
            self.service_dict[room] = e.message
            self.i(u'%s，watcher操作失败，原因为%s' % (room.comment[:4], self.service_dict))
            q.task_done()
            return
        except Exception, e:
            self.service_dict[room] = str(e)
            self.i(u'%s，watcher操作失败，原因为%s' % (room.comment[:4], self.service_dict))
            q.task_done()
            return
        finally:
            zk.stop()

    def check_znode_data(self, data, service):
        data_list = data.split(';')
        if len(data_list) >= 3:
            depid_zk = '%s_%s' % (self.depid, self.deploy.gray_status+1)
            if service in ('haproxy', 'squid'):
                depid, result = data_list[1:3]
                if depid.strip() == depid_zk:
                    if result.strip() == '0':
                        return True, None
                    elif result.strip() == '2':
                        return True, u'IP或POOL不在%s的配置中' % service
                    else:
                        return False, None
                else:
                    return False, None
            elif service == 'hedwig':
                depid, result = data_list[0:2]
                if depid.strip() == depid_zk and result.strip() == '0':
                    return True, None
                else:
                    return False, None
        else:
            return False, None

    def catalina(self):
        items = deploy_detail_list(self.depid)
        item = items[0]
        host = item.host
        cmd = 'tail -n100 /usr/local/tomcat6/logs/catalina.out'
        return ssh(cmd, host)

    def check_interval(self):
        app_id = self.deploy.app_id
        items = DeployMain.objects.filter(app_id=app_id, status=4, valid=1, deptype__gt=0, packtype=self.deploy.packtype).order_by('-last_modified')[0:1]
        if items:
            last_deploy = items[0]
            last = int(last_deploy.last_modified)
            now = int(time.time())
            if now - last < CHECK_INTERVAL * 60:
                self.i(set_color('提示: 这个POOL在%s分钟内已经发布过一次' % CHECK_INTERVAL))

    # 灰度策略算法
    def _format_gray_data(self, gray_data, hosts):
        ret = []
        gray_data_list = gray_data.strip().split(',')
        if len(gray_data_list) <= 1:
            return False, '灰度发布至少需要2个阶段'
        if gray_data_list[-1] != '100':
            return False, '灰度发布最后阶段必须为100%'

        i = 1
        room_dict = dict()
        for host in hosts:
            room = self.get_room_by_ip(host)
            room_id = room.id
            # 上海南汇机房B1和上海南汇机房B2属于一个机房
            if room_id == 2:
                room_id = 1
            room_dict[room_id] = room_dict.get(room_id, [])
            room_dict[room_id].append(host)
        # self.i(room_dict)
        for each in gray_data_list:
            ret_item = {}
            item = int(each)
            ret_item['order'] = i
            ret_item['percent'] = item
            ret_item['hosts'] = self._gray_cut_hosts(room_dict, item)
            i += 1
            ret.append(ret_item)
        return True, ret

    # 机器切分算法
    def _gray_cut_hosts(self, room_dict, percent):
        # 算出要发布多少台
        hosts_all = []
        for room in room_dict:
            hosts = room_dict[room]
            hosts_sum = int(math.ceil(percent*len(hosts)/100))
            format_hosts_sum = hosts_sum
            if hosts_sum == 1:
                format_hosts_sum = 2
            if len(hosts)-format_hosts_sum == 1:
                format_hosts_sum -= 1
            hosts_all += hosts[:format_hosts_sum]
        return hosts_all

    def get_room_by_ip(self, host):
        try:
            server = Server.objects.exclude(server_status_id=400).get(ip=host)
        except Server.DoesNotExist:
            self.ie(u'找不到%s的机房!' % host)
        except Server.MultipleObjectsReturned:
            self.ie(u'%s对应多个机房!' % host)
        asset = server.asset if server.server_type_id == 1 else server.parent_asset
        room = asset.rack.room
        return room

    def get_room_group_by_host_list(self, hosts):
        room_dict = dict()
        for ip in hosts:
            room_obj = self.get_room_by_ip(ip)
            room_dict[room_obj] = room_dict.get(room_obj, [])
            room_dict[room_obj].append(ip)
        return room_dict

    def hudson_hook(self):
        items = HudsonJob.objects.filter(app_id=self.deploy.app_id)
        if items and self.deploy.packtype == 0:
            if self.deploy.deptype in [1, 2]:
                jobs = items.filter(jobtype=2)
            elif self.deploy.deptype == 0:
                jobs = items.filter(jobtype=1)
            if not jobs:
                jobs = items.filter(jobtype=0)
            job = jobs[0] if jobs else None
            if job:
                url = '%s?token=%s' % (job.url, job.token)
                code, data = httpcall2(url)
                if code is None:
                    self.ie('hudson错误：执行命令：【%s|%s】' % (url, data))
                elif code >= 400:
                    self.ie('hudson错误：执行命令：【%s|%s】' % (url, code))
                self.i('hudson执行命令：【%s|%s】' % (url, code))
            else:
                self.i('没有对应的hudson_job')

    def deploy4ycc_queryset(self, status):
        return DeployMainConfig.objects.filter(jiraid=self.deploy.jiraid, app_id=self.deploy.app_id, status=status) if self.deploy.jiraid else []

    def rollback(self):
        self.deploy.status = 8
        self.deploy.save()
        if is_locked(self.deploy):
            return False
        lock_it(self.deploy)
        self.i('开始回滚操作')
        # 灰度发布先回滚YCC
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            for deploy4ycc in self.deploy4ycc_queryset(status=2):
                self.i('<a href="/deploy/ycc/detail/?depid=%s">ycc回滚详情</a>' % deploy4ycc.depid)
                if not ycc_rollback2(deploy4ycc):
                    self.ie('异常退出')
        # 回滚
        deploy_detail_queryset = deploy_detail_list(self.depid, has_real=1, has_rollback=0)
        if self.parallel:
            result = group(parallel_rollback.s(deploy_detail.id, self.pattern) for deploy_detail in deploy_detail_queryset)()
            result_list = result.get()
            if not all(result_list):
                self.ie('未成功执行回滚')
        else:
            for deploy_detail in deploy_detail_queryset:
                single_rollback(deploy_detail, self.pattern)
                if self.deploy.packtype == 0 and self.interval and deploy_detail_queryset.filter(has_rollback=0).exists():
                    self.i(u"等待{0}秒".format(self.interval))
                    time.sleep(self.interval)
        # 灰度发布更新zookeeper
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            host_list = [deploy_detail.host for deploy_detail in deploy_detail_list(self.depid)]
            for room in self.get_room_group_by_host_list(host_list):
                for service in ZOOKEEPER['SERVICE_LIST']:
                    path = '/FlagsCenter/%s/gray_%s' % (self.full_app_name, service)
                    self.zookeeper_crud(operation='update', path=path, data='', room=room)
        # self.deploy.status = 5
        # self.deploy.last_modified = int(time.time())
        # self.deploy.save()
        trident_callback(self.deploy, 5)
        # 更新版本信息表
        self.update_version(self.deploy.last_ftpath)
        self.i('结束回滚操作')
        unlock_it(self.deploy)

    def single_rollback(self, deploy_detail):
        src = os.path.join(os.path.dirname(self.deploy.deprepath), os.path.basename(self.deploy.last_ftpath)) if self.deploy.last_ftpath else self.deploy.backup
        dst = self.deploy.path.rstrip('/')
        # if not path_exists(src, deploy_detail.host):
        #     single_pre_deploy(deploy_detail)
        if self.deploy.packtype == 0:
            status, cmd, output = ssh('/bin/rm -rf {0} && /bin/ln -s {1} {2}'.format(dst, src, dst), deploy_detail.host)
        else:
            src += '/'
            status, cmd, output = ssh('test -L %s && rm -f %s' % (dst, dst), deploy_detail.host)
            if status:
                i(deploy_detail.depid, '回滚：[%s]工作目录为软链接，需要删除。执行命令：%s 执行结果：%s###' %(deploy_detail.host, cmd, output))
            status, cmd, output = rsync4nocheck(src, dst, host_key_checking=False, checksum=True, remote_host=deploy_detail.host)
        msg = '回滚：[%s]代码回滚%s。执行命令：%s 执行结果：%s' % (deploy_detail.host, STATUS_MAPPING[status], cmd, output)
        if not status:
            self.ie(msg)
        self.i(msg)
        deploy_detail.has_rollback = 1
        deploy_detail.rollback_time = int(time.time())
        deploy_detail.complete = 1
        deploy_detail.save()
        if self.deploy.restart:
            application_restart(deploy_detail.host, self.pattern, self.cache, self.depid)
        action = u"gray_rollback" if self.deploy.is_gray_release else u"normal_rollback"
        change(user=self.deploy.user.username if self.deploy.user else None, action=action, index=deploy_detail.host, message=self.deploy.depid)

    def update_version(self, ftp_path):
        if self.deploy.packtype != 0:
            return
        deploy_version_app, created = DeployVersionApp.objects.get_or_create(
            app=self.deploy.app,
            app_env_id=2,
            pack_type=self.deploy.packtype,
            defaults={
                'ftp_path': ftp_path
            })
        if not created:
            deploy_version_app.ftp_path = ftp_path
            deploy_version_app.save()
        self.i('更新版本：%s' % ftp_path)

    def rollback_exception_handling(self):
        self.deploy.last_modified = int(time.time())
        self.deploy.save()
        trident_callback(self.deploy, 5)
        # 发送邮件
        if self.deploy.deptype != 0:
            self.i('开始发送发布完成邮件')
            self.deploy_email()
            self.i('结束发送发布完成邮件')
        self.set_healthcheck(0)
        time.sleep(HUDSON_DELAY)
        self.hudson_hook()
        self.ie('未完成发布')

    def cleanup_version(self):
        cleanup_list = []
        code_path = os.path.dirname(self.deploy.codepath)
        deploy_main_queryset = DeployMain.objects.filter(app_id=self.deploy.app_id, status=4, deptype__in=(1, 2), packtype=0).order_by('-id')[:5]
        version_list = [os.path.basename(deploy_main_obj.ftpath) for deploy_main_obj in deploy_main_queryset]
        for version in os.listdir(code_path):
            if version not in version_list:
                cleanup_list.append(version)
                try:
                    shutil.rmtree(str(os.path.join(code_path, version)))
                except Exception, e:
                    self.ie('清理版本失败，原因为：%s' % str(e.args))
        return cleanup_list
