# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from rest_framework.routers import DefaultRouter
import views_api

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'zone', views_api.DnsZoneViewSet)
router.register(r'record', views_api.DnsRecordViewSet)


urlpatterns = patterns(
    'dns_python.views_api',
    url(r'^record/bulk/by_ip/', 'record_bulk_by_ip'),
    url(r'^record/bulk/by_domain/', 'record_bulk_by_domain'),
    url(r'^zone_save/$', 'zone_save'),

    # url(r'^record_list/$', 'record_list'),
    # url(r'^record_del/$', 'record_del'),
    url(r'^record_exist/$', 'record_exist'),
    url(r'^record_save/$', 'record_save'),

    url(r'^zone_write/$', 'zone_write'),
    url(r'^history/$', 'history'),
    url(r'^zone_rollback/$', 'zone_rollback'),
    url(r'^record_save_multi/$', 'record_save_multi'),
    url(r'^zone_download/$', 'zone_download'),
    url(r'^download/$', 'download'),

    url(r'^test/$', 'test'),

    # api调用
    url(r'^domain_validate/$', 'domain_validate'),
    url(r'^domain_sync/$', 'domain_sync'),
    url(r'^domain_exists/$', 'domain_exists'),
    url(r'^domain_list/$', 'domain_list'),
    url(r'^domain_add/$', 'domain_add'),
    url(r'^domain_edit/$', 'domain_edit'),
    url(r'^domain_del/$', 'domain_del'),

    url(r'^domain_dba/$', 'domain_dba'),
)

urlpatterns += [
    url(r'', include(router.urls)),
]
