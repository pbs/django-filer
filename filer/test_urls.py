#-*- coding: utf-8 -*-
from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('filer.server.urls'))
]