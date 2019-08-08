from django.urls import path
from .views import SalespointAppointmentViewSet


urlpatterns = [
    path('update_booking_status', SalespointAppointmentViewSet.as_view({'post': 'update_status'}), name='appointment-status'),
    path('fetch_status', SalespointAppointmentViewSet.as_view({'get': 'status_list'}), name='appointment-status-list')
]