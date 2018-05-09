from django.urls import path
from .views import OTP, DoctorAppointmentsViewSet

urlpatterns = [
    path('otp/generate', OTP.as_view(), name='otp-generate'),
    path('doctorappointments', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='doctor-appointments'),
    path('doctorappointments/set-appointment',
         DoctorAppointmentsViewSet.as_view({'post': 'set_appointment'}), name='set-appointment'),
]
