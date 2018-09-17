from django.urls import path
from .views import CitiesViewSet, ServicesViewSet, SmsServiceViewSet, UpdateXlsViewSet

urlpatterns = [
    path('cities/list', CitiesViewSet.as_view({'get': 'list'}), name='cities-list'),
    path('generate/pdf', ServicesViewSet.as_view({'post': 'generatepdf'}, ), name='generate-pdf'),
    path('generate/pdf2', ServicesViewSet.as_view({'post': 'generate_pdf_template'}, ), name='generate-pdf2'),
    path('send/email', ServicesViewSet.as_view({'post': 'send_email'}, ), name='send-email'),
    path('send/sms', SmsServiceViewSet.as_view({'post': 'send_sms'}, ), name='send-sms'),
    # path('update_xl', UpdateXlsViewSet.as_view({'post': 'update'}, ), name='update-xl'),
    path('chat_prescription/<str:name>', ServicesViewSet.as_view({'get': 'download_pdf'}, ), name='download-pdf'),
]