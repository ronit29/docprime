from django.conf.urls import url
from django.urls import path
from django.views.generic import TemplateView

from .views import (DoctorAppointmentsViewSet, DoctorProfileView, DoctorHospitalView,
                    DoctorBlockCalendarViewSet, PrescriptionFileViewset, SearchedItemsViewSet, DoctorListViewSet,
                    DoctorProfileUserViewSet, DoctorAvailabilityTimingViewSet, HealthTipView, ConfigView,
                    DoctorAppointmentNoAuthViewSet, DoctorContactNumberViewSet, DoctorFeedbackViewSet,
                    HospitalAutocomplete, CreateAdminViewSet, OfflineCustomerViewSet, HospitalNetworkListViewset,
                    AppointmentMessageViewset, IpdProcedureViewSet, HospitalViewSet, IpdProcedureSyncViewSet,
                    PracticeSpecializationAutocomplete, SimilarSpecializationGroupAutocomplete, create_record,
                    RecordAPIView, record_map)

urlpatterns = [
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/create', DoctorAppointmentsViewSet.as_view({'post': 'create'}), name='create-appointment'),
    path('appointment/cod-to-prepaid/create', DoctorAppointmentsViewSet.as_view({'post': 'create_new'}), name='cod-to-prepaid-appointment'),
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
    path('top/hospitals', SearchedItemsViewSet.as_view({'get': 'top_hospitals'}), name='top-hopspitals'),
    path('doctorsearch', DoctorListViewSet.as_view({'get': 'list'}), name='search-doctor'),
    path('doctorsearchbyhospital', DoctorListViewSet.as_view({'get':'search_by_hospital'}), name='search-doctor-by-hospital'),
    path('doctorsearch_by_url', DoctorListViewSet.as_view({'get':'list_by_url'}), name='search_by_specializaton'),
    path('doctortiming', DoctorAvailabilityTimingViewSet.as_view({'get': 'list'}), name='doctor-timing-availability'),
    path('doctortiming_new', DoctorAvailabilityTimingViewSet.as_view({'get': 'list_new'}), name='doctor-timing-availability-new'),
    path('doctortiming_v2', DoctorAvailabilityTimingViewSet.as_view({'get': 'list_v2'}), name='doctor-timing-availability-newest'),
    path('healthtips', HealthTipView.as_view({'get': 'list'}), name='health-tip'),
    path('config', ConfigView.as_view({'post': 'retrieve'}), name='config'),
    # path('test', TestView.as_view({'post': 'retrieve'}), name='test'),
    path('contact-number/<int:doctor_id>', DoctorContactNumberViewSet.as_view({'get':'retrieve'}), name='doctor-contact-number'),
    path('feedback', DoctorFeedbackViewSet.as_view({'post': 'feedback'}), name='doctor-feedback'),
    path('hospital-autocomplete', HospitalAutocomplete.as_view(), name='hospital-autocomplete'),
    path('practicespecialization-autocomplete', PracticeSpecializationAutocomplete.as_view(), name='practicespecialization-autocomplete'),
    path('similarspecializationgroup-autocomplete', SimilarSpecializationGroupAutocomplete.as_view(), name='similarspecializationgroup-autocomplete'),
    path('create_admin', CreateAdminViewSet.as_view({'post': 'create'}), name='create_admin'),
    path('update_admin', CreateAdminViewSet.as_view({'post': 'update'}), name='update_admin'),
    path('delete_admin', CreateAdminViewSet.as_view({'post': 'delete'}), name='delete_admin'),
    path('list_admin_entities', CreateAdminViewSet.as_view({'get': 'list_entities'}), name='list_entities'),
    path('list_admins', CreateAdminViewSet.as_view({'get': 'list_entity_admins'}), name='list_admins'),
    path('admins_assoc_doctors/<int:pk>', CreateAdminViewSet.as_view({'get': 'assoc_doctors'}), name='assoc_doctors'),
    path('admins_assoc_hosp/<int:pk>', CreateAdminViewSet.as_view({'get': 'assoc_hosp'}), name='assoc_hosp'),
    path('create_offline_appointments', OfflineCustomerViewSet.as_view({'post': 'create_offline_appointments'}), name='create_offline_appointments'),
    path('create_offline_patients', OfflineCustomerViewSet.as_view({'post': 'create_offline_patients'}), name='create_offline_patients'),
    path('update_offline_appointments', OfflineCustomerViewSet.as_view({'post': 'update_offline_appointments'}), name='update_offline_appointments'),
    path('offline_timings', OfflineCustomerViewSet.as_view({'get': 'offline_timings'}), name='offline_timings'),
    path('list_patients', OfflineCustomerViewSet.as_view({'get': 'list_patients'}), name='list_patients'),
    path('list_appointments', OfflineCustomerViewSet.as_view({'get': 'list_appointments'}), name='list_appointments'),
    path('list_hospital/<int:hospital_network_id>', HospitalNetworkListViewset.as_view({'get':'list'}),name='list_hospital'),
    path('send_message', AppointmentMessageViewset.as_view({'post': 'send_message'}), name='send_message'),
    path('request_encryption_key', AppointmentMessageViewset.as_view({'post': 'encryption_key_request_message'}), name='encryption_key_request_message'),
    path('ipd_procedure/list_by_alphabet', IpdProcedureViewSet.as_view({'get': 'list_by_alphabet'}), name='list_ipd_procedure_by_alphabet'),
    path('ipd_procedure_by_url/<str:url>', IpdProcedureViewSet.as_view({'get': 'ipd_procedure_detail_by_url'}), name='ipd_procedure_detail_by_url'),
    path('ipd_procedure/<int:pk>', IpdProcedureViewSet.as_view({'get': 'ipd_procedure_detail'}), name='ipd_procedure_detail'),
    path('hospitalsearch_by_url/<str:url>', HospitalViewSet.as_view({'get': 'list_by_url'}), name='hospitals_by_url'),
    path('ipd_procedure/<int:ipd_pk>/hospitals', HospitalViewSet.as_view({'get': 'list'}), name='ipd_procedure_hospitals'),
    path('hospital/<int:pk>', HospitalViewSet.as_view({'get': 'retrive'}), name='hospital_detail'),
    path('hospitals', HospitalViewSet.as_view({'get': 'list'}), name='hospitals_list'),
    path('hospital_by_url', HospitalViewSet.as_view({'get': 'retrieve_by_url'}), name='hospital_detail_by_url'),
    path('ipd_procedure/create_lead', IpdProcedureViewSet.as_view({'post': 'create_lead'}), name='ipd_procedure_lead'),
    path('ipd_procedure/update_lead', IpdProcedureViewSet.as_view({'post': 'update_lead'}), name='ipd_procedure_lead_update'),
    path('ipd_procedure/sync_lead', IpdProcedureSyncViewSet.as_view({'post': 'sync_lead'}), name='ipd_procedure_sync_lead'),
    path('licence/update', DoctorProfileView.as_view({'post': 'licence_update'}), name='licence_update'),
    path('hospital/filter', DoctorListViewSet.as_view({'get': 'hosp_filtered_list'}), name='hospital-filter-in-doctor-search'),
    path('speciality/filter', DoctorListViewSet.as_view({'get': 'speciality_filtered_list'}), name='speciality-filter-in-doctor-search'),
    path('hospitals_near_you', HospitalViewSet.as_view({'get': 'near_you_hospitals'}), name='hospitals-near-you'),
    url(r'^$', TemplateView.as_view(template_name='doctor/home.html'), name='home'),
    url(r'^create/$', create_record, name="create_record"),
    url('record_api', RecordAPIView.as_view({'get': 'list'}), name="record API"),
    url(r'^view/$', record_map, name="record map"),
]

