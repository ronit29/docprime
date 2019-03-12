from rest_framework import serializers
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         DoctorNumber, Address, GenericAdmin, UserSecretKey,
                                         UserPermission, Address, GenericAdmin, GenericLabAdmin)
from ondoc.doctor import models as doc_models
from ondoc.common.models import GlobalNonBookable
from ondoc.procedure.models import Procedure
from ondoc.diagnostic.models import LabAppointment
from ondoc.api.v1.doctor import serializers as v1_serializers
from ondoc.api.v1.diagnostic import serializers as v1_diagnostic_serailizers

from dateutil.relativedelta import relativedelta
from django.utils import timezone
logger = logging.getLogger(__name__)
User = get_user_model()


class DoctorBlockCalenderSerializer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in doc_models.DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(required=False, choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    start_time = serializers.TimeField(required=False)
    end_date = serializers.DateField()
    end_time = serializers.TimeField(required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Hospital.objects.all())

    def validate(self, attrs):
        doctor = attrs.get("doctor_id")
        hospital = attrs.get("hospital_id")
        interval = attrs.get("interval")
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if doctor and hospital and (hospital not in doctor.hospitals.all()):
            raise serializers.ValidationError("incorrect hospital id or doctor id")
        if start_time and not end_time:
            raise serializers.ValidationError("end time is required with start time")
        if not start_time and end_time:
            raise serializers.ValidationError("start time is required with end time")
        if not interval and not (start_time and end_time):
            raise serializers.ValidationError("neither interval nor start time,end time found")
        return attrs


class DoctorProfileSerializer(serializers.ModelSerializer):
    images = v1_serializers.DoctorImageSerializer(read_only=True, many=True)
    qualifications = v1_serializers.DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = v1_serializers.DoctorPracticeSpecializationSerializer(read_only=True, many=True, source='doctorpracticespecializations')
    languages = v1_serializers.DoctorLanguageSerializer(read_only=True, many=True)
    availability = serializers.SerializerMethodField(read_only=True)
    emails = v1_serializers.DoctorEmailSerializer(read_only=True, many=True)
    mobiles = v1_serializers.DoctorMobileSerializer(read_only=True, many=True)
    medical_services = v1_serializers.MedicalServiceSerializer(read_only=True, many=True)
    experiences = v1_serializers.DoctorExperienceSerializer(read_only=True, many=True)
    associations = v1_serializers.DoctorAssociationSerializer(read_only=True, many=True)
    awards = v1_serializers.DoctorAwardSerializer(read_only=True, many=True)
    display_name = serializers.ReadOnlyField(source='get_display_name')
    thumbnail = serializers.SerializerMethodField()

    def get_availability(self, obj):
        data = doc_models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj).select_related("doctor_clinic__doctor",
                                                                                           "doctor_clinic__hospital")
        return v1_serializers.DoctorHospitalSerializer(data, context=self.context, many=True).data

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        thumbnail = obj.get_thumbnail()
        if thumbnail:
            return request.build_absolute_uri(thumbnail) if thumbnail else None
        else:
            return None

    class Meta:
        model = doc_models.Doctor
        fields = (
            'id', 'name', 'display_name', 'gender', 'about', 'license', 'emails', 'practicing_since', 'images',
            'languages', 'qualifications', 'general_specialization', 'availability', 'mobiles', 'medical_services',
            'experiences', 'associations', 'awards', 'appointments', 'hospitals', 'thumbnail', 'signature', 'is_live')


class DoctorLeaveValidateQuerySerializer(serializers.Serializer):
    doctor_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Hospital.objects.all())


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')
    doctor_id = serializers.IntegerField(read_only=True)
    hospital_id = serializers.IntegerField(read_only=True)
    doctor_name = serializers.ReadOnlyField(source='doctor.get_display_name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')

    class Meta:
        model = doc_models.DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')


class PracticeSpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.PracticeSpecialization
        fields = '__all__'


class QualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Qualification
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Language
        fields = '__all__'


class MedicalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.MedicalService
        fields = '__all__'


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = '__all__'


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Specialization
        fields = '__all__'


