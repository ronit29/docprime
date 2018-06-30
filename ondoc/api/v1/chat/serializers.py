from rest_framework import serializers
from ondoc.doctor.models import Doctor
from django.contrib.auth import get_user_model
User = get_user_model()


class DoctorListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Doctor
        fields = '__all__'