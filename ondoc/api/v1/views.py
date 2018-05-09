from rest_framework.viewsets import GenericViewSet
from rest_framework.generics import GenericAPIView
from .serializers import OTPSerializer, OTPVerificationSerializer, UserSerializer
from rest_framework.response import Response

from ondoc.sms.api import send_otp
from ondoc.authentication.models import User
class OTP(GenericViewSet):

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

class User(GenericViewSet):
    def login(self, request, format=None):
        pass
    def register(self, request, format=None):

        data = {'phone_number':request.data.get('phone_number'),'otp':request.data.get('otp')}
        data['profile'] = {
            'name': request.data.get('name'),
            'age': request.data.get('age'),
            'gender': request.data.get('gender'),
            'email': request.data.get('email'),
        }


        serializer = UserSerializer(data=data)
        if serializer.is_valid(raise_exception=True):
            pass
        pass    