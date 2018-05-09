from rest_framework import serializers
from ondoc.authentication.models import OtpVerifications, User, UserProfile

from django.contrib.auth import get_user_model
User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], isExpired=False).exists():
            raise serializers.ValidationError("Invalid OTP")
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    age = serializers.IntegerField(min_value=1, max_value=150)
    email = serializers.EmailField()
    gender = serializers.ChoiceField(UserProfile.GENDER_CHOICES)
    class Meta:
        model = UserProfile
        fields = ('name', 'age', 'email', 'gender')


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        pass

    class Meta:
        model = User
        fields = ('phone_number', 'profile', 'otp')
