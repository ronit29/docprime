from django.conf.urls import url, include
# from .v1.router import api_urlpatterns as api_v1
from rest_framework.urlpatterns import format_suffix_patterns
from . import views

app_name = 'doctor'
urlpatterns = [
    url(r'^admin/ajax/doctor/crop_doctor_image/', views.crop_doctor_image, name='crop_doctor_image'),
    # url(r'^(?P<version>(v1|v2))/', include(api_v1)),
]

format_suffix_patterns(urlpatterns)