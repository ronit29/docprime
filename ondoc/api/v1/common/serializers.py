from rest_framework import serializers


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailServiceSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=1000000)
    subject = serializers.CharField(max_length=1000)
    to = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=10)
    cc = serializers.ListField(child=serializers.EmailField(), required=False, max_length=10)


class SMSServiceSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)


class XlsSerializer(serializers.Serializer):
    file = serializers.FileField()