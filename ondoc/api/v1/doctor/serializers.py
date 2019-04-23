from django.utils.safestring import mark_safe
from rest_framework import serializers
from rest_framework.fields import CharField
from django.db.models import Q, Avg, Count, Max, F, ExpressionWrapper, DateTimeField
from collections import defaultdict, OrderedDict
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer, OpdAppointmentProcedureMappingSerializer
from ondoc.api.v1.ratings.serializers import RatingsGraphSerializer
from ondoc.cart.models import Cart
from ondoc.common.models import Feature
from ondoc.doctor.models import (OpdAppointment, Doctor, Hospital, DoctorHospital, DoctorClinicTiming,
                                 DoctorAssociation,
                                 DoctorAward, DoctorDocument, DoctorEmail, DoctorExperience, DoctorImage,
                                 DoctorLanguage, DoctorMedicalService, DoctorMobile, DoctorQualification, DoctorLeave,
                                 Prescription, PrescriptionFile, Specialization, DoctorSearchResult, HealthTip,
                                 CommonMedicalCondition, CommonSpecialization,
                                 DoctorPracticeSpecialization, DoctorClinic, OfflineOPDAppointments, OfflinePatients,
                                 CancellationReason, HealthInsuranceProvider, HospitalDocument, HospitalNetworkDocument)
from ondoc.diagnostic import models as lab_models
from ondoc.authentication.models import UserProfile, DoctorNumber, GenericAdmin, GenericLabAdmin
from django.db.models import Avg
from django.db.models import Q

from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from ondoc.account.models import Order, Invoice
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.ratings import serializers as rating_serializer
from ondoc.api.v1.utils import is_valid_testing_data, form_time_slot, GenericAdminEntity, util_absolute_url, \
    util_file_name, aware_time_zone
from django.utils import timezone
from django.contrib.auth import get_user_model
import math
import datetime
import pytz
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
import json
import logging
from dateutil import tz
from django.conf import settings

from ondoc.insurance.models import UserInsurance, InsuranceThreshold, InsuranceDoctorSpecializations
from ondoc.authentication import models as auth_models
from ondoc.location.models import EntityUrls, EntityAddress
from ondoc.procedure.models import DoctorClinicProcedure, Procedure, ProcedureCategory, \
    get_included_doctor_clinic_procedure, get_procedure_categories_with_procedures, IpdProcedure, \
    IpdProcedureFeatureMapping, IpdProcedureLead, DoctorClinicIpdProcedure, IpdProcedureDetail
from ondoc.seo.models import NewDynamic
from ondoc.ratings_review import models as rate_models
from rest_framework.response import Response


logger = logging.getLogger(__name__)

User = get_user_model()


class CommaSepratedToListField(CharField):
    def __init__(self, **kwargs):
        self.typecast_to = kwargs.pop('typecast_to', int)
        super(CommaSepratedToListField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        result = []
        try:
            result = list(map(self.typecast_to, data.strip(",").split(",")))
        except:
            pass
        return result

    def to_representation(self, value):
        result = []
        try:
            result = list(map(self.typecast_to, value.strip(",").split(",")))
        except:
            pass
        return result


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()


class AppointmentFilterSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(
                                                    Q(is_live=True) | Q(source_type=Hospital.PROVIDER)), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(
                                                    Q(is_live=True) | Q(source_type=Doctor.PROVIDER)), required=False)
    date = serializers.DateField(required=False)


class AppointmentFilterUserSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all(), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), required=False)
    date = serializers.DateField(required=False)


class OpdAppointmentSerializer(serializers.ModelSerializer):
    DOCTOR_TYPE = 'doctor'
    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    display_name = serializers.ReadOnlyField(source='doctor.get_display_name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    # patient_dob = serializers.ReadOnlyField(source='profile.dob')
    patient_gender = serializers.ReadOnlyField(source='profile.gender'),
    patient_image = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    doctor_thumbnail = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    type = serializers.ReadOnlyField(default='doctor')
    allowed_action = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()

    def get_allowed_action(self, obj):
        request = self.context.get('request')
        return obj.allowed_action(request.user.user_type, request)

    class Meta:
        model = OpdAppointment
        fields = ('id', 'doctor_name', 'hospital_name', 'patient_name', 'patient_image', 'type',
                  'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start',
                  'time_slot_end', 'doctor_thumbnail', 'patient_thumbnail', 'display_name', 'invoices', 'reports')

    def get_patient_image(self, obj):
        if obj.profile and obj.profile.profile_image:
            return obj.profile.profile_image.url
        else:
            return ""

    def get_patient_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.profile and obj.profile.profile_image:
            photo_url = obj.profile.profile_image.url
            return request.build_absolute_uri(photo_url)
        else:
            return None

    def get_doctor_thumbnail(self, obj):
        request = self.context.get('request')
        thumbnail = obj.doctor.get_thumbnail()
        if thumbnail:
            return request.build_absolute_uri(thumbnail) if thumbnail else None
        else:
            return None
            # url = static('doctor_images/no_image.png')
            # return request.build_absolute_uri(url)

    def get_invoices(self, obj):
        return obj.get_invoice_urls()

    def get_reports(self, obj):
        return []


class OpdAppModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpdAppointment
        fields = '__all__'


class OpdAppTransactionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    profile_detail = serializers.JSONField()
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    booked_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    fees = serializers.DecimalField(max_digits=10, decimal_places=2)
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    time_slot_start = serializers.DateTimeField()
    payment_type = serializers.IntegerField()
    coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default = [])
    discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    insurance = serializers.PrimaryKeyRelatedField(queryset=UserInsurance.objects.all(), allow_null=True)
    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    extra_details = serializers.JSONField(required=False)

class OpdAppointmentPermissionSerializer(serializers.Serializer):
    appointment = OpdAppointmentSerializer()
    permission = serializers.IntegerField()


class CreateAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    start_date = serializers.DateTimeField()
    start_time = serializers.FloatField()
    end_date = serializers.CharField(required=False)
    end_time = serializers.FloatField(required=False)
    time_slot_start = serializers.DateTimeField(required=False)
    payment_type = serializers.ChoiceField(choices=OpdAppointment.PAY_CHOICES)
    coupon_code = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    procedure_ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=Procedure.objects.filter()), required=False)
    use_wallet = serializers.BooleanField(required=False)
    cart_item = serializers.PrimaryKeyRelatedField(queryset=Cart.objects.all(), required=False, allow_null=True)
    # procedure_category_ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ProcedureCategory.objects.filter(is_live=True)), required=False, default=[])
    # time_slot_end = serializers.DateTimeField()

    def validate(self, data):

        ACTIVE_APPOINTMENT_STATUS = [OpdAppointment.BOOKED, OpdAppointment.ACCEPTED,
                                     OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.RESCHEDULED_DOCTOR]
        MAX_APPOINTMENTS_ALLOWED = 10
        MAX_FUTURE_DAY = 40
        request = self.context.get("request")
        unserialized_data = self.context.get("data")
        cart_item_id = data.get('cart_item').id if data.get('cart_item') else None
        use_duplicate = self.context.get("use_duplicate", False)
        time_slot_start = (form_time_slot(data.get('start_date'), data.get('start_time'))
                           if not data.get("time_slot_start") else data.get("time_slot_start"))

        time_slot_end = None

        doctor_clinic = data.get('doctor').doctor_clinics.filter(hospital=data.get('hospital'), enabled=True).first()
        if not doctor_clinic:
            raise serializers.ValidationError("Doctor Hospital not related.")
        if not data.get('doctor').enabled_for_online_booking or \
                not data.get('hospital').enabled_for_online_booking or not doctor_clinic.enabled_for_online_booking:
            raise serializers.ValidationError("Online booking not enabled")

        if OpdAppointment.objects.filter(profile=data.get("profile"), doctor=data.get("doctor"),
                                         hospital=data.get("hospital"), time_slot_start=time_slot_start) \
                                .exclude(status__in=[OpdAppointment.COMPLETED, OpdAppointment.CANCELLED]).exists():
            raise serializers.ValidationError("Appointment for the selected date & time already exists. Please change the date & time of the appointment.")

        if not is_valid_testing_data(request.user, data["doctor"]):
            logger.error("Error 'Both User and Doctor should be for testing' for opd appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Both User and Doctor should be for testing")

        if data.get('end_date') and data.get('end_time'):
            time_slot_end = form_time_slot(data.get('end_date'), data.get('end_time'))

        if not request.user.user_type == User.CONSUMER:
            logger.error(
                "Error 'Not allowed to create appointment as user type is not consumer' for opd appointment with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError("Not allowed to create appointment")

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            logger.error(
                "Error 'Invalid profile id' for opd appointment with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError("Invalid profile id")

        if time_slot_start < timezone.now():
            raise serializers.ValidationError("Cannot book in past")

        delta = time_slot_start - timezone.now()
        if delta.days > MAX_FUTURE_DAY:
            raise serializers.ValidationError("Cannot book appointment more than "+str(MAX_FUTURE_DAY)+" days ahead")

        # time_slot_hour = round(float(time_slot_start.hour) + (float(time_slot_start.minute) * 1 / 60), 2)

        doctor_leave = DoctorLeave.objects.filter(deleted_at__isnull=True, doctor=data.get('doctor'), start_date__lte=time_slot_start.date(), end_date__gte=time_slot_start.date(), start_time__lte=time_slot_start.time(), end_time__gte=time_slot_start.time()).exists()

        if doctor_leave:
            logger.error(
                "Error 'Doctor is on leave' for opd appointment with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError("Doctor is on leave")


        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=data.get('doctor'),
                                                 doctor_clinic__hospital=data.get('hospital'),
                                                 day=time_slot_start.weekday(), start__lte=data.get("start_time"),
                                                 end__gte=data.get("start_time")).exists():
            logger.error(
                "Error 'Invalid Time slot' for opd appointment with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError("Invalid Time slot")

        # if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, doctor=data.get('doctor'), profile=data.get('profile')).exists():
        #     raise serializers.ValidationError('A previous appointment with this doctor already exists. Cancel it before booking new Appointment.')

        if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile = data.get('profile')).count()>=MAX_APPOINTMENTS_ALLOWED:
            logger.error(
                "Error 'Max active appointments reached' for opd appointment with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError('Max'+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        if data.get("coupon_code"):
            coupon_codes = data.get("coupon_code", [])
            coupon_obj = None
            if RandomGeneratedCoupon.objects.filter(random_coupon__in=coupon_codes).exists():
                expression = F('sent_at') + datetime.timedelta(days=1) * F('validity')
                annotate_expression = ExpressionWrapper(expression, DateTimeField())
                random_coupons = RandomGeneratedCoupon.objects.annotate(last_date=annotate_expression
                                                                       ).filter(random_coupon__in=coupon_codes,
                                                                                sent_at__isnull=False,
                                                                                consumed_at__isnull=True,
                                                                                last_date__gte=datetime.datetime.now()
                                                                                ).all()
                if random_coupons:
                    coupon_obj = Coupon.objects.filter(id__in=random_coupons.values_list('coupon', flat=True))
                else:
                    raise serializers.ValidationError('Invalid coupon codes')

            if coupon_obj:
                coupon_obj = Coupon.objects.filter(code__in=coupon_codes) | coupon_obj
            else:
                coupon_obj = Coupon.objects.filter(code__in=coupon_codes)

            if coupon_obj:
                for coupon in coupon_obj:
                    profile = data.get("profile")
                    obj = OpdAppointment()
                    if obj.validate_user_coupon(cart_item=cart_item_id, user=request.user, coupon_obj=coupon, profile=profile).get("is_valid"):
                        if not obj.validate_product_coupon(coupon_obj=coupon,
                                                           doctor=data.get("doctor"), hospital=data.get("hospital"),
                                                           procedures=data.get("procedure_ids"),
                                                           product_id=Order.DOCTOR_PRODUCT_ID):
                            raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                    else:
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                data["coupon_obj"] = list(coupon_obj)

        data["existing_cart_item"] = None
        if unserialized_data:
            is_valid, duplicate_cart_item = Cart.validate_duplicate(unserialized_data, request.user, Order.DOCTOR_PRODUCT_ID, cart_item_id)
            if not is_valid:
                if use_duplicate and duplicate_cart_item:
                    data["existing_cart_item"] = duplicate_cart_item
                else:
                    raise serializers.ValidationError("Item already exists in cart.")

        if OpdAppointment.objects.filter(profile=data.get("profile"), doctor=data.get("doctor"),
                                         hospital=data.get("hospital"), procedures__in=data.get("procedure_ids", []),
                                         time_slot_start=time_slot_start) \
                .exclude(status__in=[OpdAppointment.COMPLETED, OpdAppointment.CANCELLED]).exists():
            raise serializers.ValidationError("Appointment for the selected date & time already exists. Please change the date & time of the appointment.")

        if data.get('hospital') and not data.get('hospital').enabled_for_cod and data.get('payment_type') == OpdAppointment.COD:
            raise serializers.ValidationError('Doctor/Hospital not enabled for COD payment')

        if data.get('hospital') and not data.get('hospital').enabled_for_prepaid and data.get('payment_type') == OpdAppointment.PREPAID:
            raise serializers.ValidationError('Doctor/Hospital not enabled for PREPAID payment')

        if 'use_wallet' in data and data['use_wallet'] is False:
            data['use_wallet'] = False
        else:
            data['use_wallet'] = True

        is_appointment_insured = data.get('is_appointment_insured')
        insurance_id = data.get('insurance_id')
        insurance_message = data.get('insurance_message')
        if is_appointment_insured:
            data['payment_type'] = OpdAppointment.PAY_CHOICES.INSURANCE

        return data

    @staticmethod
    def form_time_slot(timestamp, time):
        to_zone = tz.gettz(settings.TIME_ZONE)
        min, hour = math.modf(time)
        min *= 60
        dt_field = timestamp.astimezone(to_zone).replace(hour=int(hour), minute=int(min), second=0, microsecond=0)
        return dt_field


class SetAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    time_slot_start = serializers.DateTimeField()
    time_slot_end = serializers.DateTimeField()

    def validate(self, data):
        request = self.context.get("request")
        user_profile = UserProfile.objects.filter(pk=int(data.get("profile").id)).first()
        if not user_profile:
            raise serializers.ValidationError("Profile does not exists.")
        if not user_profile.user == request.user:
            raise serializers.ValidationError("Profile of user is not correct")
        if OpdAppointment.objects.filter(~Q(status=OpdAppointment.REJECTED),
                                         profile=data.get('profile').id).count() >= 3:
            raise serializers.ValidationError("Can not create more than 3 appointments at a time.")
        return data


class OTPFieldSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    otp = serializers.IntegerField(max_value=9999)


class OTPConfirmationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    otp = serializers.IntegerField(max_value=9999)

    def validate(self, attrs):
        if not OpdAppointment.objects.filter(id=attrs['id']).filter(otp=attrs['otp']).exists():
            raise serializers.ValidationError("Invalid OTP")
        return attrs


class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    time_slot_start = serializers.DateTimeField(required=False)
    time_slot_end = serializers.DateTimeField(required=False)
    start_date = serializers.DateTimeField(required=False)
    # start_date = serializers.CharField(required=False)
    start_time = serializers.FloatField(required=False)
    cancellation_reason = serializers.PrimaryKeyRelatedField(
        queryset=CancellationReason.objects.filter(visible_on_front_end=True), required=False)
    cancellation_comment = serializers.CharField(required=False, allow_blank=True)


class DoctorImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorImage
        fields = ('name', )


class DoctorQualificationSerializer(serializers.ModelSerializer):
    qualification = serializers.ReadOnlyField(source='qualification.name')
    specialization = serializers.ReadOnlyField(source='specialization.name')
    college = serializers.ReadOnlyField(source='college.name')

    class Meta:
        model = DoctorQualification
        fields = ('passing_year', 'qualification', 'specialization', 'college')


class DoctorLanguageSerializer(serializers.ModelSerializer):

    language = serializers.ReadOnlyField(source='language.name')

    class Meta:
        model = DoctorLanguage
        fields = ('language', )


class DoctorHospitalSerializer(serializers.ModelSerializer):
    doctor = serializers.ReadOnlyField(source='doctor_clinic.doctor.name')
    hospital_name = serializers.ReadOnlyField(source='doctor_clinic.hospital.name')
    address = serializers.ReadOnlyField(source='doctor_clinic.hospital.get_hos_address')
    short_address = serializers.ReadOnlyField(source='doctor_clinic.hospital.get_short_address')
    hospital_id = serializers.ReadOnlyField(source='doctor_clinic.hospital.pk')
    hospital_thumbnail = serializers.SerializerMethodField()
    day = serializers.SerializerMethodField()
    discounted_fees = serializers.IntegerField(read_only=True, allow_null=True, source='deal_price')
    lat = serializers.SerializerMethodField(read_only=True)
    long = serializers.SerializerMethodField(read_only=True)
    insurance = serializers.SerializerMethodField(read_only=True)

    enabled_for_online_booking = serializers.SerializerMethodField(read_only=True)
    show_contact = serializers.SerializerMethodField(read_only=True)
    enabled_for_cod = serializers.BooleanField(source='doctor_clinic.hospital.enabled_for_cod')
    enabled_for_prepaid = serializers.BooleanField(source='doctor_clinic.hospital.enabled_for_prepaid')
    is_price_zero = serializers.SerializerMethodField()

    def get_show_contact(self, obj):
        if obj.doctor_clinic and obj.doctor_clinic.hospital and obj.doctor_clinic.hospital.spoc_details.all():
            return 1

        if obj.doctor_clinic and obj.doctor_clinic.doctor and obj.doctor_clinic.doctor.mobiles.all():
            return 1

        return 0

    
    def get_enabled_for_online_booking(self, obj):
        enable_for_online_booking = False
        if obj.doctor_clinic:
            doctor_clinic = obj.doctor_clinic
            if obj.doctor_clinic.hospital and obj.doctor_clinic.doctor:
                if doctor_clinic.hospital.enabled_for_online_booking and doctor_clinic.doctor.enabled_for_online_booking and doctor_clinic.enabled_for_online_booking:
                   enable_for_online_booking = True
        return enable_for_online_booking

    def get_lat(self, obj):
        if obj.doctor_clinic.hospital.location:
            return obj.doctor_clinic.hospital.location.y
        return None

    def get_long(self, obj):
        if obj.doctor_clinic.hospital.location:
            return obj.doctor_clinic.hospital.location.x
        return None

    def get_hospital_thumbnail(self, instance):
        request = self.context.get("request")
        return request.build_absolute_uri(
            instance.doctor_clinic.hospital.get_thumbnail()) if instance.doctor_clinic.hospital.get_thumbnail() else None

    def get_day(self, attrs):
        day = attrs.day
        return dict(DoctorClinicTiming.DAY_CHOICES).get(day)

    def validate(self, data):
        data['doctor'] = self.context['doctor']
        data['hospital'] = self.context['hospital']

        return data

    def get_insurance(self, obj):
        request = self.context.get("request")
        user = request.user
        resp = Doctor.get_insurance_details(user)

        # enabled for online booking check
        doctor_clinic = obj.doctor_clinic
        doctor = doctor_clinic.doctor
        hospital = doctor_clinic.hospital
        enabled_for_online_booking = doctor_clinic.enabled_for_online_booking and doctor.enabled_for_online_booking and hospital.enabled_for_online_booking

        if hospital.enabled_for_prepaid and obj.mrp is not None and resp['insurance_threshold_amount'] is not None and obj.mrp <= resp['insurance_threshold_amount'] and enabled_for_online_booking and \
                not (request.query_params.get('procedure_ids') or request.query_params.get('procedure_category_ids')) and doctor.is_enabled_for_insurance:

            user_insurance = None if not user.is_authenticated or user.is_anonymous else user.active_insurance
            if not user_insurance:
                return resp

            doctor_specialization = self.context.get('doctor_specialization',None)
            if not doctor_specialization:
                resp['is_insurance_covered'] = True
            else:
                specialization = doctor_specialization[1]
                doctor_specialization_count_dict = self.context.get('doctor_specialization_count_dict', {})
                if not doctor_specialization_count_dict:
                    resp['is_insurance_covered'] = True
                if specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST and doctor_specialization_count_dict.get(specialization, {}).get('count') >= settings.INSURANCE_GYNECOLOGIST_LIMIT:
                    resp['is_insurance_covered'] = False
                elif specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST and doctor_specialization_count_dict.get(specialization, {}).get('count') >= settings.INSURANCE_ONCOLOGIST_LIMIT:
                    resp['is_insurance_covered'] = False
                else:
                    resp['is_insurance_covered'] = True

        return resp

    def get_is_price_zero(self, obj):
        if obj.fees and obj.fees == 0:
            return True
        else:
            return False

    class Meta:
        model = DoctorClinicTiming
        fields = ('doctor', 'hospital_name', 'address','short_address', 'hospital_id', 'start', 'end', 'day', 'deal_price',
                  'discounted_fees', 'hospital_thumbnail', 'mrp', 'lat', 'long', 'id','enabled_for_online_booking',
                  'insurance', 'show_contact', 'enabled_for_cod', 'enabled_for_prepaid', 'is_price_zero')
        # fields = ('doctor', 'hospital_name', 'address', 'hospital_id', 'start', 'end', 'day', 'deal_price', 'fees',
        #           'discounted_fees', 'hospital_thumbnail', 'mrp',)


class DoctorEmailSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorEmail
        fields = ('email', 'is_primary')


class DoctorAssociationSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorAssociation
        fields = ('name', 'id')


class DoctorMobileSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorMobile
        fields = ('number', 'is_primary')


class DoctorExperienceSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorExperience
        fields = ('hospital', 'start_year', 'end_year', )


class DoctorAwardSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorAward
        fields = ('name', 'year')


class MedicalServiceSerializer(serializers.ModelSerializer):

    name = serializers.ReadOnlyField(source='service.name')
    description = serializers.ReadOnlyField(source='service.name')

    class Meta:
        model = DoctorMedicalService
        fields = ('id', 'name', 'description')


class DoctorPracticeSpecializationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True, source='specialization.name')

    class Meta:
        model = DoctorPracticeSpecialization
        fields = ('name', )


class DoctorProfileSerializer(serializers.ModelSerializer):
    images = DoctorImageSerializer(read_only=True, many=True)
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = DoctorPracticeSpecializationSerializer(read_only=True, many=True, source='doctorpracticespecializations')
    languages = DoctorLanguageSerializer(read_only=True, many=True)
    availability = serializers.SerializerMethodField(read_only=True)
    emails = DoctorEmailSerializer(read_only=True, many=True)
    mobiles = DoctorMobileSerializer(read_only=True, many=True)
    medical_services = MedicalServiceSerializer(read_only=True, many=True)
    experiences = DoctorExperienceSerializer(read_only=True, many=True)
    associations = DoctorAssociationSerializer(read_only=True, many=True)
    awards = DoctorAwardSerializer(read_only=True, many=True)
    display_name = serializers.ReadOnlyField(source='get_display_name')
    thumbnail = serializers.SerializerMethodField()

    def get_availability(self, obj):
        data = DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj).select_related("doctor_clinic__doctor",
                                                                                           "doctor_clinic__hospital")
        return DoctorHospitalSerializer(data, context=self.context, many=True).data

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        thumbnail = obj.get_thumbnail()
        if thumbnail:
            return request.build_absolute_uri(thumbnail) if thumbnail else None
        else:
            return None


    # def to_representation(self, doctor):
    #     parent_rep = super().to_representation(doctor)
    #     try:
    #         parent_rep['images'] = parent_rep['images'][0]
    #     except KeyError as e:
    #         return parent_rep
    #
    #     return parent_rep

    class Meta:
        model = Doctor
        fields = (
            'id', 'name', 'display_name', 'gender', 'about', 'license', 'emails', 'practicing_since', 'images',
            'languages', 'qualifications', 'general_specialization', 'availability', 'mobiles', 'medical_services',
            'experiences', 'associations', 'awards', 'appointments', 'hospitals', 'thumbnail', 'signature', 'is_live',
            'source_type')


class HospitalModelSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    long = serializers.SerializerMethodField()
    hospital_thumbnail = serializers.SerializerMethodField()

    address = serializers.SerializerMethodField()

    def get_address(self, obj):
        return obj.get_hos_address() if obj.get_hos_address() else None

    def get_lat(self, obj):
        loc = obj.location
        if loc:
            return loc.y
        return None

    def get_long(self, obj):
        loc = obj.location
        if loc:
            return loc.x
        return None

    def get_hospital_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            return obj.get_thumbnail()
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'operational_since', 'lat', 'long', 'address', 'registration_number',
                  'building', 'sublocality', 'locality', 'city', 'hospital_thumbnail', )


