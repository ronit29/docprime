from django.urls import path
from .views import CitiesViewSet

urlpatterns = [
    path('cities/list', CitiesViewSet.as_view({'get': 'list'}), name='cities-list'),
]
