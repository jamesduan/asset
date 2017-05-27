from django.conf import settings
from assetv2.settingsapi import CONFIGINFO_V3_DOMAINS
from cmdb.models import DdUsers, App, DdUsersDomains
from asset.models import Room
from server.models import ServerStandard
from kazoo.client import KazooClient
import os
import json


def get_app_filter_by_request_user(request, ignore_superuser=False):
    user_obj = request.user
    if user_obj is None:
        return App.objects.filter(id=0)
    group_list = user_obj.groups.values()
    group_id_list = [group['id'] for group in group_list]
    if (not ignore_superuser and user_obj.is_superuser) or settings.GROUP_ID.get(
            request.GET.get('group_name')) in group_id_list:
        # return App.objects.filter(status=0)
        return App.objects.all()
    dd_user_obj = DdUsers.objects.filter(username=user_obj.username, enable=0).first()
    if dd_user_obj is None:
        return App.objects.filter(id=0)
    domain_queryset = dd_user_obj.domains.all()
    domain_id_list = [domain.id for domain in domain_queryset]
    # return App.objects.filter(status=0, domainid__in=domain_id_list)
    return App.objects.filter(domainid__in=domain_id_list)


def get_domains_by_request_user(request):
    user_obj = request.user
    dd_user_obj = DdUsers.objects.filter(username=user_obj.username, enable=0).first()
    return dd_user_obj.domains.all() if dd_user_obj else None

def get_domains_id_by_request_user(request):
    user_obj = request.user
    if user_obj is None:
        return []
    dd_user_obj = DdUsers.objects.filter(username=user_obj.username, enable=0).first()
    domains=dd_user_obj.domains.all() if dd_user_obj else []
    return [domain.id for domain in domains]

def get_app_id_filter_by_request_user(request, ignore_superuser=False):
    user_obj = request.user
    if user_obj is None:
        return []
    group_list = user_obj.groups.values()
    group_id_list = [group['id'] for group in group_list]
    if not ignore_superuser and user_obj.is_superuser:
        return [app.id for app in App.objects.all()] + [0]
    if settings.GROUP_ID.get(request.GET.get('group_name')) in group_id_list:
        return [app.id for app in App.objects.all()]
    dd_user_obj = DdUsers.objects.filter(username=user_obj.username, enable=0).first()
    if dd_user_obj is None:
        return []
    domain_queryset = dd_user_obj.domains.all()
    domain_id_list = [domain.id for domain in domain_queryset]
    return [app.id for app in App.objects.filter(domainid__in=domain_id_list)]


def is_configinfo_v3_domains(request):
    flag = False
    user_obj = request.user
    dd_user_domains_obj = DdUsersDomains.objects.filter(ddusers__id=DdUsers.objects.filter(username=user_obj.username)[0].id)
    for dudo in dd_user_domains_obj:
        if dudo.dddomain.id in CONFIGINFO_V3_DOMAINS:
            flag = True
    return flag


def get_haproxy_group_by_app_obj(app_obj, room_obj):
    group_list = []
    try:
        zk = KazooClient(hosts=room_obj.haproxy_zk_cluster)
        zk.start()
        full_group_list = zk.get_children('/reflection')
        zk.stop()
        prefix = '%s__%s__' % (app_obj.site.name, app_obj.name) if app_obj.site.id != 1 else '%s__' % app_obj.name
        group_list = [group.split('__')[-1] for group in full_group_list if group.startswith(prefix)]
    except Exception, e:
        pass
    return group_list


def get_haproxy_info_by_ip(ip):
    haproxy_dict = dict()
    server_obj = ServerStandard.objects.exclude(server_status_id=400).filter(ip=ip).first()
    if server_obj is None:
        return haproxy_dict
    app_obj = server_obj.app
    prefix = '%s__%s__' % (app_obj.site.name, app_obj.name) if app_obj.site.id != 1 else '%s__' % app_obj.name
    for room_obj in Room.objects.all():
        if not room_obj.haproxy_zk_cluster:
            continue
        zk = KazooClient(hosts=room_obj.haproxy_zk_cluster)
        zk.start()
        full_group_list = zk.get_children('/reflection')
        for group in full_group_list:
            if group.startswith(prefix):
                group_name = group.split('__')[-1]
                data, stat = zk.get(os.path.join('/reflection', group))
                haproxy_list = json.loads(data).get('haproxy_list', [])
                for haproxy in haproxy_list:
                    if ip in zk.get_children(os.path.join('/serverList', haproxy, app_obj.site.name, app_obj.name, group_name)):
                        haproxy_dict[room_obj.name] = haproxy_dict.get(room_obj.name, [])
                        haproxy_dict[room_obj.name].append(group_name)
        zk.stop()
    return haproxy_dict