class DoctorHospitalScheduleSerializer(serializers.ModelSerializer):
    # hospital = HospitalModelSerializer()
    day = serializers.SerializerMethodField()
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()

    def get_day(self, obj):
        day = obj.day
        return dict(DoctorClinicTiming.DAY_CHOICES).get(day)

    def get_start(self, obj):
        start = obj.start
        return dict(DoctorClinicTiming.TIME_CHOICES).get(start)

    def get_end(self, obj):
        end = obj.end
        return dict(DoctorClinicTiming.TIME_CHOICES).get(end)

    class Meta:
        model = DoctorClinicTiming
        # fields = ('id', 'day', 'start', 'end', 'fees', 'hospital')
        fields = ('day', 'start', 'end', 'fees')


class DoctorHospitalListSerializer(serializers.Serializer):
    min_fees = serializers.IntegerField()
    hospital = HospitalModelSerializer()
    # hospital = serializers.SerializerMethodField()

    def get_hospital(self, obj):
        queryset = Hospital.objects.get(pk=obj['hospital'])
        serializer = HospitalModelSerializer(queryset, context=self.context)
        return serializer.data


class DoctorBlockCalenderSerialzer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    # def validate(self, attrs):
    #     request = self.context.get("request")
    #     if DoctorLeave.objects.filter(doctor=request.user.doctor.id, deleted_at__isnull=True).exists():
    #         raise serializers.ValidationError("Doctor can apply on one leave at a time")
    #     return attrs


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')
    doctor_name = serializers.CharField(read_only=True, source='doctor.name')
    hospital_name = serializers.CharField(read_only=True, source='hospital.name', allow_null=True)

    class Meta:
        model = DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')


class PrescriptionFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = PrescriptionFile
        fields = ('prescription', 'name')


class PrescriptionFileDeleteSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(
        queryset=OpdAppointment.objects.all())
    id = serializers.IntegerField()

    def validate_appointment(self, value):
        request = self.context.get('request')
        if not OpdAppointment.objects.filter(doctor=request.user.doctor).exists():
            logger.error(
                "Error 'Appointment is not correct' for removing Prescription with data - " + json.dumps(
                    request.data))
            raise serializers.ValidationError("Appointment is not correct.")
        return value


class PrescriptionSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(queryset=OpdAppointment.objects.all())
    prescription_details = serializers.CharField(allow_blank=True, allow_null=True, required=False, max_length=300)
    name = serializers.FileField()

    # def validate_appointment(self, value):
    #     request = self.context.get('request')
    #     if not OpdAppointment.objects.filter(doctor=request.user.doctor).exists():
    #         logger.error(
    #             "Error 'Appointment is not correct' for Prescription create with data - " + json.dumps(
    #                 request.data.get('appointment')))
    #         raise serializers.ValidationError("Appointment is not correct.")
    #     return value


