from decimal import Decimal

from django.core.validators import MinValueValidator
from rest_framework import serializers
from ondoc.doctor.models import Doctor
from django.contrib.auth import get_user_model
User = get_user_model()


class DoctorListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Doctor
        fields = '__all__'


class ChatReferralNumberSerializer(serializers.Serializer):

    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)

    def validate(self, attrs):
        user = User.objects.prefetch_related('referral').filter(phone_number=attrs['phone_number'], user_type=User.CONSUMER).first()
        if not user:
            raise serializers.ValidationError('User with Provided PhoneNumber not exists!')
        attrs['user'] = user
        return attrs


class ChatLoginSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=1000000000,max_value=9999999999)


class ChatTransactionModelSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    extra_details = serializers.JSONField(required=False)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    promotional_amount = serializers.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])