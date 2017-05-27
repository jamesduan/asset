# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('asset.views',

    url(r'^gettemplate/$', 'gettemplate'),
    url(r'^ipsegment/$', 'ipsegmentlist'),
    url(r'^rack/$', 'racklist'),
    url(r'^model/$', 'modellist'),
    url(r'^room/$', 'zonelist'),
    url(r'^repair/$', 'repairlist'),
    url(r'^assetchart/(?P<id>[0-9]+)/(?P<type>[a-z]+)/(?P<is_print>[0-9])/$', 'assetchart'),
    url(r'^pre_asset/$', 'pre_asset'),
    url(r'^extranetip/$', 'extranetip'),
    url(r'$', 'assetlist'),
)
