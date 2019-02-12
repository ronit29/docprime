from rest_framework import serializers
from rest_framework.fields import CharField
from django.db.models import Q, Avg, Count, Max
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.api.v1.utils import is_valid_testing_data, form_time_slot, GenericAdminEntity
from django.contrib.auth import get_user_model
import math, datetime, logging
from django.conf import settings
from ondoc.doctor.models import Doctor, Hospital, DoctorLeave


logger = logging.getLogger(__name__)

User = get_user_model()

class DoctorBlockCalenderSerializer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_date = serializers.DateField()
    end_time = serializers.TimeField()
    doctor_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=Hospital.objects.all())

    def validate(self, attrs):
        doctor = attrs.get("doctor_id")
        hospital = attrs.get("hospital_id")
        if doctor and hospital and (hospital not in doctor.hospitals):
            raise serializers.ValidationError("incorrect hospital id or doctor id")


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')
    doctor_id = serializers.IntegerField(read_only=True)
    hospital_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')
