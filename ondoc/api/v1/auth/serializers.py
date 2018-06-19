from rest_framework import serializers
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         UserPermission, Address)
from ondoc.doctor.models import DoctorMobile
import datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999)

    def validate(self, attrs):

        # if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.CONSUMER).exists():
        #     raise serializers.ValidationError('User does not exist')

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


# class UserProfileSerializer(serializers.ModelSerializer):
#     name = serializers.CharField()
#     age = serializers.IntegerField(min_value=1, max_value=150)
#     email = serializers.EmailField()
#     gender = serializers.ChoiceField(UserProfile.GENDER_CHOICES)
#     class Meta:
#         model = UserProfile
#         fields = ('name', 'age', 'email', 'gender')


class UserSerializer(serializers.ModelSerializer):
    # profile = UserProfileSerializer(required=True)
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")

        if User.objects.filter(phone_number=attrs['phone_number'],user_type=User.CONSUMER).exists():
            raise serializers.ValidationError('User already exists')

        return attrs

    def create(self, validated_data):
        # profile_data = validated_data.pop('profile')
        # age = profile_data.pop('age')
        # # need to convert age to date of birth
        # dob = datetime.datetime.now() - relativedelta(years=age)
        # profile_data['dob'] = dob

        validated_data.pop('otp')
        validated_data['user_type'] = User.CONSUMER
        validated_data['is_phone_number_verified'] = True

        user = User.objects.create(**validated_data)
        # profile = UserProfile.objects.create(user=user, **profile_data)

        return user

    class Meta:
        model = User
        fields = ('phone_number', 'otp')
        # fields = ('phone_number', 'profile', 'otp')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class NotificationEndpointSerializer(serializers.ModelSerializer):

    class Meta:
        model = NotificationEndpoint
        fields = '__all__'


class NotificationEndpointSaveSerializer(serializers.Serializer):
    device_id = serializers.CharField(required=False)
    token = serializers.CharField()


class NotificationEndpointDeleteSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        request = self.context.get("request")
        if not NotificationEndpoint.objects.filter(token=attrs.get('token')).exists():
            raise serializers.ValidationError("Token does not exists.")
        if not NotificationEndpoint.objects.filter(user=request.user, token=attrs.get('token')).exists():
            raise serializers.ValidationError("Token does not  match.")
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    GENDER_CHOICES = UserProfile.GENDER_CHOICES
    name = serializers.CharField()
    age = serializers.IntegerField(read_only=True)
    gender = serializers.ChoiceField(choices=GENDER_CHOICES)
    email = serializers.EmailField(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = ("id", "name", "email", "gender", "phone_number", "is_otp_verified", "is_default_user",
                  "profile_image", "age", "user", "dob")

    def validate_profile_image(self, value):
        if value.image.width != value.image.height:
            raise serializers.ValidationError("Image should be square")
        return value

class UserPermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserPermission
        exclude = ('created_at', 'updated_at',)


class AddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = Address
        fields = "__all__"

    def validate(self, attrs):
        request = self.context.get("request")
        if attrs.get("user") != request.user:
            raise serializers.ValidationError("User is not correct.")
        if attrs.get("profile") and not UserProfile.objects.filter(user=request.user, id=attrs.get("profile").id).exists():
            raise serializers.ValidationError("Profile is not correct.")
        return attrs

class AppointmentqueryRetrieveSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)
    # id = serializers.IntegerField(required=True)
