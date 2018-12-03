from django.urls import path
from .views import GeoIPAddressURLViewSet, AdwordLocationCriteriaViewset


urlpatterns = [
    path('details', GeoIPAddressURLViewSet.as_view({'get': 'ip_details'}), name='ip-address-details'),
    path('detect', GeoIPAddressURLViewSet.as_view({'get':'get_lat_long_city'}), name='lat-long-city'),
    path('adword/<int:criteria_id>', AdwordLocationCriteriaViewset.as_view({'get': 'retrieve'}), name='location-details'),
]