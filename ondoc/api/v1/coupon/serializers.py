from rest_framework import serializers
from ondoc.account.models import Order
from ondoc.cart.models import Cart
from ondoc.diagnostic.models import Lab, LabTest, AvailableLabTest, LabAppointment, LabTestCategory
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from ondoc.doctor.models import Doctor, Hospital, PracticeSpecialization, OpdAppointment
from ondoc.procedure.models import Procedure, ProcedureCategory
from ondoc.authentication.models import UserProfile
from django.contrib.auth import get_user_model
from ondoc.api.v1.doctor.serializers import CommaSepratedToListField
from django.db.models import F, Q, ExpressionWrapper, DateTimeField
import datetime

User = get_user_model()


class ProductIDSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(required=False, choices=Order.PRODUCT_IDS)
    lab_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Lab.objects.filter(is_live=True))
    test_ids = CommaSepratedToListField(required=False)
    procedures_ids = CommaSepratedToListField(required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(required=False,
                                                   queryset=Doctor.objects.filter(is_live=True, enabled=True))
    hospital_id = serializers.PrimaryKeyRelatedField(required=False,
                                                   queryset=Hospital.objects.filter(is_live=True, enabled=True))
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    coupon_code = serializers.CharField(required=False)
    profile_id = serializers.PrimaryKeyRelatedField(required=False, queryset=UserProfile.objects.all())
    cart_item = serializers.PrimaryKeyRelatedField(queryset=Cart.objects.all(), required=False, allow_null=True)
    show_all = serializers.BooleanField(required=False)

    def validate(self, attrs):
        product_id = attrs.get("product_id")
        lab = attrs.get("lab_id")
        doctor = attrs.get("doctor_id")
        test_ids = attrs.get("test_ids")
        procedures_ids = attrs.get("procedures_ids")
        if product_id:
            if product_id == Order.DOCTOR_PRODUCT_ID and lab:
                raise serializers.ValidationError("Invalid product id for lab")
            if product_id == Order.LAB_PRODUCT_ID and doctor:
                raise serializers.ValidationError("Invalid product id for doctor")
        if test_ids:
            attrs["tests"] = LabTest.objects.filter(id__in=test_ids)
        if procedures_ids:
            attrs["procedures"] = Procedure.objects.filter(id__in=procedures_ids)
        return attrs


class CouponListSerializer(serializers.Serializer):

    coupon_code = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)

    def validate(self, attrs):
        codes = attrs.get("coupon_code")
        coupons_data, random_coupons = None, None
        if RandomGeneratedCoupon.objects.filter(random_coupon__in=codes).exists():
            expression = F('sent_at') + datetime.timedelta(days=1) * F('validity')
            annotate_expression = ExpressionWrapper(expression, DateTimeField())
            random_coupons = RandomGeneratedCoupon.objects.annotate(last_date=annotate_expression
                                                                    ).filter(random_coupon__in=codes,
                                                                             sent_at__isnull=False,
                                                                             consumed_at__isnull=True,
                                                                             last_date__gte=datetime.datetime.now()
                                                                             ).all()
            if random_coupons:
                coupons_data = Coupon.objects.filter(id__in=random_coupons.values_list('coupon', flat=True))
        if coupons_data:
            coupons_data = Coupon.objects.filter(code__in=codes) | coupons_data
        else:
            coupons_data = Coupon.objects.filter(code__in=codes)
        if not random_coupons and not (coupons_data.exists() and len(coupons_data) == len(set(attrs.get("coupon_code")))):
            raise serializers.ValidationError("Invalid Coupon Codes")
        return attrs


class UserSpecificCouponSerializer(CouponListSerializer):

    lab = serializers.PrimaryKeyRelatedField(required=False,queryset=Lab.objects.filter(is_live=True), allow_null=True)
    tests = serializers.ListField(child=serializers.PrimaryKeyRelatedField(required=False, queryset=LabTest.objects.all()),  required=False)
    procedures = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(required=False, queryset=Procedure.objects.all()), required=False)
    doctor = serializers.PrimaryKeyRelatedField(required=False, queryset=Doctor.objects.filter(is_live=True), allow_null=True)
    hospital = serializers.PrimaryKeyRelatedField(required=False, queryset=Hospital.objects.filter(is_live=True), allow_null=True)
    profile = serializers.PrimaryKeyRelatedField(required=False, queryset=UserProfile.objects.all(), allow_null=True)
    cart_item = serializers.PrimaryKeyRelatedField(queryset=Cart.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):

        codes = attrs.get("coupon_code")
        deal_price=attrs.get("deal_price")
        lab = attrs.get("lab")
        tests = attrs.get("tests", [])
        doctor = attrs.get("doctor")
        hospital = attrs.get("hospital")
        procedures = attrs.get("procedures", [])
        product_id = attrs.get("product_id")

        if product_id:
            if product_id == Order.DOCTOR_PRODUCT_ID and lab:
                raise serializers.ValidationError("Invalid product id for lab")
            if product_id == Order.LAB_PRODUCT_ID and doctor:
                raise serializers.ValidationError("Invalid product id for doctor")

        coupons_data, random_coupons = None, None

        coupons_data = RandomGeneratedCoupon.get_coupons(codes)

        if not coupons_data:
            raise serializers.ValidationError("Unknown Coupon Code")
        attrs["coupons_data"] = coupons_data

        if deal_price:
            coupons_data = coupons_data.filter(Q(min_order_amount__isnull=True) | Q(min_order_amount__lte = deal_price))
            if len(coupons_data) == 0:
                raise serializers.ValidationError("Coupon invalid, minimum order amount criteria not met")

        # if not coupons_data.exists() or len(coupons_data) != len(set(attrs.get("coupon_code"))):
        if not random_coupons and not (coupons_data.exists() and len(coupons_data) == len(set(attrs.get("coupon_code")))):
            raise serializers.ValidationError("Invalid Coupon Codes")

        if product_id == Order.LAB_PRODUCT_ID:
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

        elif product_id == Order.DOCTOR_PRODUCT_ID:
            if doctor and hospital and not Doctor.objects.filter(id=doctor.id, doctor_clinics__hospital=hospital).exists():
                raise serializers.ValidationError("wrong combination of doctor and hospital")
            elif doctor and hospital and procedures and \
                not Doctor.objects.filter(id=doctor.id, doctor_clinics__hospital=hospital,
                                          doctor_clinics__procedures_from_doctor_clinic__procedure__in=procedures).exists():
                    raise serializers.ValidationError("wrong combination of doctor, hospital and procedures")
            else:
                for coupon in coupons_data:
                    obj = OpdAppointment()
                    if not obj.validate_product_coupon(coupon_obj=coupon,
                                                       doctor=doctor, hospital=hospital, procedures=procedures,
                                                       product_id=Order.DOCTOR_PRODUCT_ID):
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        return attrs
