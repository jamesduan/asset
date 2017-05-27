# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('dns_python.views',
    url(r'zone/$', 'zone'),
    url(r'record/$', 'record'),
)
