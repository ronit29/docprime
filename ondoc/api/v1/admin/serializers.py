from rest_framework import serializers


class AgenctVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
