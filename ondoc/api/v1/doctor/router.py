from django.urls import path
from .views import DoctorAppointmentsViewSet, DoctorProfileView, DoctorHospitalView

urlpatterns = [
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/create', DoctorAppointmentsViewSet.as_view({'post': 'create'}), name='create-appointment'),
    path('appointment/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}), name='get-appointment-detail'),
    path('appointment/<int:pk>/update', DoctorAppointmentsViewSet.as_view({'post': 'update'}),
         name='update-appointment-detail'),
    path('doctorprofile/<int:pk>/',
         DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('doctorclinic/',
         DoctorHospitalView.as_view({'get': 'list'}), name='doctor-hospital'),
    path('doctorclinic/<int:pk>/',
         DoctorHospitalView.as_view({'get': 'retrieve'}), name='doctor-detail-hospital'),
]