from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from ondoc.authentication.models import OtpVerifications, User, UserProfile
from ondoc.authentication.serializers import UserAuthSerializer
from random import randint
from .service import sendOTP

@api_view(['POST', ])
def register_user(request, format='json'):
    try:
        phone_number = request.data['phone_number']
        otp = request.data['otp']
        otpEntry = OtpVerifications.objects.get(phone_number=phone_number, code=otp, isExpired=False)
    except OtpVerifications.DoesNotExist:
        return Response('No OTP found',status=404)

    userData = request.data
    userData['is_phone_number_verified'] = True
    serializer = UserAuthSerializer(data=userData, context={'user_type': 3})
    
    if serializer.is_valid(raise_exception=True):
        user = serializer.save()
        if user:
            json = serializer.data
            return Response(json, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', ])
def generate_otp(request):
    """
    Sends OTP to the provided phone number
    """
    phone_number = request.data['phone_number']
    random_otp = randint(1000,9999)
    response = {
        "message" : "OTP Generated Sucessfuly."
    }
    
    try:
        sendOTP(phone_number, random_otp)
        otpEntry = OtpVerifications.objects.create(phone_number=phone_number, code=random_otp, country_code="+91")
        otpEntry.save()

        user_data = User.objects.get(phone_number=phone_number, user_type=3)
        user_profile = UserProfile.objects.get(user=user_data)

        return Response(response)
    except User.DoesNotExist:
        response['message'] = 'User Not found'
        return Response(response, status=200)
    except UserProfile.DoesNotExist:
        response['message'] = 'UserProfile Not found'
        return Response(response, status=200)
    except Exception as e:
        return Response(str(e),status=500)


@api_view(['POST', ])
def verify_otp(request):
    """
    Takes OTP and user details, verifies those and will then create session and creates a user if required. and return sessionId
    """
    
    phone_number = request.data['phone_number']
    otp = request.data['otp']

    try:
        otpEntry = OtpVerifications.objects.get(phone_number=phone_number, code=otp, isExpired=False)
        response = {
            "message" : "Sucessfuly. Logged In"
        }
        return Response(response,status=200)
    except OtpVerifications.DoesNotExist:
        return Response('No OTP found',status=404)    
    except Exception as e:
        return Response(str(e),status=500)

    
