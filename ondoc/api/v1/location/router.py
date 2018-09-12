from django.urls import path
from .views import SearchUrlsViewSet

urlpatterns = [
    path('entity/list', SearchUrlsViewSet.as_view({'get': 'list'}), name='entity-list'),
]
