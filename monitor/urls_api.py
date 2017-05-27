from django.conf.urls import patterns, url
from monitor import views_api

urlpatterns = patterns('monitor.views_api',
    url(r'^event/$', views_api.EventList.as_view()),
    url(r'^eventv2/$', 'get_eventlistv2'),
    url(r'^event/(?P<pk>[0-9]+)/$', views_api.EachEvent.as_view()),
    url(r'event/updateall/$', 'eventupdateall'),
    url(r'^alarm/$', views_api.AlarmList.as_view()),
    url(r'^alarmv2/$', 'get_alarmlistv2'),
    url(r'^alarmcallback/$', 'alarm_callback'),
    url(r'^eventprecallback/$', 'event_preprocess_callback'),
    url(r'^eventfilter/$', views_api.EventFilterList.as_view()),
    url(r'^eventfilter/(?P<pk>[0-9]+)/$', views_api.EachEventFilter.as_view()),
    url(r'^eventconvergence/$', views_api.EventConvergenceRuleList.as_view()),
    url(r'^eventconvergence/(?P<pk>[0-9]+)/$', views_api.EachEventConvergenceRule.as_view()),
    url(r'^sourcelist/$', views_api.SourceList.as_view()),
    url(r'^typelist/$', views_api.TypeList.as_view()),
    url(r'^levellist/$', views_api.LevelList.as_view()),
    url(r'^test/$', views_api.Test.as_view()),
    url(r'^event/frontrightop/$', 'front_right_operate'),
    url(r'^AI/$', 'showAI'),
    url(r'^eventadjustment/$', views_api.EventLevelAdjustmentList.as_view()),
    url(r'^eventadjustment/(?P<pk>[0-9]+)/$', views_api.EachEventLevelAdjustment.as_view()),
    url(r'^eventmask/$', views_api.EventMaskList.as_view()),
    url(r'^eventmask/(?P<pk>[0-9]+)/$', views_api.EachEventMask.as_view()),
    url(r'^event/misinform/$', 'confirm_event_accuracy'),
)