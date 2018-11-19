from django.urls import path
from .views import (DoctorAppointmentsViewSet, DoctorProfileView, DoctorHospitalView,
                    DoctorBlockCalendarViewSet, PrescriptionFileViewset, SearchedItemsViewSet, DoctorListViewSet,
                    DoctorProfileUserViewSet, DoctorAvailabilityTimingViewSet, HealthTipView, ConfigView,
                    DoctorAppointmentNoAuthViewSet, DoctorContactNumberViewSet, DoctorFeedbackViewSet,
                    HospitalAutocomplete, CreateAdminViewSet)

urlpatterns = [
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/create', DoctorAppointmentsViewSet.as_view({'post': 'create'}), name='create-appointment'),
    path('appointment/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}), name='get-appointment-detail'),
    path('appointment/<int:pk>/update', DoctorAppointmentsViewSet.as_view({'post': 'update'}),
         name='update-appointment-detail'),
    path('appointment/complete', DoctorAppointmentsViewSet.as_view({'post': 'complete'}),
         name='appointment-complete'),
    path('noauthappointment/complete', DoctorAppointmentNoAuthViewSet.as_view({'post': 'complete'}),
         name='noauthappointment-complete'),
    path('profile',
         DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('profileuserview/<int:pk>', DoctorProfileUserViewSet.as_view({'get': 'retrieve'}), name='doctor-profile-user-view'),
    path('profileuserviewbyurl', DoctorProfileUserViewSet.as_view({'get': 'retrieve_by_url'}), name='doctor-profile-user-view'),
    path('clinic',
         DoctorHospitalView.as_view({'get': 'list'}), name='doctor-hospital'),
    path('clinic/<int:pk>',
         DoctorHospitalView.as_view({'get': 'retrieve'}), name='doctor-detail-hospital'),
    path('block-calender', DoctorBlockCalendarViewSet.as_view({'get': 'list'}), name='get-block-calender'),
    path('block-calender/create', DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),
    path('block-calender/<int:pk>/delete', DoctorBlockCalendarViewSet.as_view({'post': 'destroy'}),
         name='block-calender-delete'),
    path('prescription-file', PrescriptionFileViewset.as_view({'get': 'list'}), name='upload-list'),
    path('prescription-file/upload', PrescriptionFileViewset.as_view({'post': 'create'}), name='upload-prescription'),
    path('prescription-file/remove', PrescriptionFileViewset.as_view({'delete': 'remove'}), name='remove-prescription'),
    path('searcheditems', SearchedItemsViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('commonconditions', SearchedItemsViewSet.as_view({'get': 'common_conditions'}), name='common-conditions'),
    path('doctorsearch', DoctorListViewSet.as_view({'get': 'list'}), name='search-doctor'),
    path('doctorsearch_by_url', DoctorListViewSet.as_view({'get':'list_by_url'}), name='search_by_specializaton'),
    path('doctortiming', DoctorAvailabilityTimingViewSet.as_view({'get': 'list'}), name='doctor-timing-availability'),
    path('healthtips', HealthTipView.as_view({'get': 'list'}), name='health-tip'),
    path('config', ConfigView.as_view({'post': 'retrieve'}), name='config'),
    # path('test', TestView.as_view({'post': 'retrieve'}), name='test'),
    path('contact-number/<int:doctor_id>', DoctorContactNumberViewSet.as_view({'get':'retrieve'}), name='doctor-contact-number'),
    path('feedback', DoctorFeedbackViewSet.as_view({'post': 'feedback'}), name='doctor-feedback'),
    path('hospital-autocomplete', HospitalAutocomplete.as_view(), name='hospital-autocomplete'),
    path('create_admin', CreateAdminViewSet.as_view({'post': 'create'}), name='create_admin'),
    path('update_admin', CreateAdminViewSet.as_view({'post': 'update'}), name='update_admin'),
    path('list_admin_entities', CreateAdminViewSet.as_view({'get': 'list_entities'}), name='list_entities'),
    path('list_admins', CreateAdminViewSet.as_view({'get': 'list_entity_admins'}), name='list_admins'),
    path('admins_assoc_doctors/<int:pk>', CreateAdminViewSet.as_view({'get': 'assoc_doctors'}), name='assoc_doctors'),
    path('admins_assoc_hosp/<int:pk>', CreateAdminViewSet.as_view({'get': 'assoc_hosp'}), name='assoc_hosp'),
]
