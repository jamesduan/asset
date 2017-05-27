# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from rest_framework.routers import DefaultRouter
import views_api

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'path', views_api.DeployPathViewSet)
router.register(r'ftp_path', views_api.DeployFtpViewSet)
router.register(r'hudson_job', views_api.HudsonJobViewSet)
router.register(r'process_pattern',views_api.DeployProcessPatternViewSet)

urlpatterns = patterns(
    'deploy.views_api',
    url(r'^muti_save_deploy_v2', 'muti_save_deploy_v2'),
    url(r'^ftp/list/$', 'ftp_list'),
    url(r'^rollback/$', 'rollback'),
    url(r'^auto_publish/$', 'auto_publish'),
    url(r'^auto_pre_deploy/$', 'auto_pre_deploy'),
    url(r'^auto_single_deploy/$', 'auto_single_deploy'),
    url(r'^config_rollback/$', 'config_rollback'),
    url(r'^config_auto_publish/$', 'config_auto_publish'),
    url(r'^permitted/$', 'permitted'),
    url(r'^log/$', 'log'),
    url(r'^log2/$', 'log2'),
    url(r'^log/reboot/$', 'log_reboot'),
    url(r'^catalina/$', 'catalina'),
    url(r'^online_report/$', 'online_report'),
    url(r'^auto_reboot/$', 'auto_reboot'),
    url(r'^redis/(?P<category>.+)/$', 'redis_python'),
    url(r'^version/$', views_api.DeployVersionAppList.as_view()),
    url(r'^version/(?P<pk>[0-9]+)/$', views_api.DeployVersionAppDetail.as_view()),
    url(r'^main/list/$', views_api.DeployMainList.as_view()),
    url(r'^detail/list/$', views_api.DeployDetailList.as_view()),
    url(r'^rollback/reason/list/$', views_api.DeployRollbackReasonList.as_view()),
    url(r'^status/(?P<depid>.+[WS])/$', views_api.Status.as_view()),
    url(r'^status/(?P<depid>.+C)/$', views_api.StatusConfig.as_view()),
    url(r'^main/config/list/$', views_api.DeployMainConfigList.as_view()),
    url(r'^main/config/list/v2/$', views_api.DeployMainConfigListV2.as_view()),
    url(r'^detail/config/list/$', views_api.DeployDetailConfigList.as_view()),
    url(r'^in_progress/(?P<depid>.+[WS])/$', views_api.InProgress.as_view()),
    url(r'^in_progress/(?P<depid>.+C)/$', views_api.InProgressConfig.as_view()),
    url(r'^ticket/(?P<ticket_id>.+)/$', views_api.DeployTicketCeleryDetail.as_view()),
    url(r'^stg/list/$', views_api.Deployv3StgMainList.as_view()),
    url(r'^stg/list/(?P<depid>[0-9]+)/$', views_api.Deployv3StgMainDetail.as_view()),
    url(r'^stg/detail/$',  views_api.Deployv3StgDetail.as_view()),
    url(r'^stg/detail/event/$', 'stg_deploy_event'),
    url(r'^hooks/gitlab_push$', 'gitlab_push'),
    url(r'^gitlab/push_event', 'gitlab_push_event'),
    url(r'^gitlab/merge_event', 'gitlab_request_merge_event'),
    url(r'^publish/count/$', 'publish_count'),
    url(r'^publish/trend/$', 'publish_trend'),
    url(r'^publish/compare/$', 'publish_compare'),
    url(r'^dashboard/pool/$', 'dashboard_pool'),
    url(r'^jenkins/job/$', 'jenkins_job'),
    url(r'^config/info/$', 'config_info'),
    url(r'^publish/screen/$', 'publish_screen'),
    url(r'^jenkins/job/list/$', views_api.JenkinsJobList.as_view()),
    url(r'^stg/limit/list/$', views_api.Deployv3StgMaxtimeList.as_view()),
    url(r'^stg/limit/detail/(?P<pk>[0-9]+)/$', views_api.Deployv3StgMaxtimeDetail.as_view()),
    url(r'^main/list/v2/$', views_api.DeployMainListV2.as_view()),
    url(r'^main/detail/v2/(?P<depid>.+[WS])/$', views_api.DeployMainDetailV2.as_view()),
    url(r'^auto_publish/v2/$', 'auto_publish_v2'),
    url(r'^rollback/v2/$', 'rollback_v2'),
    url(r'^bulk/list/$', 'bulk_list'),
    url(r'^bulk/rollback/$', 'bulk_rollback'),
    url(r'^sre/pandora/$', 'sre_pandora'),
    url(r'^sre/pandora/v2/$', 'sre_pandora_v2'),
    url(r'^test/http_500/$', 'test_http_500'),
)

urlpatterns += [
    url(r'', include(router.urls)),
]
