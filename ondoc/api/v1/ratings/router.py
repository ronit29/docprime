from django.urls import path
#from .views import (LabTestList, LabList, LabAppointmentView, SearchPageViewSet, LabTimingListView,
#                    AvailableTestViewSet, LabReportFileViewset, DoctorLabAppointmentsViewSet, DoctorLabAppointmentsNoAuthViewSet)
from .views import SubmitRatingViewSet

urlpatterns = [
    path('submitratings', SubmitRatingViewSet.as_view({'post': 'create'}), name='submit-rating'),
]

