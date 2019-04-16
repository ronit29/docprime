from django.urls import path
from .views import ChatSearchedItemsViewSet, DoctorsListViewSet, DoctorProfileViewSet, UserProfileViewSet, \
    ChatPrescriptionViewSet, ChatReferralViewSet

urlpatterns = [
    path('chatsearcheditems', ChatSearchedItemsViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('doctors', DoctorsListViewSet.as_view({'get': 'list'}), name='searched-items'),
    path('doctor/profile/<int:pk>', DoctorProfileViewSet.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('user/profile', UserProfileViewSet.as_view({'get': 'retrieve'}), name='user-profile'),
    path('chatprescription', ChatPrescriptionViewSet.as_view({'get':'retrieve'}), name='chat-prescription'),
    path('getreferral', ChatReferralViewSet.as_view({'post':'retrieve'}), name='get-referral'),
]
