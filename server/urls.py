# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('server.views',

    url(r'install/$', 'serverinstalllist'),
    url(r'virtual/$', 'servervirtuallist'),
    url(r'server/$', 'serverlist'),
    url(r'^lb_group/$', 'lb_group'),
    url(r'^detail/$', 'server_detail'),
    url(r'^log/detail/$', 'server_log'),
)
