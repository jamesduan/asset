# -*- coding: utf-8 -*-
from __future__ import division
from django.template import loader
from kazoo.client import KazooClient
from kazoo.exceptions import KazooException
from threading import Thread, Lock
from cmdb.models import *
from asset.models import Room
from deploy.utils.DeployCommon import *
from deploy.utils.Utils import *
from deploy.utils.PreDeploy import PreDeploy
from deploy.tasks import parallel_rollback
from util.httplib import httpcall2
from util.timelib import timelength_format
from util.sendmail import sendmail_html, sendmail_v2
from django.contrib.auth.models import User
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
from change.utiltask import RL_all_deploy
from celery.exceptions import Reject


class Publish:
    def __init__(self, depid, from_scratch=True, rollback_type={'type': 0, 'interval': DEPLOY_INTERVAL}):
        self.depid = depid
        self.deploy = DeployMain.objects.get(depid=depid)
        self.pool_name = '/'.join([self.deploy.app.site.name, self.deploy.app.name])
        self.cache = get_cache('deploy')
        self.pattern = get_process_pattern_by_app_id(self.deploy.app_id)
        self.ip_list = [deploy_detail.server.ip for deploy_detail in self.get_deploy_detail_queryset()]
        # self.cache.set(self.depid, [dict(log_dict, **{'error': False}) for log_dict in self.cache.get(self.depid)])
        self.rollback_type = rollback_type
        self.gray_stage_list = []
        self.from_scratch = from_scratch
        self.room_delay_dict = dict()
        self.service_dict = dict()

    def ie(self, log):
        if log:
            self.i(log, error=True)
            self.update_deploy_obj()
            if self.deploy.status == 9:
                self.update_deploy_status(10)
            elif self.deploy.status == 11:
                self.update_deploy_status(12)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.depid, log, error)

    def health_check(self):
        if self.deploy.packtype != 0:
            return True
        self.i('检查HealthCheck是否设置')
        url = HC['PREFIX'] + HC['API'].format(self.deploy.app_id)
        fp = urllib2.urlopen(url)
        result = json.loads(fp.read())
        return result['data']['isSetHealthCheck']

    def set_healthcheck(self, status=1):
        if self.deploy.packtype != 0:
            return
        status, url, msg = set_healthcheck(self.ip_list, status)
        output = ':'.join([msg, url])
        if status:
            self.i(output)
        else:
            self.ie(output)

    def deploy_email(self):
        if self.deploy.deptype == 0:
            return None
        app_id = self.deploy.app_id
        try:
            contact = AppContact.objects.get(pool_id=app_id)
        except AppContact.DoesNotExist:
            self.i('POOL联系人信息没有设置，请在itil的pool联系人中设置(不影响正常发布)。')
        mails = [contact.domain_email] + contact.p_email.split(',')
        mails += MAIL_RECIPIENT
        to = [item.strip() for item in mails if item.strip()]
        jiraid = self.deploy.jiraid
        subject = '%s-%s-%s-%s上线结果' % (contact.domain_name, self.pool_name, self.deploy.get_packtype_display(),
                                       stamp2str(time.time(), formt='%Y-%m-%d'))
        cmdstr, status, output = self.catalina()
        if not status:
            self.i('取Tomcat日志时报错，无法发送邮件(不影响正常发布)。')
        log = output
        import cgi
        html = loader.render_to_string('deploy/deploy_mail.html', {
            'jiraid': jiraid,
            'pool': cgi.escape(self.pool_name),
            'log': cgi.escape(log)}) if self.deploy.packtype == 0 else loader.render_to_string('mail/deploy/manual/static/publish_success.html',
                                                                                                {
                                                                                                    'jiraid' : jiraid,
                                                                                                    'pool' : cgi.escape(self.pool_name),
                                                                                                })
        if self.deploy.deptype == 1:
            latest_ftp_path = latest_staging_version(self.deploy)
            if latest_ftp_path:
                extra_list = ['检测到发布的版本和当前Stg版本不同']
                extra_list.append('发布的版本：%s' % os.path.basename(self.deploy.ftpath))
                extra_list.append('Stg的版本：%s' % os.path.basename(latest_ftp_path))
                html = '<br>'.join(extra_list) + html
        maintained_server_obj_list = Server.objects.filter(app_id=self.deploy.app_id, server_status_id=210, server_env_id=2)
        if maintained_server_obj_list.exists():
            html = '维护中的主机没有发布，请知悉:%s<br>' % ','.join(
                [server_obj.ip for server_obj in maintained_server_obj_list]) + html
            to.append('IT_OPS_SA@yhd.com')
        self.i('邮件发送给%s' % to)
        if not to:
            self.i('domain的email没有设置，请在itil的pool联系人中设置(不影响正常发布)。')
        # sendmail_html(subject=subject, html_content=html.encode('utf8'), recipient_list=MAIL_RECIPIENT)
        sendmail_v2(subject=subject, html_content=html.encode('utf8'), recipient_list=to, app=self.deploy.app)

    def update_deploy_obj(self):
        self.deploy = DeployMain.objects.get(depid=self.depid)

    def update_deploy_status(self, status):
        self.deploy.last_modified = int(time.time())
        self.deploy.status = status
        self.deploy.save(update_fields=['last_modified', 'status'])

        username = User.objects.get(pk=self.deploy.uid).username
        index = self.deploy.depid
        app_id = self.deploy.app_id
        deploy_webapp_detail_url = DEPLOY_DETAIL_URL % (OMS_HOST, self.deploy.depid)
        deploy_type_msg = '-'.join(["程序发布", self.deploy.deptype_name, self.deploy.packtype_name])
        message = """ 单号: <a href="%s" target="_blank">%s</a> 发布类型为: %s 更改状态为: %s """ % (deploy_webapp_detail_url, 
                                                                                     self.deploy.depid, 
                                                                                     deploy_type_msg, 
                                                                                     self.deploy.status_name)
        RL_all_deploy(username, index, message, app_id)

    # 开始发布
    def auto_publish(self):
        # time.sleep(random.random() * 2)
        if is_locked_v2(self.deploy):
            # self.ie('%s，不允许发布' % self.deploy.get_status_display())
            message = '有额外的请求发布, %s，不允许发布' % self.deploy.get_status_display()
            self.i(message)
            raise Reject(message)
        # 检查预发布是否完成
        if self.deploy.status < 3:
            pre_deploy = PreDeploy(depid=self.deploy.depid)
            pre_deploy.auto_publish()
            self.deploy = DeployMain.objects.get(depid=self.depid)
        self.i('开始发布')
        # deploy start time 
        self.update_deploy_status(9)
        self.deploy.signal = 0
        self.deploy.save()
        if self.from_scratch:
            # 重新初始化发布列表，避免发布之前有新的服务器上架
            deploy_detail_init_v2(self.deploy)
            if not DeployDetailV2.objects.filter(depid=self.depid, is_source=0):
                msg = '没有使用中的主机，请联系SRE'
                self.i(msg, error=True)
                self.update_deploy_status(3)
                raise DeployError(msg)
            self.ip_list = [deploy_detail.server.ip for deploy_detail in self.get_deploy_detail_queryset()]
            # 检查HealthCheck是否设置
            if not self.health_check():
                self.ie('HealthCheck有问题，请检查是否设置HealthCheck')
            # 关闭HealthCheck
            self.set_healthcheck(1)
            # 检查最近是否有过发布
            if self.deploy.deptype > 0:
                self.check_interval()
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            self.gray_deploy()
        else:
            self.normal_deploy()
        # 更新版本信息表
        self.update_version(self.deploy.ftpath)
        # 发送邮件
        if self.deploy.deptype != 0:
            self.deploy_email()
        trident_callback(self.deploy, 4)
        self.i('发布完成')
        # 清理版本
        if self.deploy.packtype == 0:
            cleanup_list = self.cleanup_version()
            if cleanup_list:
                self.i('清理了这些版本%s' % cleanup_list)
        time.sleep(HUDSON_DELAY)
        self.set_healthcheck(0)
        self.hudson_hook()

    def normal_deploy(self):
        for deploy_detail in self.get_deploy_detail_queryset({'has_real': 0}):
            self.update_deploy_obj()
            if self.deploy.signal == 1:
                self.ie('发布被暂停')
            if not deploy_detail.has_backup:
                single_backup(deploy_detail)
            if not deploy_detail.has_pre:
                single_pre_deploy(deploy_detail)
            if not deploy_detail.has_real:
                # if self.deploy.packtype == 0 and self.deploy.restart:
                #     server_obj = Server.objects.exclude(server_status_id=400).get(ip=deploy_detail.host)
                #     for log in detector_method(server_obj, 'disabled'):
                #         self.i(log)
                # 正式发布
                try:
                    single_deploy_v2(deploy_detail)
                except Exception, e:
                    self.ie(e.message)
                # 等待间隔
                if self.deploy.packtype == 0 and self.deploy.restart_interval and len(self.get_deploy_detail_queryset({'has_real': 0})):
                    self.i('等待{0}秒'.format(self.deploy.restart_interval))
                    now = int(time.time())
                    while int(time.time()) - now < self.deploy.restart_interval:
                        self.update_deploy_obj()
                        if self.deploy.signal == 1:
                            self.ie('发布被暂停')
                        time.sleep(1)

    def gray_deploy(self):
        self.gray_stage_list = self.deploy.gray_release_info.split(',')
        # 按照IDC分组
        room_dict = get_room_group_by_server_queryset([deploy_detail.server for deploy_detail in self.get_deploy_detail_queryset()])
        # 计算各IDC的发布间隔 & 计算灰度阶段
        for room in room_dict:
            # 计算各IDC发布间隔
            self.room_delay_dict[room] = self.deploy.recover_time / (len(room_dict[room]) * (1 - self.deploy.colony_surplus / 100))
            # 计算灰度阶段
            gray_stage = 0
            for percent in self.gray_stage_list:
                gray_stage += 1
                for server_obj in room_dict[room][:int(math.ceil(len(room_dict[room])*int(percent)/float(100)))]:
                    deploy_detail_obj = self.get_deploy_detail_queryset().get(server=server_obj)
                    if deploy_detail_obj.gray_stage == 0:
                        deploy_detail_obj.gray_stage = gray_stage
                        deploy_detail_obj.save()
        # 设置偏移量
        if not self.deploy.gray_offset_start:
            self.deploy.gray_offset_start = str(random.randint(0, 999999))
            self.deploy.save()
            self.i('偏移量:%s' % self.deploy.gray_offset_start)
        # 循环发布直到所有阶段完毕，或者需要回滚
        while self._gray_deploy():
            pass

    def _gray_deploy(self):
        self.current_gray_status = self.deploy.gray_status + 1
        self.i('灰度第%s次开始' % self.current_gray_status)
        if self.deploy.status == 6:
            self.update_deploy_status(9)
        # ********** 发布阶段 **********
        # ycc发布
        for deploy4ycc in self.deploy4ycc_queryset(status=2):

            room_ids = []
            if deploy4ycc.idc:
                room_ids = TRIDENT_CMDB_IDC_MAPPING[deploy4ycc.idc]
                ycc_code = TRIDENT_YCC_IDC_MAPPING[deploy4ycc.idc]
            else:
                room_ids = [deploy4ycc.zone_id]
                ycc_code = Room.objects.get(id=deploy4ycc.zone_id).ycc_code

            white_list = [deploy_detail_obj.server.ip for deploy_detail_obj in
                          self.get_deploy_detail_queryset({'gray_stage__lte': self.current_gray_status}) if
                          deploy_detail_obj.server.rack.room.id in room_ids]
            black_list = [deploy_detail_obj.server.ip for deploy_detail_obj in
                          self.get_deploy_detail_queryset({'gray_stage__gt': self.current_gray_status}) if
                          deploy_detail_obj.server.rack.room.id in room_ids]
            self.i('<a href="/deploy/ycc/detail/?depid=%s">%s的ycc发布详情</a>' % (deploy4ycc.depid, ycc_code))
            if not ycc_black(deploy4ycc, black_list, white_list):
                self.ie('异常退出')
        # 正式发布
        for deploy_detail in self.get_deploy_detail_queryset({'has_real': 0, 'gray_stage': self.current_gray_status}):
            self.update_deploy_obj()
            if self.deploy.signal == 1:
                self.ie('发布暂停')
            if not deploy_detail.has_backup:
                single_backup(deploy_detail)
            if not deploy_detail.has_pre:
                single_pre_deploy(deploy_detail)
            # if self.deploy.restart:
            #     server_obj = Server.objects.exclude(server_status_id=400).get(ip=deploy_detail.server.ip)
            #     for log in detector_method(server_obj, 'disabled'):
            #         self.i(log)
            try:
                single_deploy_v2(deploy_detail)
            except Exception, e:
                self.ie(e.message)
            room_obj = deploy_detail.server.rack.room
            delay = self.room_delay_dict[room_obj]
            if len(self.get_deploy_detail_queryset({'has_real': 0, 'gray_stage': self.current_gray_status})):
                self.i('{0}的机器，等待{1}秒'.format(room_obj.comment[:4], int(delay)))
                now = int(time.time())
                while int(time.time()) - now < delay:
                    self.update_deploy_obj()
                    if self.deploy.signal == 1:
                        self.ie('发布被暂停')
                    time.sleep(1)
        # zookeeper - 创建线程作为监听器
        self.i('开始监听zk回写，监听超时时间为{0}秒'.format(ZOOKEEPER['WATCHER_TIMEOUT']))
        self.service_dict = dict()
        queue = Queue()
        lock = Lock()
        room_dict = get_room_group_by_server_queryset([deploy_detail.server for deploy_detail in
                                                            self.get_deploy_detail_queryset(
                                                                {'gray_stage__lte': self.current_gray_status})])
        for room in room_dict:
            for service in ZOOKEEPER['SERVICE_LIST']:
                # listen to /FlagsCenter/<siteName#poolName>/gray_hedwig/gray_hedwig.result
                worker = Thread(target=self.zookeeper_watcher, args=(queue, lock, room, [server.ip for server in room_dict[room]]))
                worker.setDaemon(True)
                worker.start()
                queue.put(service)

        # 等待所有线程退出
        queue.join()
        # 发布状态更新
        self.deploy.gray_status += 1
        self.deploy.status = 6
        self.deploy.save()
        self.i('灰度发布第%s步完成' % self.deploy.gray_status)
        # ********** 阶段等待 **********
        self.i('等待%s分钟' % self.deploy.gray_stage_interval)
        now = int(time.time())
        while int(time.time()) - now < self.deploy.gray_stage_interval * 60:
            self.update_deploy_obj()
            if self.deploy.status != 6:
                self.ie(None)
            time.sleep(1)
        # ********** 检测阶段 **********
        detector_dict = dict()
        for deploy_detail_obj in self.get_deploy_detail_queryset({'gray_stage': self.current_gray_status}):
            self.update_deploy_obj()
            if self.deploy.status != 6:
                self.ie(None)
            if deploy_detail_obj.server.server_status_id == 200:
                detector_dict[deploy_detail_obj.server.ip] = self.detector_check(deploy_detail_obj.server.ip)
        if self.deploy.gray_rollback_type:
            self.i('忽略detector检测')
        else:
            if all(detector_dict.values()):
                self.i('detector检测成功')
            else:
                self.i(set_color('detector检测失败，准备回退|%s</span' % detector_dict))
                self.rollback()
                # return False
        # 判断是否退出循环
        return False if len(self.gray_stage_list) == self.deploy.gray_status else True

    def detector_check(self, ip):
        start_time = datetime.datetime.now() - datetime.timedelta(
            seconds=int(self.deploy.gray_stage_interval * 60 * 0.7))
        start_timestamp = int(time.mktime(start_time.timetuple())) * 1000
        url = DETECTOR['PREFIX'] + DETECTOR['HEALTH_API'] % (
        self.deploy.app.site.name, self.deploy.app.name, ip, start_timestamp)
        code, result = httpcall2(url)
        self.i('detector|%s|%s|%s' % (url, code, result))
        try:
            health_detail_dict = json.loads(result)
        except Exception, e:
            health_detail_dict = {}
        return True if health_detail_dict.get('status') == 1 else False

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
                self.i('%s，获取节点%s数据成功，值为%s' % (room_cn_name, path, data))
                return data
            elif operation == 'update':
                path = kwargs['path']
                data = kwargs['data']
                zk.ensure_path(path)
                zk.set(path, bytes(data))
                print ':'.join([str(zk.hosts), 'set', path, data])
                self.i('%s，更新节点%s成功，值为%s' % (room_cn_name, path, data))
                print ':'.join([str(zk.hosts), 'get', path, zk.get(path)[0]])
                return True
        except KazooException, e:
            self.i('%s，%s操作失败，原因为%s' % (room_cn_name, operation, e.message))
            return False
        except Exception, e:
            self.i('%s，%s操作失败，原因为%s' % (room_cn_name, operation, str(e)))
            return False
        finally:
            zk.stop()

    def zookeeper_watcher(self, queue, lock, room, ip_list):
        service = queue.get()
        path = '/FlagsCenter/%s/gray_%s' % (self.pool_name, service)
        if service == 'haproxy':
            path = '/FlagsCenter/%s' % self.pool_name
        path_result = os.path.join(path, 'gray_%s.result' % service)
        depid_zk = '%s_%s' % (self.depid, self.current_gray_status)
        offset_start = self.deploy.gray_offset_start
        offset_end = 10000 * int(self.gray_stage_list[self.deploy.gray_status])
        self.service_dict[room] = self.service_dict.get(room, dict())
        self.service_dict[room][service] = self.service_dict[room].get(service)
        try:
            zk = KazooClient(hosts=room.zk_cluster)
            zk.start()
            zk.ensure_path(path_result)

            # 创建监听器
            @zk.DataWatch(path_result)
            def watch_node(data, stat, event):
                if event is not None:
                    self.service_dict[room][service] = data
                    print ':'.join([str(zk.hosts), data])
            # 更新节点
            data = '' if len(self.gray_stage_list) == self.current_gray_status else {
                'haproxy': '%s;%s;%s,%s;%s' % (self.pool_name, depid_zk, offset_start, offset_end, ','.join(ip_list)),
                'squid': '%s;%s;%s,%s' % (self.pool_name, depid_zk, offset_start, offset_end),
                'hedwig': '%s;%s,%s;%s' % (depid_zk, offset_start, offset_end, ','.join(ip_list))
            }.get(service)
            zk.set(path, bytes(data))
            self.i('%s，更新节点%s成功，值为%s' % (room.comment[:4], path, data))
            print ':'.join([str(zk.hosts), 'set', path, data])
            print ':'.join([str(zk.hosts), 'get', path, zk.get(path)[0]])
            # 观察回写结果
            now = int(time.time())
            while int(time.time()) - now < ZOOKEEPER['WATCHER_TIMEOUT'] * ZOOKEEPER['WATCHER_TIMES']:
                if self.service_dict[room][service]:
                    lock.acquire()
                    self.i('%s，%s回写数据正常，数据为%s' % (room.comment[:4], service, self.service_dict[room][service]))
                    lock.release()
                    queue.task_done()
                    return
                time.sleep(1.0 / ZOOKEEPER['WATCHER_TIMES'])
            lock.acquire()
            self.i('%s，%s没有回写数据' % (room.comment[:4], service))
            lock.release()
            queue.task_done()
            return
        except KazooException, e:
            lock.acquire()
            self.i('%s，zk操作%s失败，原因为%s' % (room.comment[:4], path, e.message))
            lock.release()
            queue.task_done()
            return
        except Exception, e:
            lock.acquire()
            self.i('%s，zk操作%s失败，原因为%s' % (room.comment[:4], path, str(e)))
            lock.release()
            queue.task_done()
            return
        finally:
            zk.stop()

    # def check_znode_data(self, data, service):
    #     data_list = data.split(';')
    #     if len(data_list) >= 3:
    #         depid_zk = '%s_%s' % (self.depid, self.deploy.gray_status + 1)
    #         if service in ('haproxy', 'squid'):
    #             depid, result = data_list[1:3]
    #             if depid.strip() == depid_zk:
    #                 if result.strip() == '0':
    #                     return True, None
    #                 elif result.strip() == '2':
    #                     return True, 'IP或POOL不在%s的配置中' % service
    #                 else:
    #                     return False, None
    #             else:
    #                 return False, None
    #         elif service == 'hedwig':
    #             depid, result = data_list[0:2]
    #             if depid.strip() == depid_zk and result.strip() == '0':
    #                 return True, None
    #             else:
    #                 return False, None
    #     else:
    #         return False, None

    def catalina(self):
        cmd = 'tail -n100 /usr/local/tomcat6/logs/catalina.out'
        return ssh(cmd, self.get_deploy_detail_queryset().first().server.ip)

    def check_interval(self):
        deploy_main_obj = DeployMain.objects.filter(app_id=self.deploy.app_id, status=4, valid=1, deptype__gt=0, packtype=self.deploy.packtype).last()
        if deploy_main_obj:
            last = int(deploy_main_obj.last_modified)
            now = int(time.time())
            if now - last < CHECK_INTERVAL * 60:
                self.i(set_color('提示: 这个POOL在%s分钟内已经发布过一次' % CHECK_INTERVAL))

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
        return DeployMainConfig.objects.filter(jiraid=self.deploy.jiraid, app_id=self.deploy.app_id,
                                               status=status) if self.deploy.jiraid else []

    def rollback(self):
        self.i('开始回滚')
        self.update_deploy_status(11)
        self.deploy.signal = 0
        self.deploy.save()
        # 配置回滚
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            for deploy4ycc in self.deploy4ycc_queryset(status=2):
                self.i('<a href="/deploy/ycc/detail/?depid=%s">ycc回滚详情</a>' % deploy4ycc.depid)
                if not ycc_rollback2(deploy4ycc):
                    self.ie('异常退出')
        # 代码回滚
        deploy_detail_init_v2(self.deploy)
        # 串行
        if self.rollback_type['type'] == 0:
            interval = self.rollback_type['interval']
            for deploy_detail in self.get_deploy_detail_queryset({'has_real': 1, 'has_rollback': 0}):
                self.update_deploy_obj()
                if self.deploy.signal == 1:
                    self.ie('回滚被暂停')
                try:
                    single_rollback_v2(deploy_detail, self.pattern)
                except Exception, e:
                    self.ie(e.message)
                if self.deploy.packtype == 0 and interval and self.get_deploy_detail_queryset({'has_real':1, 'has_rollback': 0}).exists():
                    self.i(u"等待{0}秒".format(interval))
                    now = int(time.time())
                    while int(time.time()) - now < interval:
                        self.update_deploy_obj()
                        if self.deploy.signal == 1:
                            self.ie('发布被暂停')
                        time.sleep(1)
        # 并行
        elif self.rollback_type['type'] == 1:
            result = group(parallel_rollback.s(deploy_detail.id, self.pattern) for deploy_detail in
                           self.get_deploy_detail_queryset({'has_real': 1, 'has_rollback': 0}))()
            result_list = result.get()
            if not all(result_list):
                self.ie('部分主机回滚失败')
        # 分组
        # {"type":2,"interval":15,"group_interval":0,"policy":{"1":{"type":"1","percent":"30"},"2":{"type":"0","percent":"70"}}}
        elif self.rollback_type['type'] == 2:
            percent_sum = 0
            interval = self.rollback_type['interval']
            group_interval = self.rollback_type['group_interval']
            deploy_detail_queryset = self.get_deploy_detail_queryset({'has_real': 1, 'has_rollback': 0})
            for stage in self.rollback_type['policy']:
                rollback_type = self.rollback_type['policy'][stage]['type']
                percent = self.rollback_type['policy'][stage]['percent']
                percent_sum += percent
                current_deploy_detail_queryset = deploy_detail_queryset[: int(math.ceil(len(deploy_detail_queryset)*int(percent_sum)/float(100)))]
                if rollback_type == 0:
                    for deploy_detail in current_deploy_detail_queryset:
                        self.update_deploy_obj()
                        if self.deploy.signal == 1:
                            self.ie('回滚被暂停')
                        if DeployDetailV2.objects.get(id=deploy_detail.id).has_rollback == 1:
                            continue
                        try:
                            single_rollback_v2(deploy_detail, self.pattern)
                        except Exception, e:
                            self.ie(e.message)
                        if self.deploy.packtype == 0 and interval:
                            self.i(u"等待{0}秒".format(interval))
                            now = int(time.time())
                            while int(time.time()) - now < interval:
                                self.update_deploy_obj()
                                if self.deploy.signal == 1:
                                    self.ie('发布被暂停')
                                time.sleep(1)
                if rollback_type == 1:
                    result = group(parallel_rollback.s(deploy_detail.id, self.pattern) for deploy_detail in
                                   current_deploy_detail_queryset if
                                   DeployDetailV2.objects.get(id=deploy_detail.id).has_rollback == 0)()
                    result_list = result.get()
                    if not all(result_list):
                        self.ie('部分主机回滚失败')
                if int(stage) < len(self.rollback_type['policy']):
                    self.i(u"等待{0}分钟".format(group_interval))
                    now = int(time.time())
                    while int(time.time()) - now < group_interval * 60:
                        self.update_deploy_obj()
                        if self.deploy.signal == 1:
                            self.ie('发布被暂停')
                        time.sleep(1)
        # 灰度发布更新zookeeper
        if self.deploy.is_gray_release == 1 and self.deploy.packtype == 0:
            room_dict = get_room_group_by_server_queryset([deploy_detail.server for deploy_detail in self.get_deploy_detail_queryset()])
            for room in room_dict:
                for service in ZOOKEEPER['SERVICE_LIST']:
                    path = '/FlagsCenter/%s/gray_%s' % (self.pool_name, service)
                    if service == 'haproxy':
                        path = '/FlagsCenter/%s' % self.pool_name
                    self.zookeeper_crud(operation='update', path=path, data='', room=room)
        # 更新版本信息表
        self.update_version(self.deploy.last_ftpath)
        # 发送邮件
        if self.deploy.deptype != 0:
            self.deploy_email()
        self.set_healthcheck(0)
        trident_callback(self.deploy, 5)
        self.i('结束回滚操作')
        time.sleep(HUDSON_DELAY)
        self.hudson_hook()

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

    def cleanup_version(self):
        cleanup_list = []
        code_path = os.path.dirname(self.deploy.codepath)
        deploy_main_queryset = DeployMain.objects.filter(app_id=self.deploy.app_id, status=4, deptype__in=(1, 2),
                                                         packtype=0).order_by('-id')[:5]
        version_list = [os.path.basename(deploy_main_obj.ftpath) for deploy_main_obj in deploy_main_queryset]
        for version in os.listdir(code_path):
            if version not in version_list:
                cleanup_list.append(version)
                try:
                    shutil.rmtree(str(os.path.join(code_path, version)))
                except Exception, e:
                    self.ie('清理版本失败，原因为：%s' % str(e.args))
        return cleanup_list

    def get_deploy_detail_queryset(self, filters={}):
        original_filters = {
            'depid': self.depid,
            'server__server_env_id': 2
        }
        original_filters = dict(original_filters, **filters)
        return DeployDetailV2.objects.filter(**original_filters)
