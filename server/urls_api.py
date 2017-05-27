# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from rest_framework.routers import DefaultRouter
import views_api

# router = DefaultRouter()
# router.register(r'lb_group', views_api.LBGroupViewSet)

# urlpatterns = [
#     url(r'', include(router.urls)),
# ]

urlpatterns = patterns('server.views_api',

    url(r'ostemplate/$', views_api.ServerOsTemplateList.as_view()),
    url(r'apptemplate/$', views_api.ServerAppTemplateList.as_view()),
    url(r'host/$', views_api.ResourcesVmList.as_view()),
    url(r'host/(?P<pk>.+)/$', views_api.ResourcesVmDetail.as_view()),
    url(r'^ip/(?P<ip>.+)/$', views_api.ServerByIpDetail.as_view()),
    url(r'^sn/(?P<sn>.+)/$', views_api.ServerBySnDetail.as_view()),
    url(r'server/$', views_api.ServerList.as_view()),
    url(r'serverdetail/$', views_api.ServerDetailList.as_view()),
    url(r'serverstandard/$', views_api.ServerStandardList.as_view()),
    url(r'serverstandard/(?P<pk>.+)/$', views_api.ServerStandardDetail.as_view()),
    url(r'install/$', views_api.ServerInstallList.as_view()),
    url(r'install/docker/$', views_api.ServerInstallForDocker.as_view()),
    url(r'install/(?P<pk>.+)/$', views_api.ServerInstallDetail.as_view()),
    url(r'import/hybrid/$', views_api.ServerForHybridList.as_view()),
    url(r'num_of_free_servers/$', views_api.NumOfFreeServers.as_view()),
    url(r'vmexpand/$', views_api.VmExpand.as_view()),
    url(r'vmreduce/$', views_api.VmReduce.as_view()),
    url(r'haproxy/group/$', 'haproxy_group'),
    url(r'notification/$', 'notification'),
    url(r'^log/virtual/$', views_api.VirtualLog.as_view()),


    url(r'^(?P<pk>.+)/$', views_api.ServerDetail.as_view()),

    url(r'$', views_api.ServerList.as_view())

)
