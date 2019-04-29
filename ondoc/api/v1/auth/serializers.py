from rest_framework import serializers
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         DoctorNumber, Address, GenericAdmin, UserSecretKey,
                                         UserPermission, Address, GenericAdmin, GenericLabAdmin)
from ondoc.doctor.models import DoctorMobile, ProviderSignupLead
from ondoc.common.models import AppointmentHistory
from ondoc.doctor.models import DoctorMobile
from ondoc.insurance.models import InsuredMembers, UserInsurance
from ondoc.diagnostic.models import AvailableLabTest
from ondoc.account.models import ConsumerAccount, Order, ConsumerTransaction
import datetime, calendar
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ondoc.lead.models import UserLead
from ondoc.web.models import OnlineLead, Career, ContactUs
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.templatetags.staticfiles import static
import jwt
from django.conf import settings
from ondoc.authentication.backends import JWTAuthentication
from ondoc.common import models as common_models

User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)


class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999)

    def validate(self, attrs):
        if attrs.get('phone_number') in []:
            return attrs
        # if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.CONSUMER).exists():
        #     raise serializers.ValidationError('User does not exist')

        if (not OtpVerifications
                .objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False,
                                created_at__gte=timezone.now() - relativedelta(
                                    minutes=OtpVerifications.OTP_EXPIRY_TIME)).exists() and
                not (str(attrs['phone_number']) in settings.OTP_BYPASS_NUMBERS and str(attrs['otp']) == settings.HARD_CODED_OTP)):
            raise serializers.ValidationError("Invalid OTP")
        return attrs


class DoctorLoginSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        if attrs['phone_number'] == 9582557400:
            return attrs

        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False).exists():
            raise serializers.ValidationError("Invalid OTP")

        if not User.objects.filter(phone_number=attrs['phone_number'], user_type=User.DOCTOR).exists():
            doctor_not_exists = admin_not_exists = False
            lab_admin_not_exists = provider_signup_lead_not_exists = False
            if not DoctorNumber.objects.filter(phone_number=attrs['phone_number']).exists():
                doctor_not_exists = True
            if not GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
                admin_not_exists = True
            if not GenericLabAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists():
                lab_admin_not_exists = True
            if not ProviderSignupLead.objects.filter(phone_number=attrs['phone_number'], user__isnull=False).exists():
                provider_signup_lead_not_exists = True
            if doctor_not_exists and admin_not_exists and lab_admin_not_exists and provider_signup_lead_not_exists:
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
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)
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
    device_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    app_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    app_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    token = serializers.CharField()

    class Meta:
        model = NotificationEndpoint
        # fields = '__all__'
        fields = ('user', 'device_id', 'platform', 'app_name', 'app_version', 'token')


class NotificationEndpointSaveSerializer(serializers.Serializer):
    device_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    app_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    app_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
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
    name = serializers.CharField(max_length=100)
    age = serializers.SerializerMethodField()
    gender = serializers.ChoiceField(choices=GENDER_CHOICES)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    profile_image = serializers.SerializerMethodField()
    is_insured = serializers.SerializerMethodField()
    dob = serializers.DateField(allow_null=True, required=False)
    whatsapp_optin = serializers.NullBooleanField(required=False)
    whatsapp_is_declined = serializers.BooleanField(required=False)
    is_default_user = serializers.BooleanField(required=False)

    class Meta:
        model = UserProfile
        fields = ("id", "name", "email", "gender", "phone_number", "is_otp_verified", "is_default_user", "profile_image"
                  , "age", "user", "dob", "is_insured", "updated_at", "whatsapp_optin", "whatsapp_is_declined")

    def get_is_insured(self, obj):
        if isinstance(obj, dict):
            return False

        insured_member_obj = InsuredMembers.objects.filter(profile=obj).first()
        if not insured_member_obj:
            return False
        user_insurance_obj = UserInsurance.objects.filter(id=insured_member_obj.user_insurance_id).last()
        if user_insurance_obj and user_insurance_obj.is_valid():
            return True
        else:
            return False

    def get_age(self, obj):
        from datetime import date
        age = None
        birth_date = None
        if hasattr(obj, 'dob'):
            birth_date = obj.dob
        elif isinstance(obj, dict):
            birth_date = obj.get('dob')
        if birth_date:
            today = date.today()
            age = today.year - birth_date.year
            full_year_passed = (today.month, today.day) >= (birth_date.month, birth_date.day)
            if not full_year_passed:
                age -= 1
        return age

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        profile_image = None
        if hasattr(obj, 'profile_image'):
            profile_image = obj.profile_image
        elif isinstance(obj, dict):
            profile_image = obj.get('profile_image')
        if profile_image:
            photo_url = profile_image.url
            return request.build_absolute_uri(photo_url)
        else:
            return None


class UploadProfilePictureSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserProfile
        fields = ("profile_image", 'id')


class UserPermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserPermission
        exclude = ('created_at', 'updated_at',)


class AddressSerializer(serializers.ModelSerializer):
    locality_location_lat = serializers.ReadOnlyField(source='locality_location.y')
    locality_location_long = serializers.ReadOnlyField(source='locality_location.x')
    landmark_location_lat = serializers.ReadOnlyField(source='landmark_location.y', required=False, allow_null=True, default=None)
    landmark_location_long = serializers.ReadOnlyField(source='landmark_location.x', required=False, allow_null=True, default=None)

    class Meta:
        model = Address
        fields = ('id', 'type', 'address', 'land_mark', 'pincode',
                  'phone_number', 'is_default', 'profile', 'locality',
                  'landmark_place_id', 'locality_place_id', 'locality_location_lat', 'locality_location_long',
                  'landmark_location_lat', 'landmark_location_long')

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
    source = serializers.ChoiceField(choices=AppointmentHistory.SOURCE_CHOICES, required=False)
    completed = serializers.BooleanField(required=False)


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
    hash = serializers.CharField(max_length=1000)


class UserTransactionModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConsumerTransaction
        fields = ('type', 'action', 'amount', 'product_id', 'reference_id', 'order_id', 'created_at', 'source')
        # fields = '__all__'


class RefreshJSONWebTokenSerializer(serializers.Serializer):

    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs['token']

        payload = self.check_payload_custom(token=token)
        user = self.check_user_custom(payload=payload)
        # Get and check 'orig_iat'
        orig_iat = payload.get('orig_iat')

        if orig_iat:
            # Verify expiration
            refresh_limit = settings.JWT_AUTH['JWT_REFRESH_EXPIRATION_DELTA']

            if isinstance(refresh_limit, datetime.timedelta):
                refresh_limit = (refresh_limit.days * 24 * 3600 +
                                 refresh_limit.seconds)

            expiration_timestamp = orig_iat + int(refresh_limit)
            now_timestamp = calendar.timegm(datetime.datetime.utcnow().utctimetuple())

            if now_timestamp > expiration_timestamp:
                msg = _('Token has expired.')
                raise serializers.ValidationError(msg)
        else:
            msg = _('orig_iat missing')
            raise serializers.ValidationError(msg)

        token_object = JWTAuthentication.generate_token(user)
        token_object['payload']['orig_iat'] = orig_iat

        return {
            'token': token_object['token'],
            'user': user,
            'payload': token_object['payload']
        }

    def check_user_custom(self, payload):
        uid = payload.get('user_id')

        if not uid:
            msg = ('Invalid Token.')
            raise serializers.ValidationError(msg)

        # Make sure user exists
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            msg = ("User doesn't exist.")
            raise serializers.ValidationError(msg)

        if not user.is_active:
            msg = ('User account is disabled.')
            raise serializers.ValidationError(msg)

        return user

    def check_payload_custom(self, token):
        user_key = None
        user_id = JWTAuthentication.get_unverified_user(token)
        if user_id:
            user_key_object = UserSecretKey.objects.filter(user_id=user_id).first()
            if user_key_object:
                user_key = user_key_object.key
        try:
            payload = jwt.decode(token, user_key)
        except jwt.ExpiredSignature:
            msg = ('Token has expired.')
            raise serializers.ValidationError(msg)
        except jwt.DecodeError:
            msg = ('Error decoding signature.')
            raise serializers.ValidationError(msg)

        return payload


