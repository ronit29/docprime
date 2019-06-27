from django.urls import path

from .views import SearchUrlsViewSet, DoctorsCitySearchViewSet

urlpatterns = [
    path('entity/list', SearchUrlsViewSet.as_view({'get': 'list'}), name='entity-list'),
    path('entity/detail', SearchUrlsViewSet.as_view({'get': 'retrieve'}), name='entity-detail'),
    path('city-inventory', SearchUrlsViewSet.as_view({'get': 'list_cities'}), name='list-all-cities'),
    path('city-inventory/<str:city>', SearchUrlsViewSet.as_view({'get': 'list_urls_by_city'}), name='list-all-urls-by-specialization-in-city'),
    path('speciality-inventory', SearchUrlsViewSet.as_view({'get': 'specialists_list'}), name='specialists_list'),
    path('speciality-inventory/<int:specialization_id>', SearchUrlsViewSet.as_view({'get': 'specialities_in_localities_list'}), name='top-popular-specialists'),
    path('static-footer', SearchUrlsViewSet.as_view({'get': 'static_footer'}), name='static-footer-throughout-website'),
    path('dynamicfooters', DoctorsCitySearchViewSet.as_view({'get': 'footer_api'}), name='footer_api'),
    path('static-speciality-footer', SearchUrlsViewSet.as_view({'get': 'top_specialities_in_top_cities'}),
         name='top_specialities_in_top_cities'),
    path('city-inventory-hospitals', SearchUrlsViewSet.as_view({'get': 'list_cities_for_hospitals'}), name='list-all-cities'),
]
