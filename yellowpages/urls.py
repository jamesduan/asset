# -*- coding: utf-8 -*-
from django.conf.urls import patterns,url

urlpatterns=patterns(
    'yellowpages.views',
    url(r'^pool/dependence/$','pool_dependence'))