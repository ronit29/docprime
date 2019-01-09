from django.urls import path
from django.conf.urls import url
from .views import ApplicableCouponsViewSet, CouponDiscountViewSet
from ondoc.crm.admin.coupon import LabNetworkAutocomplete, LabAutocomplete, TestAutocomplete, TestCategoriesAutocomplete, ProceduresAutocomplete, ProcedureCategoriesAutocomplete
urlpatterns = [
    path('applicablecoupons', ApplicableCouponsViewSet.as_view({'get': 'list'}), name='applicable-coupons'),
    path('discount', CouponDiscountViewSet.as_view({'post':'coupon_discount'}), name='coupon-discount'),
    url(r'^lab-network-autocomplete/$', LabNetworkAutocomplete.as_view(), name='lab-network-autocomplete'),
    url(r'^lab-autocomplete/$', LabAutocomplete.as_view(), name='lab-autocomplete'),
    url(r'^test-autocomplete/$', TestAutocomplete.as_view(), name='test-autocomplete'),
    url(r'^test-categories-autocomplete/$', TestCategoriesAutocomplete.as_view(), name='test-categories-autocomplete'),
    url(r'^procedures-autocomplete/$', ProceduresAutocomplete.as_view(), name='procedures-autocomplete'),
    url(r'^procedure-categories-autocomplete/$', ProcedureCategoriesAutocomplete.as_view(), name='procedure-categories-autocomplete'),
]

