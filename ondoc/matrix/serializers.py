from rest_framework import serializers
from .views import MatrixLead
from ondoc.doctor.models import Doctor
from ondoc.diagnostic.models import Lab
from django.core.validators import MaxValueValidator, MinValueValidator



class MatrixLeadDataSerializer(serializers.Serializer):
    sub_product = serializers.ChoiceField(choices=MatrixLead.SUB_TYPES)
    name = serializers.CharField()
    # gender = serializers.CharField(max_length=1, required=False)
    gender = serializers.ChoiceField(choices=MatrixLead.GENDER_TYPES, required=False)
    city = serializers.CharField()
    agent_employee_id = serializers.CharField()
    matrix_lead_id = serializers.IntegerField()
    matrix_reference_id = serializers.IntegerField(required=False)
    phone_number = serializers.IntegerField(required=False)

    def validate(self, attrs):

        if attrs['sub_product'] == MatrixLead.DOCTOR:
            if Doctor.objects.filter(matrix_lead_id=attrs.get('matrix_lead_id')).exists():
                raise serializers.ValidationError("Doctor with Same Lead Id Already Exists.")
        if attrs['sub_product'] == MatrixLead.LAB:
            if Lab.objects.filter(matrix_lead_id=attrs.get('matrix_lead_id')).exists():
                raise serializers.ValidationError("Lab with Same Lead Id Already Exists.")
        if attrs.get('phone_number'):
            if attrs['phone_number'] < 7000000000 or attrs['phone_number'] > 9999999999:
                attrs['phone_number'] = None

        return attrs