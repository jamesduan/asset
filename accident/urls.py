# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('accident.views',

    url(r'^center/$', 'accident_center'),
    url(r'^influence/$', 'pool_influence'),
    url(r'^list/$', 'accident_list'),
    url(r'^detail/$', 'accident_detail'),
    url(r'^detail/process/$', 'accident_process'),
    url(r'^loadcsv/$', 'load_accident'),
    url(r'^loadcsv/all/$', 'load_accident_all'),
    url(r'^sla/domain/$', 'sla_domain'),
)
