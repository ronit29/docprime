from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from ondoc.authentication.models import OtpVerifications, User, UserProfile
from ondoc.authentication.serializers import UserAuthSerializer, UserProfileSerializer
from random import randint
from .service import sendOTP

@api_view(['POST', ])
def register_user(request, format='json'):
    try:
        phone_number = request.data['phone_number']
        otp = request.data['otp']
        otpEntry = OtpVerifications.objects.get(phone_number=phone_number, code=otp, isExpired=False)
        otpEntry.isExpired = True
        otpEntry.save()
    except OtpVerifications.DoesNotExist:
        return Response('No OTP found',status=404)

    userData = request.data
    userData['is_phone_number_verified'] = True
    userData['is_default_user'] = True
    userData['is_otp_verified'] = True
    
    userSerializer = UserAuthSerializer(data=userData, context={'user_type': 3})
    if userSerializer.is_valid(raise_exception=True):
        user = userSerializer.save()
        if user:
            # creating user profile now
            userProfileSerializer = UserProfileSerializer(data=userData,context={ 'user': user, 'email': '' })
            if userProfileSerializer.is_valid(raise_exception=True):
                userProfile = userProfileSerializer.save()
                token = Token.objects.get_or_create(user=user)
                response = {
                    "message" : "Sucessfuly Create user and Logged In",
                    "token" : str(token[0])
                }
                return Response(response,status=200)
            else :
                return Response(userProfileSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
    else :
        return Response(userSerializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


@api_view(['POST', ])
def verify_otp(request):
    """
    Takes OTP and user details, verifies those and will then create session and creates a user if required. and return sessionId
    """
    
    phone_number = request.data['phone_number']
    otp = request.data['otp']

    try:
        otpEntry = OtpVerifications.objects.get(phone_number=phone_number, code=otp, isExpired=False)
        otpEntry.isExpired = True
        otpEntry.save()
        user_data = User.objects.get(phone_number=phone_number, user_type=3)
        token = Token.objects.get_or_create(user=user_data)

        response = {
            "message" : "Sucessfuly. Logged In",
            "token" : str(token[0])
        }
        return Response(response,status=200)
    except OtpVerifications.DoesNotExist:
        return Response('No OTP found',status=404)
    except User.DoesNotExist:
        return Response('User Not found',status=404)


@api_view(['GET', ])
@authentication_classes((TokenAuthentication, ))
@permission_classes((IsAuthenticated,))
def logout(request, format='json'):
    request.user.auth_token.delete()
    return Response(status=status.HTTP_200_OK)
