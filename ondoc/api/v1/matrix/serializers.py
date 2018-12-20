from rest_framework import serializers
from ondoc.doctor import models as doctor_model


class NumberMaskSerializer(serializers.Serializer):
    mobile = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    hospital = serializers.PrimaryKeyRelatedField(queryset=doctor_model.Hospital.objects.filter(is_live=True))
    doctor = serializers.PrimaryKeyRelatedField(queryset=doctor_model.Doctor.objects.filter(is_live=True))
