from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from yellowpages.public import pool_config_dependence
from server.models import ServerStandard,Server
from ycc.models import ConfigPostInfoV2,ConfigGroup
from cmdb.models import AppV2,App
import datetime
from django.db.models import Q

@api_view(['GET'])
@permission_classes((AllowAny, ))
def PooldependenceList(request):
    app_id=request.GET.get('app_id')
    results=pool_config_dependence(app_id)
    return Response(status=status.HTTP_200_OK, data=results)

@api_view(['GET'])
@permission_classes((AllowAny, ))
def ConfigCallList(request):
    results=[]
    app_ids=[]
    serverlist={}
    group_id=request.GET.get('group_id') if request.GET.get('group_id') else ''
    configpost=ConfigPostInfoV2.objects.filter(Q(group_id=group_id)|Q(group_id=group_id+'_jq'), update_time__gte=datetime.datetime.now() - datetime.timedelta(
                                                                          days=7)).values('ip').distinct()

    server_200=ServerStandard.objects.filter(server_status_id=200)
    for obj in server_200:
        serverlist[obj.ip]=obj.app_id

    for item in configpost:
        if serverlist.has_key(item['ip']):
            app_id=serverlist[item['ip']]
            if app_id not in app_ids:
                app_ids.append(app_id)

    for id in app_ids:
        try:
            app=App.objects.get(id=id)
            appname=app.name
            sitename=app.site.name
            pool=sitename+'/'+appname
            domainemail=app.domain.domainemailgroup if app.domain else None
            results.append({'group_id':group_id,'pool':pool,'domainemail':domainemail})
        except App.DoesNotExist:
            continue

    return Response(status=status.HTTP_200_OK, data=results)
