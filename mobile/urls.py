# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
# from django.views.generic import TemplateView

urlpatterns = patterns(
    'mobile.views',
    url(r'^register/$', 'register'),
    url(r'^loginout/$', 'loginout'),
    url(r'monitor/$', 'orderchart'),
    url(r'^personal/$', 'personal'),
    url(r'^personal/info/$', 'personal_info'),
    url(r'^yellow/$', 'yellow_find_user'),
    url(r'^yellow/find/user/$', 'yellow_find_user_result'),
    url(r'^yellow/duty/$', 'yellow_duty_list'),
    url(r'^yellow/duty/detail/$', 'yellow_duty_detail'),
    url(r'^base/$', 'base'),
    url(r'^base/monitor/$', 'base_monitor'),
    url(r'^base/yellowpage/$', 'base_yellowpage'),
    url(r'^base/mime/$', 'base_mime'),
    url(r'^home/$', 'home'),
    # url(r'^test/$', 'test'),
    url(r'^$', 'orderchart'),
)
