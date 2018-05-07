from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from ondoc.authentication.models import OtpVerifications, User, UserProfile
from ondoc.doctor.models import Doctor, DoctorMobile
from ondoc.authentication.serializers import UserAuthSerializer, UserProfileSerializer
from random import randint
from .services import sendOTP, verifyOTP

@api_view(['POST', ])
@verifyOTP
def register_user(request, format='json'):

    userData = request.data
    userData['is_phone_number_verified'] = True
    userData['is_default_user'] = True
    userData['is_otp_verified'] = True
    
    userSerializer = UserAuthSerializer(data=userData, context={'user_type': 3})
    if userSerializer.is_valid():
        user = userSerializer.save()
        try:
            # creating user profile now
            userProfileSerializer = UserProfileSerializer(data=userData,context={ 'user': user, 'email': '' })
            if userProfileSerializer.is_valid():
                userProfile = userProfileSerializer.save()
                token = Token.objects.get_or_create(user=user)
                response = {
                    "message" : "Sucessfuly Create user and Logged In",
                    "token" : str(token[0])
                }
                return Response(response,status=200)
        except:
            # TODO : deleting user for mocking rollback, fix later - make these transactional
            user.delete()
            return Response("Error Creating User Profile", status=status.HTTP_400_BAD_REQUEST)
    
    return Response(userSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

@api_view(['POST', ])
def generate_otp_user(request):
    phone_number = request.data['phone_number']
    random_otp = randint(100000,999999)
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
        response['status'] = 'User not registered'
        return Response(response, status=200)
    except UserProfile.DoesNotExist:
        response['status'] = 'User\'s Profile not found'
        return Response(response, status=200)


@api_view(['POST', ])
def generate_otp_doctor(request):
    phone_number = request.data['phone_number']
    random_otp = randint(100000,999999)
    response = {
        "message" : "OTP Generated Sucessfuly."
    }
    
    try:
        doctor_mobile = DoctorMobile.objects.get(number=phone_number, is_primary=True)
        sendOTP(phone_number, random_otp)
        otpEntry = OtpVerifications.objects.create(phone_number=phone_number, code=random_otp, country_code="+91")
        otpEntry.save()

        user_data = User.objects.get(phone_number=phone_number, user_type=3)

        return Response(response)
    except DoctorMobile.DoesNotExist:
        return Response('Doctor not registered',status=404)
    except User.DoesNotExist:
        response['status'] = 'Doctor_User Not Registered.'
        return Response(response, status=200)

@api_view(['POST', ])
@verifyOTP
def login_user(request):
    phone_number = request.data['phone_number']

    try:        
        user_data = User.objects.get(phone_number=phone_number, user_type=3)
        token = Token.objects.get_or_create(user=user_data)

        response = {
            "message" : "Sucessfuly. Logged In",
            "token" : str(token[0])
        }
        return Response(response,status=200)
    except User.DoesNotExist:
        return Response('User Not found',status=404)


@api_view(['POST', ])
@verifyOTP
def login_doctor(request):

    phone_number = request.data['phone_number']
    try:

        doctor_mobile = DoctorMobile.objects.get(number=phone_number, is_primary=True)
        doctor_data = doctor_mobile.doctor
        user_data = User.objects.get(phone_number=phone_number, user_type=2)
        token = Token.objects.get_or_create(user=user_data)

        response = {
            "message" : "Sucessfuly. Logged In",
            "token" : str(token[0])
        }
        return Response(response,status=200)
    except DoctorMobile.DoesNotExist:
        return Response('Doctor not registered',status=404)
    except User.DoesNotExist:
        # is user not exists, create one and then login
        userData = request.data
        userData['is_phone_number_verified'] = True
        userSerializer = UserAuthSerializer(data=userData, context={'user_type': 2})
        if userSerializer.is_valid(raise_exception=True):
            user = userSerializer.save()
            if user:
                # also link this user with doctor
                doctor_data.user = user
                doctor_data.save()
                token = Token.objects.get_or_create(user=user)
                response = {
                    "message" : "Sucessfuly. Logged In",
                    "token" : str(token[0])
                }
                return Response(response,status=200)
        
        return Response('Cannot register User',status=404)


@api_view(['GET', ])
@authentication_classes((TokenAuthentication, ))
@permission_classes((IsAuthenticated,))
def logout(request, format='json'):
    request.user.auth_token.delete()
    return Response(status=status.HTTP_200_OK)
