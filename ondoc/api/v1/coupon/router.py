from django.urls import path
from .views import ApplicableCouponsViewSet

urlpatterns = [
    path('applicablecoupons', ApplicableCouponsViewSet.as_view({'get': 'list'}), name='applicable-coupons'),
]
