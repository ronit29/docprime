from django.urls import include, path
from . import views

#from rest_framework.authtoken import views

urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('lab', views.lab, name='lab'),
    path('doctor', views.lab, name='doctor')
]