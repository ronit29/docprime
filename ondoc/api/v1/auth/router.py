from django.urls import path

from ondoc.api.v1.subscription_plan.views import SubscriptionPlanUserViewSet
from .views import (LoginOTP, UserViewset, NotificationEndpointViewSet,
                    UserProfileViewSet, UserAppointmentsViewSet, AddressViewsSet,
                    TransactionViewSet, UserTransactionViewSet, UserIDViewSet, OrderHistoryViewSet,
                    HospitalDoctorAppointmentPermissionViewSet, HospitalDoctorBillingPermissionViewSet,
                    OrderViewSet, ConsumerAccountRefundViewSet, RefreshJSONWebToken, OnlineLeadViewSet, UserLabViewSet,
                    OrderDetailViewSet, UserTokenViewSet, SendBookingUrlViewSet, ContactUsViewSet, CareerViewSet,
                    DoctorNumberAutocomplete, UserLeadViewSet, ReferralViewSet, UserRatingViewSet, AppointmentViewSet,
                    WhatsappOptinViewSet, DoctorScanViewSet, TokenFromUrlKey, ProfileEmailUpdateViewset,
                    BajajAllianzUserViewset)

urlpatterns = [
    path('api-token-refresh', RefreshJSONWebToken.as_view({'post':'refresh'}), name='token-refresh'),
    # path('api-token-verify/', RefreshJSONWebToken.as_view({'post': 'verify'}), name='token-verify'),
    path('otp/generate', LoginOTP.as_view({'post': 'generate'}), name='otp-generate'),
    # path('otp/verify', OTP.as_view({'post': 'verify'}), name='otp-verify'),
    path('login', UserViewset.as_view({'post': 'login'}), name='user-login'),
    path('bagic_user', BajajAllianzUserViewset.as_view({'post': 'user_login_via_bagic'}), name='bagic-login'),
    path('doctor/login', UserViewset.as_view({'post': 'doctor_login'}), name='doctor-login'),
    path('logout', UserViewset.as_view({'post': 'logout'}), name='user-logout'),
    path('doctor/logout', UserViewset.as_view({'post': 'logout'}), name='doctor-logout'),
    path('register', UserViewset.as_view({'post': 'register'}), name='user-register'),
    path('notification/endpoint/save',
         NotificationEndpointViewSet.as_view({'post': 'save'}), name='notification-endpoint-save'),
    path('notification/endpoint/delete',
         NotificationEndpointViewSet.as_view({'post': 'delete'}), name='notification-endpoint-delete'),
    # path('notification', NotificationViewSet.as_view({'get': 'list'}), name='notification-list'),
    path('userprofile', UserProfileViewSet.as_view({'get': 'list'}), name='user-profile-list'),
    path('userprofile/add', UserProfileViewSet.as_view({'post': 'create'}), name='user-profile-add'),
    path('userprofile/<int:pk>/edit', UserProfileViewSet.as_view({'post': 'update'}), name='user-profile-edit'),
    path('userprofile/<int:pk>/upload', UserProfileViewSet.as_view({'post': 'upload'}), name='user-profile-upload'),
    path('userprofile/<int:pk>', UserProfileViewSet.as_view({'get': 'retrieve'}), name='user-profile-retrieve'),
    # path('createpermission', UserPermissionViewSet.as_view({'get': 'list'}), name='user-profile-retrieve'),
    path('appointment', UserAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/<int:pk>', UserAppointmentsViewSet.as_view({'get': 'retrieve'}), name='appointment-detail'),
    path('appointment/<int:pk>/update', UserAppointmentsViewSet.as_view({'post': 'update'}), name='appointment-update'),
    path('address/create', AddressViewsSet.as_view({"post": "create"}), name='address-create'),
    path('address/<int:pk>/delete', AddressViewsSet.as_view({"post": "destroy"}), name='address-delete'),
    path('address/<int:pk>/update', AddressViewsSet.as_view({"post": "update"}), name='address-list'),
    path('address/<int:pk>', AddressViewsSet.as_view({"get": "retrieve"}), name='address-detail'),
    path('address', AddressViewsSet.as_view({"get": "list"}), name='address-list'),
    path('userid', UserIDViewSet.as_view({'get': 'retrieve'}),
         name='get-user-id'),
    path('transaction/save', TransactionViewSet.as_view({'post': 'save'}),
         name='appointment-transaction-save'),
    path('transaction/detail', UserTransactionViewSet.as_view({"get": "list"}), name="user-transaction-details"),
    path('orderhistory', OrderHistoryViewSet.as_view({"get": "list"}), name="order-history"),
    path('managablehospitals', HospitalDoctorAppointmentPermissionViewSet.as_view({"get": "list"}), name="hosp-doc-appointment-permission"),
    path('managebilling', HospitalDoctorBillingPermissionViewSet.as_view({"get": "list"}), name="hosp-doc-billing-permission"),
    path('pgdata/<int:pk>', OrderViewSet.as_view({"get": "retrieve"}), name="pg-order-detail"),
    path('refund', ConsumerAccountRefundViewSet.as_view({"post": "refund"}), name="consumer-refund"),
    path('onlinelead/create', OnlineLeadViewSet.as_view({"post": "create"}), name='doctor-signup'),
    path('userlead/create', UserLeadViewSet.as_view({"post": "create"}), name='user-signup'),
    path('manageablelabs', UserLabViewSet.as_view({"get": "list"}), name='user-manageable-labs'),
    path('order/send', SendBookingUrlViewSet.as_view({"post": "send_booking_url"}), name='send-booking-url'),
    path('order/<int:order_id>', OrderDetailViewSet.as_view({"get": "details"}), name='extract-order-detail'),
    path('order/summary/<int:order_id>', OrderDetailViewSet.as_view({"get": "summary"}), name='extract-order-summary'),
    path('token/exchange', UserTokenViewSet.as_view({"get": "details"}), name='create-user-token'),
    path('careers/upload', CareerViewSet.as_view({"post":"upload"}), name='careers-resume-upload'),
    path('contactus', ContactUsViewSet.as_view({'post': 'create'}), name='create-contact-us'),
    path('docnumber-autocomplete', DoctorNumberAutocomplete.as_view(), name='docnumber-autocomplete'),
    path('referral', ReferralViewSet.as_view({'get': 'retrieve'}), name='referral'),
    path('referral/<str:code>', ReferralViewSet.as_view({'get': 'retrieve_by_code'}), name='retrieve_by_code'),
    path('myratings', UserRatingViewSet.as_view({'get': 'list_ratings'}), name='list_ratings'),
    path('whatsapp-optin', WhatsappOptinViewSet.as_view({'post': 'update'}), name='whatsapp-optin'),
    path('upcoming/appointments',AppointmentViewSet.as_view({'get': 'upcoming_appointments'}), name='upcoming_appointments'),
    path('subscription_plan', SubscriptionPlanUserViewSet.as_view({'get': 'subscription_plan'}), name='user_subscription_plan'),
    path('appointment_qr_scan/<int:pk>', DoctorScanViewSet.as_view({'post': 'doctor_qr_scan'}), name='doctor_qr_scan'),
    path('get-token', TokenFromUrlKey.as_view({'get': 'get_token'}), name='get-token-from-url-key'),
    # path('test/', PathologyTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', PathologyTestList.as_view({'get': 'retrieve'}), name='test-detail'),
    path('profile-email/update/init', ProfileEmailUpdateViewset.as_view({'post': 'create'}), name='update-profile-email-init'),
    path('profile-email/update', ProfileEmailUpdateViewset.as_view({'post': 'update_email'}), name='update-profile-email')
]
