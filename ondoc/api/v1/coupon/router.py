from django.urls import path
from django.conf.urls import url
from .views import ApplicableCouponsViewSet, CouponDiscountViewSet
from ondoc.crm.admin.coupon import LabNetworkAutocomplete, LabAutocomplete, TestAutocomplete, \
    TestCategoriesAutocomplete, ProceduresAutocomplete, ProcedureCategoriesAutocomplete, \
    SpecializationsAutocomplete, DoctorsAutocomplete, HospitalsAutocomplete, VipGoldPlanAutocomplete
from ondoc.crm.admin.hospital import CloudLabAutocomplete
from ondoc.crm.admin.provider import AvailableLabTestAutocomplete

urlpatterns = [
    path('applicablecoupons', ApplicableCouponsViewSet.as_view({'get': 'list_v2'}), name='applicable-coupons'),
    path('discount', CouponDiscountViewSet.as_view({'post':'coupon_discount'}), name='coupon-discount'),
    url(r'^lab-network-autocomplete/$', LabNetworkAutocomplete.as_view(), name='lab-network-autocomplete'),
    url(r'^lab-autocomplete/$', LabAutocomplete.as_view(), name='lab-autocomplete'),
    url(r'^cloud-lab-autocomplete/$', CloudLabAutocomplete.as_view(), name='cloud-lab-autocomplete'),
    url(r'^available-lab-test-autocomplete/$', AvailableLabTestAutocomplete.as_view(), name='available-lab-test-autocomplete'),
    url(r'^test-autocomplete/$', TestAutocomplete.as_view(), name='test-autocomplete'),
    url(r'^test-categories-autocomplete/$', TestCategoriesAutocomplete.as_view(), name='test-categories-autocomplete'),
    url(r'^doctors-autocomplete/$', DoctorsAutocomplete.as_view(), name='doctors-autocomplete'),
    url(r'^hospitals-autocomplete/$', HospitalsAutocomplete.as_view(), name='hospitals-autocomplete'),
    url(r'^specializations-autocomplete/$', SpecializationsAutocomplete.as_view(), name='specializations-autocomplete'),
    url(r'^procedures-autocomplete/$', ProceduresAutocomplete.as_view(), name='procedures-autocomplete'),
    url(r'^procedure-categories-autocomplete/$', ProcedureCategoriesAutocomplete.as_view(), name='procedure-categories-autocomplete'),
    url(r'^vip-gold-plans-autocomplete/$', VipGoldPlanAutocomplete.as_view(), name='vip-gold-plans-autocomplete'),
]

