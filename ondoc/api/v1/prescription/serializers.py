from rest_framework import serializers
from django.db.models import Q


class PrescriptionMedicineBodySerializer(serializers.Serializer):
    symptoms = serializers.JSONField()
    observations = serializers.JSONField()


class GeneratePrescriptionPDFBodySerializer(serializers.Serializer):
    symptoms = serializers.JSONField()
    observations = serializers.JSONField()