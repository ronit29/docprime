from django.urls import path
from . import views


urlpatterns = [
    path('sitemap.xml', views.index, name='sitemap'),
    path('robots.txt', views.robots, name='robots'),
 ]
