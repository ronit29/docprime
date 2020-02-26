from django.urls import path
from .views import (BannerListViewSet)

urlpatterns = [
    path('list', BannerListViewSet.as_view({'get': 'list'}), name='banner-list'),
    path('detail/<int:pk>', BannerListViewSet.as_view({'get': 'details'}), name='banner-details'),

    ]
