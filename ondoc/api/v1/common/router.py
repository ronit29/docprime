from django.conf.urls import url
from django.urls import path
from ondoc.crm.admin.common import MatrixStateAutocomplete, MatrixCityAutocomplete, LabPricingAutocomplete, \
                                   RelatedHospitalAutocomplete
from .views import (CitiesViewSet, ServicesViewSet, SmsServiceViewSet, UpdateXlsViewSet, UploadDoctorViewSet,
                    UploadQualificationViewSet, UploadExperienceViewSet, UploadAwardViewSet, UploadHospitalViewSet,
                    UploadMembershipViewSet, SearchLeadViewSet, GetPaymentOptionsViewSet, GetSearchUrlViewSet,
                    GetKeyDataViewSet, AllUrlsViewset, DeviceDetailsSave, AppointmentPrerequisiteViewSet,

                    SiteSettingsViewSet, DepartmentRouting, CommentViewSet, DocumentUploadViewSet,
                    SponsorListingViewSet, AppointmentUtilityViewSet, GeneralLeadViewSet)
                    # SponsorListingViewSet)


urlpatterns = [
    path('cities/list', CitiesViewSet.as_view({'get': 'list'}), name='cities-list'),
    path('generate/pdf', ServicesViewSet.as_view({'post': 'generatepdf'}, ), name='generate-pdf'),
    path('generate/pdf2', ServicesViewSet.as_view({'post': 'generate_pdf_template'}, ), name='generate-pdf2'),
    path('send/email', ServicesViewSet.as_view({'post': 'send_email'}, ), name='send-email'),
    path('send/sms', SmsServiceViewSet.as_view({'post': 'send_sms'}, ), name='send-sms'),
    # path('update_xl', UpdateXlsViewSet.as_view({'post': 'update'}, ), name='update-xl'),
    path('upload_doctor', UploadDoctorViewSet.as_view({'post': 'upload'}, ), name='update-doctor'),
    path('upload_qualification', UploadQualificationViewSet.as_view({'post': 'upload'}, ), name='update-doctor'),
    path('upload_experience', UploadExperienceViewSet.as_view({'post': 'upload'}, ), name='update-experience'),
    path('upload_membership', UploadMembershipViewSet.as_view({'post': 'upload'}, ), name='update-membership'),
    path('upload_hospital', UploadHospitalViewSet.as_view({'post': 'upload'}, ), name='update-hospital'),
    path('upload_award', UploadAwardViewSet.as_view({'post': 'upload'}, ), name='update-award'),
    path('chat_prescription/<str:name>', ServicesViewSet.as_view({'get': 'download_pdf'}, ), name='download-pdf'),
    path('search-lead/create', SearchLeadViewSet.as_view({'post': 'create'}, ), name='create-search-lead'),
    path('payment-options', GetPaymentOptionsViewSet.as_view({'get':'list'},), name='payment_options'),
    url(r'^matrix-state-autocomplete/$', MatrixStateAutocomplete.as_view(), name='matrix-state-autocomplete'),
    url(r'^labpricing-autocomplete/$', LabPricingAutocomplete.as_view(), name='labpricing-autocomplete'),
    url(r'^matrix-city-autocomplete/$', MatrixCityAutocomplete.as_view(), name='matrix-city-autocomplete'),
    url(r'^related-hospital-autocomplete/$', RelatedHospitalAutocomplete.as_view(), name='related-hospital-autocomplete'),
    path('get_search_url', GetSearchUrlViewSet.as_view({'get':'search_url'}), name='get-search-url'),
    path('get_key_data', GetKeyDataViewSet.as_view({'get':'list'}), name='get-key-data'),
    path('entity-compare-autocomplete', AllUrlsViewset.as_view({'get':'list'}), name='entity-compare-autocomplete'),
    path('device-details/save', DeviceDetailsSave.as_view({'post': 'save'}), name='device-details'),
    # url(r'^insurer-autocomplete/$', InsurerAutocomplete.as_view(), name='insurer-autocomplete'),
    # url(r'^insurance-plan-autocomplete/$', InsurancePlanAutocomplete.as_view(), name='insurance-plan-autocomplete'),
    path('pre-booking', AppointmentPrerequisiteViewSet.as_view({'post': 'pre_booking'}), name='pre-booking'),
    path('settings', SiteSettingsViewSet.as_view({'get': 'get_settings'}), name='pre-get_settings'),
    path('get_department_for_routing', DepartmentRouting.as_view({'get': 'get_department'}), name='get-department'),
    path('comment/post', CommentViewSet.as_view({'post': 'create'}), name='post-comment'),
    path('comment/list', CommentViewSet.as_view({'get': 'list'}), name='list-comment'),
    path('sponsorlisting', SponsorListingViewSet.as_view({'get': 'list'}), name='sponsor-listing'),
    path('upload/document-proof', DocumentUploadViewSet.as_view({'post': 'upload_document_proofs'}), name='upload_prescription'),
    path('predicted-price-via-plan/<str:service_type>', AppointmentUtilityViewSet.as_view({'post': 'get_prices'}), name='get_prices'),
    path('push-leads', GeneralLeadViewSet.as_view({'post': 'create_lead'}), name='create_lead')
]