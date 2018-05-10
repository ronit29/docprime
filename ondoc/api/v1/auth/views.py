from rest_framework.viewsets import GenericViewSet
from rest_framework.generics import GenericAPIView
from .serializers import OTPSerializer, OTPVerificationSerializer, UserSerializer, DoctorLoginSerializer
from rest_framework.response import Response
from django.db import transaction
from rest_framework.authtoken.models import Token

from ondoc.sms.api import send_otp

from ondoc.doctor.models import DoctorMobile
from ondoc.authentication.models import OtpVerifications
from django.contrib.auth import get_user_model
User = get_user_model()


def expire_otp(phone_number):
    OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)

class LoginOTP(GenericViewSet):

    @transaction.atomic
    def generate(self, request, format=None):

        response = {'exists':0}
        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        phone_number = data['phone_number']
        send_otp("otp sent {}", phone_number)

        if User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).exists():
            response['exists']=1

        return Response(response)

    def verify(self, request, format=None):

        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({"message" : "OTP Generated Sucessfuly."})

class UserViewset(GenericViewSet):

    @transaction.atomic
    def login(self, request, format=None):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(phone_number=data['phone_number'], user_type=User.CONSUMER).first()
        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0])
        }
        return Response(response)        

    @transaction.atomic
    def register(self, request, format=None):

        data = {'phone_number':request.data.get('phone_number'),'otp':request.data.get('otp')}
        data['profile'] = {
            'name': request.data.get('name'),
            'age': request.data.get('age'),
            'gender': request.data.get('gender'),
            'email': request.data.get('email'),
        }

        serializer = UserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0])
        }
        return Response(response)

    @transaction.atomic
    def doctor_login(self, request, format=None):
        serializer = DoctorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        phone_number = data['phone_number']
        user = User.objects.filter(phone_number=phone_number, user_type=User.DOCTOR).first()

        if not user:
            doctor = DoctorMobile.objects.get(number=phone_number, is_primary=True).doctor
            user = User.objects.create(phone_number=data['phone_number'], is_phone_number_verified=True, user_type=User.DOCTOR)
            doctor.user = user
            doctor.save()

        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0])
        }
        return Response(response)
