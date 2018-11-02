from django.urls import path
from django.conf.urls import url
from .views import ApplicableCouponsViewSet, CouponDiscountViewSet
from ondoc.crm.admin.coupon import LabAutocomplete, TestAutocomplete

urlpatterns = [
    path('applicablecoupons', ApplicableCouponsViewSet.as_view({'get': 'list'}), name='applicable-coupons'),
    path('discount', CouponDiscountViewSet.as_view({'post':'coupon_discount'}), name='coupon-discount'),
    url(r'^lab-autocomplete/$', LabAutocomplete.as_view(), name='lab-autocomplete'),
    url(r'^test-autocomplete/$', TestAutocomplete.as_view(), name='test-autocomplete'),
]
