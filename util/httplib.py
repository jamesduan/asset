import urllib2
import urllib
import base64
import commands

def httpcall2(url, method="GET", header={"Content-Type": "application/x-www-form-urlencoded"}, body={}, username=None, password=None):
    try:
        if method == "GET":
            req = urllib2.Request(url)
            if username is not None and password is not None:
                str = get_api_auth(username, password)
                req.add_header('Authorization', 'Basic %s' % str)
            res = urllib2.urlopen(req)
            return res.code, res.read().strip()
        elif method == "POST":
            body = urllib.urlencode(body)
            req = urllib2.Request(url, body)
            for key in header:
                req.add_header(key, header[key])
            if username is not None and password is not None:
                str = get_api_auth(username, password)
                req.add_header('Authorization', 'Basic %s' % str)
            res = urllib2.urlopen(req)
            return res.code, res.read().strip()
        else:
            return None, method
    except urllib2.HTTPError, e:
        return e.code, e.read()
    except urllib2.URLError, e:
        return None, e.args
    except Exception, e:
        return None, e.args


def get_api_auth(username, password):
    return base64.encodestring('%s:%s' % (username, password)).replace('\n', '')

def ssh(cmdstr="", host="127.0.0.1", key="/home/deploy/.ssh/id_rsa", user="deploy"):
    ssh_cmd = '''ssh -i %s -o StrictHostKeyChecking=no -o BatchMode=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no %s@%s "%s"''' % \
              (key, user, host, cmdstr)
    status, output = commands.getstatusoutput(ssh_cmd)
    return (True if status==0 else False, ssh_cmd, output)