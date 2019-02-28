from rest_framework import serializers
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         DoctorNumber, Address, GenericAdmin, UserSecretKey,
                                         UserPermission, Address, GenericAdmin, GenericLabAdmin)
from ondoc.doctor import models as doc_models
from ondoc.procedure.models import Procedure
from ondoc.api.v1.doctor import serializers as v1_serializers
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


class GenerateOtpSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)

    def validate(self, attrs):
        admin_exists = lab_admin_exists = False
        if GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
            admin_exists = True
        if GenericLabAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
            lab_admin_exists = True
        if admin_exists or lab_admin_exists:
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        return attrs


class OtpVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False,
                   created_at__gte=timezone.now() - relativedelta(minutes=OtpVerifications.OTP_EXPIRY_TIME)).exists():
            raise serializers.ValidationError("Invalid OTP")
        admin_exists = lab_admin_exists = False
        if GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
            admin_exists = True
        if GenericLabAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
            lab_admin_exists = True
        if admin_exists or lab_admin_exists:
            raise serializers.ValidationError("admin for this phone number already exists")
        return attrs


class ProviderSignupLeadDataSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    email = serializers.EmailField()
    type = serializers.ChoiceField(choices=doc_models.ProviderSignupLead.TYPE_CHOICES)

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        phone_number = attrs.get("phone_number")
        type = attrs.get("type")
        if doc_models.ProviderSignupLead.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError("Provider with this phone number already exists")
        if int(user.phone_number) != int(phone_number):
            raise serializers.ValidationError("user and phone number mismatch")
        # if type == doc_models.ProviderSignupLead.DOCTOR and doc_models.Doctor.objects.filter(user=user).exists():
        #     raise serializers.ValidationError("Doctor for the user already exists")
        # if type == doc_models.ProviderSignupLead.HOSPITAL_ADMIN and GenericAdmin.objects.filter(user=user).exists():
        #     raise serializers.ValidationError("Generic Admin for the user already exists")
        return attrs


class ConsentIsDocprimeSerializer(serializers.Serializer):
    is_docprime = serializers.BooleanField()

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        if not (user and doc_models.ProviderSignupLead.objects.filter(user=user).exists()):
            raise serializers.ValidationError("Provider not found")
        return attrs


class CreateDoctorSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    name = serializers.CharField(max_length=200)


class BulkCreateDoctorSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)


class CreateHospitalSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    city = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=20)
    doctors = serializers.ListField(child=BulkCreateDoctorSerializer(many=False), allow_empty=True, required=False)


class CreateGenericAdminSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    phone_number = serializers.IntegerField(min_value=5555555555, max_value=9999999999)
    permission_type = serializers.ChoiceField(choices=GenericAdmin.type_choices)
    name = serializers.CharField(max_length=200, required=False)
