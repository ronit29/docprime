from django.urls import path
#from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
#                    AvailableTestViewSet, LabReportFileViewset, DoctorLabAppointmentsViewSet, DoctorLabAppointmentsNoAuthViewSet)
from .views import SubmitRatingViewSet
from .views import GetRatingViewSet

urlpatterns = [
    path('submitratings', SubmitRatingViewSet.as_view({'post': 'create'}), name='submit-rating'),
    path('getratings', GetRatingViewSet.as_view({'post': 'get_ratings'}), name='get-ratings'),
]

