from django.urls import path
from .views import LoginOTP, User

urlpatterns = [
    path('login/otp/generate', LoginOTP.as_view({'post': 'generate'}), name='otp-generate'),
    #path('otp/verify', OTP.as_view({'post': 'verify'}), name='otp-verify'),
    path('user/login', User.as_view({'post': 'login'}), name='user-login'),
    path('user/register', User.as_view({'post': 'register'}), name='user-register'),

    # path('test/', PathologyTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', PathologyTestList.as_view({'get': 'retrieve'}), name='test-detail'),
]
