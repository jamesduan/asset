# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
# from django.views.generic import TemplateView

urlpatterns = patterns(
    'deploy.views',
    # url(r'^normal/list/$', TemplateView.as_view(template_name='normal_list.html')),
    # url(r'^normal/detail/$', TemplateView.as_view(template_name='normal_detail.html')),
    url(r'^normal/list/$', 'normal_list'),
    url(r'^normal/detail/$', 'normal_detail'),
    url(r'^gray/list/$', 'gray_list'),
    url(r'^gray/detail/$', 'gray_detail'),
    url(r'^ycc/list/$', 'ycc_list'),
    url(r'^ycc/list/v2/$', 'ycc_list_v2'),
    url(r'^ycc/detail/$', 'ycc_detail'),
    url(r'^ycc/detail/v2/$', 'ycc_detail_v2'),
    url(r'^single/detail/$', 'single_detail'),
    url(r'^reboot/detail/$', 'reboot_detail'),
    url(r'^redis/$', 'redis'),
    url(r'^stg/list/$', 'stg_list'),
    url(r'^stg/detail/$', 'stg_detail'),
    url(r'^publish/count/$', 'publish_count'),
    url(r'^publish/trend/$', 'publish_trend'),
    url(r'^publish/compare/$', 'publish_compare'),
    url(r'^center/$', 'center'),
    url(r'dashboard/pool/$', 'dashboard_pool'),
    url(r'^jenkins/$', 'jenkins'),
    url(r'^publish/screen/$', 'publish_screen'),
    url(r'^publish/largescreen/$', 'publish_largescreen'),
    url(r'^path/config/$', 'path_config'),
    url(r'^hudson/job/$', 'hudson_job'),
    url(r'^stg/limit/$', 'stg_deploy_limit'),
    url(r'^prod/list/$', 'prod_list'),
    url(r'^prod/detail/$', 'prod_detail'),
    url(r'^bulk/list/$', 'bulk_list'),
    url(r'^process/pattern/$', 'process_pattern'),
    url(r'^rollback/reason/$', 'rollback_reason'),
)