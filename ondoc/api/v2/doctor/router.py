from django.urls import path
from . import views

urlpatterns = [
    path('billing_entities', views.DoctorBillingViewSet.as_view({'get': 'list'}), name='billing_entities'),
    path('profile', views.DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('block-calender', views.DoctorBlockCalendarViewSet.as_view({'get': 'list'}), name='block-calender'),
    path('block-calender/create', views.DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),
    path('practice-specializations', views.DoctorDataViewset.as_view({'get': 'get_practice_specializations'}), name='get-practice-specializations'),
    path('doctor-qualifications', views.DoctorDataViewset.as_view({'get': 'get_doctor_qualifications'}), name='get-doctor-qualifications'),
    path('languages', views.DoctorDataViewset.as_view({'get': 'get_languages'}), name='get-languages'),
    path('medical-services', views.DoctorDataViewset.as_view({'get': 'get_doctor_medical_services'}), name='get-doctor-medical-services'),
    path('procedures', views.DoctorDataViewset.as_view({'get': 'get_procedures'}), name='get-procedures'),
    path('specializations', views.DoctorDataViewset.as_view({'get': 'get_specializations'}), name='get-specializations'),
    path('upcoming/appointments', views.AppointmentViewSet.as_view({'get': 'upcoming_appointments'}), name='upcoming_appointments')
]