class DoctorListSerializer(serializers.Serializer):
    SORT_CHOICES = ('fees', 'experience', 'distance', )
    SITTING_CHOICES = [type_choice[1] for type_choice in Hospital.HOSPITAL_TYPE_CHOICES]
    specialization_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=str)
    condition_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=str)
    procedure_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=str)
    procedure_category_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=str)
    longitude = serializers.FloatField(default=77.071848)
    latitude = serializers.FloatField(default=28.450367)
    sits_at = CommaSepratedToListField(required=False, max_length=100, typecast_to=str)
    sort_on = serializers.ChoiceField(choices=SORT_CHOICES, required=False)
    min_fees = serializers.IntegerField(required=False)
    max_fees = serializers.IntegerField(required=False)
    is_female = serializers.BooleanField(required=False)
    is_available = serializers.BooleanField(required=False)
    search_id = serializers.IntegerField(required=False, allow_null=True)
    doctor_name = serializers.CharField(required=False)
    hospital_name = serializers.CharField(required=False)
    max_distance = serializers.IntegerField(required=False, allow_null=True)
    min_distance = serializers.IntegerField(required=False, allow_null=True)
    is_insurance = serializers.BooleanField(required=False)
    hospital_id = serializers.IntegerField(required=False, allow_null=True)
    locality = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    ipd_procedure_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=str)

    def validate_ipd_procedure_ids(self, attrs):
        try:
            temp_attrs = [int(attr) for attr in attrs]
            temp_attrs=set(temp_attrs)
            if IpdProcedure.objects.filter(id__in=temp_attrs, is_enabled=True).count() == len(temp_attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid IPD Procedure IDs')
        raise serializers.ValidationError('Invalid IPD Procedure IDs')


    def validate_procedure_ids(self, attrs):
        try:
            temp_attrs = [int(attr) for attr in attrs]
            if Procedure.objects.filter(id__in=temp_attrs, is_enabled=True).count() == len(temp_attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Procedure IDs')
        raise serializers.ValidationError('Invalid Procedure IDs')


    def validate_procedure_category_ids(self, attrs):
        try:
            temp_attrs = [int(attr) for attr in attrs]
            if ProcedureCategory.objects.filter(id__in=temp_attrs, is_live=True).count() == len(temp_attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Procedure Category IDs')
        raise serializers.ValidationError('Invalid Procedure Category IDs')

    def validate_specialization_id(self, value):
        request = self.context.get("request")
        if not Specialization.objects.filter(id__in=value.strip()).count() == len(value.strip()):
            logger.error(
                "Error 'Invalid specialization Id' for Doctor Search with data - " + json.dumps(
                    request.query_params))
            raise serializers.ValidationError("Invalid specialization Id.")
        return value

    def validate_sits_at(self, value):
        if not set(value).issubset(set(self.SITTING_CHOICES)):
            raise serializers.ValidationError("Not a Valid Choice")
        return value


class DoctorProfileUserViewSerializer(DoctorProfileSerializer):
    #emails = None
    experience_years = serializers.IntegerField(allow_null=True)
    is_license_verified = serializers.SerializerMethodField()
    # hospitals = DoctorHospitalSerializer(read_only=True, many=True, source='get_hospitals')
    hospitals = serializers.SerializerMethodField(read_only=True)
    procedures = serializers.SerializerMethodField(read_only=True)
    hospital_count = serializers.IntegerField(read_only=True, allow_null=True)
    enabled_for_online_booking = serializers.BooleanField()
    availability = None
    seo = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    display_rating_widget = serializers.SerializerMethodField()
    rating_graph = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()
    unrated_appointment = serializers.SerializerMethodField()
    is_gold = serializers.SerializerMethodField()
    search_data = serializers.SerializerMethodField()
    enabled_for_cod = serializers.SerializerMethodField()

    def get_enabled_for_cod(self, obj):
        return obj.enabled_for_cod()

    def get_is_license_verified(self, obj):        
        doctor_clinics = obj.doctor_clinics.all()
        for doctor_clinic in doctor_clinics:
            if doctor_clinic and doctor_clinic.hospital:
                if obj.is_license_verified and obj.enabled_for_online_booking and doctor_clinic.hospital.enabled_for_online_booking and doctor_clinic.enabled_for_online_booking:
                    return True
        return False

    def get_search_data(self, obj):
        data = {}
        lat = None
        lng = None
        specialization = None
        specialization_id = None
        title = None
        locality = None
        sublocality = None
        max_distance = 15000
        #clinics = [clinic_hospital for clinic_hospital in obj.doctor_clinics.all()]
        #top_specialization = None
        result_count = None
        url = None

        entity = self.context.get('entity')
        if entity:
            locality = entity.locality_value
            sublocality = entity.sublocality_value
            lat = entity.sublocality_latitude
            lng = entity.sublocality_longitude


        # if clinics:
        #     hospital = clinics[0]
        #     if hospital.hospital and hospital.hospital.location:
        #         lat = hospital.hospital.location.y
        #         long = hospital.hospital.location.x
        #         hosp_entity_relation = hospital.hospital.entity.all().prefetch_related('location')
        #         for entity_relation in hosp_entity_relation:
        #             entity_address = entity_relation.location
        #             if entity_address.type_blueprint == 'LOCALITY':
        #                 locality = entity_address.alternative_value
        #             if entity_address.type_blueprint == 'SUBLOCALITY':
        #                 sublocality = entity_address.alternative_value
            if len(obj.doctorpracticespecializations.all())>0:
                dsp = [specialization.specialization for specialization in obj.doctorpracticespecializations.all()]
                top_specialization = DoctorPracticeSpecialization.objects.filter(specialization__in=dsp).values('specialization')\
                    .annotate(doctor_count=Count('doctor'),name=Max('specialization__name')).order_by('-doctor_count').first()

                if top_specialization:
                        specialization = top_specialization.get('name')
                        specialization_id = top_specialization.get('specialization')

            if lat and lng and specialization_id:
                doctors = Doctor.objects.filter(
                    doctorpracticespecializations__specialization=specialization_id,
                    hospitals__location__dwithin=(Point(float(lng), float(lat)), D(m=max_distance)),
                    is_live=True,
                    is_test_doctor=False,
                    is_internal=False,
                    hospitals__is_live=True
                )

                result_count = doctors.values('id').distinct().count()

            if sublocality and locality and specialization_id:

                url = EntityUrls.objects.filter(sublocality_value=sublocality, locality_value=locality, specialization_id=specialization_id,
                                          is_valid=True, sitemap_identifier='SPECIALIZATION_LOCALITY_CITY').values_list('url').first()

                title = specialization + 's in ' + sublocality + ' ' + locality

            if lat and lng and specialization_id and title and result_count and url:
                return {'lat':lat, 'long':lng, 'specialization_id': specialization_id, 'title':title,
                        'result_count':result_count, 'url': url[0]}
        return None

    def get_display_rating_widget(self, obj):
        rate_count = obj.rating.filter(is_live=True).count()
        avg = 0
        if rate_count:
            all_rating = []
            for rate in obj.rating.filter(is_live=True):
                all_rating.append(rate.ratings)
            if all_rating:
                avg = sum(all_rating) / len(all_rating)
        if rate_count > 5 or (rate_count <= 5 and avg > 4):
            return True
        return False

    def get_is_gold(self, obj):
        return False #obj.is_gold and obj.enabled_for_online_booking

    def get_rating(self, obj):
        app = OpdAppointment.objects.select_related('profile').filter(doctor_id=obj.id).all()

        queryset = obj.rating.select_related('user').prefetch_related('compliment', 'user__profiles').exclude(Q(review='') | Q(review=None))\
                                                            .filter(is_live=True)\
                                                            .order_by('-ratings', '-updated_at')
        reviews = rating_serializer.RatingsModelSerializer(queryset, many=True, context={'app': app})
        return reviews.data[:5]

    def get_unrated_appointment(self, obj):
        request = self.context.get('request')
        if request:
            if request.user.is_authenticated:
                user = request.user
                opd_app = None
                opd = user.appointments.filter(doctor=obj, status=OpdAppointment.COMPLETED).order_by('-updated_at').first()
                if opd and opd.is_rated == False:
                    opd_app = opd
                if opd_app:
                    data = AppointmentRetrieveSerializer(opd_app, many=False, context={'request': request})
                    return data.data
            return None

    def get_rating_graph(self, obj):
        if obj and obj.rating:
            data = rating_serializer.RatingsGraphSerializer(obj.rating.prefetch_related('compliment')
                                                                      .filter(is_live=True),
                                                            context={'request':self.context.get('request')}).data
            return data
        return None

    def get_seo(self, obj):
        if self.parent:
            return None

        specializations = [doctor_specialization.specialization for doctor_specialization in obj.doctorpracticespecializations.all()]
        clinics = [clinic_hospital for clinic_hospital in obj.doctor_clinics.all()]
        # entity = EntityUrls.objects.filter(entity_id=obj.id, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE,
        #                                    is_valid=True)
        sublocality = None
        locality = None
        entity = None
        if self.context.get('entity'):
            entity = self.context.get('entity')
            if entity.additional_info:
                locality = entity.additional_info.get('locality_value')
                sublocality = entity.additional_info.get('sublocality_value')

        title = "Dr. " + obj.name
        description = "Dr. " + obj.name + ': ' + "Dr. " + obj.name

        doc_spec_list = []

        for name in specializations:
            doc_spec_list.append(str(name))
        if len(doc_spec_list) >= 1:
            title +=  ' - '+', '.join(doc_spec_list)
            description += ' is ' + ', '.join(doc_spec_list)
        if sublocality and locality:
            # title += ' in ' + sublocality + " " + locality + ' - Consult Online'
            description += ' in ' + sublocality + " " + locality
        elif locality:
            # title += ' in ' + locality + ' - Consult Online'
            description += ' in ' + locality

        title += ' | Book Appointment Online'

        hospital = []
        for hospital_name in clinics:
            hospital.append(str(hospital_name.hospital))
        if len(hospital) >= 1:
            description += ' consulting patients at '+', '.join(hospital)

        description += '. Book appointments online, check fees, address and more.'

        doctor_realted_hospitals = obj.doctor_clinics.all()

        #if hospital type is null then use a default large value 
        doctor_realted_hospitals =sorted(doctor_realted_hospitals, key=lambda x: x.hospital.hospital_type or 100)
        doctor_associated_hospital = None

        if len(doctor_realted_hospitals):
            doctor_hospital = doctor_realted_hospitals[0]
            doctor_associated_hospital = doctor_hospital.hospital

        price = None
        opening_hours = ''
        address_locality = ''
        address_city = ''
        address_pincode = ''
        street_address = ''
        latitude = None
        longitude = None

        if doctor_associated_hospital:
            address_locality = doctor_associated_hospital.locality
            address_city = doctor_associated_hospital.city
            address_pincode = doctor_associated_hospital.pin_code
            street_address = doctor_associated_hospital.get_hos_address()
            latitude = doctor_associated_hospital.location.y if getattr(doctor_associated_hospital, 'location', None) else None
            longitude = doctor_associated_hospital.location.x if getattr(doctor_associated_hospital, 'location', None) else None
            if doctor_hospital:
                availability_qs = doctor_hospital.availability
                if availability_qs.exists():
                    av = availability_qs.all()[0]
                    opening_hours = '%.2f-%.2f' % (av.start,
                                                   av.end)
                    price = av.mrp

        schema = {
            'name': self.instance.get_display_name(),
            'image': self.instance.get_thumbnail() if self.instance.get_thumbnail() else static('web/images/doc_placeholder.png'),
            '@context': 'http://schema.org',
            '@type': 'MedicalBusiness',
            'address': {
                '@type': 'PostalAddress',
                'addressLocality': address_locality,
                'addressRegion': address_city,
                'postalCode': address_pincode,
                'streetAddress': street_address
            },
            'description': self.instance.about,
            'priceRange': price,
            'openingHours': opening_hours,
            'location': {
                '@type': 'Place',
                'geo': {
                    '@type': 'GeoCircle',
                    'geoMidpoint': {
                        '@type': 'GeoCoordinates',
                        'latitude': latitude,
                        'longitude': longitude
                    }
                }
            }

        }
        if entity:
            new_object = NewDynamic.objects.filter(url__url=entity.url, is_enabled=True).first()
            if new_object:
                if new_object.meta_title:
                    title = new_object.meta_title
                if new_object.meta_description:
                    description = new_object.meta_description

        return {'title': title, "description": description, 'schema': schema}

    def get_breadcrumb(self, obj):

        if self.parent:
            return None
        # entity = EntityUrls.objects.filter(entity_id=obj.id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Doctor')
        breadcrums = None
        if self.context.get('entity'):
            entity = self.context.get('entity')
            breadcrums = entity.additional_info.get('breadcrums')
            if breadcrums:
                return breadcrums
        return breadcrums

    def get_procedures(self, obj):
        selected_clinic = self.context.get('hospital_id')
        category_ids = self.context.get('category_ids')
        selected_procedure_ids = self.context.get('selected_procedure_ids')
        other_procedure_ids = self.context.get('other_procedure_ids')
        data = obj.doctor_clinics.all()
        result_for_a_doctor = OrderedDict()
        for doctor_clinic in data:
            all_doctor_clinic_procedures = list(doctor_clinic.procedures_from_doctor_clinic.all())
            selected_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                            selected_procedure_ids)
            other_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                         other_procedure_ids)

            selected_procedures_serializer = DoctorClinicProcedureSerializer(selected_procedures_data,
                                                                             context={'is_selected': True,
                                                                                      'category_ids': category_ids if category_ids else None},
                                                                             many=True)
            other_procedures_serializer = DoctorClinicProcedureSerializer(other_procedures_data,
                                                                          context={'is_selected': False,
                                                                                   'category_ids': category_ids if category_ids else None},
                                                                          many=True)
            selected_procedures_list = list(selected_procedures_serializer.data)
            other_procedures_list = list(other_procedures_serializer.data)
            final_result = get_procedure_categories_with_procedures(selected_procedures_list,
                                                                    other_procedures_list)
            result_for_a_doctor[doctor_clinic.hospital.pk] = final_result
        if selected_clinic and result_for_a_doctor.get(selected_clinic, None):
            result_for_a_doctor.move_to_end(selected_clinic, last=False)
        return result_for_a_doctor

    def get_hospitals(self, obj):
        request = self.context.get('request')
        user = request.user
        data = DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj,
                                                 doctor_clinic__enabled=True,
                                                 doctor_clinic__hospital__is_live=True).select_related(
            "doctor_clinic__doctor", "doctor_clinic__hospital").prefetch_related("doctor_clinic__hospital__spoc_details","doctor_clinic__doctor__mobiles")
        if obj:
            doctor_specialization = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(obj)
            if doctor_specialization:
                self.context['doctor_specialization'] = doctor_specialization
                user_insurance = None if not user.is_authenticated or user.is_anonymous else user.active_insurance
                if user_insurance:
                    doctor_specialization_count_dict = InsuranceDoctorSpecializations.get_already_booked_specialization_appointments(user, user_insurance, doctor_specialization=doctor_specialization[1])
                    self.context['doctor_specialization_count_dict'] = doctor_specialization_count_dict
        return DoctorHospitalSerializer(data, context=self.context, many=True).data

    class Meta:
        model = Doctor
        # exclude = ('created_at', 'updated_at', 'onboarding_status', 'is_email_verified',
        #            'is_insurance_enabled', 'is_retail_enabled', 'user', 'created_by', )
        fields = ('about', 'is_license_verified', 'additional_details', 'display_name', 'associations', 'awards', 'experience_years', 'experiences', 'gender',
                  'hospital_count', 'hospitals', 'procedures', 'id', 'languages', 'name', 'practicing_since', 'qualifications',
                  'general_specialization', 'thumbnail', 'license', 'is_live', 'seo', 'breadcrumb', 'rating', 'rating_graph',
                  'enabled_for_online_booking', 'unrated_appointment', 'display_rating_widget', 'is_gold', 'search_data', 'enabled_for_cod')


