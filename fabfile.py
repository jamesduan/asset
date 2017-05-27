# -*- coding: utf-8 -*-
from fabric.api import *

env.user = 'root'
env.password = '1qaz2wsx'
env.hosts = ['192.168.16.241']

def pack():
    """ 打包 """
    tar_files = [
        './*'
    ]
    local('rm -f assetv2.tar.gz')
    local('tar -czvf assetv2.tar.gz --exclude=\'*.tar.gz\' --exclude=\'fabfile.py*\' %s' % ' '.join(tar_files))

def deploy():
    """ 发布 """
    # 打包
    pack()
    # 部署
    remote_tmp_tar = '/tmp/assetv2.tar.gz'
    remote_work_dir = '/var/www/project/wzq/assetv2'
    run('rm -f %s' % remote_tmp_tar)
    put('assetv2.tar.gz', remote_tmp_tar)
    run('rm -rf %s/*' % remote_work_dir)
    run('tar xf %s -C %s' % (remote_tmp_tar, remote_work_dir))
    local('rm -f assetv2.tar.gz')
    run('supervisorctl restart wzq_mobile')

