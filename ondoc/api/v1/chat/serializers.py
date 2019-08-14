from decimal import Decimal

from django.core.validators import MinValueValidator
from rest_framework import serializers

from ondoc.authentication.models import UserProfile
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
    GENDER_CHOICES = UserProfile.GENDER_CHOICES
    phone_number = serializers.IntegerField(min_value=1000000000,max_value=9999999999)
    name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=GENDER_CHOICES)
    # age = serializers.SerializerMethodField()
    dob = serializers.DateField(allow_null=True, required=True)
    is_default_user = serializers.BooleanField(required=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)


class ChatTransactionModelSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    extra_details = serializers.JSONField(required=False)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    promotional_amount = serializers.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])