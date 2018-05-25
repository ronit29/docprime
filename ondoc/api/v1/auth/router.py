from django.urls import path
from .views import LoginOTP, UserViewset, NotificationEndpointViewSet, NotificationViewSet, UserProfileViewSet

urlpatterns = [
    path('otp/generate', LoginOTP.as_view({'post': 'generate'}), name='otp-generate'),
    #path('otp/verify', OTP.as_view({'post': 'verify'}), name='otp-verify'),
    path('login', UserViewset.as_view({'post': 'login'}), name='user-login'),
    path('doctor/login', UserViewset.as_view({'post': 'doctor_login'}), name='doctor-login'),
    path('register', UserViewset.as_view({'post': 'register'}), name='user-register'),
    path('notification/endpoint/save',
         NotificationEndpointViewSet.as_view({'post': 'save'}), name='notification-endpoint-save'),
    path('notification/endpoint/delete',
         NotificationEndpointViewSet.as_view({'post': 'delete'}), name='notification-endpoint-delete'),
    path('notification', NotificationViewSet.as_view({'get': 'list'}), name='notification-list'),
    path('userprofile', UserProfileViewSet.as_view({'get': 'list'}), name='user-profile-list'),
    path('userprofile/add', UserProfileViewSet.as_view({'post': 'create'}), name='user-profile-add'),
    path('userprofile/<int:pk>/edit', UserProfileViewSet.as_view({'post': 'update'}), name='user-profile-edit'),
    path('userprofile/<int:pk>', UserProfileViewSet.as_view({'get': 'retrieve'}), name='user-profile-retrieve'),

    # path('test/', PathologyTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', PathologyTestList.as_view({'get': 'retrieve'}), name='test-detail'),
]
