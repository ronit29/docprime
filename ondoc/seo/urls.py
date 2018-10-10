from django.urls import path
from . import views

from django.contrib.sitemaps.views import sitemap
from ondoc.seo.sitemaps import IndexSitemap
sitemaps = {
    'pages': IndexSitemap
}

urlpatterns = [
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}),
    path('robots.txt', views.robots, name='robots'),
 ]
