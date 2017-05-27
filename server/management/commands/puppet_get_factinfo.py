# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from assetv2.settingsapi import FACTER_API
from server.models import Server, ServerDetail
from util.timelib import stamp2str, str2stamp
from django.db import connection
import urllib2, time
import json
import yaml

class Command(BaseCommand):
    args = ''
    help = 'get server detail from puppet and update server table'

    def handle(self, *args, **options):
        apis = FACTER_API
        for api in apis:
            list_str = self.get_api(api['FACT_SEARCH'])
            if list_str:
                list = yaml.load(list_str)
                for item in list:
                    try:
                        server = Server.objects.exclude(server_status_id=400).get(ip=item)
                        server.is_puppet_control = 1
                        server.save()
                    except ObjectDoesNotExist:
                        print "ip can not found:" + item
                        server = None
                    if server:
                        uri = api['FACT_DETAIL'] + item
                        detail_str = self.get_api(uri)
                        if detail_str:
                            list = detail_str.split('\n')
                            detail = []
                            for line in list:
                                if line.strip()[0:1] != '!' and line.strip()[0:5] != '--- !':
                                    detail.append(line)
                            detail = yaml.load(('\n').join(detail))
                            self.save_data(server.id, detail)
                        else:
                            print "puppet can not found:" + item
                    connection.close()

    def get_api(self, uri, format_data="yaml"):
        request = urllib2.Request(uri)
        request.add_header("Accept", format_data)
        try:
            fp = urllib2.urlopen(request)
            response = fp.read()
        except urllib2.HTTPError, e:
            print('error:%s' % str(e))
            response = None
        except urllib2.URLError, e:
            print('error:%s' % str(e))
            response = None

        return response

    def save_data(self, server_id, ori_str):
        data = ori_str['values']
        processorinfo = self.format_process(data)
        nicinfo = self.format_nic_info(data)
        try:
            fact_date = stamp2str(str2stamp(data.get('last_run'),'%a %b %d %H:%M:%S %Z %Y'))
        except ValueError, e:
            print('data format error(server_id=%s):%s' % (str(server_id), data.get('last_run')))
            return
        serverdetail, created = ServerDetail.objects.get_or_create(server_id=server_id,
                                                                   defaults={
                                                                       'architecture' : data.get('architecture'),
                                                                       'boardmanufacturer' : data.get('boardmanufacturer'),
                                                                       'boardserialnumber' : data.get('boardserialnumber'),
                                                                       'facterversion' : data.get('facterversion'),
                                                                       'hardwareisa' : data.get('hardwareisa'),
                                                                       'hostname' : data.get('hostname'),
                                                                       'ipaddress' : data.get('ipaddress'),
                                                                       'nicinfo' : nicinfo,
                                                                       'is_virtual' : data.get('is_virtual'),
                                                                       'kernelrelease' : data.get('kernelrelease'),
                                                                       'kernelversion' : data.get('kernelversion'),
                                                                       'fact_date' : fact_date,
                                                                       'lsbdistdescription' : data.get('lsbdistdescription'),
                                                                       'lsbmajdistrelease' : data.get('lsbmajdistrelease'),
                                                                       'lsbdistid' : data.get('lsbdistid'),
                                                                       'lsbdistrelease' : data.get('lsbdistrelease'),
                                                                       'manufacturer' : data.get('manufacturer'),
                                                                       'memorysize' : data.get('memorysize'),
                                                                       'operatingsystem' : data.get('operatingsystem'),
                                                                       'physicalprocessorcount' : data.get('physicalprocessorcount'),
                                                                       'processorcount' : data.get('processorcount'),
                                                                       'processorinfo' : processorinfo,
                                                                       'productname' : data.get('productname'),
                                                                       'puppetversion' : data.get('puppetversion'),
                                                                       'rubyversion' : data.get('rubyversion'),
                                                                       'serialnumber' : data.get('serialnumber'),
                                                                       'swapsize' : data.get('swapsize'),
                                                                       'timezone' : data.get('timezone'),
                                                                       'uptime' : data.get('uptime'),
                                                                       'created' : stamp2str(time.time()),
                                                                       'updated' : stamp2str(time.time()),
                                                                       'macaddress' : data.get('macaddress'),
                                                                       'netmask' : data.get('netmask'),
                                                                       'pythonversion': data.get('yhd_pythonversion'),
                                                                   })
        if not created:
            serverdetail.updated = stamp2str(time.time())
            serverdetail.architecture = data.get('architecture')
            serverdetail.boardmanufacturer = data.get('boardmanufacturer')
            serverdetail.boardserialnumber = data.get('boardserialnumber')
            serverdetail.facterversion = data.get('facterversion')
            serverdetail.hardwareisa = data.get('hardwareisa')
            serverdetail.hostname = data.get('hostname')
            serverdetail.ipaddress = data.get('ipaddress')
            serverdetail.nicinfo = nicinfo
            serverdetail.is_virtual = data.get('is_virtual')
            serverdetail.kernelrelease = data.get('kernelrelease')
            serverdetail.kernelversion = data.get('kernelversion')
            serverdetail.fact_date = fact_date
            serverdetail.lsbdistdescription = data.get('lsbdistdescription')
            serverdetail.lsbmajdistrelease = data.get('lsbmajdistrelease')
            serverdetail.lsbdistid = data.get('lsbdistid')
            serverdetail.lsbdistrelease = data.get('lsbdistrelease')
            serverdetail.manufacturer = data.get('manufacturer')
            serverdetail.memorysize = data.get('memorysize')
            serverdetail.operatingsystem = data.get('operatingsystem')
            serverdetail.physicalprocessorcount = data.get('physicalprocessorcount')
            serverdetail.processorcount = data.get('processorcount')
            serverdetail.processorinfo = processorinfo
            serverdetail.productname = data.get('productname')
            serverdetail.puppetversion = data.get('puppetversion')
            serverdetail.rubyversion = data.get('rubyversion')
            serverdetail.serialnumber = data.get('serialnumber')
            serverdetail.swapsize = data.get('swapsize')
            serverdetail.timezone = data.get('timezone')
            serverdetail.uptime = data.get('uptime')
            serverdetail.created = data.get('created')
            serverdetail.macaddress = data.get('macaddress')
            serverdetail.netmask = data.get('netmask')
            serverdetail.pythonversion = data.get('yhd_pythonversion')
            serverdetail.save()

    def format_process(self, data):
        ret = {}
        count = data.get("processorcount")
        for i in range(int(count)):
            key = "processor%d" % (i)
            ret[key] = data.get(key)
        return json.dumps(ret)

    def format_fact_date(self, input):
        if input != "":
            return stamp2str(input, '%Y-%m-%d %H:%M:%S')
        else:
            return time.time().strftime('%Y-%m-%d %H:%M:%S')

    def format_nic_info(self,data):
        ret = {}
        interfs = data.get("interfaces")
        inter_arr = interfs.split(',')
        for eachname in inter_arr:
            ip_key = "ipaddress_"+eachname
            ret[ip_key] = data.get(ip_key)
            mac_key = "macaddress_"+eachname
            ret[mac_key] = data.get(mac_key)
            net_mask = "netmask_"+eachname
            ret[net_mask] = data.get(net_mask)
            net_work = "network_"+eachname
            ret[net_work] = data.get(net_work)
        return json.dumps(ret)