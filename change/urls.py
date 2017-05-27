# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.conf.urls import patterns, url

urlpatterns = patterns('change.views',
    url(r'changelist/$', 'changelist'),

    url(r'exception_report/$', 'exception_report'),
    url(r'exception_trend/(?P<id>[0-9]+)/$', 'exception_trend'),
    url(r'exception_detail/(?P<id>[0-9]+)/$', 'exception_detail'),
    url(r'^exception_comment_insert/$', 'exception_comment_insert'),
    url(r'^exception_comment_update/$', 'exception_comment_update'),
    url(r'^exception_comment_delete/$', 'exception_comment_delete'),
    url(r'^exception_detail_api/$', 'exception_detail_api'),
    url(r'$', 'changelist'),
)