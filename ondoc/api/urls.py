from django.conf.urls import url, include
from django.urls import path

from .v1.doctor.router import urlpatterns as doctor_url
from .v1.auth.router import urlpatterns as auth_url


urlpatterns = [
    path('v1/doctor/',include(doctor_url)),
    path('v1/user/',include(auth_url))
]
