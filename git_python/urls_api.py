# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from rest_framework.routers import DefaultRouter
import views_api

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'git_app', views_api.GitAppViewSet)

urlpatterns = patterns(
    'git_python.views_api',
    url(r'^crud/$', 'crud'),
    url(r'^commit/$', 'commit'),
    url(r'^log/$', 'log'),
    url(r'^unmerged_blobs/$', 'unmerged_blobs'),
    url(r'^checkout/$', 'checkout'),
    url(r'^diff/$', 'diff'),
    url(r'^reset/$', 'reset'),
    url(r'^diff/cached/$', 'diff_cached'),
    url(r'^boot_sh/tree/$', 'boot_sh_tree'),
    url(r'^boot_sh/puppet/$', 'boot_sh_puppet'),
    url(r'^boot_sh/web_hook/puppet/$', 'boot_sh_web_hook_puppet'),
    url(r'^boot_sh/puppet/result/$', 'boot_sh_puppet_result'),
    url(r'^boot_sh/app/list/$', views_api.GitBootShAppList.as_view()),
    url(r'^boot_sh/app/(?P<app_id>[0-9]+)/$', views_api.GitBootShAppDetail.as_view()),

    url(r'^commit/v2/', 'commit_v2'),
    url(r'^checkout/v2/', 'checkout_v2'),
    url(r'^unmerged_blobs/v2/$', 'unmerged_blobs_v2'),
    url(r'^log/v2/$', 'log_v2'),
    url(r'^diff/v2/$', 'diff_v2'),
    url(r'^diff/cached/v2/$', 'diff_cached_v2'),
    url(r'^reset/v2/$', 'reset_v2'),
    url(r'^tools/file/(?P<pk>[0-9]+)/$', 'git_app_file'),
    url(r'^tools/tree/$', 'git_app_tree'),
    url(r'^web_hook/puppet/$', 'web_hook_puppet'),
)

urlpatterns += [
    url(r'', include(router.urls)),
]
