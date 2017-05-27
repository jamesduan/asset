# -*- coding: utf-8 -*-
from cmdb.models import App, AppContact
from deploy.models import Deployv3StgMain, Deployv3Detail, DeployLog, DeployPath, HudsonJob
from StgPublishLib import md5_check, DepFtp, DeployError
from util.sendmail import sendmail_html, sendmail_v2
from util.httplib import *
import time, urllib2, json, os
from django.core.exceptions import MultipleObjectsReturned
from assetv2.settingsdeploy import DEPLOY_STATIC_APP_ID, FTP, OMS_HOST, DEPLOY_HEALTH_CHECK, STG_DEPLOY_CREATE_DOCKER, STG_DEPLOY_DOCKER_DEPLOY,STG_APP_ID_LIST
from django.template import loader
from change import tasks
from datetime import datetime
import requests
from server.models import Server
import logging
from celery.exceptions import Reject

class Publish():
    depid = None    #发布单号
    deploy = None    # deploy object
    deploy_detail = None  # deploy detail object
    codepath = None  #发布机的目录
    release_path = None  #线上的目录
    backuppath = None    #线上备份目录
    predeploypath = None  #线上预发布目录
    vm_detail = None         #发布机器Vm
    docker_detail = None     #发布机器Docker

    def __init__(self, depid=None):
        self.depid = depid
        if self.depid:
            self.format_data(depid)

    def deploy_stg(self,is_save_process=None):
        # #判断当前pool下是否有Docker
        #
        # if self.docker_detail:
        #     # 为Docker创建当前版本镜像
        #     self.create_docker_img(self.deploy.app_id, self.deploy.source_path)

        if is_save_process is not None:
            self.deploy.is_process = 1
        self.deploy.process = 5
        self.deploy.save()


        if not self.health_check():
            self.ie('HealthCheck未设置或未加入白名单，不允许发布!')
        self.update_process(10)
        self._ftp2deployhost()
        self.deploy.version = self.get_version(self.codepath) or ''
        self.deploy.process = 30
        self.deploy.save()

        # 关闭HealthCheck
        self.i("### 关闭healthcheck ###")
        self.set_healthcheck(1)

        # 优先发布非docker类型的主机
        if self.vm_detail:
            os.chdir('/tmp') # maybe fix rsync get_cwd() problem.
            self.i("### 切换目录到/tmp ###")

            for vm in self.vm_detail:
                self.i("#########################################")
                self.i('### [%s] 开始预发布  ###' % vm.target_host)
                self._backup(vm)
                self.i('### [%s] 结束预发布  ###' % vm.target_host)
                self.i('#########################################')

            self.update_process(50)

            for vm in self.vm_detail:
                self.i("#######################################")
                self.i('###开始正式发布[%s]###' % vm.target_host)
                self._deploy(vm)
                if self.deploy.is_restart:
                    self.tomcat_restart(vm.target_host)
                self.i('###结束正式发布[%s]###' % vm.target_host)
                self.i("#######################################")
            self.update_process(80)

        is_success = True
        # 发布docker类型的主机
        if self.docker_detail:
            # 调Docker发布接口
            docker_ips = [d.target_host for d in self.docker_detail]
            self.i("### 检测到主机类型为容器 ###")
            self.docker_stg_deploy(self.deploy.app_id, self.deploy.depid, self.deploy.source_path, self.deploy.version, (',').join(docker_ips))
            # 获取docker发布状态
            is_success = self.get_deploy_result(self.deploy.depid, 2)
            if is_success:
                self.i('###docker发布完成###')
        if is_success:
            #更新发布状态为发布成功
            self.deploy.status = 2
            self.deploy.success_update = int(time.time())
            self.deploy.is_process = 0
            self.deploy.process = 100
            self.deploy.save()

            # 开启HealthCheck
            self.i("### 开启healthcheck ###")
            self.set_healthcheck(0)

            self.i('###结束所有发布操作###')

            # 发布邮件
            if self.deploy.is_autocreated == 1:
                mailto = [self.deploy.uid + '@yhd.com']
                try:
                    contact = AppContact.objects.get(pool_id=self.deploy.app_id)
                    if contact.domain_email:
                        mailto.append(contact.domain_email)
                except AppContact.DoesNotExist:
                    pass
                html_content = loader.render_to_string('mail/auto_stg_deploy_notify.html', {
                    'depid':self.depid,
                    'url': OMS_HOST + '/deploy/stg/detail/?depid=%s' % self.deploy.depid,
                })
                app_obj = App.objects.get(id=self.deploy.app_id)
                try:
                    # sendmail_html('【全自动发布系统提醒】%s/%s的stg发布单%s成功发布。' % (app_obj.site.name, app_obj.name, self.depid), html_content, mailto)
                    sendmail_v2('【全自动发布系统提醒】%s/%s的stg发布单%s成功发布。' % (app_obj.site.name, app_obj.name, self.depid), html_content, mailto, app_obj)
                except Exception, e:
                    self.write_log(self.depid, 1, "### 发送邮件失败, 错误信息: {0} ###".format(str(e)))
                    print('### send mail error: %s ###' % str(e))

            items = HudsonJob.objects.filter(app_id=self.deploy.app_id,jobtype=1)
            if items:
                job = items[0] if items else None
                if job and self.deploy.deploy_type == 0:
                    time.sleep(600)  # 等待10min再触发Hudson
                    cmdstr = "curl '%s?token=%s'" % (job.url, job.token)
                    status, output = commands.getstatusoutput(cmdstr)
                    if status != 0:
                        self.write_log(self.depid, 1, '###hudson错误：执行命令：%s 执行状态值为： %s###' % (cmdstr, status))
                        print('###hudson错误：执行命令：%s 执行状态值为： %s###' % (cmdstr, status))
                    else:
                        self.i('###hudson执行命令：【%s】###' % cmdstr)
            print('end')
        return is_success

    def rollback_stg(self):
        self.i('###开始回滚操作###')
        if self.deploy.status == 2:
            # 判断是否存在上一版本
            try:
                last_stg = Deployv3StgMain.objects.filter(app_id=self.deploy.app_id, status=2).order_by('-success_update')[1]
            except Exception, e:
                self.ie('未获取到上一个成功发布的版本！详情：%s' % str(e))
            self.update_process(10)

            if self.vm_detail:
                for item in self.vm_detail:
                    self._rollback(item.target_host)
                    if self.deploy.is_restart == 1:
                        self.tomcat_restart(item.target_host)
                self.update_process(60)

            is_success = True
            if self.docker_detail:
                docker_ips = [d.target_host for d in self.docker_detail]
                self.docker_stg_deploy(self.deploy.app_id, self.deploy.depid, last_stg.source_path, last_stg.version, (',').join(docker_ips), action='rollback')
                # 获取docker回滚状态
                is_success = self.get_deploy_result(self.deploy.depid, 3)
                if is_success:
                    self.i('###docker回滚完成###')
            if is_success:
                self.deploy.status = 3
                self.deploy.is_process = 0
                self.deploy.process = 100
                self.deploy.rollback_update = int(time.time())
                self.deploy.save()

                self.i('###结束所有回滚操作###')
        else:
            self.i('###此状态无需回滚操作###')
        print('end')
        return is_success

    def format_data(self, depid):
        self.deploy = self.get_deploy(depid)

        if self.deploy.deploy_type == 3:
            app_name_string = self.deploy.app.name + '_static'

            if self.deploy.app.site.name == 'samsclub':
                app_name_string = 'samsclub_' + app_name_string

            try:
                deploypath = DeployPath.objects.get(app_id=DEPLOY_STATIC_APP_ID,name=app_name_string)
            except DeployPath.DoesNotExist:
                self.ie('线上静态目录目录不存在,请将以下信息反馈至liweiyu处：静态目录名称：%s' % app_name_string)
            except MultipleObjectsReturned:
                self.ie('该POOL存在多个线上静态目录，不允许发布，请修改！')
        else:
            try:
                deploypath = DeployPath.objects.get(app_id=self.deploy.app_id)
            except DeployPath.DoesNotExist:
                self.ie('发布系统线上目录不存在,请联系monitor或自行配置后重新发布！')
            except MultipleObjectsReturned:
                self.ie('该POOL存在多个线上目录，不允许发布，请修改！')

        self.release_path = deploypath.path
        self.deploy_detail = Deployv3Detail.objects.filter(depid=depid)

        #根据pool灰度切换
        if self.deploy.app_id in STG_APP_ID_LIST:
            #发布机器分类
            docker_detail = []
            vm_detail = []
            for detail in self.deploy_detail:
                try:
                    server = Server.objects.exclude(server_status_id=400).get(ip = detail.target_host)
                except Exception, e:
                    self.ie('%s在server表中不存在或存在多个记录:%s' % (detail.target_host, str(e)))
                if server.server_type_id == 3:
                        docker_detail.append(detail)
                else:
                    vm_detail.append(detail)
            self.docker_detail = docker_detail
            self.vm_detail = vm_detail
        else:
            self.docker_detail = []
            self.vm_detail = self.deploy_detail

        self.codepath = '/depot/deployv2/{0}/{1}/{2}'.format(self.deploy.site.name, self.deploy.app.name, depid)
        self.backuppath = '/depot/backup/{0}'.format(depid)
        self.predeploypath = '/depot/predeploy/{0}'.format(depid)

    def get_deploy(self, depid):
        try:
            deploy = Deployv3StgMain.objects.get(depid=depid)
        except Deployv3StgMain.DoesNotExist:
            self.ie('发布号内容不存在,请检查！')

        return deploy

    def update_process(self,percent):
        self.deploy.process = percent
        self.deploy.save()


    def health_check(self):
        self.i('###检查HealthCheck是否设置###')
        url = DEPLOY_HEALTH_CHECK + "&app_id=%s" % self.deploy.app_id
        fp = urllib2.urlopen(url)
        result = json.loads(fp.read())
        return result['data']['isSetHealthCheck']

    def tomcat_restart(self, host):
        st, pids = self._tomcat_pids(host)
        self._tomcat_restart(host)
        times = 0
        while times < 15:
            time.sleep(2)
            status, newpids = self._tomcat_pids(host)
            if newpids and all([pid not in pids for pid in newpids]):
                return True
            times += 1
        self._tomcat_restart(host)
        times = 0
        while times < 30:
            time.sleep(2)
            status, newpids = self._tomcat_pids(host)
            if newpids and all([pid not in pids for pid in newpids]):
                return True
            times += 1
        self._tomcat_restart(host)

    def _tomcat_restart(self, host):
        cmdstr = "export LANG=en_US.UTF-8; /bin/bash /depot/boot.sh"
        status, cmdstr, output = ssh(cmdstr, host)
        self.i('###重启%s 结果：%s###' % (cmdstr, output))

    def _tomcat_pids(self, host):
        cmdstr = "ps -C java u --cols=1500|grep tomcat|awk '{print \$2}'"
        status, cmdstr, output = ssh(cmdstr, host)
        pids = []
        if status:
            pids = [pid.strip() for pid in output.split() if pid.strip().isdigit()]
        return (status, pids)

    def _rollback(self,host):
        src = self.backuppath.rstrip('/') + '/'
        det = self.release_path.rstrip('/') + '/'
        self.i("############################")
        self.i("开始回滚中...")
        status, cmdstr, output = self.rsync_remote4nocheck(host, src, det,None, False, checksum=True)
        self.i("执行结果: %s" %(output))
        if not status:
            self.ie('###发布：[%s]代码回滚失败。执行命令：%s，返回值：%s###' %(host,cmdstr,output))
        self.i('###回滚[%s]操作成功###' % host)
        stg_rollback_change = {
            "user": self.deploy.uid,
            "type": 'release',
            "action": 'stg_rollback',
            "index": host,
            "message": self.deploy.depid,
            "level": 'change',
            "happen_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        tasks.collect.apply_async((stg_rollback_change,))
        self.i("回滚写入变更完成。")
        self.i("################################")

    def _deploy(self,host):
        src = self.predeploypath.rstrip('/') + '/'
        det = self.release_path.rstrip('/') + '/'
        if self.deploy.deploy_type == 0:
            status, cmdstr, output = self.rsync_remote4nocheck(host.target_host, src, det)
            self.i("###正式发布: [%s] 部署类型为webapp ###\n执行命令: %s \n结果: %s\n" %(host.target_host, cmdstr, output))
        else:
            status, cmdstr, output = self.rsync_remote4nocheck(host.target_host, src, det, hotfix=True)
            self.i("###正式发布: [%s] 部署类型为static ###\n执行命令: %s \n结果: %s\n" %(host.target_host, cmdstr, output))

        if not status:
            self.ie('###正式发布：[%s]代码切换到正式环境失败。\n执行命令：%s \n执行结果：%s\n###\n' %(host.target_host,cmdstr,output))

        # self.i('###正式发布：[%s]###' % cmdstr)
        stg_deploy_change = {
            "user": self.deploy.uid,
            "type": 'release',
            "action": 'stg_deploy',
            "index": host.target_host,
            "message": self.deploy.depid,
            "level": 'change',
            "happen_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        tasks.collect.apply_async((stg_deploy_change,))
        self.i("### 写入变更消息完成。###")

    def _backup(self, detail):
        # Determine the target host release directory exists
        if not self.path_exists(self.release_path.rstrip('/'), detail.target_host):
            # if not exists create directory
            self.i("### 目标机器不存在release路径，创建release路径 ###")
            status, cmdstr, output = self.mkdir(self.release_path.rstrip('/'), detail.target_host)
            self.i("[%s]创建目录\n 执行命令: %s \n执行结果: %s \n" % (detail.target_host, cmdstr, output))
            if not status:
                self.ie('[预发布] [%s]  \n执行命令[%s]\n失败,release路径创建失败。' % (detail.target_host,cmdstr))
            self.i("### release路径创建成功 ###")

        # determine the target host backup directory exists.
        if not self.path_exists(self.backuppath.rstrip('/'), detail.target_host):
            # if not exists create backup directory
            self.i("### 目标机器不存在backup目录,创建backup目录.###")
            status, cmdstr, output = self.mkdir(self.backuppath.rstrip('/'), detail.target_host)
            self.i("[%s] 执行命令: \n%s\n 结果: %s\n"%(detail.target_host, cmdstr, output))
            if not status:
                self.ie('###预发布：[%s]备份路径创建失败。\n执行命令：%s\n###' %(detail.target_host,cmdstr))
            self.i("### backup目录创建成功 ###")

        self.i("### 备份代码 ###")
        status, cmdstr, output = self.rsync_remote4nocheck(detail.target_host, self.release_path.rstrip('/') + '/', self.backuppath.rstrip('/') + '/', None, False)
        self.i("[%s] 执行命令:\n %s \n结果: %s\n" %(detail.target_host, cmdstr, output))
        if not status:
            self.ie('###预发布：[%s]备份代码失败。\n执行命令：%s\n 执行结果：%s\n###' %(detail.target_host,cmdstr,output))
        self.i("## 备份结束 ##")

        # self.i('###预发布：[%s]###' % cmdstr)

        depprepath = self.predeploypath.rstrip('/') + '/'
        if not self.path_exists(depprepath.rstrip('/'), detail.target_host):
            self.i("### 创建预发布路径 ###")
            status, cmdstr, output = self.mkdir(depprepath.rstrip('/'), detail.target_host)
            self.i("[%s] 执行命令: %s 结果: %s" %(detail.target_host, cmdstr, output))
            if not status:
                self.ie('预发布路径创建失败。')
            self.i("## 创建预发布路径结束. ##")

        det = 'deploy@%s:%s' % (detail.target_host, self.predeploypath.rstrip('/') + '/')
        self.i("### 将代码上传到预发布路径 ###")
        status, cmdstr, output = self.rsync4nocheck(self.codepath.rstrip('/') + '/', det)
        self.i("[%s] 执行命令: %s 结果: %s" %(detail.target_host, cmdstr, output))
        if not status:
            self.ie('代码传至预发布目录失败。')
        self.i("## 代码上传结束. ##")
        self.i("###### 预发布: [%s] 恭喜！备份完成! ######"%(detail.target_host))
        # self.i('###预发布：[%s]###' % cmdstr)

        # self.i('###预发布：[%s]备份成功###' % detail.target_host)

    def _ftp2deployhost(self):
        ftpath = self.deploy.source_path
        codepath = self.codepath
        if not self.path_exists(codepath):
            status, cmdstr, output = self.mkdir(codepath)
        else:
            status, cmdstr, output = self.cleardir(codepath)
        if not status:
            self.ie('###准备数据：新建目录或清理目录时发生错误,执行命令：%s 返回值为： %s###' % (cmdstr,output))
        self.i('###准备数据：%s###' % cmdstr)

        ftp = DepFtp(host=FTP['HOST'], user=FTP['USER'], passwd=FTP['PASSWORD'])
        try:
            ftp.get(ftpath, codepath)
            ftp.get(ftpath+'.MD5', codepath)
            ftp.close()
        except Exception, e:
            self.ie('###准备数据：FTP获取数据错误，错误信息：%s###' % str(e))
        self.i('###准备数据：成功获取FTP数据###')

        package = os.path.join(codepath, os.path.basename(ftpath))
        md5file = package+'.MD5'
        status = md5_check(package, md5file)
        if not status:
            self.ie('###准备数据：MD5校验失败###')
        else:
            self.i('###准备数据：MD5校验成功###')
        status, cmdstr, output = self.uncompress(package, codepath)
        if not status:
            self.ie('###准备数据：包解压时发生错误，执行命令:%s,执行结果：%s###' % (cmdstr,output))
        else:
            self.i('###准备数据：包解压成功###')
        os.remove(package)
        os.remove(md5file)
        self.i('###准备数据：FTP获取数据成功###')

    def rsync4nocheck(self,src,det,checkip=None,hotfix=False, exclude=None, checksum=False):
        if hotfix:
            arg = '-rlpgoDc' if checksum else '-a'
        else:
            arg = '-rlpgoDc --delete' if checksum else '-a --delete'
        if exclude:
            arg += ' --exclude=%s' % exclude
        if checkip is None:
            cmdstr = "/usr/bin/rsync -e 'ssh -i /home/deploy/.ssh/id_rsa -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no' %s %s %s" % (arg, src, det)
        else:
            cmdstr = "/usr/bin/rsync -e 'ssh -i /home/deploy/.ssh/id_rsa -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no' %s %s %s" % (arg, src, det)
        status, output = commands.getstatusoutput(cmdstr)
        return (True if status==0 else False, cmdstr, output)

    def rsync_remote4nocheck(self,host,src,det,checkip=None,hotfix=False, exclude=None,
                             checksum=False,is_root=False,key="/home/deploy/.ssh/id_rsa",
                             user="deploy"):
        if hotfix:
            arg = '-rlpgoDc' if checksum else '-a'
        else:
            arg = '-rlpgoDc --delete' if checksum else '-a --delete'
        if exclude:
            arg += ' --exclude=%s' % exclude
        if checkip is None:
            cmdstr = '/usr/bin/rsync %s %s %s' % (arg, src, det)
        else:
            cmdstr = "/usr/bin/rsync -e 'ssh -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no' %s %s %s" % (key, arg, src, det)
        if is_root:
            return ssh(cmdstr, host,key,user)
        else:
            return ssh(cmdstr, host)

    def set_healthcheck(self, status=1):
        ipstr = ''
        for item in self.deploy_detail:
            ipstr += '&ip[]=%s' % item.target_host
        url = DEPLOY_HEALTH_CHECK + "&method=isDeploy{0}&deploy={1}".format(ipstr, status)
        self.i("### 设置HealthCheck状态, URL: {0} ###".format(url))
        try:
            fp = urllib2.urlopen(url)
        except Exception as e:
            self.ie("### 设置HealthCheck状态出错, 错误信息: {0} ###".format(str(e)))
        else:
            self.i("### 设置HealthCheck状态成功 ###")

    def get_version(self,path):
        path = os.path.join(path, 'META-INF/MANIFEST.MF')
        if not os.path.exists(path):
            return None
        version = ''
        continu = False
        fp = open(path)
        for line in fp:
            if line.startswith('BaseLine:'):
                version = line.split(':', 1)[1].strip()
                continu = True
            elif continu:
                if line.startswith(' '):
                    version += line.strip()
                else:
                    continu = False
        return version

    def uncompress(self,filename, topath):
        if not os.path.exists(topath):
            os.makedirs(topath)
        ext = os.path.splitext(filename)[1].strip('.').lower()
        if ext == 'zip':
            cmdstr = "unzip -oq %s -d %s" % (filename, topath)
        elif ext == 'war' or ext == 'jar':
            cmdstr = "unzip -oq %s -d %s" % (filename, topath)
        elif ext == 'tar' or ext == 'gz' or ext == 'bz2':
            os.chdir(topath)
            cmdstr = 'tar -xf %s' % filename
        else:
            return (False, '', u'不支持后缀名%s: %s' % (ext, filename))
        status, output = commands.getstatusoutput(cmdstr)
        return (True if status==0 else False, cmdstr, output)

    def path_exists(self,path, host=None):
        path = path.rstrip('/')
        if host is None:
            return os.path.exists(path)
        cmdstr = "ls -d %s" % path
        status, cmdstr, output = ssh(cmdstr, host)
        return status

    def cleardir(self,path, host=None):
        path = path.rstrip('/')
        cmdstr = "rm -rf %s/*" % path
        if host is None:
            status, output = commands.getstatusoutput(cmdstr)
            return (True if status==0 else False, cmdstr, output)
        else:
            return ssh(cmdstr, host)

    def mkdir(self,path, host=None):
        cmdstr = "mkdir -p '%s'" % path
        if host is None:
            status, output = commands.getstatusoutput(cmdstr)
            return (True if status==0 else False, cmdstr, output)
        else:
            return ssh(cmdstr, host)

    """
    发布系统错误LOG接口
    """
    def ie(self, log):
        self.write_log(self.depid, 1, log)
        self.deploy.status = 4
        self.deploy.is_process = 0
        self.deploy.save()
        raise Reject('Task failed to excute! Please check the Traceback and try again.')

    """
    发布系统信息LOG接口
    """
    def i(self, log):
        self.write_log(self.depid, 0, log)

    """
    底层LOG接口
    """
    def write_log(self, depid, type=0, log='', host='self'):
        DeployLog.objects.create(depid=depid,
                                 host=host,
                                 error=type,
                                 log=log,
                                 create_time=int(time.time()))

    def create_docker_img(self, app_id, source_path, deploy_status=True):
        post_dict = {
            'pool_id': int(app_id),
            'pool_code_path': source_path,
            'deploy_status': deploy_status
        }
        headers = {
            'Authorization': 'Basic Y21kYjpyODkhQ1VrczhJ',
            'X-Auth-User': 'admin',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(STG_DEPLOY_CREATE_DOCKER, data=json.dumps(post_dict), headers=headers)
            self.i("### 调用docker创建镜像 ###")
            if response.status_code not in [200, 201, 202]:
                self.ie("### create docker image error: {0} ###".format(str(response.text)))
        except Exception, e:
            self.ie("### connect create docker image api error: {0} ###".format(str(e)))

    def docker_stg_deploy(self, app_id, depid, source_path, code_version, container_ips, env='stg', action='deploy'):
        post_dict = {
            'pool_id': int(app_id),
            'depid': depid,
            'pool_code_path': source_path,
            'code_version': code_version,
            'container_ips': container_ips,
            'env': env,
            'action': action
        }
        headers = {
            'Authorization': 'Basic Y21kYjpyODkhQ1VrczhJ',
            'X-Auth-User': 'admin',
            'Content-Type': 'application/json'
        }
        try:
            self.i("### 请求: %s" %(STG_DEPLOY_DOCKER_DEPLOY))
            response = requests.post(STG_DEPLOY_DOCKER_DEPLOY, data=json.dumps(post_dict), headers=headers)
            self.i("### 请求完成。")
            self.i("### 结果: %s" %(response.text))
            self.i("### 调用docker%s ###" % ('发布' if action=='deploy' else '回滚'))
            if response.status_code != 200:
                self.ie("### docker stg deploy error: status->{0} result->{1} ###".format(response.status_code, str(response.text)))
        except Exception, e:
            self.ie("### connect docker stg deploy api error: {0} ###".format(str(e)))
        self.i("### docker 部署完成 ###")

    def get_deploy_result(self, depid, status):
        times = 0
        while times<360:
            time.sleep(2)
            try:
                res = Deployv3StgMain.objects.get(depid = depid)
            except Exception,e:
                print('### get docker deploy status error: %s ###' % str(e))
            if res.status == status and res.process == 100:
                return True
            elif res == 4:
                return False
        return False