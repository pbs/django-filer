#-*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('filer.server.views',
    url(r'^(?P<path>.*)$', 'serve_protected_file',),
)
