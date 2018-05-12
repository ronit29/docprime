from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import BaseFilterBackend
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.http import Http404

from django.contrib.auth import get_user_model
User = get_user_model()

from ondoc.doctor.models import OpdAppointment, DoctorHospital, Doctor, DoctorLeave
from .serializers import (OpdAppointmentSerializer, UpdateStatusSerializer,
                          AppointmentFilterSerializer, CreateAppointmentSerializer, DoctorHospitalModelSerializer,
                          DoctorHospitalListSerializer, DoctorProfileSerializer, DoctorHospitalSerializer,
                          DoctorBlockCalenderSerialzer, DoctorLeaveSerializer)
from ondoc.api.pagination import paginate_queryset

from django.db.models import Min


# class DoctorFilterBackend(BaseFilterBackend):

#     def filter_queryset(self, request, queryset, view):
#         return queryset.filter(doctor__user=request.user)

class CreateAppointmentPermission(permissions.BasePermission):
    message = 'creating appointment is not allowed.'

    def has_permission(self, request, view):
        if request.user.user_type==User.CONSUMER:
            return True
        return False


class DoctorPermission(permissions.BasePermission):
    message = 'Doctor is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.DOCTOR:
            return True
        return False


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class DoctorAppointmentsViewSet(OndocViewSet):
    authentication_classes = (TokenAuthentication, )
#     filter_backends = (DjangoFilterBackend)
    permission_classes = (IsAuthenticated,)
#     #queryset = OpdAppointment.objects.all()
    serializer_class = OpdAppointmentSerializer
#     filter_fields = ('hospital','profile','')

#     # def list (self, request):
#     #     return super().list()

#     def get_queryset(self):

#         user = self.request.user
#         if user.user_type== User.DOCTOR:
#             return OpdAppointment.objects.all(doctor=user.doctor)
#         elif user.user_type== User.CONSUMER:
#             return OpdAppointment.objects.all(user=user)

#     def list(self, request):
#         queryset = self.get_queryset()
#         serializer = AppointmentFilterSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         range = serializer.validated_data['range']
#         if range=='previous':
#             queryset.filter(time_slot_start__lte=timezone.now())
#         elif range=='upcoming':
#             queryset.filter(time_slot_start__gt=timezone.now())
#         serial = OpdAppointmentSerializer(queryset, many=True)
#         return Response(serial.data)

    # @action(methods=['post'], detail=True)
    # def update_status(self, request, pk):
    #     opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
    #     serializer = UpdateStatusSerializer(data=request.data,
    #                                         context={'request': request, 'opd_appointment': opd_appointment})
    #     serializer.is_valid(raise_exception=True)
    #     data = serializer.validated_data
    #     opd_appointment.status = data.get('status')
    #     if data.get('status') == OpdAppointment.RESCHEDULED and request.user.user_type == 3:
    #         opd_appointment.time_slot_start = data.get("time_slot_start")
    #         opd_appointment.time_slot_end = data.get("time_slot_end")
    #     opd_appointment.save()
    #     opd_appointment_serializer = OpdAppointmentSerializer(opd_appointment)
    #     return Response(opd_appointment_serializer.data)

    def get_queryset(self):

        user = self.request.user
        if user.user_type == User.DOCTOR:
            return OpdAppointment.objects.filter(doctor=user.doctor)
        elif user.user_type == User.CONSUMER:
            return OpdAppointment.objects.filter(user=user)


    def list(self, request):
        queryset = self.get_queryset()
        serializer = AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital_id = serializer.validated_data.get('hospital_id')

        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)

        if range=='previous':
            queryset = queryset.filter(time_slot_start__lte=timezone.now()).order_by('-time_slot_start')
        elif range=='upcoming':
            queryset = queryset.filter(
                status__in=[OpdAppointment.CREATED, OpdAppointment.RESCHEDULED, OpdAppointment.ACCEPTED],
                time_slot_start__gt=timezone.now()).order_by('time_slot_start')
        elif range =='pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status = OpdAppointment.CREATED).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request)    
        serializer = OpdAppointmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request):
        serializer = CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = data.get("time_slot_start")

        doctor_hospital = DoctorHospital.objects.filter(doctor=data.get('doctor'), hospital=data.get('hospital'),
            day=time_slot_start.weekday(),start__lte=time_slot_start.hour, end__gte=time_slot_start.hour).first()
        fees = doctor_hospital.fees

        data = {
            "doctor": data.get("doctor").id,
            "hospital": data.get("hospital").id,
            "profile": data.get("profile").id,
            "user": request.user.id,
            "booked_by": request.user.id,
            "fees": fees,
            "time_slot_start": time_slot_start,
            #"time_slot_end": time_slot_end,
        }

        appointment_serializer = OpdAppointmentSerializer(data=data)
        appointment_serializer.is_valid(raise_exception=True)
        appointment_serializer.save()
        resp = {}
        resp["status"] = 1
        resp["data"] = appointment_serializer.data
        return Response(data=resp)

    def update(self, request, pk=None):
        opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
        serializer = UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if request.user.user_type == User.DOCTOR:
            updated_opd_appointment = self.doctor_update(opd_appointment, validated_data)
        elif request.user.user_type == User.CONSUMER:
            updated_opd_appointment = self.consumer_update(opd_appointment, validated_data)
        opd_appointment_serializer = OpdAppointmentSerializer(updated_opd_appointment)
        response = {
            "status": 1,
            "data": opd_appointment_serializer.data
        }
        return Response(response)

    def doctor_update(self, opd_appointment, validated_data):
        opd_appointment.status = validated_data.get('status')
        opd_appointment.save()
        return opd_appointment

    def consumer_update(self, opd_appointment, validated_data):
        opd_appointment.status = validated_data.get('status')
        if validated_data.get('status') == OpdAppointment.RESCHEDULED:
            opd_appointment.time_slot_start = validated_data.get("time_slot_start")
            opd_appointment.time_slot_end = validated_data.get("time_slot_end")
        opd_appointment.save()
        return opd_appointment


