from rest_framework import serializers
from ondoc.authentication.models import OtpVerifications, User, UserProfile
from ondoc.doctor.models import DoctorMobile
import datetime
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):

        if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.CONSUMER).exists():
            raise serializers.ValidationError('User does not exist')

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")
        return attrs

class DoctorLoginSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")

        if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.DOCTOR).exists():
            if not DoctorMobile.objects.filter(number=attrs['phone_number'], is_primary=True).exists():
                raise serializers.ValidationError('No doctor with given phone number found')

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

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")

        if User.objects.filter(phone_number=attrs['phone_number'],user_type=User.CONSUMER).exists():
            raise serializers.ValidationError('User already exists')

        return attrs

    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        validated_data.pop('otp')
        validated_data['user_type'] = User.CONSUMER
        validated_data['is_phone_number_verified'] = True
        # need to convert age to date of birth
        age = profile_data.pop('age')
        dob = datetime.datetime.now() - relativedelta(years=age)
        profile_data['dob'] = dob

        user = User.objects.create(**validated_data)
        profile = UserProfile.objects.create(user=user, **profile_data)

        return user

    class Meta:
        model = User
        fields = ('phone_number', 'profile', 'otp')
