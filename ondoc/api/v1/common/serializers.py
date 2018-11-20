from rest_framework import serializers

from ondoc.lead.models import SearchLead


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailServiceSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=1000)
    to = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=10)
    cc = serializers.ListField(child=serializers.EmailField(), required=False, max_length=10)


class SMSServiceSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    phone_number = serializers.IntegerField()


class XlsSerializer(serializers.Serializer):
    file = serializers.FileField()


class DoctorXLSerializer(serializers.Serializer):
    file = serializers.FileField()
    source = serializers.CharField(max_length=20)
    batch = serializers.CharField(max_length=20)


class SearchLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchLead
        fields = '__all__'
