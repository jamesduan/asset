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
        result = 'success'
        resDict = handleImpl()
        if len(resDict) > 0:
            result = 'failure'
            for (item, errortype) in resDict.items():
                print item + ': ' + errortype
        print stamp2str(time.time()) + result

def handleImpl():
    olddataids = OldConfigInfo.objects.filter(group_version=0,
                                                status='published',
                                                environment='production')
    oldgroups = OldConfigGroup.objects.exclude(group_id__iendswith='_bj').exclude(group_id__iendswith='_gray')
    newdataids = ConfigInfo.objects.filter(env=7)
    newgroups = ConfigGroup.objects.all()
    newgroupstatuses = ConfigGroupStatus.objects.filter(status=4)

    oldDatas = getOldConfigInfos(olddataids, oldgroups)
    newDatas = getNewConfigInfos(newdataids, newgroups, newgroupstatuses)
    return cmpConfigInfos(oldDatas, newDatas)


def getOldConfigInfos(olddataids, oldgroups):
    # [idc][group_id][data_id]['content'/'md5']
    resDict = {}
    resDict['SH'] = {}
    resDict['JQ'] = {}
    #resDict['BJ'] = {}
    #resDict['WH'] = {}
    for g in oldgroups:
        group_id = g.group_id
        idc_ycc_code = g.idc
        dataids = olddataids.filter(group_id=group_id)
        if idc_ycc_code == 'JQ' and group_id.endswith('_jq'):
            group_id = group_id.replace('_jq', '')
        if not resDict.has_key(idc_ycc_code):
            continue
        if not resDict[idc_ycc_code].has_key(group_id):
            resDict[idc_ycc_code][group_id] = {}
        for d in dataids:
            data_id = d.data_id
            resDict[idc_ycc_code][group_id][data_id] = {}
            resDict[idc_ycc_code][group_id][data_id]['content'] = d.content
            resDict[idc_ycc_code][group_id][data_id]['md5'] = d.md5
    return resDict

def getNewConfigInfos(newdataids, newgroups, newgroupstatuses):
    # [idc][group_id][data_id]['content'/'md5']
    resDict = {}
    resDict['SH'] = {}
    resDict['JQ'] = {}
    #resDict['BJ'] = {}
    #resDict['WH'] = {}
    for g in newgroups:
        newgroupstatusid = newgroupstatuses.filter(group=g)
        if newgroupstatusid.exists():
            group_id = g.group_id
            idc_ycc_code = g.idc.ycc_code
            if not resDict[idc_ycc_code].has_key(group_id):
                resDict[idc_ycc_code][group_id] = {}
            dataids = newdataids.filter(group_status=newgroupstatusid[0])
            for d in dataids:
                data_id = d.data_id
                resDict[idc_ycc_code][group_id][data_id] = {}
                resDict[idc_ycc_code][group_id][data_id]['content'] = d.content
                resDict[idc_ycc_code][group_id][data_id]['md5'] = d.content_md5
    return resDict


def cmpConfigInfos(oldDatas, newDatas):
    resDict = {}
    for (idc, groupidDict) in oldDatas.items():
        for (groupid, dataidDict) in  groupidDict.items():
            for (dataid, dataDict) in dataidDict.items():
                for (datatype, data) in dataDict.items():
                    if not newDatas.has_key(idc):
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_HAS_NO_IDC'
                    elif not newDatas[idc].has_key(groupid):
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_HAS_NO_GROUPID'
                    elif not newDatas[idc][groupid].has_key(dataid):
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_HAS_NO_DATAID'
                    elif not (newDatas[idc][groupid][dataid].has_key('content') and newDatas[idc][groupid][dataid].has_key('md5')):
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_HAS_NO_CONTENT_MD5'
                    elif newDatas[idc][groupid][dataid]['content'] != oldDatas[idc][groupid][dataid]['content']:
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_OLD_DIFF_CONTENT'
                    elif newDatas[idc][groupid][dataid]['md5'] != oldDatas[idc][groupid][dataid]['md5']:
                        key = (idc, groupid,dataid, datatype)
                        resDict['#'.join(key)] = 'NEW_OLD_DIFF_MD5'
                    else:
                        pass
    return resDict





