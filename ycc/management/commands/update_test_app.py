# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import time
from util.timelib import stamp2str
from cmdb.models import Site, App
from asset.models import Room
from ycc.models import ConfigGroup, ConfigGroupStatus, ConfigInfo, OldConfigGroup, OldConfigInfo, ConfigEnv

class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        print stamp2str(time.time()) + ':begin'

        oldgroups = OldConfigGroup.objects.using('configcentre').exclude(group_id__icontains='_gray')
        newgroups = ConfigGroup.objects.all()
        sites = Site.objects.all()
        apps = App.objects.all()
        idcs = Room.objects.all()

        for g in oldgroups:
            group_id = g.group_id
            idc_ycc_code = g.idc
            pool = g.pool
            idcarr = idcs.filter(ycc_code=idc_ycc_code)
            if idcarr.exists():
                for i in idcarr:
                    if idc_ycc_code == 'SH':
                        idc = idcs.get(pk=1)
                        break
                    else:
                        idc = i
            newgroup = newgroups.filter(group_id=group_id, idc=idc)
            poolarr = pool.split('/')
            site_id = 0
            app_id = 0
            site_name = ''
            app_name = ''
            # grouptype = 1
            if len(poolarr) > 0:
                site_name = poolarr[0]
                siteset = sites.filter(name=site_name)
                if siteset.exists():
                    site_id = siteset[0].id
                if len(poolarr) > 1:
                    app_name = poolarr[1]
                    appset = apps.filter(name=app_name, status=0)
                    if appset.exists():
                        if site_id != 0:
                            appset = appset.filter(site_id=site_id)
                            if appset.exists():
                                app_id = appset[0].id
            # if app_id == 0:
            #     grouptype = 2
            if app_id != 0  and not newgroup.filter(site_id=site_id, site_name=site_name, app_id=app_id, app_name=app_name).exists():
                if newgroup.exists():
                    #print newgroup[0].__dict__
                    #print '11==\n'
                    newgroup.update(site_id=site_id, site_name=site_name, app_id=app_id, app_name=app_name)


        print stamp2str(time.time()) + ':success'

def dump(obj):
    for attr in dir(obj):
        print "obj.%s = %s" % (attr, getattr(obj, attr))