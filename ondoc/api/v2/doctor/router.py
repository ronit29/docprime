from django.urls import path
from . import views

urlpatterns = [
    path('billing_entities', views.DoctorBillingViewSet.as_view({'get': 'list'}), name='billing_entities'),
    path('hosp_data', views.HospitalProviderDataViewSet.as_view({'get': 'list'}), name='hosp_data'),
    path('profile', views.DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('block-calender', views.DoctorBlockCalendarViewSet.as_view({'get': 'list'}), name='block-calender'),
    path('block-calender/create', views.DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),
    path('practice-specializations', views.DoctorDataViewset.as_view({'get': 'get_practice_specializations'}), name='get-practice-specializations'),
    path('doctor-qualifications', views.DoctorDataViewset.as_view({'get': 'get_doctor_qualifications'}), name='get-doctor-qualifications'),
    path('languages', views.DoctorDataViewset.as_view({'get': 'get_languages'}), name='get-languages'),
    path('medical-services', views.DoctorDataViewset.as_view({'get': 'get_doctor_medical_services'}), name='get-doctor-medical-services'),
    path('procedures', views.DoctorDataViewset.as_view({'get': 'get_procedures'}), name='get-procedures'),
    path('specializations', views.DoctorDataViewset.as_view({'get': 'get_specializations'}), name='get-specializations'),
    path('provider-signup/otp', views.ProviderSignupOtpViewset.as_view({'post': 'otp_generate'}), name='otp-generate'),
    path('provider-signup/otp-verification', views.ProviderSignupOtpViewset.as_view({'post': 'otp_verification'}), name='otp-verification'),
    path('provider-signup/add', views.ProviderSignupDataViewset.as_view({'post': 'create'}), name='create-provider-signup'),
    path('provider-signup/consent', views.ProviderSignupDataViewset.as_view({'post': 'consent_is_docprime'}), name='consent-is-docprime'),
    path('encrypt_consent', views.ProviderSignupDataViewset.as_view({'post': 'encrypt_consent'}), name='encrypt_consent'),
    path('provider-signup/add/hospital', views.ProviderSignupDataViewset.as_view({'post': 'create_hospital'}), name='create-hospital'),
    path('provider-signup/add/doctor', views.ProviderSignupDataViewset.as_view({'post': 'create_doctor'}), name='create-doctor'),
    path('provider-signup/add/staffs', views.ProviderSignupDataViewset.as_view({'post': 'create_staffs'}), name='create-staffs'),
    path('provider/update/hospital/consent', views.ProviderSignupDataViewset.as_view({'post': 'update_hospital_consent'}), name='update-hospital-consent'),
    path('invoice/item', views.PartnersAppInvoice.as_view({'post': 'add_or_edit_general_invoice_item'}), name='add-or-edit-general-invoice-item'),
    path('invoice/list/items', views.PartnersAppInvoice.as_view({'get': 'list_invoice_items'}), name='list-invoice-items'),
    path('invoice/create', views.PartnersAppInvoice.as_view({'post': 'create'}), name='create-invoice'),
    path('invoice/update', views.PartnersAppInvoice.as_view({'post': 'update'}), name='update-invoice'),
    path('invoice/<str:encoded_filename>', views.PartnersAppInvoicePDF.as_view({'get': 'download_pdf'}), name='invoice-pdf'),
    path('ecs/create', views.PartnerEConsultationViewSet.as_view({'post': 'create'}), name='ecs_create'),
    path('ecs/list', views.PartnerEConsultationViewSet.as_view({'get': 'list'}), name='ecs_list'),
]


