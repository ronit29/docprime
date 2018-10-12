from rest_framework import serializers
from ondoc.coupon.models import Coupon
from ondoc.account.models import Order
from django.contrib.auth import get_user_model

from django.contrib.staticfiles.templatetags.staticfiles import static
import jwt
from django.conf import settings
from ondoc.authentication.backends import JWTAuthentication
from ondoc.common import models as common_models

User = get_user_model()


class ProductIDSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(required=False, choices=Order.PRODUCT_IDS)


class CouponListSerializer(serializers.Serializer):

    coupon_code = serializers.ListField(child=serializers.CharField())
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)

    # class Meta:
    #     model = Coupon
    #     fields = 'code'
