# -*- coding: utf-8 -*-
from dns_python.models import *
from util.timelib import *
from django.utils import simplejson
import time
import commands
import os

root_key = '/home/deploy/.ssh/id_dsa'


def ssh(cmdstr="", host="127.0.0.1", options="", key=root_key, user='root'):
    ssh_cmd = '''ssh -q -i '%s' -o StrictHostKeyChecking=no -o BatchMode=yes %s %s@%s "%s"''' % \
              (key, options, user, host, cmdstr)
    status, output = commands.getstatusoutput(ssh_cmd)
    if status != 0:
        return (ssh_cmd, False, output)
    return (ssh_cmd, True, output)


def scp(host, src, det, key=root_key, user='root', local2remote=True):
    if local2remote:
        cmdstr = "scp -q -i '%s' -o StrictHostKeyChecking=no -o BatchMode=yes -o \
            ConnectTimeout=10 %s %s@%s:%s" % (key, src, user, host, det)
    else:
        cmdstr = "scp -q -i '%s' -o StrictHostKeyChecking=no -o BatchMode=yes -o \
            ConnectTimeout=10 %s@%s:%s %s" % (key, user, host, src, det)
    status, output = commands.getstatusoutput(cmdstr)
    if status != 0:
        return (cmdstr, False, output)
    return (cmdstr, True, output)


class ZoneException(Exception):
    pass


