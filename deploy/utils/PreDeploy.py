# -*- coding: utf-8 -*-
from django.core.exceptions import *
from celery import group
from deploy.utils.DeployCommon import *
from deploy.utils.DepFtp import DepFtp
from deploy.tasks import parallel_pre_deploy
from assetv2.settingsdeploy import DEPLOY_VERSION_FILE, STAGING_NETWORK_SEGMENT


class PreDeploy():
    def __init__(self, depid):
        self.depid = depid
        self.deploy = DeployMain.objects.get(depid=depid)
        self.deploy_host_set = set([server['deploy_host'] for server in get_publish_server(self.depid, DEPLOY_PACKTYPE_APP_ID_MAPPING.get(self.deploy.packtype, self.deploy.app_id), 2)])
        self.cache = get_cache('deploy')

    def ie(self, log):
        self.i(log, error=True)
        unlock_it(self.deploy)
        raise DeployError(log)

    def i(self, log, error=False):
        i2(self.cache, self.depid, log, error)

    def auto_publish(self):
        if is_locked(self.deploy):
            self.i(set_color('当前发布或者回滚被锁住'))
            return False
        lock_it(self.deploy)
        self.init_path()
        self.update_ftp_path()
        deploy_detail_init(self.deploy)
        self.i('开始准备数据')
        if self.deploy.status == 1:
            self.prepare()
        else:
            self.i('该发布已执行过准备数据')
        self.i('结束准备数据')
        self.i('开始预发布')
        if self.deploy.status == 2:
            self.pre_deploy()
        else:
            self.i('该发布已执行过预发布')
        self.i('结束预发布')
        unlock_it(self.deploy)

    def update_ftp_path(self):
        # 获取当前POOL的上个版本
        if self.deploy.packtype != 0:
            return
        try:
            deploy_version_app = DeployVersionApp.objects.get(app_id=self.deploy.app_id, app_env_id=2, pack_type=self.deploy.packtype)
            self.deploy.last_ftpath = deploy_version_app.ftp_path
            self.i('记下当前运行的版本对应的ftp路径：{0}'.format(self.deploy.last_ftpath))
        except ObjectDoesNotExist:
            pass
        self.deploy.save()

    def prepare(self):
        if self.deploy.deptype == 1:
            self._stag2deploy()
        else:
            self._ftp2deploy()
        # 生成版本文件
        version_file = os.path.join(self.deploy.codepath, DEPLOY_VERSION_FILE)
        if not os.path.exists(version_file):
            with open(version_file, 'w') as f:
                f.write(self.deploy.version)
                self.i('创建文件{0}：{1}'.format(f.name, self.deploy.version))
        else:
            with open(version_file) as f:
                self.i('文件{0}已存在：{1}'.format(f.name, f.read()))
        self.deploy.status = 2
        self.deploy.save()

    def _stag2deploy(self):
        # src_ip_list = [server['ip'] for server in get_publish_server(self.depid, DEPLOY_PACKTYPE_APP_ID_MAPPING.get(
        #     self.deploy.packtype, self.deploy.app_id), 1) if
        #                server['idc'] == 1 and '.'.join(server['ip'].split('.')[:2]) == STAGING_NETWORK_SEGMENT.get(
        #                    'DCB')]

        src_ip_list = [server['ip'] for server in get_publish_server(self.depid, DEPLOY_PACKTYPE_APP_ID_MAPPING.get(
            self.deploy.packtype, self.deploy.app_id), 1)]
        if src_ip_list:
            src_ip = src_ip_list[0]
        else:
            self.ie('南汇staging机器不存在')
        for deploy_host in self.deploy_host_set:
            src = 'deploy@%s:%s' % (src_ip, self.deploy.path_src)
            dst = self.deploy.codepath
            host = None if DEPLOY_CODE_HOST == deploy_host else deploy_host
            if not path_exists(dst, host):
                status, cmd, output = mkdir(dst, host)
                if not status:
                    self.ie('准备数据：[%s]新建目录[%s]时发生错误, 执行命令：%s 返回值为： %s' % (host, dst, cmd, output))
            src += '/'
            dst += '/'
            status, cmd, output = rsync4nocheck(src, dst, remote_host=host)
            msg = '准备数据：从[%s]拉取数据到[%s]%s，执行命令：%s，返回值为：%s' % (src_ip, host if host else DEPLOY_CODE_HOST, STATUS_MAPPING[status], cmd, output)
            if not status:
                self.ie(msg)
            else:
                self.i(msg)

    def _ftp2deploy(self):
        ftpath = self.deploy.ftpath
        codepath = self.deploy.codepath
        for deploy_host in self.deploy_host_set:
            host = None if DEPLOY_CODE_HOST == deploy_host else deploy_host
            if not path_exists(codepath, host):
                status, cmd, output = mkdir(codepath, host)
            else:
                status, cmd, output = cleardir(codepath, host)
            if not status:
                self.ie('准备数据：[%s]新建目录或清理目录时发生错误, 执行命令：%s 返回值为： %s' % (deploy_host, cmd, output))
            self.i('准备数据：%s' % cmd)
        try:
            deploy_ftp = DeployFtp.objects.get(app_id=self.deploy.app_id)
        except DeployFtp.DoesNotExist:
            self.ie('准备数据：FTP路径没有设置，请先到路径配置里设置！')
        ftp = DepFtp(host=deploy_ftp.ftp, user=deploy_ftp.user, passwd=deploy_ftp.passwd)
        try:
            ftp.get(ftpath, codepath)
            ftp.get(ftpath+'.MD5', codepath)
            ftp.close()
        except Exception, e:
            self.ie('准备数据：FTP获取数据错误，错误信息：%s' % str(e))
        self.i('准备数据：成功获取FTP数据')
        package = os.path.join(codepath, os.path.basename(ftpath))
        md5file = package+'.MD5'
        status = md5_check(package, md5file)
        if not status:
            self.ie('准备数据：MD5校验失败')
        else:
            self.i('准备数据：MD5校验成功')
        status, cmd, output = uncompress(package, codepath)
        if not status:
            self.ie('准备数据：包解压时发生错误，执行命令:%s, 执行结果：%s' % (cmd, output))
        else:
            self.i('准备数据：包解压成功')
        os.remove(package)
        os.remove(md5file)
        self.i('准备数据：FTP获取数据成功')
        # 如果有远程的发布机
        for deploy_host in set([deploy_detail.deploy_host for deploy_detail in deploy_detail_list(self.depid)]):
            if DEPLOY_CODE_HOST != deploy_host:
                src = codepath.rstrip('/') + '/'
                dst = 'deploy@%s:%s' % (deploy_host, src)
                status, cmd, output = rsync4nocheck(src, dst, remote_host=deploy_host)
                if not status:
                    self.ie('准备数据：同步FTP数据至发布子系统[%s]错误，执行命令:%s，执行结果%s' % (deploy_host, cmd, output))
                self.i('准备数据：FTP数据已同步到发布机[%s]，执行命令：%s' % (deploy_host, cmd))

    def pre_deploy(self):
        # for deploy_detail in deploy_detail_list(self.depid):
        #     if not deploy_detail.has_backup:
        #         single_backup(deploy_detail)
        #     if not deploy_detail.has_pre:
        #         single_pre_deploy(deploy_detail)
        result = group(parallel_pre_deploy.s(deploy_detail.id) for deploy_detail in deploy_detail_list(self.depid) if not all([deploy_detail.has_backup, deploy_detail.has_pre]))()
        result_list = result.get()
        if not all(result_list):
            self.ie('未成功执行预发布')
        self.deploy.status = 3
        self.deploy.save()

    def init_path(self):
        try:
            app = App.objects.get(id=self.deploy.app_id)
            site = app.site
        except App.DoesNotExist:
            self.ie(u'应用不存在!')
        # if self.deploy.deptype == 1:
        #     latest_ftp_path = latest_staging_version(self.deploy)
        #     if latest_ftp_path:
        #         version = os.path.basename(latest_ftp_path)
        #         self.deploy.codepath = '/depot/deployv2/{0}/{1}/{2}'.format(site.name, app.name, version)
        #         self.deploy.deprepath = '/depot/predeploy/{0}'.format(version)
        #         self.deploy.ftpath = latest_ftp_path
        #         self.deploy.version = version
        #         self.deploy.status = 1
        #         self.deploy.save()
        #         DeployDetail.objects.filter(depid=self.deploy.depid).update(has_pre=0, pre_time=0)
        #         self.i('当前staging的版本已经更新为：{0}'.format(version))
        # else:
        #     self.deploy.codepath = '/depot/deployv2/{0}/{1}/{2}'.format(site.name, app.name, self.deploy.version)
        #     self.deploy.deprepath = '/depot/predeploy/{0}'.format(self.deploy.version)
        version = os.path.basename(self.deploy.ftpath)
        self.deploy.codepath = '/depot/deployv2/{0}/{1}/{2}'.format(site.name, app.name, version)
        self.deploy.deprepath = '/depot/predeploy/{0}'.format(version)
        self.deploy.version = version
        self.deploy.save()