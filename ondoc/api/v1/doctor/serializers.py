from django.utils.safestring import mark_safe
from rest_framework import serializers
from rest_framework.fields import CharField
from django.db.models import Q, Avg, Count, Max, F, ExpressionWrapper, DateTimeField
from collections import defaultdict, OrderedDict
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer, OpdAppointmentProcedureMappingSerializer
from ondoc.cart.models import Cart
from ondoc.doctor.models import (OpdAppointment, Doctor, Hospital, DoctorHospital, DoctorClinicTiming,
                                 DoctorAssociation,
                                 DoctorAward, DoctorDocument, DoctorEmail, DoctorExperience, DoctorImage,
                                 DoctorLanguage, DoctorMedicalService, DoctorMobile, DoctorQualification, DoctorLeave,
                                 Prescription, PrescriptionFile, Specialization, DoctorSearchResult, HealthTip,
                                 CommonMedicalCondition, CommonSpecialization,
                                 DoctorPracticeSpecialization, DoctorClinic, OfflineOPDAppointments, OfflinePatients,
                                 CancellationReason)
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
    util_file_name
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
from ondoc.authentication import models as auth_models
from ondoc.location.models import EntityUrls, EntityAddress
from ondoc.procedure.models import DoctorClinicProcedure, Procedure, ProcedureCategory, \
    get_included_doctor_clinic_procedure, get_procedure_categories_with_procedures
from ondoc.seo.models import NewDynamic
from ondoc.ratings_review import models as rate_models

logger = logging.getLogger(__name__)

User = get_user_model()


class CommaSepratedToListField(CharField):
    def __init__(self, **kwargs):
        self.typecast_to = kwargs.pop('typecast_to', int)
        super(CommaSepratedToListField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        return list(map(self.typecast_to, data.strip(",").split(",")))

    def to_representation(self, value):
        return list(map(self.typecast_to, value.strip(",").split(",")))


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()


class AppointmentFilterSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True), required=False)
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

        if data.get('doctor') and not data.get('doctor').enabled_for_cod() and data.get('payment_type') == OpdAppointment.COD:
            raise serializers.ValidationError('Doctor not enabled for COD payment')

        if 'use_wallet' in data and data['use_wallet'] is False:
            data['use_wallet'] = False
        else:
            data['use_wallet'] = True

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
    enabled_for_online_booking = serializers.SerializerMethodField(read_only=True)
    show_contact = serializers.SerializerMethodField(read_only=True)

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

    class Meta:
        model = DoctorClinicTiming
        fields = ('doctor', 'hospital_name', 'address','short_address', 'hospital_id', 'start', 'end', 'day', 'deal_price',
                  'discounted_fees', 'hospital_thumbnail', 'mrp', 'lat', 'long', 'id','enabled_for_online_booking', 'show_contact')
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
            'experiences', 'associations', 'awards', 'appointments', 'hospitals', 'thumbnail', 'signature', 'is_live')


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
    hospital_id = serializers.IntegerField(required=False, allow_null=True)

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
        rate_count = obj.rating.count()
        avg = 0
        if rate_count:
            all_rating = []
            for rate in obj.rating.all():
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

        queryset = obj.rating.prefetch_related('compliment').exclude(Q(review='') | Q(review=None))\
                                                            .filter(is_live=True, moderation_status__in=[rate_models.RatingsReview.PENDING,
                                                                                                         rate_models.RatingsReview.APPROVED])\
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
                                                                      .filter(is_live=True,
                                                                              moderation_status__in=[
                                                                                  rate_models.RatingsReview.PENDING,
                                                                                  rate_models.RatingsReview.APPROVED]
                                                                              ),
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
            title += ' in ' + sublocality + " " + locality + ' - Consult Online'
            description += ' in ' + sublocality + " " + locality
        elif locality:
            title += ' in ' + locality + ' - Consult Online'
            description += ' in ' + locality

        else:
            title += ' - Consult Online'

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
        data = DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj,
                                                 doctor_clinic__enabled=True,
                                                 doctor_clinic__hospital__is_live=True).select_related(
            "doctor_clinic__doctor", "doctor_clinic__hospital").prefetch_related("doctor_clinic__hospital__spoc_details","doctor_clinic__doctor__mobiles")
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
    invoices = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp', 'is_rated', 'rating_declined',
                  'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail', 'procedures', 'mrp',
                  'invoices', 'cancellation_reason', 'payment_type')

    def get_procedures(self, obj):
        if obj:
            return OpdAppointmentProcedureMappingSerializer(obj.procedure_mappings.all().select_related('procedure'), many=True).data
        return []

    def get_invoices(self, obj):
        return obj.get_invoice_urls()

    def get_cancellation_reason(self, obj):
        return obj.get_serialized_cancellation_reason()


class DoctorAppointmentRetrieveSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'allowed_action', 'effective_price',
                  'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail',
                  'display_name', 'mrp', 'payment_type')


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

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = CommonSpecialization
        fields = ('id', 'name', 'icon', )


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
        fields = ('id', 'name', 'entity_type', 'address', 'is_billing_enabled', 'is_appointment_manager')


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
        fields = ('id', 'thumbnail', 'name', 'entity_type', 'qualifications')


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
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True), required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True), required=False)
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
