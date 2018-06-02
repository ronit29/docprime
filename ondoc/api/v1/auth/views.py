from rest_framework.viewsets import GenericViewSet
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import mixins, viewsets, status

from ondoc.api.v1.auth import serializers

# from .serializers import (OTPSerializer, OTPVerificationSerializer, UserSerializer, DoctorLoginSerializer,
#                           NotificationEndpointSaveSerializer, NotificationEndpointSerializer,
#                           NotificationEndpointDeleteSerializer, NotificationSerializer, UserProfileSerializer,
#                           UserPermissionSerializer)
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from ondoc.sms.api import send_otp

from ondoc.doctor.models import DoctorMobile, Doctor, HospitalNetwork, Hospital, DoctorHospital
from ondoc.authentication.models import (OtpVerifications, NotificationEndpoint, Notification, UserProfile,
                                         UserPermission, Address)
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ondoc.api.pagination import paginate_queryset

from ondoc.doctor.models import OpdAppointment
from ondoc.api.v1.doctor.serializers import (OpdAppointmentSerializer, AppointmentFilterSerializer,
                                             UpdateStatusSerializer, CreateAppointmentSerializer)
from ondoc.diagnostic.models import (LabAppointment)
from ondoc.api.v1.diagnostic.serializers import (LabAppointmentModelSerializer)


User = get_user_model()


def expire_otp(phone_number):
    OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)

class LoginOTP(GenericViewSet):

    @transaction.atomic
    def generate(self, request, format=None):

        response = {'exists':0}
        serializer = serializers.OTPSerializer(data=request.data)
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

        serializer = serializers.OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({"message" : "OTP Generated Sucessfuly."})


class UserViewset(GenericViewSet):

    @transaction.atomic
    def login(self, request, format=None):
        serializer = serializers.OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user_exists = 1
        user = User.objects.filter(phone_number=data['phone_number'], user_type=User.CONSUMER).first()
        if not user:
            user_exists = 0
            user = User.objects.create(phone_number=data['phone_number'],
                                       is_phone_number_verified=True,
                                       user_type=User.CONSUMER)

        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0]),
            "user_exists": user_exists,
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

        serializer = serializers.UserSerializer(data=data)
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
        serializer = serializers.DoctorLoginSerializer(data=request.data)
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
        serializer = serializers.NotificationEndpointSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        notification_endpoint_data = {
            "user": request.user.id,
            "device_id": validated_data.get("device_id"),
            "token": validated_data.get("token")
        }
        notification_endpoint_serializer = serializers.NotificationEndpointSerializer(data=notification_endpoint_data)
        notification_endpoint_serializer.is_valid(raise_exception=True)
        notification_endpoint_serializer.save()
        return Response(notification_endpoint_serializer.data)

    def delete(self, request):
        serializer = serializers.NotificationEndpointDeleteSerializer(data=request.data, context={"request": request})
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
        serializer = serializers.NotificationSerializer(queryset, many=True)
        return Response(serializer.data)


class UserProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                         mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         GenericViewSet):
    serializer_class = serializers.UserProfileSerializer
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
        data = {}
        data.update(request.data)
        data['user'] = request.user.id
        if not data.get('phone_number'):
            data['phone_number'] = request.user.phone_number
        serializer = serializers.UserProfileSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        if not queryset.exists():
            serializer.validated_data['is_default_user'] = True
        serializer.save()
        return Response(serializer.data)


class UserPermissionViewSet(mixins.CreateModelMixin,
                            mixins.ListModelMixin,
                            GenericViewSet):
    queryset = DoctorHospital.objects.all()
    # serializer_class = serializers.UserPermissionSerializer

    def list(self, request, *args, **kwargs):
        params = request.query_params
        doctor_list = params['doctor_id'].split(",")
        dp_obj = DoctorPermission(doctor_list, request)
        permission_data = dp_obj.create_permission()
        return Response(permission_data)


