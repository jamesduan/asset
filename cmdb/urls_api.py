# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from cmdb import views_api

urlpatterns = patterns('cmdb.views_api',

    url(r'^site/$', views_api.SiteList.as_view()),
    url(r'^site/(?P<pk>[0-9]+)/$', views_api.SiteDetail.as_view()),
    url(r'^site/name/(?P<name>.+)/$', views_api.SiteByNameDetail.as_view()),

    url(r'^applist/$', views_api.AppWebList.as_view()),
    url(r'^app/$', views_api.AppList.as_view()),
    url(r'^app/(?P<pk>[0-9]+)/$', views_api.AppDetail.as_view()),
    url(r'^app/name/(?P<name>.+)/$', views_api.AppByNameDetail.as_view()),
    url(r'^app/by_user/$', views_api.AppListByUser.as_view()),
    url(r'^app/v2/$', views_api.AppListV2.as_view()),

    url(r'^appcontact/$', views_api.AppContactList.as_view()),
    url(r'^users/$', views_api.DdUsersList.as_view()),
    url(r'^user/v2/$', views_api.DdUsersListV2.as_view()),
    url(r'^domain/$', views_api.DdDomainList.as_view()),
    url(r'^domain/v2/$', views_api.DdDomainListV2.as_view()),
    url(r'^deptlevel2/domain/$', views_api.DomainListByDeptV2.as_view()),
    url(r'^domain/bydeptv2/$', 'domains_by_deptv2'),
    url(r'^usersdomains/$', views_api.DdUsersDomainsList.as_view()),
    url(r'^usersdomainsforrota/$', views_api.DdUsersDomainsforrotaList.as_view()),
    url(r'^rotaenter/$', views_api.RotaenterList.as_view()),
    url(r'^rotaenter/(?P<pk>[0-9]+)/$', views_api.RotaenterDetail.as_view()),
    url(r'^activity/$',views_api.RotaActivityList.as_view()),
    url(r'^activity/(?P<pk>[0-9]+)/$', views_api.RotaActivityDetail.as_view()),
    url(r'^url/$','url_app'),
    url(r'^shifttime/$',views_api.ShiftTimeList.as_view()),
    url(r'^shifttime/(?P<pk>[0-9]+)/$', views_api.ShiftTimeDetail.as_view()),
    url(r'^dailydutyconfig/$',views_api.DailyDutyConfigList.as_view()),
    url(r'^dailydutytime/$',views_api.DailyDutyTimeList.as_view()),
    url(r'^department/$', views_api.DdDepartmentList.as_view()),
    url(r'^pooltoacl/$',views_api.Pooltoacllist.as_view()),
    url(r'^acltobackend/$',views_api.Acltobackendlist.as_view()),
    url(r'^app/syncbycmis/$', 'sync_app_and_appcontact'),

    url(r'^db/instances/$', views_api.ConfigDbInstanceList.as_view()),
    url(r'^db/instances/(?P<pk>[0-9]+)/$', views_api.ConfigDbInstanceDetail.as_view()),
    url(r'^db/get_dbinstance_list/$', 'get_dbinstance_list'),
    url(r'^db/copy_db_instance/$', 'copy_db_instance'),
    url(r'^db/instanes_edit/$', 'is_exists_dbinstane'),
    url(r'^db/instanes_group/$', 'get_instanes_group'),
    url(r'^db/instanes_configinfo/$', 'get_instanes_configinfo'),

    url(r'^db/kvdefault/$', views_api.ConfigDbKvDefaultList.as_view()),
    url(r'^db/kvcustom/$', views_api.ConfigDbKvCustomList.as_view()),

)
