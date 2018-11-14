from django.urls import path
from .views import (ListInsuranceViewSet, InsuredMemberViewSet,InsuranceProfileViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
    path('summary', InsuredMemberViewSet.as_view({'post': 'summary'}), name='insurance-summary'),
    path('create', InsuredMemberViewSet.as_view({'post': 'create'}), name='insured-members'),
    path('members/list', InsuredMemberViewSet.as_view({'get': 'memberlist'}), name='insured-members-list'),
    path('members/update', InsuredMemberViewSet.as_view({'post': 'update'}), name='insured-members-update'),
    path('profile', InsuranceProfileViewSet.as_view({'get': 'profile'}), name='insurance-profile'),
]
