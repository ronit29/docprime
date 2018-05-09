from django.conf.urls import url, include
from django.urls import path

from .v1.doctor.router import urlpatterns as doctor_url

from rest_framework.urlpatterns import format_suffix_patterns


urlpatterns = [
    path('v1/',include(doctor_url))
    #url(r'^(?P<version>(v1|v2))/', include(v1)),
]

# format_suffix_patterns(urlpatterns)