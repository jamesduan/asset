# -*- coding: utf-8 -*-
import socket
from dns_python.models import *
from dns_python.utils import Zone


def update(old_ip, old_domain, new_ip, new_domain, env, owner):
    # 判断IP是否合法
    try:
        socket.inet_aton(new_ip)
    except Exception, e:
        return {'success': False, 'msg': e.args}
    # 判断环境是否合法
    dns_zone_env_obj = DnsZoneEnv.objects.filter(name=env).first()
    if dns_zone_env_obj is None:
        return {'success': False, 'msg': '%s is not a valid env' % env}
    # 根据域名和环境，找到对于应的zone
    dns_owner_queryset = DnsOwner.objects.filter(owner=owner)
    dns_zone_id_list = [dns_owner_obj.dns_zone_id for dns_owner_obj in dns_owner_queryset]
    dns_zone_queryset = DnsZone.objects.filter(id__in=dns_zone_id_list, dns_zone_env_id=dns_zone_env_obj.id)
    dns_zone_obj = None
    new_domain_tmp = new_domain
    while True:
        new_domain_tmp_list = new_domain_tmp.split('.', 1)
        if len(new_domain_tmp_list) == 2:
            domain = new_domain_tmp_list[1]
            dns_zone_obj = dns_zone_queryset.filter(domain=domain).first()
            if dns_zone_obj is not None:
                break
            new_domain_tmp = domain
        else:
            break
    if dns_zone_obj is None:
        return {'success': False, 'msg': '%s is not a valid domain_name' % new_domain}
    zone = Zone(dns_zone_obj)
    zone.user = 'domain_dba_api'
    zone.owner = owner
    # 判断待更改的记录是否合法
    dns_record_queryset = zone.get_domains(old_domain, 'A')
    dns_record_obj = dns_record_queryset.filter(rrdata=old_ip).first()
    if dns_record_obj is None:
        return {'success': False, 'msg': '%s(%s) is not a valid record' % (old_domain, old_ip)}
    elif dns_record_obj.owner != owner:
        return {'success': False, 'msg': 'the record does not belong to you' % (old_domain, old_ip)}
    try:
        zone.save_record(new_domain, zone.ttl, 'A', new_ip, dns_record_obj.id)
    except Exception, e:
        return {'success': False, 'msg': e.args}
    return {'success': True, 'dns_zone_id': dns_zone_obj.id}
    # try:
    #     zone.validate(reload=True, backup=False, force=False)
    # except Exception, e:
    #     return {'success': False, 'msg': e.args}


def jsonp(f):
    """Wrap a json response in a callback, and set the mimetype (Content-Type) header accordingly
    (will wrap in text/javascript if there is a callback). If the "callback" or "jsonp" paramters
    are provided, will wrap the json output in callback({thejson})

    Usage:

    @jsonp
    def my_json_view(request):
        d = { 'key': 'value' }
        return HTTPResponse(json.dumps(d), content_type='application/json')

    """
    from functools import wraps
    @wraps(f)
    def jsonp_wrapper(request, *args, **kwargs):
        resp = f(request, *args, **kwargs)
        if resp.status_code != 200:
            return resp
        if 'callback' in request.GET:
            callback= request.GET['callback']
            resp['Content-Type']='text/javascript; charset=utf-8'
            resp.content = "%s(%s)" % (callback, resp.content)
            return resp
        elif 'jsonpCallback' in request.GET:
            callback= request.GET['jsonpCallback']
            resp['Content-Type']='text/javascript; charset=utf-8'
            resp.content = "%s(%s)" % (callback, resp.content)
            return resp
        else:
            return resp

    return jsonp_wrapper
