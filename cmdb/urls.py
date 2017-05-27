# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.conf.urls import patterns, url

urlpatterns = patterns('cmdb.views',

    url(r'db/instances/$', 'instancesdblist'),
    url(r'^redirect', 'url_redirect'),
    url(r'^site/$', 'sitelist'),
    url(r'^app/$', 'applist'),
    url(r'^appcontact/$', 'app_contact'),
    url(r'^deptdomain/$', 'deptdomainchart'),
    url(r'^usersdomains/$', 'users_domains'),
    url(r'^userquery/$', 'userquery'),
    url(r'^gettemplate/(?P<activity_id>[0-9]+)/$', 'gettemplate'),
    # url(r'^rotaenter/(?P<activity_id>[0-9]+)/$', 'rotaenter'),
    url(r'^rotaenter/$', 'rotaenter'),
    url(r'^rotaquery/$', 'rotaquery'),
    url(r'^activity/$', 'activity'),
    url(r'^sendmail/$', 'sendmail'),
    # url(r'^searchlist/(?P<key>.*?)/$', 'searchlist'),
    # url(r'^searchdetail/(?P<key>.*?)/(?P<id>[0-9]+)/(?P<type>[0-9]+)/$', 'searchdetail'),
    url(r'^usertel/$', 'usertel'),
    url(r'^search/server/$', 'search_server'),

    url(r'^mobile/load/$', 'mobile_load'),

    url(r'$', 'app_contact'),


)

