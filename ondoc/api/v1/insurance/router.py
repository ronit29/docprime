from django.urls import path
from .views import (ListInsuranceViewSet, InsuredMemberViewSet, InsuranceProfileViewSet, InsuranceOrderViewSet,
                    InsuranceValidationViewSet, InsuranceDummyDataViewSet, InsuranceCancelViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
    # path('summary', InsuredMemberViewSet.as_view({'post': 'summary'}), name='insurance-summary'),
    path('create', InsuranceOrderViewSet.as_view({'post': 'create_order'}), name='insured-members'),
    path('lead/create', InsuranceOrderViewSet.as_view({'post': 'create_banner_lead'}), name='banner-lead-create'),
    path('members/list', InsuredMemberViewSet.as_view({'get': 'memberlist'}), name='insured-members-list'),
    path('members/update', InsuredMemberViewSet.as_view({'post': 'update'}), name='insured-members-update'),
    path('profile', InsuranceProfileViewSet.as_view({'get': 'profile'}), name='insurance-profile'),
    path('push_insurance_data', InsuranceDummyDataViewSet.as_view({'post': 'push_dummy_data'}), name='push-dummy-data'),
    path('show_insurance_data', InsuranceDummyDataViewSet.as_view({'get': 'show_dummy_data'}), name='show-dummy-data'),
    path('check_insurance', InsuranceValidationViewSet.as_view({'post': 'validation'}), name='insurance-validation'),
    path('cancel', InsuranceCancelViewSet.as_view({'get': 'insurance_cancel'}), name='insurance-cancel'),
]
