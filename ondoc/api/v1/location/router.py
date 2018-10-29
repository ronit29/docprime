from django.urls import path
from .views import SearchUrlsViewSet

urlpatterns = [
    path('entity/list', SearchUrlsViewSet.as_view({'get': 'list'}), name='entity-list'),
    path('entity/detail', SearchUrlsViewSet.as_view({'get': 'retrieve'}), name='entity-detail'),
    path('city-inventory', SearchUrlsViewSet.as_view({'get': 'list_cities'}), name='list-all-cities'),
    path('city-inventory/<str:city>', SearchUrlsViewSet.as_view({'get': 'list_urls_by_city'}), name='list-all-urls-by-specialization-in-city'),
    path('speciality-inventory', SearchUrlsViewSet.as_view({'get': 'specialists_list'}), name='specialists_list'),
    path('speciality-inventory/<int:specialization_id>', SearchUrlsViewSet.as_view({'get': 'specialities_in_localities_list'}), name='top-popular-specialists'),
]
