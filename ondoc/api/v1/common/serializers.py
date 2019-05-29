from rest_framework import serializers

from ondoc.authentication.models import UserProfile
from ondoc.common.models import GlobalNonBookable
from ondoc.diagnostic.models import Lab
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


class GlobalNonBookableSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    end_time = serializers.FloatField(read_only=True, source='end_time_in_float')

    class Meta:
        model = GlobalNonBookable
        exclude = ('booking_type', 'created_at', 'updated_at', 'deleted_at')


class AppointmentPrerequisiteSerializer(serializers.Serializer):
    lab_test = serializers.ListField(child=serializers.IntegerField(), required=True)
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all(), required=True)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=True)
    # start_date = serializers.DateTimeField(required=True)
