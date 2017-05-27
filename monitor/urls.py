from django.conf.urls import patterns, url

urlpatterns = patterns('monitor.views',

    url(r'^hello/$', 'hello'),
    url(r'^alarm/$', 'alarmlist'),
    url(r'^event/$', 'eventlist'),
    url(r'^undoneevent/$', 'undone_event'),
    url(r'^eventfilter/$', 'event_filter_keyword'),
    url(r'^eventconvergence/$', 'event_convergence_rule'),
    url(r'^eventAI/$', 'event_AI'),
    url(r'^srcdtl/$', 'source_detail'),
    url(r'^eventadjust/$', 'event_level_adjustment'),
    url(r'^eventmask/$', 'event_mask'),
    url(r'^eventconfirm/$', 'event_confirmation'),
)
