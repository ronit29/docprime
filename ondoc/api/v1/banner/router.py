from django.urls import path
from .views import (BannerListViewSet)

urlpatterns = [
    path('list', BannerListViewSet.as_view({'get': 'list'}), name='banner-list'),

    ]
