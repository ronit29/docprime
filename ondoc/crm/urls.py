from django.urls import include, path
from rest_framework.authtoken import views

urlpatterns = [
    path('auth/', views.obtain_auth_token),
]