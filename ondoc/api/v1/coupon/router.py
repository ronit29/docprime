from django.urls import path
from .views import ApplicableCouponsViewSet, CouponDiscountViewSet

urlpatterns = [
    path('applicablecoupons', ApplicableCouponsViewSet.as_view({'get': 'list'}), name='applicable-coupons'),
    path('discount', CouponDiscountViewSet.as_view({'post':'coupon_discount'}), name='coupon-discount'),
]
