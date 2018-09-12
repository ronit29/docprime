from rest_framework import serializers
from ondoc.location import models as location_models
from ondoc.doctor import models as doctor_models


class DoctorListSerializer(serializers.ModelSerializer):

    class Meta:
        model = doctor_models.Doctor
        fields = ('name', 'gender', 'practicing_since', 'online_consultation_fees')
