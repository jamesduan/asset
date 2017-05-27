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
        #tc_only_add()
        tc_only_update()
        #tc_noGS_noSync()

def tc_only_add():
    setup()
    if testImpl():
        print 'tc_only_add success'
    teardown()

def tc_only_update():
    print 'begin ' + stamp2str(time.time())
    setup()
    testImpl()
    teardownOld()
    setup()
    if testImpl():
        print 'tc_only_update success' + stamp2str(time.time())
    teardown()
    print 'end ' + stamp2str(time.time())

def tc_noGS_noSync():
    setupOld(100)
    if testImpl():
        print 'tc_noGS_noSync success'
    teardownOld()

# need to modify trigger sql: such as delete rows from a table not exist
def tc_triggerFail_updateRollback():
    tc_only_add()

def setup():
    setupNew()
    setupOld(100)

def setupNew():
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
    configgroupstatus, created = ConfigGroupStatus.objects.get_or_create(group=configgroup,
                                                                         version=1,
                                                                         status=4,
                                                                         pre_version=0)

def setupOld(olddataidnum):
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
                                                                environment='production',
                                                                gmt_expired=content,
                                                                group_version=0,
                                                                status='approved',
                                                                created_by='snyc_trigger_test',
                                                                updated_by='sync_trigger_test',
                                                                remark='',
                                                                file_type='txt',
                                                                release_type=0)
def teardown():
    teardownOld()
    teardownNew()

def teardownOld():
    group_id = 'site_app'
    OldConfigInfo.objects.using('configcentre').filter(group_id=group_id).delete()

def teardownNew():
    group_id = 'site_app'
    idc = Room.objects.get(id=1)
    ConfigGroup.objects.filter(group_id=group_id, idc=idc).delete()


def testImpl():
    print 'testImpl begin ' + stamp2str(time.time())
    group_id = 'site_app'
    olddataids = OldConfigInfo.objects.using('configcentre').filter(group_id=group_id,
                                                                        group_version=0,
                                                                        status='approved',
                                                                        environment='production')
    dataiddict = {}
    dataiddict['old'] = {}
    dataiddict['new'] = {}
    newdataids = ConfigInfo.objects.filter(group_status__group__group_id=group_id,
                                           group_status__status=4,
                                           env=7)
    for nd in newdataids:
        dataiddict['new'][nd.data_id] = {}
        dataiddict['new'][nd.data_id]['old_content'] = nd.content
        dataiddict['new'][nd.data_id]['old_md5'] = nd.content_md5
    for od in olddataids:
        dataiddict['old'][od.data_id] = {}
        dataiddict['old'][od.data_id]['old_content'] = od.content
        dataiddict['old'][od.data_id]['old_md5'] = od.md5
        content = stamp2str(time.time(),'%Y-%m-%d %H:%M:%S')
        od.content = content
        od.md5= md5(content)
        od.status = 'approved'
        od.save()
        dataiddict['old'][od.data_id]['new_content'] = od.content
        dataiddict['old'][od.data_id]['new_md5'] = od.md5
    olddataids.update(status='published')

    newdataids = ConfigInfo.objects.filter(group_status__group__group_id=group_id,
                                           group_status__status=4,
                                           env=7)
    for nd in newdataids:
        if not dataiddict['new'].has_key(nd.data_id):
            dataiddict['new'][nd.data_id] = {}
        dataiddict['new'][nd.data_id]['new_content'] = nd.content
        dataiddict['new'][nd.data_id]['new_md5'] = nd.content_md5
    same = True
    odlen = len(olddataids)
    if odlen == len(newdataids) or odlen == 0:
        for i in range(odlen):
            if olddataids[i].content != newdataids[i].content or olddataids[i].content_md5 != newdataids[i].content_md5:
                same = False
                print olddataids.data_id + '...fails'
    else:
        same = False
        print 'data_id Num diffs:' + odlen + ':' + len(newdataids) +  '...fails'
    #print stamp2str(time.time()) +  str(dataiddict) + '\n\n'
    return same


def md5(str):
    import hashlib
    m = hashlib.md5()
    m.update(str)
    return m.hexdigest()
