# -*- coding: utf-8 -*-
from assetv2.settingsapi import *
from deploy.utils.DeployError import DeployError
from deploy.models import *
from asset.models import Room
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from util.timelib import stamp2str
import random
import time


class CreateDeploy():
    def __init__(self, item_list):
        self.item_list = item_list

    def get_deploy_list(self):
        deploy_list = []
        for item in self.item_list:
            if item['pubtype'] == 1:
                try:
                    depid = self.create_publish4trident(
                        item.get('uid', 523),
                        item['app_id'],
                        item['packtype'],
                        item['deptype'],
                        item['restart'],
                        item['comment'],
                        item['jiraid'],
                        item['ftpath'],
                        item['publishDateTimeFrom'],
                        item['publishDateTimeTo'],
                        item.get('srcs', ''),
                        item.get('dets', ''),
                        item.get('grayDeployFlag', 0),
                        item.get('grayDetailInfo', dict()),
                        item.get('idc', '1'),
                        item.get('publishTimeType', 0),
                        item.get('restartInterval', 0 if time.localtime(item['publishDateTimeFrom']/1000).tm_hour ==2 else DEPLOY_INTERVAL)
                    )
                    deploy_list.append({
                            'depid': depid,
                            'taskid': item['taskid'],
                            'app_id': item['app_id'],
                            'pubtype': 1,
                            'status': 1,
                            'source_path': os.path.basename(Deployv3StgMain.objects.filter(app_id=item['app_id'], status=2, deploy_type=item['packtype']).order_by('-id')[0].source_path if item['deptype'] == 1 else item['ftpath'])
                    })
                except Exception as e:
                    detailinfo = 'wrong deploy trident info. %s' % format(str(e))
                    deploy_list.append({
                            'depid': None,
                            'taskid': item['taskid'],
                            'app_id': item['app_id'],
                            'pubtype': 1,
                            'detail': detailinfo,
                            'status': 7
                    })
            elif item['pubtype'] == 0:
                try:
                    depid = self.create_publish4trident4config(
                        item.get('uid', 523),
                        item['app_id'],
                        item.get('comment', ''),
                        item['jiraid'],
                        item.get('idc', 0),
                        item.get('publishDateTimeFrom', 0),
                        item.get('publishDateTimeTo', 0),
                        item.get('restart', 0),
                        item.get('publishTimeType', 0),
                        item.get('grayDeployFlag', 0),
                        item.get('grayDetailInfo', dict()),
                        item.get('restartInterval', 0 if time.localtime(item['publishDateTimeFrom']/1000).tm_hour ==2 else DEPLOY_INTERVAL),
                        item.get('zone', 0)
                        )
                    
                    deploy_dict = dict()
                    deploy_dict['depid'] = depid
                    deploy_dict['taskid'] = item.get('taskid')
                    deploy_dict['app_id'] = item['app_id']
                    deploy_dict['pubtype'] = 0
                    deploy_dict['status'] = 1
                    if item.get('zone'):
                        deploy_dict['name_ch'] = Room.objects.get(id=item.get('zone')).name_ch
                    else:
                        deploy_dict['idc'] = item.get('idc', 0)
                        deploy_dict['name_ch'] = None
                    deploy_list.append(deploy_dict)
                except Exception as e:
                    detailinfo = 'wrong deploy trident info. %s' % format(str(e))
                    deploy_list.append({
                        'depid': None,
                        'taskid': item.get('taskid', None),
                        'app_id': item['app_id'],
                        'pubtype': 0,
                        'detail': detailinfo,
                        'status': 7
                    })
        if not all([deploy['depid'] for deploy in deploy_list]):
            depid_list = [deploy['depid'] for deploy in deploy_list if deploy['depid'] and deploy['pubtype'] == 1]
            DeployMain.objects.filter(depid__in=depid_list).update(status=7)
            depid4config_list = [deploy['depid'] for deploy in deploy_list if deploy['depid'] and deploy['pubtype'] == 0]
            DeployMainConfig.objects.filter(depid__in=depid4config_list).update(status=7)
            for i in range(0, len(deploy_list)):
                deploy_list[i]['status'] = 7
        return deploy_list

    def create_publish4trident4config(
            self,
            user_id,
            app_id,
            comment,
            jiraid,
            idc,
            publishDateTimeFrom,
            publishDateTimeTo,
            restart,
            publishTimeType,
            gray_stage_type,
            gray_detail_info,
            restart_interval,
            zone
    ):
        depid = stamp2str(time.time(), '%Y%m%d%H%M%S') + str(random.randint(100000, 999999)) + 'C'
        deploy, created = DeployMainConfig.objects.get_or_create(depid=depid, defaults={
            'uid': user_id,
            'app_id': app_id,
            'status': 0,
            'comment': comment,
            'jiraid': jiraid,
            'create_time': int(time.time()),
            'last_modified': int(time.time()),
            'idc': idc,
            'publishdatetimefrom': int(publishDateTimeFrom)/1000,
            'publishdatetimeto': int(publishDateTimeTo)/1000,
            'restart': int(restart),
            'publishtimetype': publishTimeType,
            'gray_release_info': gray_detail_info.get('grayPercent') if gray_stage_type == 1 else None,
            'gray_stage_interval': gray_detail_info.get('stageInterval') if gray_stage_type == 1 else None,
            'restart_interval': restart_interval,
            'colony_surplus': gray_detail_info.get('colonySurplus', 75) if gray_stage_type == 1 else None,
            'recover_time': gray_detail_info.get('recoverTime', 50) if gray_stage_type == 1 else None,
            'gray_rollback_type': gray_detail_info.get('rollbackType', 1) if gray_stage_type == 1 else None,
            'zone' : Room.objects.get(id=zone) if zone else None
        })
        deploy.status = 1
        deploy.save()
        return depid

    def create_publish4trident(
            self,
            user_id,
            app_id,
            packtype,
            deptype,
            restart,
            comment,
            jiraid,
            ftpath,
            publishDateTimeFrom,
            publishDateTimeTo,
            srcs,
            dets,
            gray_stage_type,
            gray_detail_info,
            idc,
            publishTimeType,
            restart_interval
    ):
        old_app_id = app_id
        #静态POOL发布，需要强行将app_id指向静态POOL
        if packtype != 0:
            app_id = DEPLOY_PACKTYPE_MAPPING[packtype]['APP_ID']
        if deptype == 1 and not Server.objects.exclude(server_status_id=400).filter(app_id=app_id, server_env_id=1).exists():
            raise DeployError('staging机器不存在')
        depid = stamp2str(time.time(), '%Y%m%d%H%M%S') + str(random.randint(100000, 999999))
        depid += DEPLOY_PACKTYPE_MAPPING[packtype]['DEPID_SUFFIX']
        self.depid = depid
        try:
            app = App.objects.get(id=old_app_id)
            site = app.site
        except App.DoesNotExist:
            raise DeployError('应用不存在')
        if packtype != 0:
            app_name_string = app.name + DEPLOY_PACKTYPE_MAPPING[packtype]['PATH_SUFFIX']
            if site.name == 'samsclub':
                app_name_string = 'samsclub_' + app_name_string
            try:
                deploypath = DeployPath.objects.get(app_id=DEPLOY_PACKTYPE_MAPPING[packtype]['APP_ID'], name=app_name_string)
            except ObjectDoesNotExist:
                raise DeployError('线上静态目录目录不存在,请将以下信息反馈至lihaowei处：静态目录名称：%s' % app_name_string)
            except MultipleObjectsReturned:
                raise DeployError('该POOL存在多个线上静态目录，不允许发布，请修改！')
            if deploypath.path.rstrip('/') == '/var/www/yihaodian-static':
                raise DeployError('发布目录不允许配置为：%s' % deploypath.path)
        else:
            try:
                deploypath = DeployPath.objects.get(app_id=old_app_id)
            except ObjectDoesNotExist:
                raise DeployError('发布系统线上目录不存在,请联系monitor或自行配置后重新发布！')
            except MultipleObjectsReturned:
                raise DeployError('该POOL存在多个线上目录，不允许发布，请修改！')
        # 如果是staging2production，获取对应的ftp路径
        if deptype == 1:
            deployv3_main_obj = Deployv3StgMain.objects.filter(app_id=old_app_id, status=2, deploy_type=packtype).order_by('-id').first()
            if deployv3_main_obj is None:
                raise DeployError('staging从未成功发布过')
            ftpath = deployv3_main_obj.source_path
        version = os.path.basename(ftpath)
        if not [item for item in os.path.splitext(version)[0].split('-') if item.isdigit()]:
            raise DeployError('%s：不符合规范，不允许提交发布，请联系lihaowei' % version)
        #本地代码地址
        codepath = '/depot/deployv2/{0}/{1}/{2}'.format(site.name, app.name, depid)
        #线上预发布目录
        deprepath = '/depot/predeploy/{0}'.format(depid)
        #线上备份目录
        backup = '/depot/backup/{0}'.format(depid)
        path_det = deploypath.path
        path_src = deploypath.path
        #向main表插记录
        if packtype == 3:
            restart = 0
        gray_release_info = gray_detail_info.get('grayPercent', '') if gray_stage_type else ''
        if gray_release_info.startswith('0,'):
            gray_release_info = gray_release_info[2:]
        gray_stage_interval = gray_detail_info.get('stageInterval', 0) if gray_stage_type else 0
        colony_surplus = gray_detail_info.get('colonySurplus', 0) if gray_stage_type else 0
        recover_time = gray_detail_info.get('recoverTime', 0) if gray_stage_type else 0
        gray_rollback_type = gray_detail_info.get('rollbackType', 1) if gray_stage_type else 0
        deploy, created = DeployMain.objects.get_or_create(depid=depid,
                                                           defaults={
                                                               'uid': user_id if user_id else 0,
                                                               'app_id': old_app_id,
                                                               'deploypathid': deploypath.id,
                                                               'deptype': deptype,
                                                               'packtype': packtype,
                                                               'ftpath': ftpath,
                                                               'codepath': codepath,
                                                               'deprepath': deprepath,
                                                               'backup': backup,
                                                               'path': path_det,
                                                               'path_src': path_src,
                                                               'srcs': srcs,
                                                               'dets': dets,
                                                               'restart': restart,
                                                               'comment': comment,
                                                               'jiraid': jiraid,
                                                               'create_time': int(time.time()),
                                                               'last_modified': int(time.time()),
                                                               'is_gray_release': gray_stage_type,
                                                               'publishdatetimefrom': int(publishDateTimeFrom)/1000,
                                                               'publishdatetimeto': int(publishDateTimeTo)/1000,
                                                               'gray_release_info': gray_release_info,
                                                               'idc': idc,
                                                               'publishtimetype': publishTimeType,
                                                               'gray_stage_interval': gray_stage_interval,
                                                               'colony_surplus': colony_surplus,
                                                               'recover_time': recover_time,
                                                               'gray_rollback_type': gray_rollback_type,
                                                               'restart_interval': restart_interval
                                                           })
        deploy.valid = 1
        deploy.status = 1
        deploy.save()
        return depid


