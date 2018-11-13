from rest_framework import serializers
from ondoc.account.models import Order
from ondoc.diagnostic.models import Lab, LabTest
from django.contrib.auth import get_user_model
from ondoc.api.v1.doctor.serializers import CommaSepratedToListField

User = get_user_model()


class ProductIDSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(required=False, choices=Order.PRODUCT_IDS)
    lab_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Lab.objects.filter(is_live=True))
    test_ids = CommaSepratedToListField(required=False)

class CouponListSerializer(serializers.Serializer):

    coupon_code = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)


class UserSpecificCouponSerializer(CouponListSerializer):

    lab = serializers.PrimaryKeyRelatedField(required=False,queryset=Lab.objects.filter(is_live=True))
    test = serializers.ListField(child=serializers.PrimaryKeyRelatedField(required=False, queryset=LabTest.objects.all()),  required=False)
