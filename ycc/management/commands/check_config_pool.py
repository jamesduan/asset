# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from ycc.models import ConfigPostInfoV2,ConfigGroup,App,ConfigInfo,ExceptionConfigAccessDetail
from server.models import Server
from util.timelib import *


def Create(error,group_id,data_id,server,current_format ,standardgroup_id):
    object,created=ExceptionConfigAccessDetail.objects.get_or_create(error=error,group_id=group_id,data_id=data_id,ip=server.ip,site_id=server.site.id if server.site else None ,
                                                                        app_id=server.app_id,domain_id=server.app.domainid if server.app and server.app.domainid else None,standardgroup_id=standardgroup_id,
                                                                                               defaults={ 'frequency':1,'lastupdate':current_format })
    if not created and object.lastupdate.strftime('%Y-%m-%d %H:%M:%S') !=current_format:
        object.frequency=object.frequency+1
        object.lastupdate=current_format
        object.save()

class Command(BaseCommand):
    args = ''
    help = ''
    def handle(self, *args, **options):

        now=time.time()
        current_format=stamp2str(now,formt='%Y-%m-%d %H:%M:%S')
        now_ago=stamp2str(now-7*24*60*60,formt='%Y-%m-%d %H:%M:%S')
        groupiddistinct=ConfigPostInfoV2.objects.filter(update_time__gt=now_ago).values('ip','group_id','data_id').distinct()
        # print groupiddistinct
        for item in groupiddistinct:
            if item['group_id'][-3:]=='_jq':
                group_id=item['group_id'][:-3]
                room_id=4
            else:
                group_id=item['group_id']
                room_id=1
            try:
                server=Server.objects.get(server_status_id=200,ip=item['ip'])
                configgroup=ConfigGroup.objects.get(group_id=group_id,status=1,idc=room_id)

                if configgroup.app_id==0 :

                    Create(0,item['group_id'],'all',server,current_format ,'')
                    # object,created=ExceptionConfigAccessDetail.objects.get_or_create(error=0,group_id=group_id,data_id='all',ip=server.ip,site_id=server.site.id if server.site else None ,
                    #                                                     app_id=server.app_id,domain_id=server.app.domainid if server.app else None,exception_export_id=46,
                    #                                                                            defaults={ 'frequency':1,'lastupdate':current_format ,'standardgroup_id':''})
                    # if not created and object.lastupdate !=current_format:
                    #     object.frequency=object.frequency+1
                    #     object.lastupdate=current_format
                    #     object.save()
                else :
                    app=App.objects.get(id=configgroup.app_id)
                    if app.status==1:
                        Create(1,item['group_id'],'all',server,current_format ,'')

                    else:
                        appname=app.name
                        site=app.site.name

                        if site+'_'+appname !=group_id :
                            if room_id==4:
                                standardgroup_id=site+'_'+appname+'_jq'
                            else:
                                standardgroup_id=site+'_'+appname
                            Create(2,item['group_id'],'all',server,current_format ,standardgroup_id)
                        else:
                            server_env_id=server.server_env_id
                            if server_env_id==1:
                                env=6
                                group_status=0
                            else:
                                if server_env_id==2:
                                    env=7
                                    group_status=4
                                else:
                                    env=None
                                    group_status=None
                            count=ConfigInfo.objects.filter(data_id=item['data_id'], env=env,group_status__status= group_status,group_status__group__group_id=group_id,
                                              group_status__group__idc= room_id, group_status__group__status=1).count()
                            if count==0:
                                 Create(3,item['group_id'],item['data_id'],server,current_format ,'')

            except Server.DoesNotExist:
                None
            except App.DoesNotExist:
                None
            except ConfigGroup.DoesNotExist:
                None

        ExceptionConfigAccessDetail.objects.filter(lastupdate__lt=current_format).delete()

        print 'success'+stamp2str(time.time())