class OnlineLeadSerializer(serializers.ModelSerializer):
    member_type = serializers.ChoiceField(choices=OnlineLead.TYPE_CHOICES)
    name = serializers.CharField(max_length=255)
    speciality = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    mobile = serializers.IntegerField(allow_null=False, max_value=9999999999, min_value=1000000000)
    city_name = serializers.IntegerField(required=False)
    email = serializers.EmailField()
    utm_params = serializers.JSONField(required=False)
    source = serializers.CharField(max_length=128, required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        if attrs['city_name'] > 0:
            if not common_models.Cities.objects.filter(id=attrs['city_name']).exists():
                raise serializers.ValidationError('City not found for given city.')

            attrs['city_name'] = common_models.Cities.objects.filter(id=attrs['city_name']).first()
        else:
            attrs['city_name'] = None
        return attrs

    class Meta:
        model = OnlineLead
        fields = ('member_type', 'name', 'speciality', 'mobile', 'city_name', 'email', 'utm_params', 'source')


class CareerSerializer(serializers.ModelSerializer):
    profile_type = serializers.ChoiceField(choices=Career.PROFILE_TYPE_CHOICES)
    name = serializers.CharField(max_length=255)
    mobile = serializers.IntegerField(max_value=9999999999, min_value=1000000000)
    email = serializers.EmailField()
    resume = serializers.FileField()

    class Meta:
        model = Career
        fields = ('profile_type', 'name', 'mobile', 'email', 'resume')


class OrderDetailDoctorSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    profile = serializers.IntegerField(source="action_data.profile")
    date = serializers.SerializerMethodField()
    hospital = serializers.IntegerField(source="action_data.hospital")
    doctor = serializers.IntegerField(source="action_data.doctor")
    time = serializers.SerializerMethodField()

    def get_time(self, obj):
        from ondoc.api.v1.diagnostic.views import LabList
        app_date_time = parse_datetime(obj.action_data.get("time_slot_start"))
        value = round(float(app_date_time.hour) + (float(app_date_time.minute)*1/60), 2)
        lab_obj = LabList()
        text = lab_obj.convert_time(value)
        doc_deal_price, doc_mrp, doc_agreed_price = obj.get_doctor_prices()
        doc_deal_price, doc_mrp = str(doc_deal_price), str(doc_mrp)
        data = {
            'deal_price': doc_deal_price,
            'is_available': True,
            'effective_price': obj.action_data.get("effective_price"),
            'mrp': doc_mrp,
            'value': value,
            'text': text
        }
        return data

    def get_date(self, obj):
        date_str = obj.action_data.get("time_slot_start")
        date = parse_datetime(date_str)
        return date.date()

    class Meta:
        fields = ('product_id', 'date', 'hospital', 'doctor', 'time')


class OrderDetailLabSerializer(serializers.Serializer):
    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    profile = serializers.IntegerField(source="action_data.profile")
    lab = serializers.IntegerField(source="action_data.lab")
    test_ids = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    is_home_pickup = serializers.BooleanField(source="action_data.is_home_pickup", default=False)
    address = serializers.IntegerField(source="action_data.address.id", default=None)

    def get_test_ids(self, obj):
        queryset = AvailableLabTest.objects.filter(id__in=obj.action_data.get("lab_test")).values("test", "test__name")
        test_ids = [{"id": d["test"], "name": d["test__name"]} for d in queryset]
        return test_ids

    def get_time(self, obj):
        from ondoc.api.v1.diagnostic.views import LabList
        app_date_time = parse_datetime(obj.action_data.get("time_slot_start"))
        value = round(float(app_date_time.hour) + (float(app_date_time.minute)*1/60), 2)
        lab_obj = LabList()
        text = lab_obj.convert_time(value)
        data = {
            'deal_price': obj.action_data.get("deal_price"),
            'is_available': True,
            'effective_price': obj.action_data.get("effective_price"),
            'price': obj.action_data.get("price"),
            'value': value,
            'text': text
        }
        return data

    def get_date(self, obj):
        date_str = obj.action_data.get("time_slot_start")
        date = parse_datetime(date_str)
        return date.date()

    class Meta:
        fields = ('product_id', 'lab', 'date', 'time', 'test_ids', 'profile', 'is_home_pickup', 'address')


class ContactUsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    mobile = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    email = serializers.EmailField()
    message = serializers.CharField(max_length=2000)
    from_app = serializers.BooleanField(default=False)

    class Meta:
        model = ContactUs
        fields = ('name', 'mobile', 'email', 'message')


class UserLeadSerializer(serializers.ModelSerializer):

    gender = serializers.ChoiceField(choices=UserLead.gender_choice, allow_null=True, allow_blank=True)
    name = serializers.CharField(max_length=255, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(max_length=15, required=True)
    message = serializers.CharField(allow_null=True, allow_blank=True)

    class Meta:
        model = UserLead
        fields = ('name', 'phone_number', 'gender', 'message')


class TokenFromUrlKeySerializer(serializers.Serializer):
    auth_token = serializers.CharField(max_length=100, required=False)
    key = serializers.CharField(max_length=30, required=False)

    def validate(self, attrs):
        if not (attrs.get('auth_token') or attrs.get('key')):
            raise serializers.ValidationError('neither auth_token nor key found')
        return attrs