class DoctorAvailabilityTimingSerializer(serializers.Serializer):
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True), required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True), required=False)


class DoctorTimeSlotSerializer(serializers.Serializer):
    images = DoctorImageSerializer(read_only=True, many=True)
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = DoctorPracticeSpecializationSerializer(read_only=True, many=True, source='doctorpracticespecializations')

    class Meta:
        model = Doctor
        fields = ('id', 'images', 'qualifications', 'general_specialization', )


class AppointmentRetrieveDoctorSerializer(DoctorProfileSerializer):
    class Meta:
        model = Doctor
        fields = ('id', 'name', 'gender', 'about', 'practicing_since',
                  'qualifications', 'general_specialization', 'display_name')


class QrcodeRetrieveDoctorSerializer(AppointmentRetrieveDoctorSerializer):
    check_qr_code = serializers.SerializerMethodField()


    def get_check_qr_code(self, obj):
        return bool(len(obj.qr_code.all()))

    class Meta(AppointmentRetrieveDoctorSerializer.Meta):
        model = Doctor
        fields = AppointmentRetrieveDoctorSerializer.Meta.fields + ('check_qr_code',)

class OpdAppointmentBillingSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp',
                  'allowed_action', 'effective_price', 'fees', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail', 'payment_type')


class AppointmentRetrieveSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()
    procedures = serializers.SerializerMethodField()
    insurance = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp', 'is_rated', 'rating_declined',
                  'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail', 'procedures', 'mrp',
                  'insurance', 'invoices', 'cancellation_reason', 'payment_type')

    def get_insurance(self, obj):
        request = self.context.get("request")
        resp = {
            'is_appointment_insured': False,
            'insurance_threshold_amount': None,
            'is_user_insured': False
        }
        if request:
            logged_in_user = request.user
            if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
                user_insurance = logged_in_user.active_insurance
                if user_insurance:
                    insurance_threshold = user_insurance.insurance_threshold
                    if insurance_threshold:
                        resp['insurance_threshold_amount'] = 0 if insurance_threshold.opd_amount_limit is None else \
                            insurance_threshold.opd_amount_limit
                        resp['is_user_insured'] = True
                        resp['insurance_expiry_date'] = user_insurance.expiry_date
                    if obj.payment_type == 3 and obj.insurance_id == user_insurance.id:
                        resp['is_appointment_insured'] = True
                    else:
                        resp['is_appointment_insured'] = False

        return resp

    def get_procedures(self, obj):
        if obj:
            return OpdAppointmentProcedureMappingSerializer(obj.procedure_mappings.all().select_related('procedure'), many=True).data
        return []

    def get_invoices(self, obj):
        return obj.get_invoice_urls()

    def get_cancellation_reason(self, obj):
        return obj.get_serialized_cancellation_reason()


