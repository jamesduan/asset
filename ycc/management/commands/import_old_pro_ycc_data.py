# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import time
from util.timelib import stamp2str
from cmdb.models import Site, App
from asset.models import Room
from ycc.models import ConfigGroup, ConfigGroupStatus, ConfigInfo, OldConfigGroup, OldConfigInfo, ConfigEnv

def md5(str):
    import hashlib
    m = hashlib.md5()
    m.update(str)
    return m.hexdigest()

class Command(BaseCommand):
    args = ''
    help = 'auto deploy'

    def handle(self, *args, **options):
        print stamp2str(time.time()) + ':begin'
        olddataids = OldConfigInfo.objects.filter(group_version=0,
                                                status='published',
                                                environment='production')
        oldgroups = OldConfigGroup.objects.exclude(group_id__iendswith='_bj').exclude(group_id__iendswith='_gray')
        #oldgroups = OldConfigGroup.objects..filter(group_id='lss_lss')
        sites = Site.objects.all()
        apps = App.objects.all()
        envs = ConfigEnv.objects.all()
        idcs = Room.objects.all()
        idc = idcs.get(pk=1)


        for g in oldgroups:
            group_id = g.group_id
            idc_ycc_code = g.idc
            pool = g.pool
            if idc_ycc_code == 'SH':
                idc = idcs.get(pk=1)
            elif idc_ycc_code == 'JQ':
                idc = idcs.get(pk=4)
            else:
                continue
            # idcarr = idcs.filter(ycc_code=idc_ycc_code)
            # if idcarr.exists():
            #     for i in idcarr:
            #         if idc_ycc_code == 'SH':
            #             idc = idcs.get(pk=1)
            #             break
            #         else:
            #             idc = i
            dataids = olddataids.filter(group_id=group_id)
            if dataids.exists():
                configinfos = []
                poolarr = pool.split('/')
                site_id = 0
                app_id = 0
                site_name = ''
                app_name = ''
                grouptype = 1
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
                else:
                    grouptype = 2
                current_time = int(time.time())
                if idc_ycc_code == 'JQ' and group_id.endswith('_jq'):
                    group_id = group_id.replace('_jq', '')
                if ConfigGroup.objects.filter(group_id=group_id, idc=idc).exists():
                    configgroup = ConfigGroup.objects.get(group_id=group_id, idc=idc)
                else:
                    configgroup, created = ConfigGroup.objects.get_or_create(group_id=group_id, idc=idc,
                                                                        defaults = {'site_id':site_id, 'site_name':site_name,
                                                                                    'app_id':app_id, 'app_name':app_name,
                                                                                    'type':grouptype, 'old_pool':pool,
                                                                                    'created':current_time,'updated':0, 'status':1})
                # ConfigGroup.objects.create(site_id=site_id, site_name=site_name, app_id=app_id, app_name=app_name,
                #                             group_id=group_id, type=grouptype, old_pool=pool, idc=idc, created=current_time,
                #                             updated=0, status=1)
                # configgroup = ConfigGroup.objects.get(group_id=group_id, idc=idc.id)
                # ConfigGroupStatus.objects.create(group=configgroup, version=0, status=0, pre_version=0)
                # ConfigGroupStatus.objects.create(group=configgroup, version=1, status=4, pre_version=0)
                # configgroupstatus = ConfigGroupStatus.objects.get(group=configgroup, version=1, status=4, pre_version=0)
                configgroupstatus, created = ConfigGroupStatus.objects.get_or_create(group=configgroup, status=0,
                                                                                     defaults = {'version': 0, 'pre_version': 0})
                configgroupstatus, created = ConfigGroupStatus.objects.get_or_create(group=configgroup, status=4,
                                                                                     defaults = {'version': 1, 'pre_version': 0})
                for d in dataids:
                    dataidname = d.data_id
                    content_md5=d.md5
                    newmd5 = md5(d.content)
                    if content_md5 != newmd5:
                        content_md5 = newmd5
                    configinfos.append(ConfigInfo(data_id=dataidname, group_status=configgroupstatus, env_id=7, content=d.content,
                                                    content_md5=content_md5, created_time=current_time, modified_time=0,
                                                    created_by=d.created_by, modified_by='', remark='', file_type=d.file_type,
                                                    cmp=1, config_type=1))
                ConfigInfo.objects.bulk_create(configinfos)
        print stamp2str(time.time()) + ':success'

