# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from apply import views_api

urlpatterns = patterns('',

    url(r'vm/$', views_api.ApplyVmList.as_view()),
    url(r'vm/(?P<pk>[0-9]+)/$', views_api.ApplyVmDetail.as_view()),

)