class NewAppointmentRetrieveSerializer(AppointmentRetrieveSerializer):
    doctor = QrcodeRetrieveDoctorSerializer()

    class Meta(AppointmentRetrieveSerializer.Meta):
        model = OpdAppointment
        # fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp', 'is_rated', 'rating_declined',
        #           'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start', 'time_slot_end',
        #           'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail', 'procedures', 'mrp',
        #           'invoices', 'cancellation_reason', 'payment_type')
        fields = AppointmentRetrieveSerializer.Meta.fields



class DoctorAppointmentRetrieveSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()
    mask_data = serializers.SerializerMethodField()
    mrp = serializers.ReadOnlyField(source='fees')

    def get_mask_data(self, obj):
        mask_number = obj.mask_number.first()
        if mask_number:
            return mask_number.build_data()
        return None

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'allowed_action', 'effective_price',
                  'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail',
                  'display_name', 'mask_data', 'payment_type', 'mrp', 'updated_at', 'created_at')


class HealthTipSerializer(serializers.ModelSerializer):

    class Meta:
        model = HealthTip
        fields = ('id', 'text',)


class MedicalConditionSerializer(serializers.ModelSerializer):

    id = serializers.ReadOnlyField(source='condition.id')
    name = serializers.ReadOnlyField(source='condition.name')
    specialization = serializers.SerializerMethodField()

    def get_specialization(self, obj):
        spc_id = []
        if obj:
            for spc in obj.condition.specialization.all():
                spc_id.append(spc.id)
        return spc_id

    class Meta:
        model = CommonMedicalCondition
        fields = ('id', 'name', 'specialization',)


class CommonSpecializationsSerializer(serializers.ModelSerializer):

    id = serializers.ReadOnlyField(source='specialization.id')
    name = serializers.ReadOnlyField(source='specialization.name')
    icon = serializers.SerializerMethodField
    url = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    def get_url(self, obj):
        url = None
        if self.context and self.context.get('spec_urls'):
            url = self.context.get('spec_urls')[obj.specialization_id]
        return url

    class Meta:
        model = CommonSpecialization
        fields = ('id', 'name', 'icon', 'url')


class ConfigGetSerializer(serializers.Serializer):

    os = serializers.CharField(max_length=10)
    ver = serializers.CharField(max_length=10)


class OpdAppointmentCompleteTempSerializer(serializers.Serializer):

    opd_appointment = serializers.IntegerField()
    otp = serializers.IntegerField(max_value=9999)

    def validate(self, attrs):
        appointment_id = attrs.get('opd_appointment')
        appointment = OpdAppointment.objects.filter(id=appointment_id).first()
        if appointment:
            if appointment.status == OpdAppointment.COMPLETED:
                raise serializers.ValidationError("Appointment Already Completed.")
            elif appointment.status == OpdAppointment.CANCELLED:
                raise serializers.ValidationError("Cannot Complete a Cancelled Appointment.")
            if not appointment.otp == attrs['otp']:
                raise serializers.ValidationError("Invalid OTP.")
        return attrs


class DoctorRatingSerializer(serializers.Serializer):
    rating = serializers.SerializerMethodField()

    def get_doctor_rating_summary(self):
        rating_row = self.rating.all()
        review_row = self.rating.filter(review__isnull=False).all()
        rating_count = rating_row.count()
        review_count = review_row.count()
        average_rating = rating_row.aggregate(Avg('ratings'))
        average_rating = average_rating['ratings__avg']

        return {'rating_count': rating_count, 'average_rating': average_rating, 'review_count': review_count}


class DoctorFeedbackBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=10, required=False)
    feedback = serializers.CharField(max_length=512, required=False)
    feedback_tags = serializers.ListField(required=False)
    email = serializers.EmailField(required=False)
    app_version = serializers.CharField(required=False, allow_blank=True)
    code_push_version = serializers.CharField(required=False, allow_blank=True)
    os = serializers.CharField(required=False, allow_blank=True)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all(), required=False)


class AdminCreateBodySerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    name = serializers.CharField(max_length=24, required=False)
    billing_enabled = serializers.BooleanField()
    appointment_enabled = serializers.BooleanField()
    entity_type = serializers.ChoiceField(choices=GenericAdminEntity.EntityChoices)
    id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=User.USER_TYPE_CHOICES)
    doc_profile = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), required=False)
    assoc_doc = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all()), required=False)
    assoc_hosp = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all()),
                                      required=False)

    def validate(self, attrs):
        if attrs['type'] == User.STAFF and 'name' not in attrs:
            raise serializers.ValidationError("Name is Required.")
        if attrs['type'] == User.DOCTOR and 'doc_profile' not in attrs and not attrs.get('doc_profile'):
            raise serializers.ValidationError("DocProfile is Required.")
        if attrs['entity_type'] == GenericAdminEntity.DOCTOR and 'assoc_hosp'not in attrs:
            raise serializers.ValidationError("Associated Hospitals  are Required.")
        if attrs['entity_type'] == GenericAdminEntity.DOCTOR and not Doctor.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Doctor Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and not Hospital.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Hospital Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.LAB and not lab_models.Lab.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Lab Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and 'assoc_doc' not in attrs:
            raise serializers.ValidationError("Associated Doctors are Required.")
        if attrs.get('type') == User.STAFF:
            valid_query = GenericAdmin.objects.filter(phone_number=attrs['phone_number'], entity_type=attrs['entity_type'])
            if attrs.get('entity_type')==GenericAdminEntity.DOCTOR:
                valid_query = valid_query.filter(doctor_id=attrs['id'], hospital_id__in=attrs.get('assoc_hosp')) \
                    if attrs.get('assoc_hosp') else valid_query.filter(doctor_id=attrs['id'], hospital_id=None)
            elif attrs.get('entity_type') == GenericAdminEntity.HOSPITAL:
                valid_query = valid_query.filter(hospital_id=attrs['id'], doctor_id=None)
                #     if attrs.get('assoc_doc') else valid_query.filter(hospital_id=attrs['id'], doctor_id=None)
            else:
                valid_query = GenericLabAdmin.objects.filter(lab_id=attrs['id'], phone_number=attrs['phone_number'])
            if valid_query.exists():
                raise serializers.ValidationError("Duplicate Permissions Exists.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and attrs.get('type') == User.DOCTOR:
            dquery = DoctorNumber.objects.select_related('doctor', 'hospital').filter(phone_number=attrs['phone_number'], hospital_id=attrs.get('id'))
            if dquery.exists():
                raise serializers.ValidationError("Phone number already assigned to Doctor " + dquery.first().doctor.name +". Add number as admin to manage multiple doctors.")
        return attrs
        # if DoctorNumber.objects.filter(doctor=attrs['doc_profile'], phone_number=attrs['phone_number']).exists():
        #     raise serializers.ValidationError("DocProfile already Allocated.")


class EntityListQuerySerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=GenericAdminEntity.EntityChoices)
    id = serializers.IntegerField()


class HospitalEntitySerializer(HospitalModelSerializer):
    entity_type = serializers.SerializerMethodField()

    def get_entity_type(self, obj):
        return GenericAdminEntity.HOSPITAL

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'entity_type', 'address', 'is_billing_enabled', 'is_appointment_manager',
                  'is_live', 'source_type')


class DoctorEntitySerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    entity_type = serializers.SerializerMethodField()

    def get_entity_type(self, obj):
        return GenericAdminEntity.DOCTOR

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        thumbnail = obj.get_thumbnail()
        if thumbnail:
            return request.build_absolute_uri(thumbnail) if thumbnail else None
        else:
            return None

    class Meta:
        model = Doctor
        fields = ('id', 'thumbnail', 'name', 'entity_type', 'qualifications', 'is_live', 'source_type')


