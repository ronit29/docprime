from django.urls import path
from . import views

urlpatterns = [
    path('billing_entities', views.DoctorBillingViewSet.as_view({'get': 'list'}), name='billing_entities'),
    path('profile', views.DoctorProfileView.as_view({'get': 'retrieve'}), name='doctor-profile'),
    path('block-calender/create', views.DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),

]
