import os
from ftplib import FTP
from deploy.utils import DeployError


class DepFtp(object):
    def __init__(self, host='ftp.yihaodian.com.cn', user='deploy', passwd=''):
        try:
            self.ftp = FTP(host, user, passwd)
        except Exception, e:
            raise DeployError('ftp connect error: %s' % str(e))
        self.ftp.set_pasv(False)  # off ftp passive mode

    def lists(self, path='/'):
        try:
            lists = self.ftp.nlst(path)
        except Exception, e:
            raise DeployError('ftp list error: %s' % str(e))
        results = []
        exts = ['war', 'jar', 'zip', 'tar', 'gz', 'bz2']
        for name in lists:
            ext = os.path.splitext(name)[1]
            if ext.strip('.').lower() in exts:
                results.append(name)
        results.sort(reverse=True)
        return results

    def get(self, name, local_path):
        name = name.strip()
        if not name.startswith('/'):
            name = '/' + name
        dirname, basename = os.path.split(name)
        if len(basename) == 0:
            raise DeployError('file not exists in ftp: %s' % name)
        try:
            if self.ftp.pwd() != dirname:
                self.ftp.cwd(dirname)
            callback = open(os.path.join(local_path, basename), 'wb').write
            commond = 'RETR %s' % basename
            self.ftp.retrbinary(commond, callback)
        except Exception, e:
            raise DeployError('ftp get error: %s' % str(e))

    def close(self):
        self.ftp.close()