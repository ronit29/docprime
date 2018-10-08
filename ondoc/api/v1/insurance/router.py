from django.urls import path
from .views import (ListInsuranceViewSet, InsuredMemberViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
    path('create', InsuredMemberViewSet.as_view({'post': 'create'}), name='insured-members'),
]