class DoctorProfileView(viewsets.GenericViewSet):
    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):
        doctor  = get_object_or_404(Doctor, pk=request.user.doctor.id)
        serializer = DoctorProfileSerializer(doctor, many=False)

        return Response(serializer.data)


class DoctorHospitalView(mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = DoctorHospital.objects.all()
    serializer_class = DoctorHospitalSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.DOCTOR:
            return DoctorHospital.objects.filter(doctor=user.doctor)


    def list(self, request):
        user = request.user
        queryset = self.get_queryset().values('hospital').annotate(min_fees=Min('fees'))

        serializer = DoctorHospitalListSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk):
        user = request.user

        queryset = self.get_queryset().filter(hospital=pk)
        if len(queryset) == 0:
            raise Http404("No Hospital matches the given query.")

        serializer = DoctorHospitalModelSerializer(queryset, many=True)
        return Response(serializer.data)

class DoctorBlockCalendarViewSet(OndocViewSet):
    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated, DoctorPermission, )
    INTERVAL_MAPPING = {DoctorLeave.INTERVAL_MAPPING.get(key): key for key in DoctorLeave.INTERVAL_MAPPING.keys()}

    def get_queryset(self):
        user = self.request.user
        return DoctorLeave.objects.filter(doctor=user.doctor.id, deleted_at__isnull=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = DoctorLeaveSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = DoctorBlockCalenderSerialzer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor_leave_data = {
            "doctor": request.user.doctor.id,
            "start_time": self.INTERVAL_MAPPING[validated_data.get("interval")][0],
            "end_time": self.INTERVAL_MAPPING[validated_data.get("interval")][1],
            "start_date": validated_data.get("start_date"),
            "end_date": validated_data.get("end_date")
        }
        doctor_leave_serializer = DoctorLeaveSerializer(data=doctor_leave_data)
        doctor_leave_serializer.is_valid(raise_exception=True)
        doctor_leave_serializer.save()
        return Response(doctor_leave_serializer.data)

    def destroy(self, request, pk=None):
        current_time = timezone.now()
        doctor_leave = DoctorLeave.objects.get(pk=pk)
        doctor_leave.deleted_at = current_time
        doctor_leave.save()
        return Response({
            "status": 1
        })
