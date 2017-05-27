# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from rest_framework.routers import DefaultRouter
from views_api import UsersList, HistoryUserList

# Create a router and register our viewsets with it.
router = DefaultRouter()

urlpatterns = patterns(
    'mobile.views_api',
    url(r'^login/$', 'mobile_login'),
    url(r'^get/user/$', 'get_user'),
    url(r'^yellow/today/activity/$', 'today_duty_activity'),
    url(r'chart/realtime_order/$', 'chart_realtime_order'),
    url(r'yellow/find_user/$', UsersList.as_view()),
    url(r'yellow/history_user/$', HistoryUserList.as_view()),
    url(r'yellow/user/$', 'find_return_user'),
    url(r'yellow/duty/info/$', 'today_duty_info'),
    url(r'cmdb/deptv2/domain/$', 'deptv2_domains'),
    url(r'cmdb/deptv2/dept/domain/$', 'deptv2_dept_domains'),
)

urlpatterns += [
    url(r'', include(router.urls)),
]
