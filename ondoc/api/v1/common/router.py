from django.urls import path
from .views import CitiesViewSet, ServicesViewSet

urlpatterns = [
    path('cities/list', CitiesViewSet.as_view({'get': 'list'}), name='cities-list'),
    path('generate/pdf', ServicesViewSet.as_view({'post': 'generatepdf'}, ), name='generate-pdf'),
    # path('send/email', ServicesViewSet.as_view({'post': 'send_email'}, ), name='send-email'),
    # path('send/sms', ServicesViewSet.as_view({'post': 'send_sms'}, ), name='send-sms'),
    path('chat_prescription/<str:name>', ServicesViewSet.as_view({'get': 'download_pdf'}, ), name='download-pdf'),
]