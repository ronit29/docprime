from django.urls import path
from .views import IntegratorReportViewSet


urlpatterns = [
    path('report', IntegratorReportViewSet.as_view({'get': 'report'}), name='integrator-report')
]