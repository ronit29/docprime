from django.urls import path
from .views import DoctorAppointmentsViewSet

urlpatterns = [
    
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='doctor-appointments-list'),
    path('appointment/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}),
         name='doctor-appointments-detail'),
    path('appointment/set-appointment',
         DoctorAppointmentsViewSet.as_view({'post': 'set_appointment'}), name='set-appointment'),
    path('appointment/<int:pk>/update-status',
         DoctorAppointmentsViewSet.as_view({'post': 'update_status'}), name='update-status'),
]
