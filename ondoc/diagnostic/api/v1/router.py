from django.urls import path
from .views import LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView
# from rest_framework.routers import DefaultRouter
#
# router = DefaultRouter()
# router.register('test', LabTestList, base_name='LabTest')
#
#
#
# urlpatterns = router.urls
urlpatterns = [
    path('search-pg', SearchPageViewSet.as_view({'get': 'list'}), name='search-lab'),
    path('test', LabTestList.as_view({'get': 'list'}), name='test-list'),
    # path('test/<int:id>/', LabTestList.as_view({'get': 'retrieve'}), name='test-detail'),
    path('lab-list', LabList.as_view({'get': 'list'}), name='lab-list'),
    path('lab-list/<int:lab_id>', LabList.as_view({'get': 'retrieve'}), name='lab-list-detail'),
    path('lab-appointment', LabAppointmentView.as_view({'post': 'create', 'get': 'list'}),
         name='lab-create-appointment'),
    path('lab-appointment/<int:pk>', LabAppointmentView.as_view({'post':'update', 'get': 'retrieve'}),
         name='lab-update-appointment'),
    path('lab-timing', LabTimingListView.as_view({'get': 'list'}),
         name='lab-timing'),
]
