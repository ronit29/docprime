from rest_framework import serializers
from django.db.models import Q
from ondoc.prescription import models as prescription_models
from ondoc.doctor import models as doc_models


class PrescriptionAppointmentValidation():

    @staticmethod
    def validate_appointment_key(parent, attrs):
        if not parent and ((not 'appointment_id' in attrs  or not 'appointment_type' in attrs) or
                                (not('appointment_id') or not('appointment_type'))):
            raise serializers.ValidationError('Appointment data invalid')
        return attrs

    @staticmethod
    def validate_appointment_object(attrs):
        if attrs and attrs.get('appointment_type') == prescription_models.PresccriptionPdf.OFFLINE:
            queryset = doc_models.OfflineOPDAppointments.objects.filter(id=attrs.get('appointment_id'))
        elif attrs.get('appointment_type') == prescription_models.PresccriptionPdf.DOCPRIME_OPD:
            queryset = doc_models.OpdAppointment.objects.filter(id=attrs.get('appointment_id'))
        appointment_object = queryset.first()
        if not appointment_object:
            raise serializers.ValidationError('No Appointment found')
        if not appointment_object.status == doc_models.OpdAppointment.COMPLETED:
            raise serializers.ValidationError('Appointment not completed')
        return appointment_object


class PrescriptionMedicineBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    quantity = serializers.IntegerField(required=False)
    time = serializers.CharField(max_length=64)
    duration_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES, required=False)
    duration = serializers.IntegerField(required=False)
    instruction = serializers.CharField(max_length=256, required=False)
    additional_notes = serializers.CharField(max_length=256, required=False)
    appointment_id = serializers.CharField(required=False)
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES, required=False)

    def validate(self, attrs):
        if not self.parent and ((not 'appointment_id' in attrs  or not 'appointment_type' in attrs) or
                                (not('appointment_id') or not('appointment_type'))):
            raise serializers.ValidationError('Appointment data invalid')
        return attrs


class PrescriptionSymptomsBodySerializer(serializers.Serializer):
    symptom = serializers.CharField(max_length=64)
    appointment_id = serializers.CharField()
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES)


class PrescriptionObservationBodySerializer(serializers.Serializer):
    observation = serializers.CharField(max_length=64)
    appointment_id = serializers.CharField()
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES)


class GeneratePrescriptionPDFBodySerializer(serializers.Serializer):
    symptoms = serializers.ListField(child=PrescriptionSymptomsBodySerializer())
    observations = serializers.ListField(child=PrescriptionObservationBodySerializer())
    medicines = serializers.ListField(child=PrescriptionMedicineBodySerializer())
    appointment_id = serializers.CharField()
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES)

    def validate(self, attrs):
        if attrs:
            PrescriptionAppointmentValidation.validate_appointment_object(attrs)
        return attrs