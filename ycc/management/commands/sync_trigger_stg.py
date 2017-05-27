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
        print 'begin ' + stamp2str(time.time())
        res = 'Fail'
        setup()
        if tc_add():
            if tc_update():
                if tc_delete():
                    res = 'Success'
        teardown()
        print res + ' ' + stamp2str(time.time())

def setup():
    group_id = 'site_app'
    idc = Room.objects.get(id=1)
    configgroup, created = ConfigGroup.objects.get_or_create(group_id=group_id,
                                                                type=2,
                                                                old_pool=group_id,
                                                                idc=idc,
                                                                created=int(time.time()),
                                                                updated=0,
                                                                status=1)
    configgroupstatus, created = ConfigGroupStatus.objects.get_or_create(group=configgroup,
                                                                         version=0,
                                                                         status=0,
                                                                         pre_version=0)

def teardown():
    group_id = 'site_app'
    idc = Room.objects.get(id=1)
    ConfigGroup.objects.filter(group_id=group_id, idc=idc).delete()

def tc_add():
    dataid_add(100)
    return cmp()

def tc_update():
    group_id = 'site_app'
    olddataids = OldConfigInfo.objects.using('configcentre').filter(group_id=group_id, environment='staging', status='published', group_version=0)
    for od in olddataids:
        content = stamp2str(time.time(),'%Y-%m-%d %H:%M:%S')
        od.content = content
        od.md5= md5(content)
        od.save()
    return cmp()

def tc_delete():
    group_id = 'site_app'
    OldConfigInfo.objects.using('configcentre').filter(group_id=group_id, environment='staging', status='published', group_version=0).delete()
    return cmp()

def dataid_add(olddataidnum):
    group_id = 'site_app'
    for i in range(olddataidnum):
        data_id = 'data_id_%d.properties' %i
        content = stamp2str(time.time() + i * 1000)
        OldConfigInfo.objects.using('configcentre').create(data_id=data_id,
                                                                group_id=group_id,
                                                                content=content,
                                                                md5=md5(content),
                                                                gmt_create=content,
                                                                gmt_modified=content,
                                                                environment='staging',
                                                                gmt_expired=content,
                                                                group_version=0,
                                                                status='published',
                                                                created_by='snyc_trigger_test',
                                                                updated_by='sync_trigger_test',
                                                                remark='',
                                                                file_type='txt',
                                                                release_type=0)
    return cmp()

def cmp():
    res = True
    group_id = 'site_app'
    idc = Room.objects.get(id=1)
    olddataids = OldConfigInfo.objects.using('configcentre').filter(group_id=group_id, environment='staging', status='published', group_version=0)
    configgroup = ConfigGroup.objects.filter(group_id=group_id, idc=idc)
    configgroupstatus = ConfigGroupStatus.objects.filter(group=configgroup, status=0)
    newdataids = ConfigInfo.objects.filter(group_status=configgroupstatus)
    if len(olddataids) != len(newdataids):
        res = False
        print 'len(olddataids) != len(newdataids)'
    else:
        resdict = {}
        resdict['old'] = {}
        resdict['new'] = {}
        for od in olddataids:
            resdict['old'][od.data_id] = {}
            resdict['old'][od.data_id]['content'] = od.content
            resdict['old'][od.data_id]['md5'] = od.md5
        for nd in newdataids:
            resdict['new'][nd.data_id] = {}
            resdict['new'][nd.data_id]['content'] = nd.content
            resdict['new'][nd.data_id]['md5'] = nd.content_md5
        for (oldnew, dataidDict) in resdict.items():
             for (dataid, dataItemDict) in  dataidDict.items():
                 if not resdict['new'].has_key(dataid) or \
                     resdict['new'][dataid]['content'] != dataItemDict['content'] or \
                     resdict['new'][dataid]['md5'] != dataItemDict['md5']:
                     res = False
                     print dataid
    return res


def md5(str):
    import hashlib
    m = hashlib.md5()
    m.update(str)
    return m.hexdigest()
