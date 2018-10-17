from django.urls import path, re_path
from . import views

from django.contrib.sitemaps.views import sitemap
from ondoc.seo.sitemaps import IndexSitemap
sitemaps = {
    'pages': IndexSitemap
}

urlpatterns = [
    path('index-sitemap.xml', sitemap, {'sitemaps': sitemaps}),
    path('robots.txt', views.robots, name='robots'),
    re_path(r'-sitemap.xml$', views.getsitemap, name='sitemap'),
 ]
