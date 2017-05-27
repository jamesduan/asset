# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from accident import views_api

urlpatterns = patterns('accident.views_api',

    url(r'^accident/$', views_api.AccidentList.as_view()),
    url(r'^accident/all/$', views_api.AccidentAll.as_view()),
    url(r'^accident/(?P<pk>[0-9]+)/$', views_api.AccidentDetail.as_view()),
    url(r'^current/$', views_api.CurrentAccidentList.as_view()),
    url(r'^action/$', views_api.AccidentActionList.as_view()),
    url(r'^action/(?P<pk>[0-9]+)/$', views_api.AccidentActionDetail.as_view()),
    url(r'^domain/$', views_api.AccidentDomainList.as_view()),
    url(r'^pool/$', views_api.AccidentPoolList.as_view()),
    url(r'^pool/(?P<pk>[0-9]+)/$', views_api.AccidentPoolDetail.as_view()),
    url(r'^type/$', views_api.AccidentTypeList.as_view()),
    url(r'^log/$', views_api.AccidentLogList.as_view()),
    url(r'^log/image/$', views_api.AccidentLogImageList.as_view()),
    url(r'^log/sendmail/$', 'send_accident_log'),
    url(r'^influence/$', 'pool_influence'),
    url(r'^sla/domain/$', 'sla_domain'),

)
