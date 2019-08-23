from django.urls import path
from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
                    AvailableTestViewSet, LabReportFileViewset, DoctorLabAppointmentsViewSet,
                    DoctorLabAppointmentsNoAuthViewSet, TestDetailsViewset, LabTestCategoryListViewSet,
                    CompareLabPackagesViewSet, DigitalReports, LabTestCategoryLandingUrlViewSet,
                    IPDMedicinePageLeadViewSet)

# from rest_framework.routers import DefaultRouter
#
# router = DefaultRouter()
# router.register('test', LabTestList, base_name='LabTest')
#
#
#
# urlpatterns = router.urls
urlpatterns = [
    # path('block-calender', LabBlockCalendarViewSet.as_view({'get': 'list'}), name='get-lab-block-calender'),
    path('labsearch', SearchPageViewSet.as_view({'get': 'list'}), name='search-lab'),
    path('test', LabTestList.as_view({'get': 'list'}), name='test-list'),
    path('package', LabTestList.as_view({'get': 'autocomplete_packages'}), name='package-autocomplete'),
    path('packagelist', LabList.as_view({'get': 'list_packages'}), name='package-list'),
    path('package_list', LabList.as_view({'get': 'package_list'}), name='package-list'),
    # path('test/<int:id>/', LabTestList.as_view({'get': 'retrieve'}), name='test-detail'),
    path('lablist', LabList.as_view({'get': 'list'}), name='lab-list'),
    path('labnetworksearch', LabList.as_view({'get': 'search'}), name='lab-network-search'),
    path('labnetworksearchbyurl',LabList.as_view({'get': 'search_by_url'}), name='lab-network-search-by-url'),
    path('lablist_by_url', LabList.as_view({'get': 'list_by_url'}), name='search_by_city'),
    path('lablist/<int:lab_id>', LabList.as_view({'get': 'retrieve'}), name='lab-list-detail'),
    path('lablistbyurl', LabList.as_view({'get': 'retrieve_by_url'}), name='lab-list-by-url'),
    path('testbyurl', LabList.as_view({'get': 'retrieve_test_by_url'}), name='retrieve-test-by-url'),
    # path('lab/appointment', LabAppointmentsViewSet.as_view({'get': 'list'}), name='lab-appointment-list'),
    path('labappointment/create', LabAppointmentView.as_view({'post': 'create'}),
         name='lab-create-appointment'),
    path('labappointment', LabAppointmentView.as_view({'get': 'list'}), name='lab-appointment-list'),
    path('labappointment/<int:pk>', LabAppointmentView.as_view({'get': 'retrieve'}), name='get-lab-appointment-detail'),
    # path('labappointment/<int:pk>', LabAppointmentView.as_view({'get': 'retrieve_by_lab_id'}), name='get-lab-appointment-detail-by-lab'),
    path('labappointment/<int:pk>/update', LabAppointmentView.as_view({'post': 'update'}),
         name='update-lab-appointment-detail'),
    # path('labappointment/<int:pk>', LabAppointmentView.as_view({'post':'update', 'get': 'retrieve'}),
    #      name='lab-update-appointment'),
    # path('appointment/payment/retry/<int:pk>', LabAppointmentView.as_view({'get': 'payment_retry'}),
    #      name='payment-retry'),
    path('labtiming', LabTimingListView.as_view({'get': 'list'}),
         name='lab-timing'),
    path('labtiming_new', LabTimingListView.as_view({'get': 'list_new'}),
         name='lab-timing-new'),
    path('labtiming_v2', LabTimingListView.as_view({'get': 'list_v2'}),
         name='lab-timing-v2'),
    path('labtest/<int:lab_id>', AvailableTestViewSet.as_view({'get': 'retrieve'}),
         name='lab-available-test'),
    path('lab-report-file', LabReportFileViewset.as_view({'get': 'list'}), name='lab-upload-list'),
    path('lab-report-file/upload', LabReportFileViewset.as_view({'post': 'create'}), name='upload-lab-prescription'),
    path('labappointment/complete', DoctorLabAppointmentsViewSet.as_view({'post': 'complete'}),
         name='lab-appointment-complete'),
    path('appointment/complete', DoctorLabAppointmentsNoAuthViewSet.as_view({'post': 'complete'}),
         name='appointment-complete'),
    path('test/details', TestDetailsViewset.as_view({'get': 'retrieve'}), name='test-details'),
    path('test/details_by_url', TestDetailsViewset.as_view({'get': 'retrieve_test_by_url'}), name='test-details-by-url'),
    path('test/list_by_alphabet', TestDetailsViewset.as_view({'get':'list_by_alphabet'}), name='list-test-by-alphabet'),
    path('test/category', LabTestCategoryListViewSet.as_view({'get': 'list'}), name='test-category'),
    path('compare_lab_packages', CompareLabPackagesViewSet.as_view({'post': 'retrieve'}), name='lab_packages_comparison'),
    path('compare_lab_packages_by_url', CompareLabPackagesViewSet.as_view({'post': 'retrieve_by_url'}), name='lab_packages_comparison_by_url'),
    # path('digital/report/<int:booking_id>', DigitalReports.as_view({'get': 'retrieve'}), name='digital_report'),
    path('lab-test-category-landing-urls', LabTestCategoryLandingUrlViewSet.as_view({'get': 'category_landing_url'}), name='lab_test_category_landing_urls'),
    path('ipdmedicinepagelead', IPDMedicinePageLeadViewSet.as_view({'post': 'store'}), name='ipd_medicine_page_lead'),
]
