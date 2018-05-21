from django.urls import path
from .views import (DoctorAppointmentsViewSet, DoctorProfileView, DoctorHospitalView,
                    DoctorBlockCalendarViewSet,  PrescriptionFileViewset, SearchedItemsViewSet, DoctorListViewSet,
                    DoctorProfileUserViewSet)

urlpatterns = [
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/create', DoctorAppointmentsViewSet.as_view({'post': 'create'}), name='create-appointment'),
    path('appointment/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}), name='get-appointment-detail'),
    path('appointment/<int:pk>/update', DoctorAppointmentsViewSet.as_view({'post': 'update'}),
         name='update-appointment-detail'),
    path('profile',
         DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('profileuserview/<int:pk>', DoctorProfileUserViewSet.as_view({'get': 'retrieve'}), name='doctor-profile-user-view'),
    path('clinic',
         DoctorHospitalView.as_view({'get': 'list'}), name='doctor-hospital'),
    path('clinic/<int:pk>/',
         DoctorHospitalView.as_view({'get': 'retrieve'}), name='doctor-detail-hospital'),
    path('block-calender', DoctorBlockCalendarViewSet.as_view({'get': 'list'}), name='get-block-calender'),
    path('block-calender/create', DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),
    path('block-calender/<int:pk>/delete', DoctorBlockCalendarViewSet.as_view({'post': 'destroy'}),
         name='block-calender-delete'),
    path('prescription-file', PrescriptionFileViewset.as_view({'get': 'list'}), name='upload-list'),
    path('prescription-file/upload', PrescriptionFileViewset.as_view({'post': 'create'}), name='upload-prescription'),
    path('searcheditems', SearchedItemsViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('doctorsearch', DoctorListViewSet.as_view({'get': 'list'}), name='search-doctor'),
 ]
