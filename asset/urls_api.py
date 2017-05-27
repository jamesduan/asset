# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from asset import views_api

urlpatterns = patterns('',

    url(r'^zone/$', views_api.ZoneList.as_view()),
    url(r'^zone/(?P<pk>[0-9]+)/$', views_api.ZoneDetail.as_view()),
    url(r'^rack/$', views_api.RackList.as_view()),
    url(r'^rack/(?P<pk>[0-9]+)/$', views_api.RackDetail.as_view()),
    url(r'^assettype/$', views_api.AssetTypeList.as_view()),
    url(r'^assettype/(?P<pk>[0-9]+)/$', views_api.AssetTypeDetail.as_view()),
    url(r'^assetmodel/$', views_api.AssetModelList.as_view()),
    url(r'^assetmodel/(?P<pk>[0-9]+)/$', views_api.AssetModelDetail.as_view()),
    url(r'^ipsegment/$', views_api.IpSegmentList.as_view()),
    url(r'^ipsegment/(?P<pk>[0-9]+)/$', views_api.IpSegmentDetail.as_view()),
    url(r'^ip/$', views_api.IpList.as_view()),
    url(r'^ip/(?P<pk>[0-9]+)/$', views_api.IpDetail.as_view()),
    url(r'^ip2/$', views_api.IpList2.as_view()),
    url(r'^ip2/(?P<pk>[0-9]+)/$', views_api.IpDetail2.as_view()),
    url(r'^ip/bind/$', views_api.IpBind.as_view()),
    url(r'^asset/$', views_api.AssetList.as_view()),
    url(r'^asset/(?P<pk>[0-9]+)/$', views_api.AssetDetail.as_view()),
    url(r'^rackspace/$', views_api.RackSpaceList.as_view()),
    url(r'^repair/$', views_api.AssetRepairList.as_view()),
    url(r'^repair/(?P<pk>[0-9]+)/$', views_api.AssetRepairDetail.as_view()),
)
