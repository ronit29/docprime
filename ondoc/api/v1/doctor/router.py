from django.urls import path
from .views import OTP, DoctorAppointmentsViewSet

urlpatterns = [
    path('otp/generate', OTP.as_view(), name='otp-generate'),
    path('doctorappointments', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='doctor-appointments-list'),
    path('doctorappointments/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}),
         name='doctor-appointments-detail'),
    path('doctorappointments/set-appointment',
         DoctorAppointmentsViewSet.as_view({'post': 'set_appointment'}), name='set-appointment'),
    path('doctorappointments/<int:pk>/update-status',
         DoctorAppointmentsViewSet.as_view({'post': 'update_status'}), name='update-status'),
]
