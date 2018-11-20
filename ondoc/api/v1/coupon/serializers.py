from rest_framework import serializers
from ondoc.account.models import Order
from ondoc.diagnostic.models import Lab, LabTest, AvailableLabTest, LabAppointment
from ondoc.coupon.models import Coupon
from ondoc.doctor.models import Doctor
from django.contrib.auth import get_user_model
from ondoc.api.v1.doctor.serializers import CommaSepratedToListField
from django.db.models import Q

User = get_user_model()


class ProductIDSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(required=False, choices=Order.PRODUCT_IDS)
    lab_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Lab.objects.filter(is_live=True))
    test_ids = CommaSepratedToListField(required=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

class CouponListSerializer(serializers.Serializer):

    coupon_code = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)

    def validate(self, attrs):
        coupons_data = Coupon.objects.filter(code__in=attrs.get("coupon_code"))
        if coupons_data.exists() and len(coupons_data) == len(set(attrs.get("coupon_code"))):
            return attrs
        else:
            raise serializers.ValidationError("Invalid Coupon Codes")

class UserSpecificCouponSerializer(CouponListSerializer):

    lab = serializers.PrimaryKeyRelatedField(required=False,queryset=Lab.objects.filter(is_live=True))
    tests = serializers.ListField(child=serializers.PrimaryKeyRelatedField(required=False, queryset=LabTest.objects.all()),  required=False)
    doctor = serializers.PrimaryKeyRelatedField(required=False, queryset=Doctor.objects.filter(is_live=True))

    def validate(self, attrs):

        lab = attrs.get("lab")
        tests = attrs.get("tests")
        doctor = attrs.get("doctors")
        coupons_data = Coupon.objects.filter(code__in=attrs.get("coupon_code"))
        attrs["coupons_data"] = coupons_data

        if not coupons_data.exists() or len(coupons_data) != len(set(attrs.get("coupon_code"))):
            raise serializers.ValidationError("Invalid Coupon Codes")

        if lab and not tests:
            raise serializers.ValidationError("tests also required with lab")
        elif not lab and tests:
            raise serializers.ValidationError("lab also required with tests")
        elif not (lab or tests) and coupons_data.filter(Q(lab_network__isnull=False) | Q(lab__isnull=False) | Q(test__isnull=False)):
            raise serializers.ValidationError("no lab and test data given for lab specific coupon")
        elif (lab and tests):
            tests_qs = AvailableLabTest.objects.filter(lab_pricing_group__labs=attrs["lab"],
                                                       enabled=True,
                                                       test__in=attrs["tests"])
            if len(tests_qs) != len(tests):
                raise serializers.ValidationError('Invalid tests for given lab')

            if coupons_data.filter(Q(lab_network__isnull=False) | Q(lab__isnull=False) | Q(test__isnull=False)):
                for coupon in coupons_data:
                    obj = LabAppointment()
                    if not obj.validate_product_coupon(coupon_obj=coupon,
                                                       lab=lab, test=tests,
                                                       product_id=Order.LAB_PRODUCT_ID):
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        if doctor:
            for coupon in coupons_data:
                obj = LabAppointment()
                if not obj.validate_product_coupon(coupon_obj=coupon,
                                                   lab=lab, test=tests,
                                                   product_id=Order.LAB_PRODUCT_ID):
                    raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        return attrs
