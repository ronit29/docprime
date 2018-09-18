from django.urls import path
from .views import GeoIPAddressURLViewSet


urlpatterns = [
    path('details', GeoIPAddressURLViewSet.as_view({'get': 'ip_details'}), name='ip-address-details'),
]