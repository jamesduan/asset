# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('logplatform.views',

    url(r'^reg/$', 'regmain'),
    url(r'^rule/$', 'rule'),
)
