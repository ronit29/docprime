from django.urls import path
from .views import ChatSearchedItemsViewSet, DoctorsListViewSet, DoctorProfileViewSet, UserProfileViewSet, \
    ChatPrescriptionViewSet, ChatReferralViewSet, ChatUserViewSet, ChatOrderViewSet, ChatConsultationViewSet, \
    ChatOrderAuthenticatedViewSet

urlpatterns = [
    path('chatsearcheditems', ChatSearchedItemsViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('doctors', DoctorsListViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('doctor/profile/<int:pk>', DoctorProfileViewSet.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('user/profile', UserProfileViewSet.as_view({'get': 'retrieve'}), name='user-profile'),
    path('chatprescription', ChatPrescriptionViewSet.as_view({'get':'retrieve'}), name='chat-prescription'),
    path('getreferral', ChatReferralViewSet.as_view({'post':'retrieve'}), name='get-referral'),
    path('user/login', ChatUserViewSet.as_view({'post':'user_login_via_chat'}), name='chat-user-login'),
    path('order/create', ChatOrderViewSet.as_view({'post': 'create_order'}), name='chat-order-create'),
    path('consultation/cancel', ChatConsultationViewSet.as_view({'post': 'cancel'}), name='chat-consultation-cancel'),
    path('order/status', ChatOrderAuthenticatedViewSet.as_view({'get': 'status'}), name='order-status'),
]