class ProviderSignupValidations:

    @staticmethod
    def provider_signup_lead_exists(attrs):
        return doc_models.ProviderSignupLead.objects.filter(phone_number=attrs['phone_number'],
                                                            user__isnull=False).exists()

    @staticmethod
    def admin_exists(attrs):
        return GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists()

    @staticmethod
    def lab_admin_exists(attrs):
        return GenericLabAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists()

    @staticmethod
    def user_exists(attrs):
        provider_signup_lead_exists = ProviderSignupValidations.provider_signup_lead_exists(attrs)
        admin_exists = ProviderSignupValidations.admin_exists(attrs)
        lab_admin_exists = ProviderSignupValidations.lab_admin_exists(attrs)
        return (admin_exists or lab_admin_exists or provider_signup_lead_exists)

class GenerateOtpSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)

    def validate(self, attrs):
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        return attrs


class OtpVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False,
                   created_at__gte=timezone.now() - relativedelta(minutes=OtpVerifications.OTP_EXPIRY_TIME)).exists():
            raise serializers.ValidationError("Invalid OTP")
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        return attrs


class ProviderSignupLeadDataSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    email = serializers.EmailField()
    type = serializers.ChoiceField(choices=doc_models.ProviderSignupLead.TYPE_CHOICES)

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        phone_number = attrs.get("phone_number")
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        if not (user and int(user.phone_number) == int(phone_number)):
            raise serializers.ValidationError("either user is missing or user and phone number mismatch")
        return attrs


class ConsentIsDocprimeSerializer(serializers.Serializer):
    is_docprime = serializers.BooleanField()

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        if not (user and doc_models.ProviderSignupLead.objects.filter(user=user).exists()):
            raise serializers.ValidationError("Provider not found")
        return attrs


class BulkCreateDoctorSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    online_consultation_fees = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    phone_number = serializers.IntegerField(required=False, min_value=5000000000, max_value=9999999999, allow_null=True)
    is_appointment = serializers.BooleanField(default=False)
    is_billing = serializers.BooleanField(default=False)
    is_superuser = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if (attrs.get('is_appointment') or attrs.get('is_billing') or attrs.get('is_superuser')) and not attrs.get('phone_number'):
            raise serializers.ValidationError('permission type or super user access given, but phone number not provided')
        return attrs


class CreateDoctorSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    doctors = serializers.ListField(child=BulkCreateDoctorSerializer(many=False))


class BulkCreateGenericAdminSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    is_appointment = serializers.BooleanField(default=False)
    is_billing = serializers.BooleanField(default=False)
    is_superuser = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not (attrs.get('is_appointment') or attrs.get('is_billing') or attrs.get('is_superuser')):
            raise serializers.ValidationError('permission type or super user access not given')
        return attrs


class CreateGenericAdminSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    staffs = serializers.ListField(child=BulkCreateGenericAdminSerializer(many=False))


class CreateHospitalSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    city = serializers.CharField(required=False, max_length=40)
    state = serializers.CharField(required=False, max_length=40)
    country = serializers.CharField(required=False, max_length=40)
    contact_number = serializers.IntegerField(required=False, min_value=5000000000, max_value=9999999999)
    doctors = serializers.ListField(required=False, child=BulkCreateDoctorSerializer(many=False))
    staffs = serializers.ListField(required=False, child=BulkCreateGenericAdminSerializer(many=False),
                                           allow_empty=True)
    is_listed_on_docprime = serializers.BooleanField(default=False)


class DoctorModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Doctor
        fields = ('id', 'name', 'online_consultation_fees', 'source_type')


class HospitalModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Hospital
        fields = ('id', 'name', 'city', 'state', 'country', 'source_type')


class DoctorClinicModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.DoctorClinic
        fields = ('id', 'doctor', 'hospital', 'enabled')


class DoctorMobileModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.DoctorMobile
        fields = ('id', 'doctor', 'number', 'is_primary')


class GenericAdminModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenericAdmin
        fields = ('id', 'phone_number', 'permission_type', 'name', 'doctor', 'hospital', 'super_user_permission', 'entity_type')
