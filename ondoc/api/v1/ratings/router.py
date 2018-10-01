from django.urls import path
#from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
#                    AvailableTestViewSet, LabReportFileViewset, DoctorLabAppointmentsViewSet, DoctorLabAppointmentsNoAuthViewSet)
from .views import RatingsViewSet

from .views import GetComplimentViewSet

urlpatterns = [
    path('create', RatingsViewSet.as_view({'post': 'create'}), name='submit-rating'),
    path('list', RatingsViewSet.as_view({'get': 'list'}), name='get-ratings'),
    path('retrieve/<int:pk>', RatingsViewSet.as_view({'get': 'retrieve'}), name='get-ratings'),
    path('getcompliments', GetComplimentViewSet.as_view({'get': 'get_compliments'}), name='get-compliments'),
]

