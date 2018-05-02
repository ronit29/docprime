from django.conf.urls import url, include
from .v1.router import api_urlpatterns as api_v1
from .v1.views import GenericSearchView
from rest_framework.urlpatterns import format_suffix_patterns


urlpatterns = [
    url(r'^(?P<version>(v1|v2))/', include(api_v1)),
]

format_suffix_patterns(urlpatterns)