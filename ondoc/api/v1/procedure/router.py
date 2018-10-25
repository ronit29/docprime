from django.urls import path
from ondoc.api.v1.procedure.views import ProcedureListViewSet

urlpatterns = [
    path('list', ProcedureListViewSet.as_view({'list': 'list'}), name='procedure-list'),
]