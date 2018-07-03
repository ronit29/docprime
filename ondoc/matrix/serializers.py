from rest_framework import serializers
from .views import MatrixLead


class MatrixLeadDataSerializer(serializers.Serializer):
    sub_product = serializers.ChoiceField(choices=MatrixLead.SUB_TYPES)
    name = serializers.CharField()
    gender = serializers.CharField(max_length=1, required=False)
    city = serializers.CharField()
    agent_employee_id = serializers.CharField()

    def validate(self, attrs):
        if attrs['sub_product'] == MatrixLead.DOCTOR:
            if attrs.get('gender') is None:
                raise serializers.ValidationError("Gender is Required.")
        return attrs