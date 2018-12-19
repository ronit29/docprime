from rest_framework import serializers
from ondoc.account.models import Order
from ondoc.diagnostic.models import Lab, LabTest, AvailableLabTest, LabAppointment
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from ondoc.doctor.models import Doctor
from ondoc.authentication.models import UserProfile
from django.contrib.auth import get_user_model
from ondoc.api.v1.doctor.serializers import CommaSepratedToListField
from django.db.models import Q

User = get_user_model()


class ProductIDSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(required=False, choices=Order.PRODUCT_IDS)
    lab_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Lab.objects.filter(is_live=True))
    test_ids = CommaSepratedToListField(required=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    coupon_code = serializers.CharField(required=False)
    gender = serializers.ChoiceField(required=False, choices=UserProfile.GENDER_CHOICES)
    profile_id = serializers.PrimaryKeyRelatedField(required=False, queryset=UserProfile.objects.all())
    age_range = CommaSepratedToListField(required=False, max_length=2, min_length=2)

    def validate(self, attrs):
        age_range = attrs.get("age_range")
        if age_range and age_range[0] > age_range[1]:
            raise serializers.ValidationError("Invalid Age Range")
        return attrs


class CouponListSerializer(serializers.Serializer):

    coupon_code = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)

    def validate(self, attrs):
        codes = attrs.get("coupon_code")
        random_coupons = RandomGeneratedCoupon.objects.filter(random_coupon__in=codes,
                                                              sent_at__isnull=False,
                                                              consumed_at__isnull=True).all()
        coupons_data = None
        if random_coupons:
            coupon_codes = list()
            for coupon in random_coupons:
                coupon_codes.append(coupon.coupon)
            coupons_data = Coupon.objects.filter(code__in=coupon_codes)
        coupons_data = Coupon.objects.filter(code__in=codes) | coupons_data
        if not random_coupons and not (coupons_data.exists() and len(coupons_data) == len(set(attrs.get("coupon_code")))):
            raise serializers.ValidationError("Invalid Coupon Codes")
        return attrs


class UserSpecificCouponSerializer(CouponListSerializer):

    lab = serializers.PrimaryKeyRelatedField(required=False,queryset=Lab.objects.filter(is_live=True))
    tests = serializers.ListField(child=serializers.PrimaryKeyRelatedField(required=False, queryset=LabTest.objects.all()),  required=False)
    doctor = serializers.PrimaryKeyRelatedField(required=False, queryset=Doctor.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(required=False, queryset=UserProfile.objects.all())

    def validate(self, attrs):

        lab = attrs.get("lab")
        tests = attrs.get("tests")
        doctor = attrs.get("doctors")
        codes = attrs.get("coupon_code")

        random_coupons = RandomGeneratedCoupon.objects.filter(random_coupon__in=codes,
                                                              sent_at__isnull=False,
                                                              consumed_at__isnull=True).all()
        coupons_data = None
        if random_coupons:
            coupon_codes = list()
            for coupon in random_coupons:
                coupon_codes.append(coupon.coupon)
            coupons_data = Coupon.objects.filter(code__in=coupon_codes)
        coupons_data = Coupon.objects.filter(code__in=codes) | coupons_data
        attrs["coupons_data"] = coupons_data

        # if not coupons_data.exists() or len(coupons_data) != len(set(attrs.get("coupon_code"))):
        if not random_coupons and not (coupons_data.exists() and len(coupons_data) == len(set(attrs.get("coupon_code")))):
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
            pass

        return attrs