class DoctorPermission(object):

    def __init__(self, doctor_list, request):
        self.doctor_list = doctor_list
        self.request = request

    def create_permission(self):
        hospital_queryset = (DoctorHospital.objects.
                             prefetch_related('hospital__hospital_admins', 'doctor', 'doctor__user').
                             filter(doctor__in=self.doctor_list))
        permission_data = self.form_data(hospital_queryset)
        serializer = serializers.UserPermissionSerializer(data=permission_data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return serializer.data

    @staticmethod
    def form_data(hospital_queryset):
        permission_data = list()
        for data in hospital_queryset:
            permission_dict = dict()
            permission_dict['user'] = data.doctor.user.id
            permission_dict['doctor'] = data.doctor.id
            permission_dict['hospital_network'] = None
            permission_dict['hospital'] = data.hospital.id
            permission_dict['permission_type'] = UserPermission.APPOINTMENT
            hospital_admins = data.hospital.hospital_admins.all()
            flag = False
            for admin in hospital_admins:
                if admin.permission_type == UserPermission.APPOINTMENT and admin.write_permission:
                    flag = True
                    break
            if flag:
                permission_dict['read_permission'] = True
            else:
                permission_dict['write_permission'] = True

            permission_data.append(permission_dict)
        return permission_data


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class UserAppointmentsViewSet(OndocViewSet):

    serializer_class = OpdAppointmentSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return OpdAppointment.objects.filter(user=user)

    def list(self, request):
        doctor_serializer = self.doctor_appointment_list(request)
        lab_serializer = self.lab_appointment_list(request)
        combined_data = list()
        combined_data.extend(doctor_serializer)
        combined_data.extend(lab_serializer)
        combined_data = sorted(combined_data, key=lambda k: k['time_slot_start'])
        combined_data = combined_data[:20]
        return Response(combined_data)

    def lab_appointment_list(self, request):
        user = request.user
        queryset = LabAppointment.objects.filter(profile__user=user)
        queryset = paginate_queryset(queryset, request, 20)
        serializer = LabAppointmentModelSerializer(queryset, many=True)
        return serializer.data

    def doctor_appointment_list(self, request):
        user = request.user
        queryset = OpdAppointment.objects.filter(user=user)

        if not queryset:
            return Response([])
        serializer = AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital_id = serializer.validated_data.get('hospital_id')
        profile_id = serializer.validated_data.get('profile_id')

        if profile_id:
            queryset = queryset.filter(profile=profile_id)

        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)

        if range == 'previous':
            queryset = queryset.filter(time_slot_start__lte=timezone.now()).order_by('-time_slot_start')
        elif range == 'upcoming':
            queryset = queryset.filter(
                status__in=[OpdAppointment.CREATED, OpdAppointment.RESCHEDULED_DOCTOR,
                            OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.ACCEPTED],
                time_slot_start__gt=timezone.now()).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(),
                                       status=OpdAppointment.CREATED).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request, 20)
        serializer = OpdAppointmentSerializer(queryset, many=True)
        return serializer.data


class AddressViewsSet(viewsets.ModelViewSet):
    serializer_class = serializers.AddressSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        return Address.objects.filter(user=request.user)

    def create(self, request, *args, **kwargs):
        data = dict(request.data)
        data["user"] = request.user.id
        # Added recently
        if 'is_default' not in data:
            if not Address.objects.filter(user=request.user.id).exists():
                data['is_default'] = True

        serializer = serializers.AddressSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request, pk=None):
        data = request.data
        data['user'] = request.user.id
        queryset = get_object_or_404(Address, pk=pk)
        if data.get("is_default"):
            add_default_qs = Address.objects.filter(user=request.user.id, is_default=True)
            if add_default_qs:
                add_default_qs.update(is_default=False)
        serializer = serializers.AddressSerializer(queryset, data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        address = get_object_or_404(Address, pk=pk)

        if address.is_default:
            temp_addr = Address.objects.filter(user=request.user.id).first()
            if temp_addr:
                temp_addr.is_default = True
                temp_addr.save()

        # address = Address.objects.filter(pk=pk).first()
        address.delete()
        return Response({
            "status": 1
        })

