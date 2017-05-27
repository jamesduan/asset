# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from change import views_api

urlpatterns = patterns('change.views_api',
    url(r'^changelist/$', views_api.ChangeMain.as_view()),
    url(r'^action/$', views_api.ChangeAction.as_view()),
    url(r'^type/$', views_api.ChangeType.as_view()),
    url(r'^exception_report/$', views_api.ExceptionReportList.as_view()),
    url(r'^exception_trend/$', 'exception_trend'),


    url(r'$', views_api.ChangeMain.as_view()),
)
