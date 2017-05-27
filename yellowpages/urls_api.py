from django.conf.urls import patterns,url
from yellowpages import views_api

urlpatterns=patterns('yellowpages.views_api',
                     url(r'^pool/dependence/$','PooldependenceList'),
                     url(r'^config/calllist/$','ConfigCallList'),
                     )