class AdminUpdateBodySerializer(AdminCreateBodySerializer):
    remove_list = serializers.ListField()
    old_phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999, required=False)


    def validate(self, attrs):
        if attrs['type'] == User.STAFF and 'name' not in attrs:
            raise serializers.ValidationError("Name is Required.")
        if attrs['type'] == User.DOCTOR and 'doc_profile' not in attrs and not attrs.get('doc_profile'):
            raise serializers.ValidationError("DocProfile is Required.")
        if attrs['entity_type'] == GenericAdminEntity.DOCTOR and 'assoc_hosp'not in attrs:
            raise serializers.ValidationError("Associated Hospitals  are Required.")
        if attrs['entity_type'] == GenericAdminEntity.DOCTOR and not Doctor.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Doctor Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and not Hospital.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Hospital Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.LAB and not lab_models.Lab.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("entity Lab Not Found.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and 'assoc_doc' not in attrs:
            raise serializers.ValidationError("Associated Doctors are Required.")
        if attrs['entity_type'] == GenericAdminEntity.HOSPITAL and attrs.get('type') == User.DOCTOR:
            dquery = DoctorNumber.objects.select_related('doctor', 'hospital').filter(phone_number=attrs['phone_number'], hospital_id=attrs.get('id'))
            if dquery.exists():
                raise serializers.ValidationError("Phone number already assigned to Doctor " + dquery.first().doctor.name +". Add number as admin to manage multiple doctors.")
        return attrs

class AdminDeleteBodySerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    entity_type = serializers.ChoiceField(choices=GenericAdminEntity.EntityChoices)
    id = serializers.IntegerField()


class HospitalCardSerializer(serializers.Serializer):

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class DoctorDetailsRequestSerializer(serializers.Serializer):
    procedure_category_ids = CommaSepratedToListField(required=False, max_length=500)
    procedure_ids = CommaSepratedToListField(required=False, max_length=500)
    hospital_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        return super().validate(attrs)

    def validate_procedure_ids(self, attrs):
        try:
            temp_attrs = [int(attr) for attr in attrs]
            if Procedure.objects.filter(id__in=temp_attrs, is_enabled=True).count() == len(temp_attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Procedure IDs')
        raise serializers.ValidationError('Invalid Procedure IDs')

    def validate_procedure_category_ids(self, attrs):
        try:
            temp_attrs = [int(attr) for attr in attrs]
            if ProcedureCategory.objects.filter(id__in=temp_attrs, is_live=True).count() == len(temp_attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Procedure Category IDs')
        raise serializers.ValidationError('Invalid Procedure Category IDs')

    def validate_hospital_id(self, attrs):
        try:
            temp_attr = int(attrs)
            if Hospital.objects.filter(id=temp_attr, is_live=True).count():
                return attrs
        except:
            raise serializers.ValidationError('Invalid Hospital ID.')


class OfflinePatientBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=24)
    sms_notification = serializers.BooleanField(required=False)
    share_with_hospital = serializers.BooleanField(required=False)
    gender = serializers.ChoiceField(choices=OfflinePatients.GENDER_CHOICES, required=False, allow_null=True)
    dob = serializers.DateField(required=False, format="%Y-%m-%d", allow_null=True)
    calculated_dob = serializers.DateField(required=False, format="%Y-%m-%d", allow_null=True)
    referred_by = serializers.ChoiceField(choices=OfflinePatients.REFERENCE_CHOICES, required=False, allow_null=True)
    medical_history = serializers.CharField(required=False, max_length=256, allow_null=True)
    welcome_message = serializers.CharField(required=False, max_length=256)
    display_welcome_message = serializers.BooleanField(required=False)
    phone_number = serializers.ListField(required=False)
    id = serializers.UUIDField()
    age = serializers.IntegerField(required=False)


class OfflinePatientExplicitSerializer(OfflinePatientBodySerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), required=False)
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all(), required=False)


class OfflineAppointmentBodySerializer(serializers.Serializer):
    patient = OfflinePatientBodySerializer(many=False, allow_null=True, required=False)
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all())
    time_slot_start = serializers.DateTimeField()
    id = serializers.CharField()


class OfflineAppointmentUpdateBodySerializer(OfflineAppointmentBodySerializer):
    status = serializers.IntegerField()
    is_docprime = serializers.BooleanField()


class OfflineAppointmentCreateSerializer(serializers.Serializer):
    data = OfflineAppointmentBodySerializer(many=True)


class OfflineAppointmentUpdateSerializer(serializers.Serializer):
    data = OfflineAppointmentUpdateBodySerializer(many=True)


class OfflinePatientCreateSerializer(serializers.Serializer):
    data = OfflinePatientExplicitSerializer(many=True)


class GetOfflinePatientsSerializer(serializers.Serializer):
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(Q(is_live=True) | Q(source_type=Doctor.PROVIDER)), required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(Q(is_live=True) | Q(source_type=Hospital.PROVIDER)), required=False)
    updated_at = serializers.DateField(format="%Y-%m-%d", required=False)


class OfflineAppointmentFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(format="%Y-%m-%d", required=False)
    end_date = serializers.DateField(format="%Y-%m-%d", required=False)
    updated_at = serializers.DateField(format="%Y-%m-%d", required=False)
    appointment_id = serializers.CharField(required=False)


class OfflinePatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfflinePatients
        fields = ('id', 'name', 'dob', 'calculated_dob', 'gender', 'age','referred_by', 'display_welcome_message',
                  'share_with_hospital', 'sms_notification', 'medical_history', 'updated_at')


class AppointmentMessageSerializer(serializers.Serializer):
    REMINDER = 1
    DIRECTIONS = 2

    type_choices = ((REMINDER, "Reminder"), (DIRECTIONS, "Directions"))

    type = serializers.ChoiceField(choices=type_choices)
    id = serializers.CharField()
    is_docprime = serializers.BooleanField()

    def validate(self, attrs):
        from ondoc.doctor.models import OpdAppointment, OfflineOPDAppointments

        if attrs.get('is_docprime'):
            query = OpdAppointment.objects.filter(id=attrs['id'])
        else:
            query = OfflineOPDAppointments.objects.filter(id=attrs['id'])
        if not query.exists():
            raise serializers.ValidationError('Appointment Id Not Found')
        attrs['appointment'] = query.first()
        return attrs


class IpdProcedureFeatureSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='feature.name')
    icon = serializers.SerializerMethodField()

    class Meta:
        model = IpdProcedureFeatureMapping
        fields = ('name', 'value', 'icon')

    def get_icon(self, obj):
        request = self.context.get('request')
        photo_url = obj.feature.icon.url if obj.feature and obj.feature.icon else None
        return request.build_absolute_uri(photo_url)


class IpdProcedureAllDetailsSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='detail_type.name')
    show_doctors = serializers.BooleanField(source='detail_type.show_doctors')
    doctors = serializers.SerializerMethodField()

    class Meta:
        model = IpdProcedureDetail
        fields = ('name', 'value', 'show_doctors', 'doctors')

    def get_doctors(self, obj):
        result = {}
        if obj.detail_type.show_doctors:
            result = self.context.get('doctor_result_data', {})
        return result


class IpdProcedureDetailSerializer(serializers.ModelSerializer):
    features = IpdProcedureFeatureSerializer(source='feature_mappings', read_only=True, many=True)
    all_details = serializers.SerializerMethodField()
    # all_details = IpdProcedureAllDetailsSerializer(source='ipdproceduredetail_set', read_only=True, many=True)

    class Meta:
        model = IpdProcedure
        fields = ('id', 'name', 'details', 'is_enabled', 'features', 'about', 'all_details', 'show_about')

    def get_all_details(self, obj):
        return IpdProcedureAllDetailsSerializer(obj.ipdproceduredetail_set.all(), many=True, context=self.context).data


class TopHospitalForIpdProcedureSerializer(serializers.ModelSerializer):
    count_of_insurance_provider = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()
    multi_speciality = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    open_today = serializers.SerializerMethodField()
    insurance_provider = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'distance', 'certifications', 'bed_count', 'logo', 'avg_rating',
                  'count_of_insurance_provider', 'multi_speciality', 'address', 'open_today',
                  'insurance_provider')

    def get_count_of_insurance_provider(self, obj):
        return len(list(obj.health_insurance_providers.all()))

    def get_distance(self, obj):
        return int(obj.distance.m) if hasattr(obj, 'distance') and obj.distance else None

    def get_certifications(self, obj):
        certification_objs = obj.hospitalcertification_set.all()
        names = [x.name for x in certification_objs]
        return names

    def get_insurance_provider(self, obj):
        return [x.name for x in obj.health_insurance_providers.all()]

    def get_multi_speciality(self, obj):
        return len(obj.hospitalspeciality_set.all()) > 1

    def get_address(self, obj):
        return obj.get_hos_address()

    def get_logo(self, obj):
        request = self.context.get('request')
        if obj.network:
            for document in obj.network.hospital_network_documents.all():
                if document.document_type == HospitalNetworkDocument.LOGO:
                    return request.build_absolute_uri(document.name.url) if document.name else None
        else:
            for document in obj.hospital_documents.all():
                if document.document_type == HospitalDocument.LOGO:
                    return request.build_absolute_uri(document.name.url) if document.name else None
        return None

    def get_open_today(self, obj):
        now = timezone.now()
        now = aware_time_zone(now)
        if obj.always_open:
            return True
        for timing in obj.hosp_availability.all():
            if timing.day == now.weekday() and timing.start < now.hour < timing.end:
                return True
        return False


