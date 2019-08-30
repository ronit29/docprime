from django.urls import path
from .views import PlusListViewSet, PlusOrderViewSet


urlpatterns = [
    path('list', PlusListViewSet.as_view({'get': 'list'}), name='plus-list'),
    path('create', PlusOrderViewSet.as_view({'post': 'create_order'}), name='plus-subscription-create'),
]

