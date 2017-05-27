# -*- coding: gbk -*-
from django.core.management.base import BaseCommand
import urllib
import urllib2
import json
from cmdb.models import Site, App
from django.db import models
from asset.models import Room, Asset, Rack
from server.models import ServerGroup, ServerStandard
import sys
import datetime


class ServerGroupBind(models.Model):
    id = models.IntegerField(primary_key=True)
    serverstandard_id = models.IntegerField()
    servergroup_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'server_group_bind'


error_msg = 'Example: python manage-api.py zk_get_hedwig_group_new {num1} {num2}\n' \
            'num1: input IDC. Please input "sh" or "jq".\n' \
            'num2: input IS_DELETE. "0" or "1".\n' \
            '      * IS_DELETE 0: Table server_group_bind will not be delete.\n' \
            '      * IS_DELETE 1: Table server_group_bind will be delete.\n' \
            '      * IS_DELETE 2: Table server_group_bind and server_group will be delete.'


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not args:
            print error_msg
            sys.exit()
        else:
            try:
                if len(args) > 2:
                    print error_msg
                    sys.exit()
                IDC = args[0]
                # 'sh': '南汇', 'jq': '金桥'
                if IDC not in ('sh', 'jq',):
                    print error_msg
                    sys.exit()
                if IDC == 'sh':
                    domain = 'oms.yihaodian.com.cn'
                    room = 1
                elif IDC == 'jq':
                    domain = 'detector-jq.yihaodian.com.cn'
                    room = 4
                else:
                    print error_msg
                    sys.exit()
                IS_DELETE = args[1]
                if IS_DELETE not in ('0', '1', '2'):
                    print error_msg
                    sys.exit()
            except IndexError as e:
                print error_msg
                sys.exit()

        if IS_DELETE == '1':
            ServerGroupBind.objects.all().delete()
        elif IS_DELETE == '2':
            ServerGroup.objects.all().delete()
            ServerGroupBind.objects.all().delete()

        url = 'http://%s/detector-monitor/open.do?api={"s":"monitorService",' \
              '"m":"getAllGroupsByZone","p":{"zone":"%s"}}' % (domain, 1)
        info_j = get_url_to_json(url)
        if info_j:
            if '-1' in info_j.keys():
                print 'API return -1'
                push_error(domain, 'API_return_-1', 0)
            else:
                for site_app in get_yield_list_iteritems(info_j):
                    for status in get_yield_list_iteritems(site_app.get('val')):
                        if '/' not in site_app.get('key'):
                            print '%s : have\'t "/"' % site_app.get('key')
                            continue
                        site_app_list = site_app.get('key').split('/', 1)
                        site_name = site_app_list.pop(0).strip()
                        app_name = site_app_list[0].strip()
                        try:
                            site = Site.objects.get(name=site_name)
                        except Site.DoesNotExist:
                            print '%s : Site DoesNotExist.' % site_app.get('key')
                            continue
                        try:
                            app = App.objects.get(site_id=site.id, name=app_name, status=0)
                        except App.DoesNotExist:
                            print '%s : App DoesNotExist.' % site_app.get('key')
                            continue
                        except App.MultipleObjectsReturned:
                            print '%s : App MultipleObjectsReturned.' % site_app.get('key')
                            continue
                        for groups in get_yield_list(status.get('val')):
                            try:
                                if groups.get('name'):
                                    server_group, created = ServerGroup.objects.get_or_create(app_id=app.id,
                                                                                              cname=groups.get('name'),
                                                                                              room=Room.objects.get(
                                                                                                  id=room)
                                                                                              )
                                else:
                                    print '%s : Group_name is none.' % site_app.get('key')
                                    continue
                                if groups.get('children'):
                                    ips_list = []
                                    ss_list = []
                                    for ips in get_yield_list(groups.get('children')):
                                        if ips.get('name'):
                                            if ':' not in ips.get('name'):
                                                print '%s : Ips_name have\'t \':\'.' % site_app.get('key')
                                                continue
                                            ip = ips.get('name').split(':', 1)[0]
                                            ips_list.append(ip)
                                        else:
                                            print '%s : groups_children is none.' % site_app.get('key')
                                            continue
                                    server_standard = ServerStandard.objects.filter(ip__in=ips_list)
                                    if server_standard:
                                        for ss in get_yield_list(server_standard):
                                            ServerGroupBind.objects.create(serverstandard_id=ss.id,
                                                                           servergroup_id=server_group.id)
                                            ss_list.append(ss.ip.strip())
                                    else:
                                        print '%s : Server_standard in none. Detail: group:%s || IP=%s' % (
                                            site_app.get('key'), groups.get('name'), ip)
                                        continue
                                    if ips.get('children'):
                                        print '%s : IPS have\'t children.' % site_app.get('key')
                                        continue
                                    for il in get_yield_list(ips_list):
                                        if il not in ss_list:
                                            print '%s : IP not in Server. Detail: group:%s || IP=%s' % (
                                                site_app.get('key'), groups.get('name'), il)
                            except KeyError as e:
                                print '%s : Keyerror %s.' % (site_app.get('key'), e)
                                continue
                            except Exception as e:
                                print '%s : Exception: %s.' % (site_app.get('key'), e)
                                continue
                push_error(domain, 'API_return_-1', 1)
        else:
            print 'API have\'t data.'
        now = datetime.datetime.now()
        format_time = '%s-%s-%s %s:%s:%s' % (now.year, now.month, now.day, now.hour, now.minute, now.second)
        print '=========================%s:success=========================' % format_time


def get_url_to_json(url):
    try:
        data = urllib2.urlopen(url)
        return json.loads(data.read())
    except urllib2.HTTPError as e:
        print '%s\nPlease check url. ' % e
        return False
    except Exception as e:
        print e
        print 'Other error.'
        return False


def get_yield_list_iteritems(list_iteritems):
    for key, val in list_iteritems.iteritems():
        yield {
            'key': key,
            'val': val
        }


def get_yield_list(li):
    for l in li:
        yield l


def push_error(domian, error_key, value):
    error_url = 'http://%s/itil/api/?action=business&method=pushData&pool=%s&key=%s&value=%s' \
                % (urllib.quote(domian), 'yihaodian/LeDao-biz', urllib.quote(error_key), value)
    get_url_to_json(error_url)
    return True
