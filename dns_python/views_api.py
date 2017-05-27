# -*- coding: utf-8 -*-
from rest_framework import filters, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly, AllowAny
from rest_framework.response import Response
from dns_python.serializers import *
from dns_python.utils import Zone, tools, ZoneException
from dns_python.permissions import *
from rest_framework.views import APIView
from django.http import Http404
from util.timelib import stamp2str
import time
from hashlib import md5
from permissions import is_dba
import re

from django.utils import simplejson
from django.http import HttpResponse

# 由于外键存在0，所以不能进行写操作
# 下同
class DnsZoneViewSet(viewsets.ModelViewSet):
    permission_classes = (DnsPermission,)
    queryset = DnsZoneV2.objects.all()
    paginate_by = 100
    serializer_class = DnsZoneSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    search_fields = ('domain', 'ip')
    filter_fields = ('dns_zone_env__id',)

    def get_queryset(self):
        queryset = self.queryset
        if is_dba(self.request):
            owner = 3  # dns_owner表：DB管理员owner字段值
            items = DnsOwner.objects.filter(owner=owner)
            zone_ids = set([item.dns_zone_id for item in items])
            queryset = queryset.filter(id__in=zone_ids)
        return queryset


class DnsRecordViewSet(viewsets.ModelViewSet):
    permission_classes = (DnsPermission, )
    queryset = DnsRecordTempV2.objects.all()
    paginate_by = 100
    serializer_class = DnsRecordTempSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    search_fields = ('domain', 'rrdata')

    def get_queryset(self):
        queryset = self.queryset
        request = self.request

        dns_zone_id = request.GET.get('dns_zone_id', 0)

        owner = None
        if is_dba(request):  # DB管理员所属组
            owner = 3
        # owner = 3  # debug_fxc

        if owner:
            queryset = queryset.filter(owner=owner)
        queryset = queryset.filter(dns_zone_id=dns_zone_id)
        return queryset

    def perform_destroy(self, instance):
        rid = instance.id
        dns_zone_id = instance.dns_zone_id

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)
        else:
            zone = Zone(model)
            zone.user = self.request.user.username
            zone.delete_record(rid)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def zone_save(request):
    if request.method == 'POST':
        req = request.REQUEST
        zid = req.get('id', 0)
        zid = int(zid) if zid and zid.isdigit() else 0
        ip = req.get('ip', '').strip()
        ip2 = req.get('ip2', '').strip()
        name = req.get('name', '').strip()
        serial = req.get('serial', '').strip()
        domain = req.get('domain', '').strip()
        path = req.get('path', '').strip()
        ttl = req.get('ttl', '').strip()
        origin = req.get('origin', '').strip()
        origin = origin + '.' if origin and not origin.endswith('.') else origin
        env_id = req.get('dns_zone_env', 0)
        env_id = int(env_id) if env_id and env_id.isdigit() else 0
        comment = req.get('comment', '').strip()

        # 修改
        if zid:
            try:
                zone = DnsZone.objects.get(id=zid)
                zone.ip = ip
                zone.ip2 = ip2
                zone.name = name
                zone.serial = serial
                zone.domain = domain
                zone.path = path
                zone.ttl = ttl
                zone.origin = origin
                zone.dns_zone_env_id = env_id
                zone.comment = comment
                zone.save()
            except DnsZone.DoesNotExist:
                return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)
        # 新增 或 更新
        else:
            zone, created = DnsZone.objects.get_or_create(ip=ip, ip2=ip2, name=name, defaults={
                'serial': serial,
                'domain': domain,
                'path': path,
                'temp': '/data/tmp/dns/%s' % name,
                'ttl': ttl,
                'origin': origin,
                'dns_zone_env_id': env_id,
                'comment': comment
            })
            # 修改
            if not created:
                zone.serial = serial
                zone.domain = domain
                zone.path = path
                zone.temp = '/tmp/%s' % name
                zone.ttl = ttl
                zone.dns_zone_env_id = env_id
                zone.origin = origin
                zone.comment = comment
                zone.save()
        zone_o = Zone(zone)
        zone_o.zone_serial = serial

        return Response('保存成功', status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes((DnsPermission,))
def test(request):
    if request.method == 'GET':
        return Response({'method': 'GET'}, status=status.HTTP_200_OK)

    if request.method == 'POST':
        return Response({'method': 'POST'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes((DnsPermission,))
def record_list(request):
    if request.method == 'GET':
        dns_zone_id = request.GET.get('dns_zone_id', 0)

        owner = None
        if is_dba(request):  # DB管理员所属组
            owner = 3
        # owner = 3  # debug
        search = request.GET.get('search', '').strip()

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        if owner is not None:
            zone.owner = owner
            records = zone.get_records(search, whole=False)
        else:
            records = zone.get_records(search)

        id_ = request.GET.get('id', None)
        id_ = int(id_) if id_ and id_.isdigit() else None
        if id_ is not None:
            result = None
            for record in records:
                if record['id'] == id_:
                    result = record
                    break
            if result is not None:
                return Response(result, status=status.HTTP_200_OK)
            else:
                # 可能有问题！！！！！
                return Response('记录不存在，可能已被删除', status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'count': len(records), 'results': records})


@api_view(['POST'])
@permission_classes((DnsPermission,))
def record_del(request):
    if request.method == 'POST':
        rid = request.REQUEST.get('id', 0)
        rid = int(rid) if rid and rid.isdigit() else 0

        dns_zone_id = request.REQUEST.get('dns_zone_id', 0)
        dns_zone_id = int(dns_zone_id) if dns_zone_id and dns_zone_id.isdigit() else 0

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)
        else:
            zone = Zone(model)
            zone.user = request.user.username
            zone.delete_record(rid)

        return Response('删除记录成功', status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def record_exist(request):
    if request.method == 'POST':
        req = request.data

        rid = req.get('id', 0)
        rid = int(rid) if rid and rid.isdigit() else 0

        dns_zone_id = req.get('dns_zone_id', 0)
        dns_zone_id = int(dns_zone_id) if dns_zone_id and dns_zone_id.isdigit() else 0

        domain = req.get('domain', '').strip()
        rrtype = req.get('rrtype', '').strip()

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        items = zone.get_domains(domain, rrtype)
        exists = True if items and rid not in [item.id for item in items] else False
        return Response(exists, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def record_save(request):
    if request.method == 'POST':
        req = request.data
        rid = req.get('id', 0)
        rid = int(rid) if rid and rid.isdigit() else 0

        dns_zone_id = req.get('dns_zone_id', 0)
        dns_zone_id = int(dns_zone_id) if dns_zone_id and dns_zone_id.isdigit() else 0

        domain = req.get('domain', '').strip()
        ttl = req.get('ttl', '').strip()
        rrtype = req.get('rrtype', '').strip()
        rrdata = req.get('rrdata', '').strip()

        owner = req.get('owner', 0)
        owner = int(owner) if owner and owner.isdigit() else 0

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.owner = owner
        zone.user = request.user.username
        try:
            zone.save_record(domain, ttl, rrtype, rrdata, rid, owner)
        except ZoneException as e:
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response('保存成功', status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def zone_write(request):
    if request.method == 'POST':
        dns_zone_id = request.data.get('dns_zone_id', 0)

        dns_reload = request.data.get('reload', 0)
        dns_reload = True if dns_reload else False

        dns_backup = request.data.get('backup', 0)
        dns_backup = True if dns_backup else False

        force = 1
        owner = 0
        if is_dba(request):
            owner = 3
            force = 0

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.owner = owner
        zone.user = request.user.username
        try:
            zone.validate(dns_reload, dns_backup, force=force)
        except ZoneException as e:
            response = Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            response = Response('生效Zone文件成功', status=status.HTTP_200_OK)
        return response


@api_view(['GET'])
@permission_classes((DnsPermission,))
def history(request):
    if request.method == 'GET':
        req = request.REQUEST
        limit = req.get('limit', 10)
        zone_id = req.get('dns_zone_id', 0)

        owner = None
        if is_dba(request):
            owner = 3

        try:
            model = DnsZone.objects.get(id=zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除' + str(zone_id), status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        if owner is None:
            items = zone.get_history(limit=limit)
        else:
            zone.owner = owner
            items = zone.get_history(limit=limit, whole=False)
        lists = []
        for item in items:
            old_data = item['old_data'] or {}
            new_data = item['new_data'] or {}
            old_domain = old_data.get('domain', '')
            old_ttl = old_data.get('ttl', '')
            old_rrtype = old_data.get('rrtype', '')
            old_rrdata = old_data.get('rrdata', '')
            new_domain = new_data.get('domain', '')
            new_ttl = new_data.get('ttl', '')
            new_rrtype = new_data.get('rrtype', '')
            new_rrdata = new_data.get('rrdata', '')
            diff = ''
            if old_domain != new_domain:
                diff += '域名: {0}\t=>\t{1}\n'.format(old_domain, new_domain)
            if old_ttl != new_ttl:
                diff += 'TTL: {0}\t=>\t{1}\n'.format(old_ttl, new_ttl)
            if old_rrtype != new_rrtype:
                diff += '类型: {0}\t=>\t{1}\n'.format(old_rrtype, new_rrtype)
            if old_rrdata != new_rrdata:
                diff += '值: {0}\t=>\t{1}\n'.format(old_rrdata, new_rrdata)
            lists.append({
                'id': item['id'],
                'dns_zone_id': item['dns_zone_id'],
                'dns_record_id': item['dns_record_id'],
                'old_domain': old_domain,
                'new_domain': new_domain,
                'action': item['action'],
                'username': item['username'],
                'ctime': item['ctime_date'],
                'stamp': stamp2str(item['ctime'], '%Y%m%d%H%M'),
                'diff': diff
            })

        return Response({'results': lists, 'count': len(lists)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def zone_rollback(request):
    if request.method == 'POST':
        dns_zone_id = request.REQUEST.get('dns_zone_id', 0)
        dns_zone_id = int(dns_zone_id) if dns_zone_id and dns_zone_id.isdigit() else 0

        ids = request.REQUEST.get('ids', '').strip()
        ids = ids.split(',')

        # import time
        # time.sleep(3)
        # return Response(ids, status=status.HTTP_200_OK)

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.user = request.user.username
        try:
            zone.rollback(ids)
        except ZoneException as e:
            status_, output = False, str(e)
        else:
            status_, output = True, 'Zone文件回滚成功'
        return Response(output, status=status.HTTP_200_OK if status_ else status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def record_save_multi(request):
    if request.method == 'POST':
        req = request.REQUEST
        dns_zone_id = req.get('dns_zone_id', 0)
        dns_zone_id = int(dns_zone_id) if dns_zone_id and dns_zone_id.isdigit() else 0
        lists = req.get('lists', '').strip()
        owner = req.get('owner', 0)
        owner = int(owner) if owner and owner.isdigit() else 0

        # return Response(lists.splitlines(), status=status.HTTP_200_OK)

        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.owner = owner
        zone.user = request.user.username
        for line in lists.splitlines():
            if not line.strip():
                continue
            try:
                domain, rrtype, rrdata = line.split()
                zone.save_record(domain, '', rrtype, rrdata, 0, owner)
            except ZoneException as e:
                return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response('保存成功', status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((DnsPermission,))
def zone_download(request):
    if request.method == 'POST':
        dns_zone_id = request.REQUEST.get('dns_zone_id', 0)
        try:
            model = DnsZone.objects.get(id=dns_zone_id)
        except DnsZone.DoesNotExist:
            return Response('Zone文件不存在，可能已经删除', status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.write_zone(origin=False)
        key = md5(zone.name+str(time.time())).hexdigest()
        Download.objects.create(key=key, name=zone.name, path=zone.temp, file_type='zip')
        return Response({'key': key, 'msg': u'生成zone文件成功'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes((AllowAny,))
def download(request):
    ''' 通用下载功能， 下载支持CSV, PDF, ZIP '''
    if request.method == 'GET':
        key = request.REQUEST.get('key', '').strip()
        try:
            d = Download.objects.get(key=key)
        except Download.DoesNotExist:
            # return Response(u'您想下载的文件不存在哦', status=status.HTTP_404_NOT_FOUND, mimetype='application/json')
            response = simplejson.dumps({'success': False, 'msg': u'您想下载的文件不存在哦'})
            return HttpResponse(response, mimetype='application/json')

        def read_file(path, buf=262144):
            with open(path, "rb") as f:
                while True:
                    c = f.read(buf)
                    if c:
                        yield c
                    else:
                        break

        try:
            data = read_file(d.path)
        except IOError:
            # return Response(u'您想下载的文件已被删除', status=status.HTTP_404_NOT_FOUND, mimetype='application/json')
            response = simplejson.dumps({'success': False, 'msg': u'您想下载的文件已被删除'})
            return HttpResponse(response, mimetype='application/json')

        if d.file_type == 'csv':
            # response = Response(data, mimetype='text/csv')
            response = HttpResponse(data, mimetype='text/csv')
            response['Content-Disposition'] = 'attachment; filename="%s"' % d.name.encode('utf-8')
        elif d.file_type == 'pdf':
            # response = Response(data, content_type='application/pdf')
            response = HttpResponse(data, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="%s"' % d.name.encode('utf-8')
        else:
            # response = Response(data, content_type='application/zip')
            response = HttpResponse(data, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="%s"' % d.name.encode('utf-8')
        return response


@api_view(['GET'])
@permission_classes((AllowAny,))
def domain_validate(request):
    if request.method == 'GET':
        zone_id = request.REQUEST.get('zone_id')
        owner = request.REQUEST.get('owner')
        force = request.REQUEST.get('force')

        zone_id = int(zone_id) if zone_id and zone_id.isdigit() else 0
        owner = int(owner) if owner and owner.isdigit() else 9
        force = True if force else False

        try:
            model = DnsZone.objects.get(id=zone_id)
        except DnsZone.DoesNotExist:
            return Response({'msg': 'Zone文件不存在，可能已经删除'}, status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.owner = owner
        zone.validate(reload=True, backup=False, force=force)
        return Response({'msg': 'Zone生效成功'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes((AllowAny,))
def domain_sync(request):
    if request.method == 'GET':
        zone_id = request.REQUEST.get('zone_id')
        owner = request.REQUEST.get('owner')
        zone_id = int(zone_id) if zone_id and zone_id.isdigit() else 0
        owner = int(owner) if owner and owner.isdigit() else 9

        try:
            model = DnsZone.objects.get(id=zone_id)
        except DnsZone.DoesNotExist:
            return Response({'msg': 'Zone文件不存在，可能已经删除'}, status=status.HTTP_404_NOT_FOUND)

        zone = Zone(model)
        zone.owner = owner
        zone.sync_records(True if owner == 0 else False)
        return Response({'msg': 'Zone同步成功'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_exists(request):
    ''' 判断域名是否存在 '''
    if request.method == 'POST':
        key = request.GET.get('key', 'merchant_shop').strip()
        domain = request.GET.get('domain', '').strip()
        # 检查domain是否符合规则: 域名不能低于4个字符，不能超过20个字符。只能含有“字母”“数字”
        pat = r'^[a-zA-Z0-9]{4,20}(\.yhd\.com)?$'
        m = re.match(pat, domain)
        if not m:
            response = simplejson.dumps({'success': False, 'msg': u'域名不符合规则，请检查'})
            return HttpResponse(response)
        try:
            item = DnsApiZone.objects.get(key=key)
        except DnsApiZone.DoesNotExist:
            response = simplejson.dumps({'success': False, 'msg': u'无效的请求'})
            return HttpResponse(response)
        model = item.zone
        if not model:
            response = simplejson.dumps({'success': False, 'msg': u'Zone不存在'})
            return HttpResponse(response)
        zone = Zone(model)
        exists = zone.domain_exists(domain)
        response = simplejson.dumps({'success': True, 'exists': exists})
        return HttpResponse(response)


@api_view(['GET', 'POST'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_list(request):
    ''' 二级域名列表 '''
    # 之前的不标准，又无调用记录，不确定也无妨如何调用的
    if True:
        key = request.GET.get('key', 'merchant_shop').strip()
        try:
            item = DnsApiZone.objects.get(key=key)
        except DnsApiZone.DoesNotExist:
            response = simplejson.dumps({'success': False, 'msg': u'无效的请求'})
            return HttpResponse(response)
        model = item.zone
        if not model:
            response = simplejson.dumps({'success': False, 'msg': u'Zone不存在'})
            return HttpResponse(response)
        zone = Zone(model)
        records = zone.get_records(search=None, temp=True, whole=True)
        lists = [record['domain'].split('.yhd.com.')[0] for record in records if record['rrtype']=='CNAME' and record['rrdata']=='merchant-shop.yhd.com.yhcdn.cn.']
        response = simplejson.dumps({'success': True, 'total': len(lists), 'lists': lists})
        return HttpResponse(response)


@api_view(['POST'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_add(request):
    ''' 增加域名列表 '''
    if request.method == 'POST':
        key = request.REQUEST.get('key', 'merchant_shop')
        intime = request.REQUEST.get('intime', '1')
        intime = int(intime) if intime and intime.isdigit() else 1
        lists = [item.strip() for item in request.REQUEST.get('lists', '').split(',')]
        if not lists:
            response = simplejson.dumps({'success': False, 'msg': u'请输入域名列表'})
            return HttpResponse(response)
        pat = r'^[a-zA-Z0-9]{4,20}(\.yhd\.com)?$'
        for domain in lists:
            m = re.match(pat, domain)
            if not m:
                response = simplejson.dumps({'success': False, 'msg': u'域名不符合规则, 请检查'})
                return HttpResponse(response)
        try:
            item = DnsApiZone.objects.get(key=key)
        except DnsApiZone.DoesNotExist:
            response = simplejson.dumps({'success': False, 'msg': u'无效的请求'})
            return HttpResponse(response)
        model = item.zone
        if not model:
            response = simplejson.dumps({'success': False, 'msg': u'Zone不存在'})
            return HttpResponse(response)
        zone = Zone(model)
        zone.user = 'domain_add_api'
        zone.owner = 9      # owner = 9 表示属于API
        exists = []
        dones = []
        for domain in lists:
            domain = domain.strip()
            if zone.domain_exists(domain):
                exists.append(domain)
            else:
                try:
                    zone.save_record(domain, zone.ttl, 'CNAME', 'merchant-shop.yhd.com.yhcdn.cn.')
                except ZoneException as e:
                    pass
                else:
                    dones.append(domain)
        '''if intime and dones:
            zone.validate(reload=True, backup=False)         # 生效'''
        response = simplejson.dumps({'success': True, 'exists': exists})
        return HttpResponse(response)


@api_view(['POST'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_edit(request):
    ''' 修改域名列表 '''
    if request.method == 'POST':
        key = request.REQUEST.get('key', 'merchant_shop')
        intime = request.REQUEST.get('intime', '1')
        intime = int(intime) if intime and intime.isdigit() else 1
        lists = request.REQUEST.get('lists')
        if not lists:
            response = simplejson.dumps({'success': False, 'msg': u'请输入需要修改的域名列表'})
            return HttpResponse(response)
        lists = simplejson.loads(lists)
        pat = r'^[a-zA-Z0-9]{4,20}(\.yhd\.com)?$'
        for dict_domain in lists:
            if not dict_domain:
                continue
            old_domain = dict_domain['oldDomainName']
            new_domain = dict_domain['newDomainName']
            m = re.match(pat, new_domain)
            if not m:
                response = simplejson.dumps({'success': False, 'msg': u'新域名{0}不符合规则, 请检查'.format(new_domain)})
                return HttpResponse(response)
        try:
            item = DnsApiZone.objects.get(key=key)
        except DnsApiZone.DoesNotExist:
            response = simplejson.dumps({'success': False, 'msg': u'无效的请求'})
            return HttpResponse(response)
        model = item.zone
        if not model:
            response = simplejson.dumps({'success': False, 'msg': u'Zone不存在'})
            return HttpResponse(response)
        zone = Zone(model)
        zone.user = 'domain_add_api'
        zone.owner = 9      # owner = 9 表示属于API
        result = []
        rlists = []
        for dict_domain in lists:
            if not dict_domain:
                continue
            old_domain = dict_domain['oldDomainName']
            new_domain = dict_domain['newDomainName']
            domains = zone.get_domains(old_domain, 'CNAME')
            if not domains:
                # 旧的域名不存在
                result.append({'oldDomainName': old_domain, 'newDomainName': new_domain, 'msg': u'域名不存在，无法修改'})
                rlists.append({'oldDomainName': old_domain, 'newDomainName': new_domain})
                continue
            domain = domains[0]
            if domain.owner != 9:
                # 只能修改API添加的域名
                result.append({'oldDomainName': old_domain, 'newDomainName': new_domain, 'msg': u'没有权限修改该域名，请联系SA'})
                rlists.append({'oldDomainName': old_domain, 'newDomainName': new_domain})
                continue
            try:
                zone.save_record(new_domain, zone.ttl, 'CNAME', 'merchant-shop.yhd.com.yhcdn.cn.', domain.id)
            except ZoneException as e:
                result.append({'oldDomainName': old_domain, 'newDomainName': new_domain, 'msg': str(e)})
                rlists.append({'oldDomainName': old_domain, 'newDomainName': new_domain})
            else:
                result.append({'oldDomainName': old_domain, 'newDomainName': new_domain, 'msg': 'success'})
        response = simplejson.dumps({'success': True, 'result': result, 'lists': rlists})
        return HttpResponse(response)


@api_view(['POST'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_del(request):
    ''' 删除域名列表 '''
    if request.methed == 'POST':
        key = request.REQUEST.get('key', 'merchant_shop')
        intime = request.REQUEST.get('intime', '1')
        intime = int(intime) if intime and intime.isdigit() else 1
        lists = [item.strip() for item in request.REQUEST.get('lists', '').split(',')]
        if not lists:
            response = simplejson.dumps({'success': False, 'msg': u'请输入域名列表'})
            return HttpResponse(response)
        pat = r'^[a-zA-Z0-9]{4,20}(\.yhd\.com)?$'
        for domain in lists:
            m = re.match(pat, domain)
            if not m:
                response = simplejson.dumps({'success': False, 'msg': u'域名不符合规则, 请检查'})
                return HttpResponse(response)
        try:
            item = DnsApiZone.objects.get(key=key)
        except DnsApiZone.DoesNotExist:
            response = simplejson.dumps({'success': False, 'msg': u'无效的请求'})
            return HttpResponse(response)
        model = item.zone
        if not model:
            response = simplejson.dumps({'success': False, 'msg': u'Zone不存在'})
            return HttpResponse(response)
        zone = Zone(model)
        zone.user = 'domain_add_api'
        zone.owner = 9      # owner = 9 表示属于API
        result = []
        rlists = []
        for domain in lists:
            domain = domain.strip()
            domains = zone.get_domains(domain, 'CNAME')
            if not domains:
                result.append({'domainName': domain, 'msg': u'域名不存在，无法删除'})
                rlists.append(domain)
                continue
            o = domains[0]
            if o.owner != 9:
                # 只能删除API添加的域名
                result.append({'domainName': domain, 'msg': u'没有权限删除该域名，请联系SA'})
                rlists.append(domain)
                continue
            try:
                zone.delete_record(o.id)
            except ZoneException as e:
                result.append({'domainName': domain, 'msg': str(e)})
                rlists.append(domain)
            else:
                result.append({'domainName': domain, 'msg': 'success'})
        response = simplejson.dumps({'success': True, 'lists': rlists, 'result': result})
        return HttpResponse(response)


@api_view(['GET'])
@permission_classes((AllowAny,))
@tools.jsonp
def domain_dba(request):
    if request.method == 'GET':
        action = request.REQUEST.get('action', 'add').strip()
        if action not in ('add', 'edit'):
            response = simplejson.dumps({'success': False, 'msg': u'action invalid.'})
            return HttpResponse(response)
        domain_old = request.REQUEST.get('oldDomain', '').strip()
        domain_new = request.REQUEST.get('newDomain', '').strip()
        ipaddr_old = request.REQUEST.get('oldIP', '').strip()
        ipaddr_new = request.REQUEST.get('newIP', '').strip()
        pat = r'^\d{1,3}(\.\d{1,3}){3}$'
        if not re.match(pat, ipaddr_new):
            response = simplejson.dumps({'success': False, 'msg': u'IP invalid.'})
            return HttpResponse(response)
        env = request.REQUEST.get('env', 'prod')
        env_id = {'stag': 0, 'prod': 1}.get(env, -1)
        items = DnsOwner.objects.filter(owner=3)
        zone_ids = [int(item.dns_zone_id) for item in items]
        models = DnsZone.objects.filter(id__in=zone_ids, dns_zone_env_id=env_id)
        model = None
        for item in models:
            if domain_new.endswith(item.domain):
                model = item
                break
        if not model:
            response = simplejson.dumps({'success': False, 'msg': 'zone not exists, maybe new domain invalid.'})
            return HttpResponse(response)

        zone = Zone(model)
        zone.user = 'domain_dba_api'
        zone.owner = 3      # owner = 3 表示属于DBA

        record_id = 0
        if action == 'edit':
            deny = True
            domains = zone.get_domains(domain_old, 'A')
            for domain in domains:
                if domain.rrdata == ipaddr_old:
                    record_id = domain.id
                    if domain.owner == 3:
                        deny = False
                    break
            if not record_id:
                response = simplejson.dumps({'success': False, 'msg': 'old domain not exists.'})
                return HttpResponse(response)
            if deny:
                response = simplejson.dumps({'success': False, 'msg': 'this domain does not own to dba, permission deny.'})
                return HttpResponse(response)
        try:
            zone.save_record(domain_new, zone.ttl, 'A', ipaddr_new, record_id)
        except ZoneException as e:
            response = simplejson.dumps({'success': False, 'msg': 'error when save record, maybe record duplicated.'})
            return HttpResponse(response)
        try:
            zone.validate(reload=True, backup=False, force=False)
        except Exception, e:
            response = simplejson.dumps({'success': False, 'msg': 'error when validate record:' + str(e.args)})
            return HttpResponse(response)
        response = simplejson.dumps({'success': True, 'msg': 'success saved.'})
        return HttpResponse(response)


@api_view(['GET'])
@permission_classes((DBAPermission, ))
def record_bulk_by_ip(request):
    old_ip = request.query_params.get('old_ip')
    new_ip = request.query_params.get('new_ip')
    if old_ip is None or new_ip is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='old_ip or new_ip is not supplied')
    env = request.query_params.get('env')
    if env is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='env is not supplied')
    dns_zone_id_list = []
    success_list = []
    dns_record_queryset = DnsRecordV2.objects.filter(rrtype='A', owner=3, dns_zone__dns_zone_env__name=env, rrdata=old_ip)
    if dns_record_queryset.count() == 0:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='record for rrdata(%s) and env(%s) does not exist' % (old_ip, env))
    for dns_record_obj in dns_record_queryset:
        domain = dns_record_obj.domain.rstrip('.')
        result = tools.update(old_ip=old_ip, old_domain=domain, new_ip=new_ip, new_domain=domain, env=env, owner=3)
        if result.get('success'):
            dns_zone_id_list.append(result.get('dns_zone_id'))
            success_list.append(domain)
        else:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data=result.get('msg'))
    for dns_zone_id in set(dns_zone_id_list):
        dns_zone_obj = DnsZone.objects.filter(id=dns_zone_id).first()
        if dns_zone_obj is None:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data='dns_zone_id(%s) does not exist' % dns_zone_id)
        zone = Zone(dns_zone_obj)
        try:
            zone.validate(reload=True, backup=False, force=False)
        except Exception, e:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={'dns_zone_id': dns_zone_id, 'msg': e.args})
    return Response(status=status.HTTP_200_OK, data=success_list)


@api_view(['GET'])
@permission_classes((DBAPermission, ))
def record_bulk_by_domain(request):
    old_ip = request.query_params.get('old_ip')
    new_ip = request.query_params.get('new_ip')
    if old_ip is None or new_ip is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='old_ip or new_ip is not supplied')
    env = request.query_params.get('env')
    if env is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='env is not supplied')
    domain_list = request.query_params.get('domain_list')
    if domain_list is None:
        return Response(status=status.HTTP_400_BAD_REQUEST, data='domain_list is not supplied')
    dns_zone_id_list = []
    success_list = []
    failure_list = []
    for domain in domain_list.split(','):
        result = tools.update(old_ip=old_ip, old_domain=domain, new_ip=new_ip, new_domain=domain, env=env, owner=3)
        if result.get('success'):
            dns_zone_id_list.append(result.get('dns_zone_id'))
            success_list.append(domain)
        else:
            failure_list.append(domain)
    for dns_zone_id in set(dns_zone_id_list):
        dns_zone_obj = DnsZone.objects.filter(id=dns_zone_id).first()
        if dns_zone_obj is None:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data='dns_zone_id(%s) does not exist' % dns_zone_id)
        zone = Zone(dns_zone_obj)
        try:
            zone.validate(reload=True, backup=False, force=False)
        except Exception, e:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={'dns_zone_id': dns_zone_id, 'msg': e.args})
    return Response(status=status.HTTP_200_OK, data={'success_list': success_list, 'failure_list': failure_list})
