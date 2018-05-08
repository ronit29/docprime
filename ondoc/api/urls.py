from django.conf.urls import url, include
from django.urls import path

from .v1.router import urlpatterns as v1

from rest_framework.urlpatterns import format_suffix_patterns


urlpatterns = [
    path('v1/',include(v1))
    #url(r'^(?P<version>(v1|v2))/', include(v1)),
]

# format_suffix_patterns(urlpatterns)