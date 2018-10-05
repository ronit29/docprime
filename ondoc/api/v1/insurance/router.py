from django.urls import path
from .views import (ListInsuranceViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
]