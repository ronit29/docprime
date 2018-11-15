from rest_framework import serializers
from ondoc.location import models as location_models
from ondoc.doctor import models as doctor_models
from ondoc.location.models import CityInventory


class DoctorListSerializer(serializers.ModelSerializer):

    class Meta:
        model = doctor_models.Doctor
        fields = ('name', 'gender', 'practicing_since', 'online_consultation_fees')


class EntityDetailSerializer(serializers.Serializer):
    pageUrl = serializers.CharField(required=True)

    def validate(self, data):
        return data
