from rest_framework.views import APIView
from .serializers import OTPSerializer
from rest_framework.response import Response

from ondoc.sms.api import send_otp

class OTP(APIView):

    def post(self, request, format=None):

        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        phone_number = data['phone_number']        
        send_otp("otp sent {}", phone_number)
        return Response({"message" : "OTP Generated Sucessfuly."})