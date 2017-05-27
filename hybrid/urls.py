# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url


urlpatterns = patterns('hybrid.views',
    
    url(r'^requirement/$', 'requirementlist'),
    url(r'^requirementdetail/$', 'requirementdetaillist'),

)
