from rest_framework import serializers
from ondoc.account.models import Order
from ondoc.cart.models import Cart
from ondoc.diagnostic.models import Lab, LabTest, AvailableLabTest, LabAppointment, LabTestCategory
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from ondoc.doctor.models import Doctor, Hospital, PracticeSpecialization, OpdAppointment
from ondoc.plus.models import PlusPlans, PlusUser
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
    plan_id = serializers.PrimaryKeyRelatedField(required=False, queryset=PlusPlans.objects.all())
    show_all = serializers.BooleanField(required=False)

    def validate(self, attrs):
        product_id = attrs.get("product_id")
        lab = attrs.get("lab_id")
        doctor = attrs.get("doctor_id")
        test_ids = attrs.get("test_ids")
        procedures_ids = attrs.get("procedures_ids")
        plus_plan = attrs.get('plan_id')
        if product_id:
            if not product_id == Order.LAB_PRODUCT_ID and lab:
                raise serializers.ValidationError("Invalid product id for lab")
            if not product_id == Order.DOCTOR_PRODUCT_ID and doctor:
                raise serializers.ValidationError("Invalid product id for doctor")
            if product_id not in [Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID] and plus_plan:
                raise serializers.ValidationError("Invalid product id for plus plans")
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
    plan = serializers.PrimaryKeyRelatedField(required=False, queryset=PlusPlans.objects.all())

    def validate(self, attrs):

        codes = attrs.get("coupon_code")
        deal_price=attrs.get("deal_price")
        lab = attrs.get("lab")
        tests = attrs.get("tests", [])
        doctor = attrs.get("doctor")
        hospital = attrs.get("hospital")
        procedures = attrs.get("procedures", [])
        product_id = attrs.get("product_id")
        plan = attrs.get('plan')

        if product_id:
            if product_id in [Order.DOCTOR_PRODUCT_ID, Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID] and lab:
                raise serializers.ValidationError("Invalid product id for lab")
            if product_id in [Order.LAB_PRODUCT_ID, Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID] and doctor:
                raise serializers.ValidationError("Invalid product id for doctor")
            if product_id in [Order.DOCTOR_PRODUCT_ID, Order.LAB_PRODUCT_ID] and plan:
                raise serializers.ValidationError("Invalid product id for plan")

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
        elif product_id == Order.VIP_PRODUCT_ID:
            if plan and plan.is_gold:
                raise serializers.ValidationError("Wrong combination of plan and product_id")
            else:
                for coupon in coupons_data:
                    obj = PlusUser()
                    if not obj.validate_product_coupon(coupon_obj=coupon, gold_vip_plan_id=plan.id,
                                                       product_id=Order.VIP_PRODUCT_ID):
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        elif product_id == Order.GOLD_PRODUCT_ID:
            if plan and not plan.is_gold:
                raise serializers.ValidationError("Wrong combination of plan and product_id")
            else:
                for coupon in coupons_data:
                    obj = PlusUser()
                    if not obj.validate_product_coupon(coupon_obj=coupon, gold_vip_plan_id=plan.id,
                                                       product_id=Order.GOLD_PRODUCT_ID):
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        return attrs


class CouponSerializer(serializers.ModelSerializer):
    coupon_type = serializers.SerializerMethodField()
    coupon_id = serializers.SerializerMethodField()
    desc = serializers.SerializerMethodField()
    coupon_count = serializers.SerializerMethodField()
    is_cashback = serializers.SerializerMethodField()
    is_payment_specific = serializers.SerializerMethodField()
    valid = serializers.SerializerMethodField()
    invalidating_message = serializers.SerializerMethodField()

    def get_coupon_type(self, obj):
        return obj.type

    def get_coupon_id(self, obj):
        return obj.id

    def get_desc(self, obj):
        return obj.description

    def get_coupon_count(self, obj):
        return obj.count

    def get_is_cashback(self, obj):
        return obj.coupon_type == Coupon.CASHBACK

    def get_is_payment_specific(self, obj):
        return bool(obj.payment_option)

    def get_valid(self, obj):
        coupon_properties = self.context.get('coupon_properties')
        valid = True
        if coupon_properties:
            valid = coupon_properties.get('valid', True)
        return valid

    def get_invalidating_message(self, obj):
        coupon_properties = self.context.get('coupon_properties')
        invalidating_message = ''
        if coupon_properties:
            invalidating_message = coupon_properties.get('invalidating_message', '')
        return invalidating_message

    class Meta:
        model = Coupon
        fields = ('coupon_type', 'coupon_id', 'code', 'desc', 'coupon_count', 'heading', 'is_corporate', 'is_cashback', 'tnc', 'is_payment_specific', 'valid', 'invalidating_message')