class Zone(object):
    ''' Zone File management object. '''

    def __init__(self, model):
        self.model = model
        self.zone_id = model.id
        self.serial = model.serial
        self.host = model.ip
        self.host2 = model.ip2
        self.name = model.name
        self.domain = model.domain
        self.path = model.path
        self.temp = model.temp
        self.ttl = model.ttl
        self.origin = model.origin
        self.ctime = int(time.time())
        self._origin = ''
        self._owner = 0
        self.logging = True
        self.user = 'system'

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value):
        self._owner = value

    @property
    def zone_serial(self):
        return self.serial

    @zone_serial.setter
    def zone_serial(self, value):
        self.serial = value
        self.model.serial = value
        self.model.save()
        try:
            soa_head = DnsRecord.objects.get(dns_zone_id=self.zone_id, rrtype='SOA')
        except DnsRecord.DoesNotExist:
            self.save_soahead('@', self.ttl, '@       root ( %s 3H 15M 1W 1D )' % value)
        else:
            # 更新record表 SOA记录的 serial
            soa_value = soa_head.rrdata
            part_a, part_b = soa_value.split('(')
            part_b = part_b.split()
            part_b[0] = value
            part_b = ' '.join(part_b)
            rrdata = part_a.strip() + ' ( ' + part_b.strip()
            self.save_soahead(soa_head.domain, soa_head.ttl, rrdata)

    def update_serial(self):
        serial = self.zone_serial
        day = stamp2str(time.time(), '%Y%m%d')
        if serial[:8] < day:
            new = '%s01' % day
        else:
            num = serial[8:10].ljust(2, '0')
            num = str(int(num) + 1).rjust(2, '0') if num < '99' else '99'
            new = '%s%s' % (serial[:8], num)
        self.zone_serial = new

    def domain_exists(self, domain, rrtype=None, temp=True):
        if not self.origin:
            raise ZoneException('请先设置ORIGIN的值')
        origin = self.origin
        origin = origin + '.' if not origin.endswith('.') else origin
        if domain and domain != '@':
            domain = domain + '.' if not domain.endswith('.') else domain
            domain = domain + origin if not domain.endswith(origin) else domain
        if temp:
            if rrtype:
                return DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, domain=domain, rrtype=rrtype).exists()
            else:
                return DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, domain=domain).exists()
        else:
            if rrtype:
                return DnsRecord.objects.filter(dns_zone_id=self.zone_id, domain=domain, rrtype=rrtype).exists()
            else:
                return DnsRecord.objects.filter(dns_zone_id=self.zone_id, domain=domain).exists()

    def get_domains(self, domain, rrtype=None, temp=True):
        if not self.origin:
            raise ZoneException('请先设置ORIGIN的值')
        origin = self.origin
        origin = origin + '.' if not origin.endswith('.') else origin
        if domain and domain != '@':
            domain = domain + '.' if not domain.endswith('.') else domain
            domain = domain + origin if not domain.endswith(origin) else domain
        if temp:
            if rrtype:
                return DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, domain=domain, rrtype=rrtype)
            else:
                return DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, domain=domain)
        else:
            if rrtype:
                return DnsRecord.objects.filter(dns_zone_id=self.zone_id, domain=domain, rrtype=rrtype)
            else:
                return DnsRecord.objects.filter(dns_zone_id=self.zone_id, domain=domain)

    def has_soahead(self):
        return DnsRecord.objects.filter(dns_zone_id=self.zone_id, rrtype='SOA').exists()

    def get_records(self, search, temp=True, whole=True):
        DnsRecordCls = DnsRecordTemp if temp else DnsRecord
        if search:
            from django.db.models import Q
            if whole:
                items = DnsRecordCls.objects.filter(
                    Q(dns_zone_id=self.zone_id),
                    Q(domain__contains=search) | Q(rrdata__contains=search)
                )
            else:
                items = DnsRecordCls.objects.filter(
                    Q(dns_zone_id=self.zone_id),
                    Q(owner=self.owner),
                    Q(domain__contains=search) | Q(rrdata__contains=search)
                )
        else:
            if whole:
                items = DnsRecordCls.objects.filter(dns_zone_id=self.zone_id)
            else:
                items = DnsRecordCls.objects.filter(dns_zone_id=self.zone_id, owner=self.owner)
        return [{
                    'id': item.id,
                    'dns_zone_id': item.dns_zone_id,
                    'domain': item.domain,
                    'ttl': item.ttl,
                    'origin': self.origin,
                    'prefix': item.domain.rsplit('.' + self.origin, 1)[0] if self.origin else item.domain,
                    'rrtype': item.rrtype,
                    'rrdata': item.rrdata,
                    'owner': item.owner,
                    'status': getattr(item, 'status', 0)
                } for item in items]

    def save_record(self, domain, ttl, rrtype, rrdata, record_id=0, owner=None, temp=True):
        if rrtype == 'SOA':
            self.save_soahead(domain, ttl, rrdata)
            return None
        # 预处理, 后缀和CNAME
        if not self.origin:
            raise ZoneException('请先设置ORIGIN的值')
        origin = self.origin
        origin = origin + '.' if not origin.endswith('.') else origin
        if domain and domain != '@':
            domain = domain + '.' if not domain.endswith('.') else domain
            domain = domain + origin if not domain.endswith(origin) else domain
        if rrtype == 'CNAME':
            rrdata = rrdata + '.' if rrdata and not rrdata.endswith('.') else rrdata

        try:
            temp_record = DnsRecordTemp.objects.get(id=record_id)
        except DnsRecordTemp.DoesNotExist:
            # 新增
            # CNAME和A不能共存
            if rrtype in ['A', 'CNAME']:
                e_rrtype = 'CNAME' if rrtype == 'A' else 'A'
                if self.domain_exists(domain, e_rrtype, temp=True):
                    raise ZoneException('{0} 的{1}记录已存在，无法保存'.format(domain, e_rrtype))
            # End
            # 新增 或 更新
            temp_record, created = DnsRecordTemp.objects.get_or_create(
                dns_zone_id=self.zone_id,
                domain=domain,
                rrtype=rrtype,
                rrdata=rrdata,
                defaults={
                    'ttl': ttl or self.ttl,
                    'status': 1,  # 状态1表示修改中(新增或更新)
                    'owner': self.owner if owner is None else owner,
                    'username': self.user,
                    'ctime': self.ctime
                }
            )
            if not created:
                temp_record.ttl = ttl or self.ttl
                temp_record.ctime = self.ctime
                temp_record.status = 1
                if owner is not None:
                    temp_record.owner = owner
                temp_record.username = self.user
                temp_record.save()
        else:
            # 更新
            # CNAME和A不能共存
            if rrtype in ['A', 'CNAME']:
                e_rrtype = 'CNAME' if rrtype == 'A' else 'A'
                filters = {'dns_zone_id': self.zone_id, 'domain': domain, 'rrtype': e_rrtype}
                if DnsRecordTemp.objects.filter(**filters).exclude(id=record_id).exists():
                    raise ZoneException('{0} 的{1}记录已存在，无法保存'.format(domain, e_rrtype))
            # End
            filters = {'dns_zone_id': self.zone_id, 'domain': domain, 'rrtype': rrtype, 'rrdata': rrdata}
            if DnsRecordTemp.objects.filter(**filters).exclude(id=record_id).exists():
                raise ZoneException('{0} 重复的域名记录已存在，无法保存'.format(domain))
            temp_record.domain = domain
            temp_record.rrtype = rrtype
            temp_record.rrdata = rrdata
            temp_record.ttl = ttl or self.ttl
            temp_record.status = 1
            if owner is not None:
                temp_record.owner = owner
            temp_record.username = self.user
            temp_record.ctime = self.ctime
            temp_record.save()
        if not temp:
            self.temp2record(temp_record)

    def save_soahead(self, domain, ttl, rrdata):
        soahead, created = DnsRecordTemp.objects.get_or_create(
            dns_zone_id=self.zone_id,
            rrtype='SOA',
            defaults={
                'domain': domain,
                'rrdata': rrdata,
                'ttl': ttl or self.ttl,
                'status': 0,
                'owner': 0,
                'ctime': self.ctime
            })
        if not created:
            soahead.domain = domain
            soahead.rrdata = rrdata
            soahead.ttl = ttl or self.ttl
            soahead.status = 0
            soahead.owner = 0
            soahead.username = self.user
            soahead.ctime = self.ctime
            soahead.save()
        soahead_record = soahead.record
        if not soahead_record:
            soahead_record = DnsRecord.objects.create(
                id=soahead.id,
                dns_zone_id=soahead.dns_zone_id,
                domain=soahead.domain,
                ttl=soahead.ttl,
                rrtype=soahead.rrtype,
                rrdata=soahead.rrdata,
                owner=soahead.owner,
                ctime=soahead.ctime
            )
        else:
            soahead_record.dns_zone_id = soahead.dns_zone_id
            soahead_record.domain = soahead.domain
            soahead_record.ttl = soahead.ttl
            soahead_record.rrtype = soahead.rrtype
            soahead_record.rrdata = soahead.rrdata
            soahead_record.owner = soahead.owner
            soahead_record.ctime = soahead.ctime
            soahead_record.save()
        # 更新serial
        serial = rrdata.split('(')[1].split()[0]
        self.serial = serial
        self.model.serial = serial
        self.model.save()

    def temp2record(self, temp):
        ''' 临时表写入Record表 '''
        record = temp.record
        if self.logging:
            self.write_record_history(temp, record)
        if temp.status == -1:
            if record:
                record.delete()
            temp.delete()
            return None
        if not record:
            record = DnsRecord.objects.create(
                id=temp.id,
                dns_zone_id=temp.dns_zone_id,
                domain=temp.domain,
                ttl=temp.ttl,
                rrtype=temp.rrtype,
                rrdata=temp.rrdata,
                owner=temp.owner,
                ctime=temp.ctime
            )
        else:
            record.dns_zone_id = temp.dns_zone_id
            record.domain = temp.domain
            record.ttl = temp.ttl
            record.rrtype = temp.rrtype
            record.rrdata = temp.rrdata
            record.owner = temp.owner
            record.ctime = temp.ctime
            record.save()
        temp.status = 0
        temp.save()

    def write_record_history(self, temp, record):
        ''' Record变更 '''
        action = None
        new_data = {
            'domain': getattr(temp, 'domain'),
            'ttl': getattr(temp, 'ttl'),
            'rrtype': getattr(temp, 'rrtype'),
            'rrdata': getattr(temp, 'rrdata')
        }
        if record:
            if temp.id != record.id: return None
            old_data = {
                'domain': getattr(record, 'domain'),
                'ttl': getattr(record, 'ttl'),
                'rrtype': getattr(record, 'rrtype'),
                'rrdata': getattr(record, 'rrdata')
            }
            if temp.status == -1:
                action = 'D'
                new_data = {}
            else:
                if new_data == old_data: return None
                action = 'U'
        else:
            if temp.status == -1: return None
            action = 'C'
            old_data = {}
        if action is not None:
            DnsRecordHistory.objects.create(
                dns_record_id=temp.id,
                dns_zone_id=temp.dns_zone_id,
                old_data=simplejson.dumps(old_data),
                new_data=simplejson.dumps(new_data),
                action=action,
                owner=temp.owner,
                username=temp.username,
                ctime=int(time.time())
            )

    def delete_record(self, record_id, temp=True):
        try:
            temp_record = DnsRecordTemp.objects.get(id=record_id)
        except DnsRecordTemp.DoesNotExist:
            DnsRecord.objects.filter(id=record_id).delete()
        else:
            temp_record.status = -1  # -1表示删除
            temp_record.username = self.user
            if not temp:
                self.temp2record(temp_record)
            else:
                temp_record.save()

    def clean_records(self, ctime=None, temp=True):
        ctime = ctime or self.ctime
        temps = DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, ctime__lt=ctime)  # .update(status=-1)
        for temp in temps:
            if temp.record:
                temp.status = -1
            else:
                temp.status = 1
            temp.save()

    def get_origin_zone(self):
        cmdstr, status, output = scp(self.host, self.path, self.temp, local2remote=False)
        if not status:
            raise ZoneException(output)

    def write_origin_zone(self):
        status_all, out_all = True, ''
        if self.host:
            cmdstr, status, output = scp(self.host, self.temp, self.path, local2remote=True)
            status_all = status_all and status
            if status:
                status_check, out_check = self.check(main=True, backup=False)
                status_all = status_all and status_check
                if status_check:
                    status_reload, out_reload = self.reload(main=True, backup=False)
                    status_all = status_all and status_reload
                    if not status_reload:
                        out_all = 'reload error: %s' % out_reload
                else:
                    out_all = 'check error: %s' % out_check
            else:
                out_all = 'scp error: %s' % output
        if self.host2:
            cmdstr2, status2, output2 = scp(self.host2, self.temp, self.path, local2remote=True)
            status_all = status_all and status2
            if status2:
                status_check, out_check = self.check(main=False, backup=True)
                status_all = status_all and status_check
                if status_check:
                    status_reload, out_reload = self.reload(main=False, backup=True)
                    status_all = status_all and status_reload
                    if not status_reload:
                        out_all = 'reload error: %s' % out_reload
                else:
                    out_all = 'check error: %s' % out_check
            else:
                out_all = 'scp error: %s' % output

        if not status_all:
            raise ZoneException(out_all)

    def parse_record(self, line):
        if 'IN' not in line or 'SOA' in line: return None
        head, tail = line.split('IN')
        items = head.split()
        if items:
            domain = '' if len(items) == 1 and items[0].isdigit() else items[0]
            ttl = items[-1] if (len(items) == 2 or (len(items) == 1 and items[0].isdigit())) else self.ttl
        else:
            domain = ''
            ttl = self.ttl
        rrtype, rrdata = tail.split(None, 1)
        self.save_record(domain, ttl, rrtype, rrdata)

    def parse_soahead(self, records):
        soa_head = ''
        for line in records:
            line = line.strip()
            if not line: continue
            # 去掉注释
            if line.startswith(';'): continue
            line = line.split(';')[0].strip()
            if line.startswith('$'): continue
            if 'IN' in line and 'SOA' in line:
                soa_head = line
            elif 'IN' not in line:
                soa_head = ' '.join((soa_head, line))
            elif 'IN' in line and soa_head:
                break
        head, tail = soa_head.split('IN')
        items = head.split()
        domain = '' if not items else items[0]
        ttl = items[1] if len(items) == 2 else self.ttl
        rrtype, rrdata = tail.split(None, 1)
        self.save_soahead(domain, ttl, rrdata)

    def parse_zone(self, origin=True):
        ''' 解析Zone文件, 写入到DB '''
        if origin:
            self.get_origin_zone()
        fp = open(self.temp)
        soa_head = ''
        records = fp.readlines()
        # 解析SOA头
        self.parse_soahead(records)
        # 解析记录
        for line in records:
            line = line.strip()
            if not line: continue
            # 去掉注释
            if line.startswith(';'): continue
            line = line.split(';')[0].strip()
            # 处理全局变量
            if line.startswith('$'):
                name, value = line.split()
                if name == '$TTL':
                    self.ttl = int(value)
                    self.model.ttl = int(value)
                    self.model.save()
                elif name == '$ORIGIN':
                    self.origin = value
                    self.model.origin = value
                    self.model.save()
                continue
            self.parse_record(line)
        fp.close()
        self.clean_records()

    def sync_records(self, whole=False):
        ''' Temp表数据写入Record '''
        if whole:
            temps = DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id).exclude(status=0)
        else:
            temps = DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id, owner=self.owner).exclude(status=0)
        for temp in temps:
            self.temp2record(temp)
        records = DnsRecord.objects.filter(dns_zone_id=self.zone_id)
        # 剔除Record表中的脏数据
        for record in records:
            if not DnsRecordTemp.objects.filter(id=record.id).exists():
                record.delete()
        return temps

    def init_records(self):
        ''' 初始同步Temp和Record, 缺陷是不记录变更日志, 不建议调用 '''
        temps = DnsRecordTemp.objects.filter(dns_zone_id=self.zone_id)
        records = DnsRecord.objects.filter(dns_zone_id=self.zone_id)
        records.delete()
        for temp in temps:
            record = DnsRecord.objects.create(
                id=temp.id,
                dns_zone_id=temp.dns_zone_id,
                domain=temp.domain,
                ttl=temp.ttl,
                rrtype=temp.rrtype,
                rrdata=temp.rrdata,
                owner=temp.owner,
                ctime=temp.ctime
            )

    def write_zone(self, origin=True):
        ''' Record表写入Zone文件 '''
        fp = open(self.temp, 'w')
        if self.ttl:
            fp.write('$TTL\t%s\n' % self.ttl)
        soa_head = DnsRecord.objects.get(dns_zone_id=self.zone_id, rrtype='SOA')
        head_ttl = ' ' if str(soa_head.ttl) == str(self.ttl) else soa_head.ttl
        line = "%s\t%s\tIN\tSOA\t%s\n" % (soa_head.domain, head_ttl, soa_head.rrdata)
        fp.write(line)
        ns_records = DnsRecord.objects.filter(dns_zone_id=self.zone_id, rrtype='NS')
        for record in ns_records:
            record_ttl = ' ' if str(record.ttl) == str(self.ttl) else record.ttl
            line = "%s\t%s\tIN\t%s\t%s\n" % (record.domain, record_ttl, record.rrtype, record.rrdata)
            fp.write(line)
        fp.write('\n')
        records = DnsRecord.objects.filter(dns_zone_id=self.zone_id)
        for record in records:
            if record.rrtype == 'SOA' or record.rrtype == 'NS': continue
            record_ttl = ' ' if str(record.ttl) == str(self.ttl) else record.ttl
            line = "%s\t%s\tIN\t%s\t%s\n" % (record.domain, record_ttl, record.rrtype, record.rrdata)
            fp.write(line)
        fp.close()
        if origin:
            self.write_origin_zone()

    def validate(self, reload=False, backup=False, force=False):
        ''' 记录生效 '''
        self.logging = True  # 记录日志
        rst = self.sync_records(True if self.owner == 0 else False)  # Temp数据写入Record
        if not rst and not force: return None  # 没有修改，不强制生效
        if backup:
            self.backup()
        self.update_serial()  # 更新序列号
        self.write_zone()  # DB数据写入Zone文件

    def backup(self):
        if self.host:
            self._backup(self.host)
        if self.host2:
            self._backup(self.host2)

    def _backup(self, host):
        ''' 备份Zone文件 '''
        cmdstr = "ls -d %s" % self.path
        cmdstr, status, output = ssh(cmdstr, host)
        # path文件不存在
        if not status:
            raise ZoneException(cmdstr, output)
        backup_path = os.path.join(os.path.dirname(self.path), 'backup')
        cmdstr = "ls -d %s" % backup_path
        cmdstr, status, output = ssh(cmdstr, host)
        # backup目录不存在
        if not status:
            cmdstr = "mkdir -p '%s'" % backup_path
            cmdstr, status, output = ssh(cmdstr, host)
            # 创建 backup目录失败
            if not status:
                raise ZoneException(cmdstr, output)
        path = os.path.join(backup_path, '%s.%s' % (self.name, self.zone_serial))
        cmdstr = "cp -pf %s %s" % (self.path, path)
        cmdstr, status, output = ssh(cmdstr, host)
        if not status:
            raise ZoneException(cmdstr, output)
        bak, created = DnsZoneHistory.objects.get_or_create(
            dns_zone_id=self.zone_id,
            serial=self.zone_serial,
            defaults={'path': path, 'ctime': int(time.time())})

    def get_history(self, stamp=0, limit=0, whole=True):
        if whole:
            if limit:
                items = DnsRecordHistory.objects.filter(dns_zone_id=self.zone_id).order_by('-id')[0:limit]
            else:
                items = DnsRecordHistory.objects.filter(dns_zone_id=self.zone_id, ctime__gte=stamp).order_by('-id')
        else:
            if limit:
                items = DnsRecordHistory.objects.filter(dns_zone_id=self.zone_id, owner=self.owner).order_by('-id')[
                        0:limit]
            else:
                items = DnsRecordHistory.objects.filter(dns_zone_id=self.zone_id, owner=self.owner,
                                                        ctime__gte=stamp).order_by('-id')
        lists = [{
                     'id': item.id,
                     'dns_zone_id': item.dns_zone_id,
                     'dns_record_id': item.dns_record_id,
                     'action': item.action,
                     'old_data': simplejson.loads(item.old_data) or {},
                     'new_data': simplejson.loads(item.new_data) or {},
                     'username': item.username,
                     'ctime': item.ctime,
                     'ctime_date': stamp2str(item.ctime, '%Y-%m-%d %H:%M')
                 } for item in items]
        return lists

    def record2history(self, history):
        if history.action == 'C':
            self.delete_record(history.dns_record_id)
        else:
            data = simplejson.loads(history.old_data)
            self.save_record(data['domain'], data['ttl'], data['rrtype'], data['rrdata'], history.dns_record_id,
                             history.owner)

    def rollback(self, ids):
        ''' 回滚 '''
        dones = []
        items = DnsRecordHistory.objects.filter(dns_zone_id=self.zone_id, id__in=ids).order_by('id')
        for history in items:
            if history.dns_record_id in dones:
                continue
            self.record2history(history)
            dones.append(history.dns_record_id)

    def check(self, main=True, backup=True):
        ''' check zone '''
        cmdstr = 'named-checkzone %s %s' % (self.domain, self.path)
        status, output = True, ''
        if main and self.host:
            cmdstr1, status1, output1 = ssh(cmdstr, self.host)
            status = status and status1
            output = '%s\n%s:%s' % (output, self.host, output1)
        if backup and self.host2:
            cmdstr2, status2, output2 = ssh(cmdstr, self.host2)
            status = status and status2
            output = '%s\n%s:%s' % (output, self.host2, output2)
        return (status, output)

    def reload(self, main=True, backup=True):
        ''' rndc reload '''
        cmdstr = 'rndc reload %s' % self.domain
        status, output = True, ''
        if main and self.host:
            cmdstr1, status1, output1 = ssh(cmdstr, self.host)
            status = status and status1
            output = '%s\n%s:%s' % (output, self.host, output1)
        if backup and self.host2:
            cmdstr2, status2, output2 = ssh(cmdstr, self.host2)
            status = status and status2
            output = '%s\n%s:%s' % (output, self.host2, output2)
        return (status, output)
