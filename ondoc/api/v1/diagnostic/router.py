from django.urls import path
from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
                    AvailableTestViewSet, AddressViewsSet)
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
    path('address/create', AddressViewsSet.as_view({"post": "create"}), name='address-create'),
    path('address/<int:pk>/delete', AddressViewsSet.as_view({"post": "destroy"}), name='address-delete'),
    path('address/<int:pk>', AddressViewsSet.as_view({"get": "retrieve"}), name='address-detail'),
    path('address', AddressViewsSet.as_view({"get": "list"}), name='address-list'),

    path('lab-timing', LabTimingListView.as_view({'get': 'list'}),
         name='lab-timing'),
    path('lab-test/<int:lab_id>', AvailableTestViewSet.as_view({'get': 'retrive'}),
         name='lab-available-test'),
]
