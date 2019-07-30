from rest_framework import serializers

from ondoc.api.v1.utils import form_time_slot
from ondoc.authentication import models as auth_models
from ondoc.account.models import Order
from ondoc.authentication.models import UserProfile
from ondoc.cart.models import Cart
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from ondoc.diagnostic.models import LabTest, AvailableLabTest, Lab, LabPricingGroup
from django.db.models import F, Case, When, Value, IntegerField

from ondoc.doctor.models import Doctor, Hospital
import datetime

from ondoc.procedure.models import DoctorClinicProcedure, Procedure


class CartCreateSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    data = serializers.JSONField(required=True)


class CartItemSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    tests = serializers.SerializerMethodField()
    coupons = serializers.SerializerMethodField()
    lab = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    hospital = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    procedures = serializers.SerializerMethodField()


    def get_procedures(self, obj):
        procedures_ids = obj.data.get("procedure_ids", [])
        if not procedures_ids:
            return []

        doctor_clinic = DoctorClinicProcedure.objects \
            .filter(procedure_id__in=procedures_ids, doctor_clinic__doctor_id=obj.data.get('doctor'), doctor_clinic__hospital_id=obj.data.get('hospital')) \
            .values('mrp', 'deal_price', name=F('procedure__name'))

        return doctor_clinic

    def get_date(self, obj):
        from django.utils.timezone import make_aware

        if not obj.data.get("start_date"):
            return None

        date_field = obj.data.get("start_date").find('T')
        if date_field:
            date_field = obj.data.get("start_date")[:date_field]
        return form_time_slot(make_aware(datetime.datetime.strptime(date_field, '%Y-%m-%d')), float(obj.data.get("start_time")))

    def get_thumbnail(self, obj):
        if obj.data.get('doctor'):
            doc = Doctor.objects.filter(id=obj.data.get('doctor')).first()
            if doc:
                return doc.get_thumbnail()

        if obj.data.get('lab'):
            lab_data = Lab.objects.filter(id=obj.data.get('lab')).first()
            if lab_data:
                return lab_data.get_thumbnail()
        return None

    def get_lab(self, obj):
        lab_data = Lab.objects.filter(id=obj.data.get('lab')).values('name')
        if lab_data:
            return lab_data[0]
        return None

    def get_doctor(self, obj):
        doctor_data = Doctor.objects.filter(id=obj.data.get('doctor')).values('name')
        if doctor_data:
            return doctor_data[0]
        return None

    def get_hospital(self, obj):
        hospital_data = Hospital.objects.filter(id=obj.data.get('hospital')).values('name')
        if hospital_data:
            return hospital_data[0]
        return None


    def get_profile(self, obj):
        profile_data = UserProfile.objects.filter(id=obj.data.get('profile')).values('name')
        if profile_data:
            return profile_data[0]
        return None

    def get_tests(self, obj):
        if not obj.data.get('test_ids', None) or not obj.data.get('lab', None):
            return []
        lab_pricing_group = LabPricingGroup.objects.filter(labs__in=[obj.data.get('lab')])
        if not lab_pricing_group.exists():
            return []
        tests = AvailableLabTest.objects.select_related('test', 'lab')\
                                        .filter(lab_pricing_group=lab_pricing_group.first(), test_id__in=obj.data.get('test_ids'))\
                                        .annotate(test_name=F('test__name'), deal_price=Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                                                                             When(custom_deal_price__isnull=False, then=F('custom_deal_price'))))\
                                        .values('test_name', 'deal_price', 'mrp')
        return tests


    def get_coupons(self, obj):
        coupon_data = RandomGeneratedCoupon.get_coupons(obj.data.get('coupon_code', []))
        if coupon_data:
            coupon_data = coupon_data.annotate(is_cashback=Case(When(coupon_type=Coupon.DISCOUNT, then=Value(0)),
                                                                When(coupon_type=Coupon.CASHBACK, then=Value(1)), output_field=IntegerField())
                                               )\
                                .values('code', 'id', 'is_cashback', 'random_coupon_code')

        if coupon_data and coupon_data.exists():
            coupon_list = []
            for c in coupon_data:
                c["code"] = c["random_coupon_code"] or c["code"]
                coupon_list.append(c)
            return coupon_list
        return None

    class Meta:
        model = Cart
        fields = ('tests', 'profile', 'coupons', 'doctor', 'hospital', 'lab', 'thumbnail', 'date', 'procedures')