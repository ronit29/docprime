from django.urls import path
from .views import (ListInsuranceViewSet, InsuredMemberViewSet, InsuranceProfileViewSet, InsuranceOrderViewSet,
                    InsuranceValidationViewSet, InsuranceDummyDataViewSet, InsuranceCancelViewSet, InsuranceNetworkViewSet,
                    InsuranceEndorsementViewSet, UserBankViewSet)


urlpatterns = [
    path('list', ListInsuranceViewSet.as_view({'get': 'list'}), name='insurance-list'),
    path('availability', ListInsuranceViewSet.as_view({'get': 'check_is_insurance_available'}), name='insurance-city-availability'),
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
    path('cancel-master', InsuranceCancelViewSet.as_view({'get': 'cancel_master'}), name='insurance-cancel-master'),
    path('network/search', InsuranceNetworkViewSet.as_view({'get': 'list'}), name='insurance-network'),
    path('endorsement', InsuranceEndorsementViewSet.as_view({'get':'get_endorsement_data'}), name='insurance-endorsement'),
    path('push_endorsement_data', InsuranceDummyDataViewSet.as_view({'post': 'push_endorsement_data'}), name='push-endorsement-data'),
    path('show_endorsement_data', InsuranceDummyDataViewSet.as_view({'get': 'show_endorsement_data'}), name='show-endorsement-data'),
    path('endorsement/create', InsuranceEndorsementViewSet.as_view({'post': 'create'}), name='create-endorsement'),
    path('member/<int:pk>/upload', InsuranceEndorsementViewSet.as_view({'post': 'upload'}), name='insuredmember-document-upload'),
    path('bank/upload', UserBankViewSet.as_view({'post': 'upload'}), name='userbank-document-upload'),
    path('push_bank_data', UserBankViewSet.as_view({'post': 'create'}), name='push-userbank-data'),
]

