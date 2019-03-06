from rest_framework import serializers
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from ondoc.doctor import models as doc_models
from ondoc.procedure.models import Procedure
from ondoc.api.v1.doctor import serializers as v1_serializers
from ondoc.diagnostic.models import LabAppointment
from ondoc.api.v1.diagnostic import serializers as v1_diagnostic_serailizers

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


class OpdAppointmentFuture(v1_serializers.OpdAppointmentSerializer):
    address = serializers.SerializerMethodField()
    provider_id = serializers.IntegerField(source='doctor.id')
    name = serializers.ReadOnlyField(source='doctor.name')

    class Meta:
        model = doc_models.OpdAppointment
        fields = ('id', 'provider_id', 'name', 'hospital_name', 'patient_name', 'type',
                  'status', 'time_slot_start', 'time_slot_end', 'address')

    def get_address(self, obj):
        return obj.hospital.get_hos_address()


class LabAppointmentFuture(v1_diagnostic_serailizers.LabAppointmentModelSerializer):
    address = serializers.SerializerMethodField()
    provider_id = serializers.IntegerField(source='lab.id')
    name = serializers.ReadOnlyField(source='lab.name')
    hospital_name = serializers.SerializerMethodField()

    class Meta:
        model = LabAppointment
        fields = ('id', 'provider_id', 'name', 'hospital_name', 'patient_name', 'type',
                  'status', 'time_slot_start', 'time_slot_end', 'address')

    def get_address(self, obj):
        return obj.lab.get_lab_address()

    def get_hospital_name(self, obj):
        return None