class HospitalDetailIpdProcedureSerializer(TopHospitalForIpdProcedureSerializer):
    lat = serializers.SerializerMethodField()
    long = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    ipd_procedure_categories = serializers.SerializerMethodField()
    other_network_hospitals = serializers.SerializerMethodField()
    doctors = serializers.SerializerMethodField()
    rating_graph = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    display_rating_widget = serializers.SerializerMethodField()
    opd_timings = serializers.SerializerMethodField()
    contact_number = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'distance', 'certifications', 'bed_count', 'logo', 'avg_rating',
                  'multi_speciality', 'address', 'open_today', 'insurance_provider',
                  'opd_timings', 'contact_number',
                  'lat', 'long', 'about', 'services', 'images', 'ipd_procedure_categories', 'other_network_hospitals',
                  'doctors', 'rating_graph', 'rating', 'display_rating_widget'
                  )

    def get_lat(self, obj):
        if obj.location:
            return obj.location.y
        return None

    def get_long(self, obj):
        if obj.location:
            return obj.location.x
        return None

    def get_about(self, obj):
        if obj.network:
            return obj.network.about
        return obj.about

    def get_opd_timings(self, obj):
        return obj.opd_timings

    def get_contact_number(self, obj):
        for x in obj.hospital_helpline_numbers.all():
            return ("{} ".format(x.std_code) if x.std_code else "") + str(x.number)
        return None

    def get_services(self, obj):
        request = self.context.get('request')
        return [{'icon': request.build_absolute_uri(x.icon.url), 'name': x.name} for x in obj.service.all() if x.icon]

    def get_images(self, obj):
        request = self.context.get('request')
        # TODO: SHASHANK_SINGH Thumbnail to be added or not
        return [{'original': request.build_absolute_uri(img.name.url), "thumbnail": None, "cover_image": img.cover_image} for img in
                obj.hospitalimage_set.all() if img.name]

    def get_ipd_procedure_categories(self, obj):
        result = {}
        queryset = IpdProcedure.objects.prefetch_related('ipd_category_mappings__category').filter(
            doctor_clinic_ipd_mappings__enabled=True,
            doctor_clinic_ipd_mappings__doctor_clinic__doctor__is_live=True,
            doctor_clinic_ipd_mappings__doctor_clinic__enabled=True,
            doctor_clinic_ipd_mappings__doctor_clinic__hospital=obj,
            is_enabled=True).distinct()
        for ipd_procedure in queryset:
            for category_mapping in ipd_procedure.ipd_category_mappings.all():
                if category_mapping.category.id in result:
                    result[category_mapping.category.id]['ipd_procedures'].append(
                        {'id': ipd_procedure.id, 'name': ipd_procedure.name})
                else:
                    result[category_mapping.category.id] = {'id': category_mapping.category.id,
                                                            'name': category_mapping.category.name,
                                                            'ipd_procedures': [
                                                                {'id': ipd_procedure.id, 'name': ipd_procedure.name}]}
        return list(result.values())

    def get_other_network_hospitals(self, obj):
        result = []
        if not obj.network:
            return result
        for temp_hospital in obj.network.assoc_hospitals.all():
            if not temp_hospital.id == obj.id:
                result.append(
                    {'id': temp_hospital.id, 'name': temp_hospital.name, 'address': temp_hospital.get_hos_address(),
                     'lat': temp_hospital.location.y if temp_hospital.location else None,
                     'long': temp_hospital.location.x if temp_hospital.location else None})
        return result

    def get_doctors(self, obj):
        from ondoc.api.v1.doctor.views import DoctorListViewSet
        request = self.context.get('request')
        validated_data = self.context.get('validated_data')
        doctor_list_viewset = DoctorListViewSet()
        return doctor_list_viewset.list(request,
                                        parameters={'hospital_id': str(obj.id), 'longitude': validated_data.get('long'),
                                                    'latitude': validated_data.get('lat'), 'sort_on': 'experience',
                                                    'restrict_result_count': 3}).data

    def get_rating_graph(self, obj):
        from ondoc.ratings_review.models import RatingsReview
        if obj.network:
            queryset = RatingsReview.objects.prefetch_related('compliment') \
                .filter(Q(is_live=True, appointment_type=RatingsReview.OPD),
                        Q(appointment_id__in=OpdAppointment.objects.filter(hospital__network=obj.network).values_list(
                            'id', flat=True)) |
                        Q(related_entity_id=obj.id, appointment_id__isnull=True))
        else:
            queryset = RatingsReview.objects.prefetch_related('compliment') \
                .filter(Q(is_live=True, appointment_type=RatingsReview.OPD),
                        Q(appointment_id__in=OpdAppointment.objects.filter(hospital=obj).values_list('id', flat=True)) |
                        Q(related_entity_id=obj.id, appointment_id__isnull=True))
        return RatingsGraphSerializer(queryset, context={'request': self.context.get('request')}).data

    def get_rating(self, obj):
        app = OpdAppointment.objects.select_related('profile').filter(hospital_id=obj.id).all()
        if obj.network:
            queryset = rate_models.RatingsReview.objects.prefetch_related('compliment') \
                           .exclude(Q(review='') | Q(review=None)) \
                           .filter(Q(is_live=True, appointment_type=rate_models.RatingsReview.OPD),
                                   Q(appointment_id__in=OpdAppointment.objects.filter(hospital__network=obj.network).values_list(
                                       'id', flat=True)) |
                                   Q(related_entity_id=obj.id, appointment_id__isnull=True)) \
                           .order_by('-ratings', '-updated_at')[:5]
        else:
            queryset = rate_models.RatingsReview.objects.prefetch_related('compliment') \
                           .exclude(Q(review='') | Q(review=None)) \
                           .filter(Q(is_live=True, appointment_type=rate_models.RatingsReview.OPD),
                                   Q(appointment_id__in=OpdAppointment.objects.filter(hospital=obj).values_list(
                                       'id', flat=True)) |
                                   Q(related_entity_id=obj.id, appointment_id__isnull=True)) \
                           .order_by('-ratings', '-updated_at')[:5]
        reviews = rating_serializer.RatingsModelSerializer(queryset, many=True, context={'app': app})
        return reviews.data

    def get_display_rating_widget(self, obj):
        from ondoc.ratings_review.models import RatingsReview
        if obj.network:
            queryset = RatingsReview.objects.prefetch_related('compliment') \
                .filter(Q(is_live=True, appointment_type=RatingsReview.OPD),
                        Q(appointment_id__in=OpdAppointment.objects.filter(hospital__network=obj.network).values_list(
                            'id', flat=True)) |
                        Q(related_entity_id=obj.id, appointment_id__isnull=True))
        else:
            queryset = RatingsReview.objects.prefetch_related('compliment') \
                .filter(Q(is_live=True, appointment_type=RatingsReview.OPD),
                        Q(appointment_id__in=OpdAppointment.objects.filter(hospital=obj).values_list('id', flat=True)) |
                        Q(related_entity_id=obj.id, appointment_id__isnull=True))

        queryset = list(queryset)
        rate_count = len(queryset)
        avg = 0
        if rate_count:
            all_rating = []
            for rate in queryset:
                all_rating.append(rate.ratings)
            if all_rating:
                avg = sum(all_rating) / len(all_rating)
        if rate_count > 5 or (rate_count <= 5 and avg > 4):
            return True
        return False


class HospitalRequestSerializer(serializers.Serializer):
    long = serializers.FloatField(default=77.071848)
    lat = serializers.FloatField(default=28.450367)
    min_distance = serializers.IntegerField(required=False)
    max_distance = serializers.IntegerField(required=False)
    provider_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)

    def validate_provider_ids(self, attrs):
        try:
            attrs = set(attrs)
            if HealthInsuranceProvider.objects.filter(id__in=attrs).count() == len(attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Health Insurance Provider IDs')
        raise serializers.ValidationError('Invalid Health Insurance Provider IDs')


class IpdProcedureLeadSerializer(serializers.ModelSerializer):
    ipd_procedure = serializers.PrimaryKeyRelatedField(queryset=IpdProcedure.objects.filter(is_enabled=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True), required=False)
    name = serializers.CharField(max_length=100)
    phone_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    email = serializers.EmailField(max_length=256)
    gender = serializers.ChoiceField(choices=UserProfile.GENDER_CHOICES)
    age = serializers.IntegerField(min_value=1, max_value=120, required=False, default=None)
    dob = serializers.DateTimeField(required=False, default=None)

    class Meta:
        model = IpdProcedureLead
        fields = '__all__'

    def validate(self, attrs):
        ipd_procedure = attrs.get('ipd_procedure')
        hospital = attrs.get('hospital')
        age = attrs.get('age')
        dob = attrs.get('dob')
        if all([age, dob]):
            raise serializers.ValidationError('Only one of age or DOB is required.')
        if not any([age, dob]):
            raise serializers.ValidationError('Either age or DOB is required.')
        if ipd_procedure and hospital:
            if not DoctorClinicIpdProcedure.objects.filter(enabled=True, ipd_procedure=ipd_procedure,
                                                           doctor_clinic__hospital=hospital):
                raise serializers.ValidationError('IPD procedure is not available in the hospital.')
        return super().validate(attrs)


class HospitalDetailRequestSerializer(serializers.Serializer):
    long = serializers.FloatField(default=77.071848)
    lat = serializers.FloatField(default=28.450367)


class IpdDetailsRequestDetailRequestSerializer(serializers.Serializer):
    long = serializers.FloatField(default=77.071848)
    lat = serializers.FloatField(default=28.450367)


class OpdAppointmentUpcoming(OpdAppointmentSerializer):
    address = serializers.SerializerMethodField()
    provider_id = serializers.IntegerField(source='doctor.id')
    name = serializers.ReadOnlyField(source='doctor.name')

    class Meta:
        model = OpdAppointment
        fields = ('id', 'provider_id', 'name', 'hospital_name', 'patient_name', 'type',
                  'status', 'time_slot_start', 'time_slot_end', 'address')

    def get_address(self, obj):
        return obj.hospital.get_hos_address()
