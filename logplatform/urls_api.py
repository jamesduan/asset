# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from logplatform import views_api

urlpatterns = patterns('logplatform.views_api',
    url(r'^reg/$', views_api.RegList.as_view()),
    url(r'^reg/(?P<pk>[0-9]+)/$', views_api.RegDetail.as_view()),
    url(r'^test_reg/(?P<pk>[0-9]+)/$', views_api.TestReg.as_view()),
)
