# -*- coding: gbk -*-
from django.core.management.base import BaseCommand
from asset.models import Room
from cmdb.models import App
import time
import datetime
import urllib2
import urllib
import json
from server.models import ServerStandard
from ycc.models import SoaServiceGroupBind, SoaService, SoaServiceGroup, SoaServiceGroupRegister, SoaEnv, SoaDomain, \
    ExceptionDetailSoaBind


class Command(BaseCommand):
    def handle(self, *args, **options):
        start = time.clock()
        rooms = ['1', '4']

        SoaServiceGroupRegister.objects.all().delete()
        # SoaServiceGroupBind.objects.all().delete()
        # SoaServiceGroup.objects.all().delete()
        # SoaService.objects.all().delete()
        ExceptionDetailSoaBind.objects.all().delete()
        app_insts = App.objects.filter(status=0)
        room_instas = Room.objects.filter(id__in=rooms)
        soa_env_instas = SoaEnv.objects.all()
        soa_service_insert_ids = []
        soa_service_group_insert_ids = []
        soa_service_group_bind_insert_ids = []
        log_bind_not_exist = []
        log_bind_mut = []
        log_reg_not_exist = []
        log_reg_mut = []
        log_service_created = []
        log_group_created = []
        log_bind_created = []
        i = 0
        for ai in get_yield_list(app_insts):
            for room in get_yield_list(room_instas):
                for soa_env in soa_env_instas:
                    try:
                        soa_domain_insta = SoaDomain.objects.get(idc=room.id, env=soa_env.id, status=1)
                        idc_code = get_zk_idc(str(room.id))
                        i += 1
                        pool_name = '%s/%s' % (ai.site.name.strip(), ai.name.strip())
                        url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'getAppInfo',p:{zkClusterId:'1',appCode:'%s'},z:'%s'}" \
                              % (soa_domain_insta.domain, urllib.quote(pool_name), soa_domain_insta.zone_code)
                        info_j = get_url_to_json(url)
                        if info_j:
                            for info in get_yield_list(info_j):
                                if info:
                                    for key_val in get_yield_list_iteritems(info):
                                        if key_val['key'] == 'text':
                                            path = key_val['val'].split('[')[0]
                                            try:
                                                soa_service_inst, created = SoaService.objects.get_or_create(app=ai,
                                                                                                             service_path=path,
                                                                                                             room=room,
                                                                                                             env=soa_env)
                                                if created:
                                                    log_service_created.append(
                                                        'Path created. Detail: %s||%s||%s||%s' % (
                                                        path, room.id, soa_env.id, ai.id))
                                                soa_service_insert_ids.append(soa_service_inst.id)
                                            except SoaService.MultipleObjectsReturned:
                                                continue
                                            detail_url = "http://%s/detector-monitor/ajax.do?rmi={s:'groupService',m:'getGroupsByApp',p:{zkClusterId:'1',app:'%s/hedwig_camps'},z:'%s'}" \
                                                         % (soa_domain_insta.domain, urllib.quote(path),
                                                            soa_domain_insta.zone_code)
                                            detail_info_j = get_url_to_json(detail_url)
                                            if detail_info_j:
                                                for detail_info in get_yield_list(detail_info_j):
                                                    if detail_info:
                                                        for d_key_val in get_yield_list_iteritems(detail_info):
                                                            if d_key_val['key'] == 'text':
                                                                try:
                                                                    soa_service_group_inst, created = SoaServiceGroup.objects.get_or_create(
                                                                        soa_service=soa_service_inst,
                                                                        cname=d_key_val['val'])
                                                                    if created:
                                                                        log_group_created.append(
                                                                            'Group created. Detail: %s||%s||%s||%s||%s' % (
                                                                            path, room.id, soa_env.id, ai.id,
                                                                            soa_service_group_inst.id))
                                                                    soa_service_group_insert_ids.append(
                                                                        soa_service_group_inst.id)
                                                                except SoaServiceGroup.MultipleObjectsReturned:
                                                                    continue
                                                            elif d_key_val['key'] == 'children':
                                                                if d_key_val['val']:
                                                                    for ip_port_s in get_yield_list(d_key_val['val']):
                                                                        if ip_port_s:
                                                                            if ip_port_s['text']:
                                                                                ip_port = ip_port_s.get('text').split(
                                                                                    ':')
                                                                                ip = ip_port.pop(0)
                                                                                port = ip_port.pop()
                                                                                try:
                                                                                    server_inst = ServerStandard.objects.get(
                                                                                        ip=ip,
                                                                                        server_status__id__in=[200,
                                                                                                               210])
                                                                                    try:
                                                                                        soa_service_group_bind_inst, created = SoaServiceGroupBind.objects.get_or_create(
                                                                                            serverstandard=server_inst,
                                                                                            soa_service_group=soa_service_group_inst,
                                                                                            port=port)
                                                                                        if created:
                                                                                            log_bind_created.append(
                                                                                                'Group created. Detail: %s||%s||%s||%s||%s||%s' % (
                                                                                                path, room.id,
                                                                                                soa_env.id, ai.id,
                                                                                                soa_service_group_inst.id,
                                                                                                soa_service_group_bind_inst.id))
                                                                                        soa_service_group_bind_insert_ids.append(
                                                                                            soa_service_group_bind_inst.id)
                                                                                    except SoaServiceGroupBind.MultipleObjectsReturned:
                                                                                        continue
                                                                                except ServerStandard.DoesNotExist:
                                                                                    tmp_msg = 'BIND----IP is not exists: {%s} || %s %s. parm:{%s;%s;%s;%s}' % (
                                                                                        ip, pool_name,
                                                                                        soa_domain_insta.zone_code,
                                                                                        path, '%s:%s' % (ip, port),
                                                                                        soa_service_group_inst.cname,
                                                                                        soa_domain_insta.zone_code)
                                                                                    if tmp_msg not in log_bind_not_exist:
                                                                                        log_bind_not_exist.append(
                                                                                            tmp_msg)
                                                                                except ServerStandard.MultipleObjectsReturned:
                                                                                    tmp_msg = 'BIND----IP is multipleObjectsReturned (Status have 200 and 210): {%s} || %s %s. parm:{%s;%s;%s;%s}' % (
                                                                                        ip, pool_name,
                                                                                        soa_domain_insta.zone_code,
                                                                                        path, '%s:%s' % (ip, port),
                                                                                        soa_service_group_inst.cname,
                                                                                        soa_domain_insta.zone_code)
                                                                                    if tmp_msg not in log_bind_mut:
                                                                                        log_bind_mut.append(tmp_msg)
                                        elif key_val['key'] == 'children':
                                            if key_val['val']:
                                                for reg_info in get_yield_list(key_val['val']):
                                                    if reg_info:
                                                        if reg_info.get('text'):
                                                            ip_port = reg_info.get('text').split(':')
                                                            ip = ip_port.pop(0)
                                                            port = ip_port.pop()
                                                            if ',' in reg_info.get('service_path'):
                                                                reg_path = reg_info.get('service_path').split(',')[
                                                                    0].strip()
                                                            else:
                                                                reg_path = ''
                                                            try:
                                                                server_inst1 = ServerStandard.objects.get(ip=ip,
                                                                                                          server_status__id__in=[
                                                                                                              200, 210])
                                                                soa_service_group_reg_inst = SoaServiceGroupRegister.objects.create(
                                                                    serverstandard=server_inst1,
                                                                    soa_service=soa_service_inst,
                                                                    port=port)
                                                            except ServerStandard.DoesNotExist:
                                                                tmp_msg = 'REG----IP is not exists: {%s} || %s %s. parm:{%s;%s;%s;%s}' % (
                                                                    ip, pool_name,
                                                                    soa_domain_insta.zone_code,
                                                                    reg_path, '%s:%s' % (ip, port),
                                                                    '',
                                                                    soa_domain_insta.zone_code)
                                                                if tmp_msg not in log_reg_not_exist:
                                                                    log_reg_not_exist.append(tmp_msg)
                                                            except ServerStandard.MultipleObjectsReturned:
                                                                tmp_msg = 'REG-----IP is multipleObjectsReturned (Status have 200 and 210): {%s} || %s %s. parm:{%s;%s;%s;%s}' % (
                                                                    ip, pool_name,
                                                                    soa_domain_insta.zone_code,
                                                                    reg_path, '%s:%s' % (ip, port),
                                                                    '',
                                                                    soa_domain_insta.zone_code)
                                                                if tmp_msg not in log_reg_mut:
                                                                    log_reg_mut.append(tmp_msg)
                    except SoaDomain.DoesNotExist:
                        continue
                    except SoaDomain.MultipleObjectsReturned:
                        continue
        if soa_service_insert_ids:
            ss_deletes = SoaService.objects.exclude(id__in=soa_service_insert_ids)
            for ss_deletes_intance in ss_deletes:
                ssg_deletes = SoaServiceGroup.objects.filter(soa_service__id=ss_deletes_intance.id)
                for ssg_deletes_intance in ssg_deletes:
                    ssgb_deletes = SoaServiceGroupBind.objects.filter(
                        soa_service_group__id=ssg_deletes_intance.id).delete()
                ssg_deletes.delete()
            ss_deletes.delete()
        if soa_service_group_insert_ids:
            ssg_deletes = SoaServiceGroup.objects.exclude(id__in=soa_service_group_insert_ids)
            for ssg_deletes_intance in ssg_deletes:
                ssgb_deletes = SoaServiceGroupBind.objects.filter(soa_service_group__id=ssg_deletes_intance.id).delete()
            ssg_deletes.delete()
        if soa_service_group_bind_insert_ids:
            ssgb_deletes = SoaServiceGroupBind.objects.exclude(id__in=soa_service_group_bind_insert_ids).delete()
        # print '-------------------------------------------------------------------------------------'
        log_list = {}
        if log_bind_not_exist:
            for log in log_bind_not_exist:
                # print '%s: %s' % (log_bind_not_exist.index(log) + 1, log)
                if not log_list.get('1'):
                    log_list['1'] = []
                log_list['1'].append(log)
        # print '-------------------------------------------------------------------------------------'
        if log_reg_not_exist:
            for log in log_reg_not_exist:
                # print '%s: %s' % (log_reg_not_exist.index(log) + 1, log)
                if not log_list.get('3'):
                    log_list['3'] = []
                log_list['3'].append(log)
        # print '-------------------------------------------------------------------------------------'
        if log_bind_mut:
            for log in log_bind_mut:
                # print '%s: %s' % (log_bind_mut.index(log) + 1, log)
                if not log_list.get('2'):
                    log_list['2'] = []
                log_list['2'].append(log)
        # print '-------------------------------------------------------------------------------------'
        if log_reg_mut:
            for log in log_reg_mut:
                # print '%s: %s' % (log_reg_mut.index(log) + 1, log)
                if not log_list.get('4'):
                    log_list['4'] = []
                log_list['4'].append(log)
        if log_list:
            for key, logs in log_list.iteritems():
                for log in logs:
                    parm = log.split('||', 1)[1].split('{', 1)[1].split('}', 1)[0]
                    parms = parm.split(';')
                    ExceptionDetailSoaBind.objects.create(
                        type=int(key), content=parms[1].split(':')[0],
                        time=int(time.time()),
                        path=parms[0],
                        port=parms[1].split(':')[1],
                        group=parms[2],
                        zone=parms[3]
                    )
        now = datetime.datetime.now()
        format_time = '%s-%s-%s %s:%s:%s' % (now.year, now.month, now.day, now.hour, now.minute, now.second)
        print '=========================%s:success=========================' % format_time
        end = time.clock()
        print("The function run time is : %.03f seconds" % (end - start))


def get_url_to_json(url):
    try:
        data = urllib2.urlopen(url)
        return json.loads(data.read())
    except urllib2.HTTPError as e:
        print '%s\nPlease check url. ' % e
        print url
        return False
    except Exception as e:
        print url
        print e
        print 'Other error.'
        return False


def get_zk_idc(idc_id):
    zone = ''
    if idc_id == '1':
        zone = 'ZONE_NH'
    elif idc_id == '4':
        zone = 'ZONE_JQ'
    return zone


def get_yield_list_iteritems(list_iteritems):
    for key, val in list_iteritems.iteritems():
        yield {
            'key': key,
            'val': val
        }


def get_yield_list(li):
    for l in li:
        yield l
