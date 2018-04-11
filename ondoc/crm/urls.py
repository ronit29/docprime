from django.urls import include, path
from . import views

#from rest_framework.authtoken import views

urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('', views.index, name='index'),

]