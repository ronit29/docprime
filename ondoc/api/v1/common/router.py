from django.conf.urls import url
from django.urls import path
from ondoc.crm.admin.common import MatrixStateAutocomplete, MatrixCityAutocomplete
from .views import (CitiesViewSet, ServicesViewSet, SmsServiceViewSet, UpdateXlsViewSet, UploadDoctorViewSet,
                    UploadQualificationViewSet, UploadExperienceViewSet, UploadAwardViewSet, UploadHospitalViewSet,
                    UploadMembershipViewSet, SearchLeadViewSet, GetPaymentOptionsViewSet)

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
    url(r'^matrix-city-autocomplete/$', MatrixCityAutocomplete.as_view(), name='matrix-city-autocomplete'),
]