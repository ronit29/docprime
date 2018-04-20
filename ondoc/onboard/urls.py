from django.urls import include, path
from . import views

#from rest_framework.authtoken import views

urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('lab', views.BaseOnboard.as_view(), name='lab'),
    # path('lab', views.lab, name='lab'),
    path('otp', views.otp, name='otp'),
    # path('doctor', views.lab, name='doctor'),
    path('generate-url', views.generate, name='generate-url')
]