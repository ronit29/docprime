# base/router.py
from django.conf.urls import url
from .views import DoctorView, GenericSearchView, DoctorAvailability, DoctorProfile
from rest_framework import routers, serializers, viewsets


router = routers.DefaultRouter()

# router.register(r'doctors', DoctorViewSet)


urlpatterns = [
    url(r'^search', GenericSearchView.as_view()), 
    url(r'^doctors', DoctorView.as_view()), 
    url(r'^availability', DoctorAvailability.as_view()),
    url(r'^profile', DoctorProfile.as_view())
]

api_urlpatterns = urlpatterns + router.urls