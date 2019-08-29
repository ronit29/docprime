from django.urls import path
from .views import PlusListViewSet


urlpatterns = [
    path('list', PlusListViewSet.as_view({'get': 'list'}), name='plus-list'),
]

