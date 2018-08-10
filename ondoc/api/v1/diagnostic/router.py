from django.urls import path
from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
                    AvailableTestViewSet)
# from rest_framework.routers import DefaultRouter
#
# router = DefaultRouter()
# router.register('test', LabTestList, base_name='LabTest')
#
#
#
# urlpatterns = router.urls
urlpatterns = [
    #path('block-calender', LabBlockCalendarViewSet.as_view({'get': 'list'}), name='get-lab-block-calender'),
    path('labsearch', SearchPageViewSet.as_view({'get': 'list'}), name='search-lab'),
    path('test', LabTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', LabTestList.as_view({'get': 'retrieve'}), name='test-detail'),
    path('lablist', LabList.as_view({'get': 'list'}), name='lab-list'),
    path('lablist/<int:lab_id>', LabList.as_view({'get': 'retrieve'}), name='lab-list-detail'),
    # path('lab/appointment', LabAppointmentsViewSet.as_view({'get': 'list'}), name='lab-appointment-list'),
    path('labappointment/create', LabAppointmentView.as_view({'post': 'create'}),
         name='lab-create-appointment'),
    path('labappointment', LabAppointmentView.as_view({'get': 'list'}), name='lab-appointment-list'),
    path('labappointment/<int:pk>', LabAppointmentView.as_view({'get': 'retrieve'}), name='get-lab-appointment-detail'),
    path('labappointment/<int:pk>/update', LabAppointmentView.as_view({'post': 'update'}),
         name='update-lab-appointment-detail'),
    # path('labappointment/<int:pk>', LabAppointmentView.as_view({'post':'update', 'get': 'retrieve'}),
    #      name='lab-update-appointment'),
    # path('appointment/payment/retry/<int:pk>', LabAppointmentView.as_view({'get': 'payment_retry'}),
    #      name='payment-retry'),
    path('labtiming', LabTimingListView.as_view({'get': 'list'}),
         name='lab-timing'),
    path('labtest/<int:lab_id>', AvailableTestViewSet.as_view({'get': 'retrieve'}),
         name='lab-available-test'),
]
