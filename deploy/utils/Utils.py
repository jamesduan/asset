# -*- coding: utf-8 -*-
import os
import commands
import redis
import json
from hashlib import md5
from django.core.mail import EmailMessage


def md5_check(package, md5file):
    fp = open(package, 'rb')
    md = md5(fp.read())
    fp.close()
    mfp = open(md5file, 'rb')
    code = mfp.read().strip()
    mfp.close()
    return True if code == md.hexdigest() else False


def uncompress(filename, dst_path):
    if not os.path.exists(dst_path):
        os.makedirs(dst_path)
    ext = os.path.splitext(filename)[1].strip('.').lower()
    if ext in ('zip', 'war', 'jar'):
        cmd = 'unzip -oq %s -d %s' % (filename, dst_path)
    elif ext in ('tar', 'gz', 'bz2'):
        os.chdir(dst_path)
        cmd = 'tar -xf %s -C %s' % (filename, dst_path)
    else:
        return False, '', u'不支持后缀名%s: %s' % (ext, filename)
    status, output = commands.getstatusoutput(cmd)
    return not bool(status), cmd, output


def ssh(cmd='', host='127.0.0.1', key='/home/deploy/.ssh/id_rsa', user='deploy'):
    ssh_cmd = 'ssh -q -i %s -o StrictHostKeyChecking=no -o BatchMode=yes -o UserKnownHostsFile=/dev/null %s@%s "%s"' % \
              (key, user, host, cmd)
    status, output = commands.getstatusoutput(ssh_cmd)
    return not bool(status), ssh_cmd, output


def rsync4nocheck(src, dst, host_key_checking=True, hotfix=False, exclude=None, checksum=False, remote_host=None):
    if hotfix:
        arg = '-rlpgoDc' if checksum else '-a'
    else:
        arg = '-rlpgoDc --delete' if checksum else '-a --delete'
    if exclude:
        arg += ' --exclude=%s' % exclude
    if not host_key_checking:
        cmd = '/usr/bin/rsync %s %s %s' % (arg, src, dst)
    else:
        cmd = "/usr/bin/rsync -e 'ssh -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no' %s %s %s" % (arg, src, dst)
    if remote_host:
        return ssh(cmd, remote_host)
    else:
        status, output = commands.getstatusoutput(cmd)
        return not bool(status), cmd, output


def path_exists(path, host=None):
    path = path.rstrip('/')
    if host is None:
        return os.path.exists(path)
    cmd = 'test -d %s -o -L %s' % (path, path)
    status, cmd, output = ssh(cmd, host)
    return status


def mkdir(path, host=None):
    path = path.rstrip('/')
    cmd = 'mkdir -p %s' % path
    if host is None:
        status, output = commands.getstatusoutput(cmd)
        return not bool(status), cmd, output
    else:
        return ssh(cmd, host)


def cleardir(path, host=None):
    path = path.rstrip('/')
    cmd = 'rm -rf %s/*' % path
    if host is None:
        status, output = commands.getstatusoutput(cmd)
        return not bool(status), cmd, output
    else:
        return ssh(cmd, host)


def set_color(string, color='red'):
    return '<span style="color: %s">%s</span>' % (color, string)


def send_email(
        subject,
        content,
        recipient_list,
        from_email='noreplay@cmdbapi.yihaodian.com.cn',
        bcc=None,
        connection=None,
        attachments=None,
        headers=None,
        cc=None):
    msg = EmailMessage(subject, content, from_email, recipient_list, bcc, connection, attachments, headers, cc)
    msg.content_subtype = 'html'
    msg.send()


def task_report(redis_host, redis_port, task_id, ip=None):
    r1 = redis.Redis(host=redis_host, port=redis_port, db=1)
    key1 = 'celery-task-meta-{0}'.format(task_id)
    ready = r1.exists(key1)
    task_dict = json.loads(r1.get(key1)) if ready else dict()
    task_dict['ready'] = ready
    task_dict['logs'] = []
    task_dict['ip'] = ip
    task_dict['task_id'] = task_id
    task_dict['status'] = task_dict.get('status')
    task_dict['result'] = task_dict.get('result', dict())
    task_dict['result']['exc_message'] = task_dict['result'].get('exc_message')
    r2 = redis.Redis(host=redis_host, port=redis_port, db=2)
    log_list = r2.lrange(task_id, 0, -1)
    for log in log_list:
        try:
            log_dict = json.loads(log)
            task_dict['logs'].append(log_dict)
        except:
            continue
    return task_dict