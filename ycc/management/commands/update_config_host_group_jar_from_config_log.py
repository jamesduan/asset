# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
import time
from util.timelib import stamp2str
from server.models import Server
from ycc.models import ConfigLog, ConfigHost, ConfigGroup, ConfigDependGroup, ConfigJar, ConfigJarVersion, ConfigHostJarVersion
from cmdb.models import App, Site
import json, re
import datetime
from django.db.models import Max


class Command(BaseCommand):
    args = ''
    help = 'update table config_host,config_depend_group from config_log'

    def handle(self, *args, **options):
        count_suc = fail1 = fail2 = fail3 = fail4 = fail5 = fail6 = fail7 = 0
        curent_date = stamp2str(time.time()-3600*24, formt='%Y-%m-%d 00:00:00')
        next_date = stamp2str(time.time(), formt='%Y-%m-%d 00:00:00')

        print stamp2str(time.time()) + ':start'

        raw_sql = "select * from config_log where log_time>='%s' and log_time<'%s' and log_type='%s' " \
                  "group by log_operator" % (curent_date, next_date, 'client_metainfo_production')

        queryset = list(ConfigLog.objects.raw(raw_sql))
        count = len(queryset)

        print stamp2str(time.time()) + ':sync %d records' % count

        for q in queryset:
            try:
                server = Server.objects.exclude(server_status_id=400).get(ip=q.log_operator)
            except Server.DoesNotExist:
                fail1 +=1
                print stamp2str(time.time()) + ':%s has no Server object' % q.log_operator
                continue
            except Server.MultipleObjectsReturned:
                fail2 +=1
                print stamp2str(time.time()) + ':%s has muti Server object' % q.log_operator
                continue

            if q.log_level[-3:] == '_jq':
                idc = 4
                groupid = q.log_level[:-3]
            else:
                idc = 1
                groupid = q.log_level
            try:
                main_group = ConfigGroup.objects.get(group_id=groupid, idc=idc)
            except ConfigGroup.DoesNotExist:
                print stamp2str(time.time()) + ':%s has no group object' % q.log_operator
            except ConfigGroup.MultipleObjectsReturned:
                print stamp2str(time.time()) + ':%s has muti group object' % q.log_operator
            detail = json.loads(q.log_detail)

            tmp_appcode = detail['appCode'].split("/")
            if len(tmp_appcode) > 1:
                tmp_site = tmp_appcode[0]
                tmp_pool = tmp_appcode[1]
                try:
                    site = Site.objects.get(name=tmp_site)
                except Site.DoesNotExist:
                    print stamp2str(time.time()) + ':%s has wrong poolid(site:%s)' % (q.id, tmp_site)
                    ori_validated_pool_name = ''
                else:
                    try:
                        app = App.objects.get(site_id=site.id, name=tmp_pool, status=0)
                    except App.DoesNotExist:
                        print stamp2str(time.time()) + ':%s has wrong poolid(app:%s)' % (q.id, tmp_pool)
                        ori_validated_pool_name = ''
                    except App.MultipleObjectsReturned:
                        print stamp2str(time.time()) + ':%s has wrong poolid(muti app:%s)' % (q.id, tmp_pool)
                        ori_validated_pool_name = ''
                    else:
                        ori_validated_pool_name = detail['appCode']
            else:
                ori_validated_pool_name = ''


            config_host, created = ConfigHost.objects.get_or_create(server_id=server.id, ori_main_group_id=q.log_level,
                                                                    defaults={
                'ori_pool_name':        detail['appCode'],
                'ori_validated_pool_name': ori_validated_pool_name,
                'pool_name':            server.app.site.name + '/' + server.app.name if server.app and server.app.site else '',
                'main_group_id':        main_group.id if main_group else 0,
                'create_time':          int(time.time())

            })
            if not created:
                config_host.ori_pool_name = detail['appCode']
                config_host.pool_name = server.app.site.name + '/' + server.app.name if server.app and server.app.site else ''
                config_host.main_group_id = main_group.id if main_group else 0
                config_host.ori_validated_pool_name = ori_validated_pool_name
                config_host.create_time = int(time.time())
                config_host.save()
            count_suc += 1

            for d in detail['list']:
                if d['resource'] == 'MANIFEST.MF':
                    if d['detailState']:
                        content = re.findall(r'Class-Path: (.*) Specification-Vendor', d['memo'].encode('utf-8'))
                        if not content:
                            content = re.findall(r'Class-Path: (.*)  Name: Build Information', d['memo'].encode('utf-8'))
                            if not content:
                                print stamp2str(time.time()) + 'wrong jar data structure:host=' + q.log_operator
                                continue
                        if content:
                            all_jar = re.findall(r'.*?\.jar', content[0].strip().encode('utf-8'))
                            for j in all_jar:
                                config_jar = re.findall(r'(.*?)([-_])([0-9])(.*)', j.strip())
                                if not config_jar:
                                    config_jar = re.findall(r'(.*?)(-[vbrs])([0-9])(.*)', j.strip())
                                    if not config_jar:
                                        print(u'failure:host=' + q.log_operator  + u' and config_main_group=' + q.log_level + u'的jar包' + j + u'版本名不符合规则！')
                                        continue
                                #同步config_jar表
                                jar, created = ConfigJar.objects.get_or_create(config_jar = config_jar[0][0])
                                #同步config_jar_version表
                                jar_version, vcreated = ConfigJarVersion.objects.get_or_create(config_jar_id = jar.id,
                                                                                               config_jar_version = j.strip(),
                                                                                               defaults={'create_time':int(time.time())})
                                if not vcreated:
                                    jar_version.create_time = int(time.time())
                                    jar_version.save()
                                #同步config_host_jar_version表
                                host_jar_version, hcreated = ConfigHostJarVersion.objects.get_or_create(config_host_id = config_host.id,
                                                                                                        config_jar_version_id = jar_version.id,
                                                                                                        defaults={'create_time':int(time.time())})
                                if not hcreated:
                                    host_jar_version.create_time = int(time.time())
                                    host_jar_version.save()


            # for d in detail['list']:
            #     if d['resource'] == 'CONFIG_GROUPS':
            #         if d['detailState']:
            #             #同步config_depend_group表
            #             dgroup = d['memo'].encode('utf-8')[1:-1].split(',')
            #             for dg in dgroup:
            #                 dg = dg.strip()
            #                 if dg[-3:] == '_jq':
            #                     didc = 4
            #                     dgroupid = dg[:-3]
            #                 else:
            #                     didc = 1
            #                     dgroupid = dg
            #                 try:
            #                     depend_group = ConfigGroup.objects.get(group_id=dgroupid, idc=didc)
            #                 except ConfigGroup.DoesNotExist:
            #                     print "failure: config_log's id: %d has no depend group object" % q.id
            #                     continue
            #                 except ConfigGroup.MultipleObjectsReturned:
            #                     print "failure: config_log's id: %d has muti depend group object" % q.id
            #                     continue
            #
            #                 host_dgroup, dcreated = ConfigDependGroup.objects.get_or_create(config_host_id = config_host.id, ori_depend_group_id = dg, defaults={
            #                     'depend_group_id':        depend_group.id if depend_group else 0
            #                 })
            #                 if not dcreated:
            #                     host_dgroup.depend_group_id = depend_group.id if depend_group else 0
            #                     host_dgroup.save()
            #         else:
            #             print(u'failure:server' + q.log_operator  + u'的detailState（CONFIG_GROUPS）不存在！')
            #     elif d['resource'] == 'MANIFEST.MF':
            #         if d['detailState']:
            #             content = re.findall(r'Class-Path: (.*) Specification-Vendor', d['memo'].encode('utf-8'))
            #             if not content:
            #                 content = re.findall(r'Class-Path: (.*)  Name: Build Information', d['memo'].encode('utf-8'))
            #                 if not content:
            #                     print(u'failure:host=' + q.log_operator  + u' and config_main_group=' + q.log_level + u'的jar包外层匹配错误！')
            #                     continue
            #             if content:
            #                 all_jar = re.findall(r'.*?\.jar', content[0].strip().encode('utf-8'))
            #                 for j in all_jar:
            #                     config_jar = re.findall(r'(.*?)([-_])([0-9])(.*)', j.strip())
            #                     if not config_jar:
            #                         config_jar = re.findall(r'(.*?)(-[vbrs])([0-9])(.*)', j.strip())
            #                         if not config_jar:
            #                             print(u'failure:host=' + q.log_operator  + u' and config_main_group=' + q.log_level + u'的jar包' + j + u'版本名不符合规则！')
            #                             continue
            #                     #同步config_jar表
            #                     jar, created = ConfigJar.objects.get_or_create(config_jar = config_jar[0][0])
            #                     #同步config_jar_version表
            #                     jar_version, vcreated = ConfigJarVersion.objects.get_or_create(config_jar_id = jar.id,
            #                                                                                    config_jar_version = j.strip())
            #                     if not vcreated:
            #                         jar_version.config_jar_id = jar.id
            #                         jar_version.save()
            #                     #同步config_host_jar_version表
            #                     host_jar_version, hcreated = ConfigHostJarVersion.objects.get_or_create(config_host_id = config_host.id, config_jar_version_id = jar_version.id)
            #         else:
            #             print(u'failure:server' + q.log_operator  + u'的detailState（MANIFEST.MF）不存在！')
            #     else:
            #         print "log id: %d has no config_groups or manifest.mf" % (q.id, )

        print stamp2str(time.time()) + ':finished. success %d, error %d' % (count_suc, fail1+fail2)