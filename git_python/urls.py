# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
# from django.views.generic import TemplateView

urlpatterns = patterns(
    'git_python.views',
    url(r'^boot_sh/$', 'boot_sh'),
    url(r'^git_app/$', 'git_app'),
)
