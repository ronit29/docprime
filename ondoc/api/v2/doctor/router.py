from django.urls import path
from .views import DoctorBillingViewSet, DoctorBlockCalendarViewSet

urlpatterns = [
    path('billing_entities', DoctorBillingViewSet.as_view({'get': 'list'}), name='billing_entities'),
    path('block-calender/create', DoctorBlockCalendarViewSet.as_view({'post': 'create'}), name='block-calender-create'),

]
