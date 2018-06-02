from django.urls import include, path
from django.conf import settings
from . import views

#from rest_framework.authtoken import views

app_name = 'crm'
urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('', views.index, name='index'),
]

if settings.DEBUG:
    urlpatterns += [path('api-login/', views.login, name='login')]