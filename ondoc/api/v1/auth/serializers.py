from rest_framework import serializers
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         UserPermission, Address, GenericAdmin)
from ondoc.doctor.models import DoctorMobile
from ondoc.account.models import ConsumerAccount, Order, ConsumerTransaction
import datetime
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.templatetags.staticfiles import static
User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)


class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999)

    def validate(self, attrs):

        # if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.CONSUMER).exists():
        #     raise serializers.ValidationError('User does not exist')

        if (not OtpVerifications
                .objects
                .filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False,
                        created_at__gte=timezone.now() - relativedelta(minutes=OtpVerifications.OTP_EXPIRY_TIME))
                .exists()):
            raise serializers.ValidationError("Invalid OTP")
        return attrs


class DoctorLoginSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=7000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")

        if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.DOCTOR).exists():
            doctor_not_exists = admin_not_exists = False
            if not DoctorMobile.objects.filter(number=attrs['phone_number'], is_primary=True).exists():
                doctor_not_exists = True
            if not GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
                admin_not_exists = True
            if doctor_not_exists and admin_not_exists:
                raise serializers.ValidationError('No Doctor or Admin with given phone number found')

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

        return user

    class Meta:
        model = User
        fields = ('phone_number', 'otp')


# class NotificationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Notification
#         fields = '__all__'


class NotificationEndpointSerializer(serializers.ModelSerializer):

    class Meta:
        model = NotificationEndpoint
        # fields = '__all__'
        fields = ('user', 'device_id', 'token', )


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
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ("id", "name", "email", "gender", "phone_number", "is_otp_verified", "is_default_user",
                  "profile_image", "age", "user", "dob")

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.profile_image:
            photo_url = obj.profile_image.url
            return request.build_absolute_uri(photo_url)
        else:
            url = static('doctor_images/no_image.png')
            return request.build_absolute_uri(url)


class UploadProfilePictureSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserProfile
        fields = ("profile_image", 'id')


class UserPermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserPermission
        exclude = ('created_at', 'updated_at',)


class AddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = Address
        fields = ('id', 'type', 'place_id', 'address', 'land_mark', 'pincode',
                  'phone_number', 'is_default', 'profile')

    def create(self, validated_data):
        request = self.context.get("request")
        if not request:
            raise ValueError("Request is None.")
        validated_data['user'] = request.user
        if 'is_default' not in request.data:
            if not Address.objects.filter(user=request.user.id).exists():
                validated_data['is_default'] = True
        return super().create(validated_data)

    def validate(self, attrs):
        request = self.context.get("request")
        # if attrs.get("user") != request.user:
        #     raise serializers.ValidationError("User is not correct.")
        if attrs.get("profile") and not UserProfile.objects.filter(user=request.user, id=attrs.get("profile").id).exists():
            raise serializers.ValidationError("Profile is not correct.")
        return attrs

class AppointmentqueryRetrieveSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)


class ConsumerAccountModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumerAccount
        fields = "__all__"


class TransactionSerializer(serializers.Serializer):
    # productId = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    # referenceId = serializers.IntegerField(required=False)
    orderId = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    orderNo = serializers.CharField(max_length=200, required=False)
    paymentMode = serializers.CharField(max_length=200, required=False)

    responseCode = serializers.CharField(max_length=200)
    bankTxId = serializers.CharField(max_length=200, allow_blank=True, required=False)
    txDate = serializers.CharField(max_length=100)
    bankName = serializers.CharField(max_length=200, required=False)
    currency = serializers.CharField(max_length=200)
    statusCode = serializers.IntegerField()
    pgGatewayName = serializers.CharField(max_length=20, required=False)
    txStatus = serializers.CharField(max_length=200)
    pgTxId = serializers.CharField(max_length=200)
    pbGatewayName = serializers.CharField(max_length=200, required=False)


class UserTransactionModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConsumerTransaction
        fields = ('type', 'action', 'amount', 'product_id', 'reference_id', 'order_id')
        # fields = '__all__'
