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
from server.models import ServerGroup, Server
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        server = Server.objects.exclude(server_status_id=400)
        for item in server:
            try:
                if item.server_type_id == 1:
                    asset = Asset.objects.get(assetid=item.assetid)
                else:
                    asset = Asset.objects.get(assetid=item.parent)
                rack_name = asset.rack.real_name
                item.rack_id = asset.rack_id
                if rack_name:
                    try:
                        item.rack_id = Rack.objects.get(name=rack_name, room_id=asset.rack.room_id).id
                    except Rack.DoesNotExist:
                        item.rack_id = asset.rack_id
                item.save()
            except Asset.DoesNotExist:
                print item.assetid
            if item.server_type_id == 0:
                try:
                    parent_server = Server.objects.exclude(server_status_id=400).get(assetid=item.parent)
                    item.parent_ip = parent_server.ip
                    item.save()
                except Server.DoesNotExist:
                    print item.ip

        print stamp2str(time.time()) + ':success'

