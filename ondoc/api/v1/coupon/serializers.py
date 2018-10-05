from rest_framework import serializers
from ondoc.coupon.models import Coupon
from django.contrib.auth import get_user_model
User = get_user_model()


class CouponListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Coupon
        fields = '__all__'