from server.models import ServerStandard
from ycc.models import ConfigPostInfoV2,ConfigGroup
from cmdb.models import AppV2
import datetime

def pool_config_dependence(app_id):
    results=[]
    try:
        pool=AppV2.objects.get(id=app_id).site.name+'/'+AppV2.objects.get(id=app_id).name
        server=ServerStandard.objects.filter(server_status_id=200,server_env_id=2,app__id=app_id).first()
        ip=server.ip if server else None
        configpost=ConfigPostInfoV2.objects.filter(ip=ip, update_time__gte=datetime.datetime.now() - datetime.timedelta(
                                                                               days=3))
        # group_id_list=[item['group_id'].rstrip('_jq') for item in configpost.values('group_id').distinct()]
        for item in configpost.values('group_id').distinct():
            dict={}
            dict['pool']=pool
            dict['group_id']=item['group_id'].rstrip('_jq')
            configgroup=ConfigGroup.objects.filter(group_id=item['group_id'].rstrip('_jq'),status=1).first()
            main_app_id=configgroup.app_id if configgroup else None
            if int(app_id)==main_app_id:
                dict['type']=1
            else:
                dict['type']=0
            results.append(dict)
    except AppV2.DoesNotExist:
        None
    return results