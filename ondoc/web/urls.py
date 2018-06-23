from django.urls import path
from django.conf.urls import url
from . import views


app_name = 'web'
urlpatterns = [
    path('', views.index, name='index'),
    url(r'^careers/', views.careers_page, name='careers_page'),
    url(r'^privacy/', views.privacy_page, name='privacy_page'),
    url(r'^media/', views.media_page, name='media_page'),
]
