from django.urls import path
#from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
#                    AvailableTestViewSet, LabReportFileViewset, DoctorLabAppointmentsViewSet, DoctorLabAppointmentsNoAuthViewSet)
from .views import SubmitRatingViewSet
from .views import GetRatingViewSet
from .views import GetComplimentViewSet

urlpatterns = [
    path('submitratings', SubmitRatingViewSet.as_view({'post': 'create'}), name='submit-rating'),
    path('getratings', GetRatingViewSet.as_view({'get': 'get_ratings'}), name='get-ratings'),
    path('getcompliments', GetComplimentViewSet.as_view({'get': 'get_compliments'}), name='get-compliments'),
]

