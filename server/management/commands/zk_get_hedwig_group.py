# -*- coding: utf-8 -*-
'''
    @description:

    @copyright:     ©2013 yihaodian.com
    @author:        jackie
    @since:         15-03-24
    @version:       1.0
    @author:        jackie
'''
from django.core.management.base import BaseCommand
from util.timelib import *
from kazoo.client import KazooClient, KazooState, KeeperState
from assetv2.settingsapi import IDC
from cmdb.models import Site, App
from asset.models import Room, Asset, Rack
from server.models import ServerGroup, ServerStandard
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class ServerGroupBind(models.Model):
    id = models.IntegerField(primary_key=True)
    serverstandard_id = models.IntegerField()
    servergroup_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'server_group_bind'


class Command(BaseCommand):
    args = ''
    help = 'zk listen'

    def handle(self, *args, **options):
        idc_name = args[0]
        is_need_delete = args[1]
        if is_need_delete == "1":
            ServerGroupBind.objects.all().delete()
        room = Room.objects.get(name=idc_name)
        zk = KazooClient(hosts=room.zk_cluster)
        zk.start()
        children = zk.get_children("/AppPathDict")
        for item in children:
            path_tmp = item.split(":")[0].replace("#", "/")
            pool = item.split(":")[1]
            info = pool.split("#")
            # if len(info) == 1:
            #     info = pool.split("_")
            if len(info) <= 1:
                print("Error info: %s" % item)
                continue
            site_name = info[0]
            app_name = info[1]
            path = path_tmp + "/hedwig_camps"
            roll_path = path_tmp + "/hedwig_roll"
            try:
                site = Site.objects.get(name=site_name)
            except Site.DoesNotExist:
                print("Error site_name: %s not exists: item %s" % (site_name, item))
                continue
            try:
                app = App.objects.get(site_id=site.id, name=app_name, status=0)
            except App.DoesNotExist:
                print("Error app_name: %s not exists: item %s" % (app_name, item))
                continue
            except App.MultipleObjectsReturned:
                print("Muti app_name: %s " % app_name)
                continue

            if zk.exists(roll_path):
                if zk.exists(path):
                    chd = zk.get_children(path)
                    chd_roll = zk.get_children(roll_path)
                    format_ips = [x[0:x.find(":")] for x in chd_roll]
                    for item_group in chd:
                        group, created = ServerGroup.objects.get_or_create(app_id=app.id, cname=item_group, room_id=room.id)
                        # if item_group == "refugee":
                        #     server = ServerStandard.objects.filter(app_id=app.id).filter(ip__in=format_ips)
                        # else:
                        #     path_server = path + "/" + item_group
                        #     if zk.exists(path_server):
                        #         chdr = zk.get_children(path_server)
                        #
                        #         if len(chdr) >= 1:
                        #             format_ips_bf = [x[0:x.find(":")] for x in chdr]
                        #             return_ips = []
                        #             for item_ip in format_ips_bf:
                        #                 try:
                        #                     a = format_ips.index(item_ip)
                        #                     return_ips.append(item_ip)
                        #                 except ValueError:
                        #                     pass
                        #
                        #             server = ServerStandard.objects.filter(ip__in=return_ips)
                        #         else:
                        #             #print("Error group children: %s not exists" % path_server)
                        #             continue
                        #     else:
                        #         #print("Error group path: %s" % path_server)
                        #         continue
                        path_server = path + "/" + item_group
                        if zk.exists(path_server):
                            chdr = zk.get_children(path_server)

                            if len(chdr) >= 1:
                                format_ips_bf = [x[0:x.find(":")] for x in chdr]
                                return_ips = []
                                for item_ip in format_ips_bf:
                                    try:
                                        a = format_ips.index(item_ip)
                                        return_ips.append(item_ip)
                                    except ValueError:
                                        pass

                                server = ServerStandard.objects.filter(ip__in=return_ips)
                            else:
                                #print("Error group children: %s not exists" % path_server)
                                continue
                        else:
                            #print("Error group path: %s" % path_server)
                            continue
                        for item_server in server:
                            item_server.groups.add(group)
                else:
                    print("Error hedwig_camps path: %s path not exists" % path)
                    pass
            else:
                #print("Error hedwig_roll path: %s path not exists" % roll_path)
                pass

        zk.stop()

        print stamp2str(time.time()) + ':success'

