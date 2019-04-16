from rest_framework import serializers
from ondoc.doctor import models as doctor_model
from ondoc.common.models import AppointmentHistory


class NumberMaskSerializer(serializers.Serializer):
    mobile = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    hospital = serializers.PrimaryKeyRelatedField(queryset=doctor_model.Hospital.objects.filter(is_live=True))
    doctor = serializers.PrimaryKeyRelatedField(queryset=doctor_model.Doctor.objects.filter(is_live=True))


class IvrSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField(required=True)
    source = serializers.ChoiceField(choices=(("ivr", 'Auto IVR'),))
    appointment_type = serializers.ChoiceField(choices=(('DC', 'Diagnostic'), ('D', 'Doctor')))
    phone_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    response = serializers.IntegerField()
    status = serializers.IntegerField()
