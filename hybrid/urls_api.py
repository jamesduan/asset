# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from hybrid import views_api

urlpatterns = patterns('',

    url(r'^requirement/$', views_api.HybridRequirementList.as_view()),
    url(r'^requirement/(?P<pk>[0-9]+)/$', views_api.HybridRequirementDetail1.as_view()),

    url(r'^requirementdetail/$', views_api.HybridRequirementDetailList.as_view()),
    url(r'^requirementdetail/(?P<pk>[0-9]+)/$', views_api.HybridRequirementDetailDetail.as_view()),

)
