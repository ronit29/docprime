from django.urls import path
from .views import (ListInsuranceViewSet, InsuredMemberViewSet, InsuranceProfileViewSet, InsuranceOrderViewSet,
                    InsuranceValidationViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
    # path('summary', InsuredMemberViewSet.as_view({'post': 'summary'}), name='insurance-summary'),
    path('create', InsuranceOrderViewSet.as_view({'post': 'create_order'}), name='insured-members'),
    path('banner-lead/create', InsuranceOrderViewSet.as_view({'post': 'create_banner_lead'}), name='banner-lead-create'),
    path('members/list', InsuredMemberViewSet.as_view({'get': 'memberlist'}), name='insured-members-list'),
    path('members/update', InsuredMemberViewSet.as_view({'post': 'update'}), name='insured-members-update'),
    path('profile', InsuranceProfileViewSet.as_view({'get': 'profile'}), name='insurance-profile'),
    path('check_insurance', InsuranceValidationViewSet.as_view({'post': 'validation'}), name='insurance-validation'),
]