from rest_framework import serializers
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from ondoc.doctor import models as doc_models
from ondoc.api.v1.doctor import serializers as v1_serializers
logger = logging.getLogger(__name__)
User = get_user_model()


class DoctorBlockCalenderSerializer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in doc_models.DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_date = serializers.DateField()
    end_time = serializers.TimeField()
    doctor_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Hospital.objects.all())

    def validate(self, attrs):
        doctor = attrs.get("doctor_id")
        hospital = attrs.get("hospital_id")
        if doctor and hospital and (hospital not in doctor.hospitals):
            raise serializers.ValidationError("incorrect hospital id or doctor id")


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


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')
    doctor_id = serializers.IntegerField(read_only=True)
    hospital_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = doc_models.DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')

