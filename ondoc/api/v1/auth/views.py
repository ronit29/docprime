from rest_framework.viewsets import GenericViewSet
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import mixins

from .serializers import (OTPSerializer, OTPVerificationSerializer, UserSerializer, DoctorLoginSerializer,
                          NotificationEndpointSaveSerializer, NotificationEndpointSerializer,
                          NotificationEndpointDeleteSerializer, NotificationSerializer, UserProfileSerializer,
                          UserPermissionSerializer)
from rest_framework.response import Response
from django.db import transaction
from rest_framework.authtoken.models import Token

from ondoc.sms.api import send_otp

from ondoc.doctor.models import DoctorMobile, Doctor, HospitalNetwork, Hospital, DoctorHospital
from ondoc.authentication.models import (OtpVerifications, NotificationEndpoint, Notification, UserProfile,
                                         UserPermission)
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ondoc.api.pagination import paginate_queryset

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

        req_type = request.query_params.get('type')

        if req_type == 'doctor':
            if DoctorMobile.objects.filter(number=phone_number, is_primary=True).exists():
                response['exists']=1
        else:
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
        # data['profile'] = {
        #     'name': request.data.get('name'),
        #     'age': request.data.get('age'),
        #     'gender': request.data.get('gender'),
        #     'email': request.data.get('email'),
        # }

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


class NotificationEndpointViewSet(GenericViewSet):
    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated,)

    def save(self, request):
        serializer = NotificationEndpointSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        notification_endpoint_data = {
            "user": request.user.id,
            "device_id": validated_data.get("device_id"),
            "token": validated_data.get("token")
        }
        notification_endpoint_serializer = NotificationEndpointSerializer(data=notification_endpoint_data)
        notification_endpoint_serializer.is_valid(raise_exception=True)
        notification_endpoint_serializer.save()
        return Response(notification_endpoint_serializer.data)

    def delete(self, request):
        serializer = NotificationEndpointDeleteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        notification_endpoint = NotificationEndpoint.objects.filter(token=validated_data.get('token')).first()
        notification_endpoint.delete()
        return Response(data={"status": 1, "message": "deleted"})


class NotificationViewSet(GenericViewSet):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        queryset = paginate_queryset(queryset=Notification.objects.filter(user=request.user),
                                     request=request)
        serializer = NotificationSerializer(queryset, many=True)
        return Response(serializer.data)


class UserProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                         mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         GenericViewSet):
    serializer_class = UserProfileSerializer
    queryset = UserProfile.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        queryset = UserProfile.objects.filter(user=request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = request.data
        data['user'] = request.user.id
        if not data.get('phone_number'):
            data['phone_number'] = request.user.phone_number
        serializer = UserProfileSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        if not queryset.exists():
            serializer.validated_data['is_default_user'] = True
        serializer.save()
        return Response(serializer.data)


class UserPermissionViewSet(mixins.CreateModelMixin,
                            mixins.ListModelMixin,
                            GenericViewSet):
    queryset = DoctorHospital.objects.all()
    # serializer_class = UserPermissionSerializer

    def list(self, request, *args, **kwargs):
        params = request.query_params
        dp_obj = ResetDoctorPermission(params['doctor_id'])
        permission_data = dp_obj.create_permission()
        serializer = UserPermissionSerializer(data=permission_data, many=True)
        # serializer.is_valid(raise_exception=True)
        serializer.is_valid(raise_exception=True)
        # serializer.save()
        return Response([])


class ResetDoctorPermission(object):

    def __init__(self, doctor_id):
        self.doctor_id = doctor_id

    def create_permission(self):

        # up_queryset = (UserPermission.objects.all().prefetch_related('hospital_network__hospital_set').
        #                filter(permission=UserPermission.APPOINTMENT_WRITE))

        up1 = (UserPermission.objects.prefetch_related('hospital_network__hospital_set').
               filter(permission=UserPermission.APPOINTMENT_WRITE))
        hospital_queryset = (DoctorHospital.objects.select_related("doctor").filter(doctor=self.doctor_id))
        # hospital_network_queryset = HospitalNetwork.objects.filter()
        # admin = UserPermission.objects.filter(doctor=self.doctor_id)
        permission_data = list()
        for data in hospital_queryset:
            temp_dict = dict()
            temp_dict['user'] = data.doctor.user.id
            temp_dict['doctor'] = data.doctor.id
            temp_dict['hospital_network'] = None
            temp_dict['hospital'] = data.hospital.id
            if data.hospital.hospital_admins or data.hospital.network.network_admins:
                temp_dict['permission'] = UserPermission.APPOINTMENT_READ
            else:
                temp_dict['permission'] = UserPermission.APPOINTMENT_WRITE

            permission_data.append(temp_dict)

        return permission_data

