# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('ycc.views',
    url(r'^group/$', 'group_v3'),
    url(r'^group/v3/$', 'group_v3'),
    url(r'^dbassociation/$', 'db_association'),
    # url(r'configinfo/$', 'configinfolist'),
    url(r'^proconfiginfo/v2/$', 'proconfiginfov2list'),
    url(r'^configinfo/v2/$', 'configinfov3list'),
    url(r'^configinfo/v3/$', 'configinfov3list'),
                       url(r'^soa_service/$', 'soa_service'),
    # url(r'status/$', 'group_status'),
    # url(r'import/$', 'importGroupData'),
    url(r'^copy/$', 'copyGroupData'),
    url(r'^cmp/$', 'cmpconfiginfos'),
    url(r'^dbupdate/$', 'dbupdatelist'),
    url(r'^config/subscribe/$', 'config_subscribe_list'),
    url(r'^config/maingroup/$', 'config_maingroup'),
    url(r'^grayrelease/blackip/$', 'gray_release_blackip'),
    url(r'^roomapps/$', 'room_apps'),
)





