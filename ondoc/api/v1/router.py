from django.urls import path
from .views import OTP

urlpatterns = [
    path('otp/generate', OTP.as_view(), name='otp-generate'),
    # path('test/', PathologyTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', PathologyTestList.as_view({'get': 'retrieve'}), name='test-detail'),
]
