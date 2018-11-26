from django.urls import path
from ondoc.api.v1.procedure.views import ProcedureListViewSet, DoctorClinicProcedureViewSet

urlpatterns = [
    path('list', ProcedureListViewSet.as_view({'get': 'list'}), name='procedure-list'),
    path('details', DoctorClinicProcedureViewSet.as_view({'get': 'details'}), name='procedure-details'),
]