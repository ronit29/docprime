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

from ondoc.doctor.models import OpdAppointment, DoctorHospital
from .serializers import OpdAppointmentSerializer, SetAppointmentSerializer, UpdateStatusSerializer, AppointmentFilterSerializer



# class DoctorFilterBackend(BaseFilterBackend):

#     def filter_queryset(self, request, queryset, view):
#         return queryset.filter(doctor__user=request.user)




class CreateAppointmentPermission(permissions.BasePermission):
    message = 'creating appointment is not allowed.'

    def has_permission(self, request, view):
        if request.user.user_type==User.CONSUMER:
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
    filter_backends = (DjangoFilterBackend)
    permission_classes = (IsAuthenticated,)
    #queryset = OpdAppointment.objects.all()
    serializer_class = OpdAppointmentSerializer
    filter_fields = ('hospital','profile','')

    # def list (self, request):
    #     return super().list()

    def get_queryset(self):

        user = self.request.user
        if user.user_type== User.DOCTOR:
            return OpdAppointment.objects.all(doctor=user.doctor)
        elif user.user_type== User.CONSUMER:
            return OpdAppointment.objects.all(user=user)

    def list(self, request):
        queryset = self.get_queryset()
        serializer = AppointmentFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        range = serializer.validated_data['range']
        if range=='previous':
            queryset.filter(time_slot_start__lte=timezone.now())
        elif range=='upcoming':
            queryset.filter(time_slot_start__gt=timezone.now())
        serial = OpdAppointmentSerializer(queryset, many=True)
        return Response(serial.data)

    @action(methods=['post'], detail=False, permission_classes=[IsAuthenticated, CreateAppointmentPermission])
    def set_appointment(self, request):
        serializer = SetAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data

        time_slot_start = parameters.get("time_slot_start")
        time_slot_end = parameters.get("time_slot_end")

        doctor_hospital = (
            DoctorHospital.objects.filter(doctor=parameters.get('doctor'), hospital=parameters.get('hospital')).filter(
                day=time_slot_start.weekday(), start__lte=time_slot_start.hour, end__gte=time_slot_end.hour).first())

        if not doctor_hospital:
            return Response(data={"message": "Doctor is not available."}, status=status.HTTP_400_BAD_REQUEST)

        fees = doctor_hospital.fees
        data = {
            "doctor": parameters.get("doctor").id,
            "hospital": parameters.get("hospital").id,
            "profile": parameters.get("profile").id,
            "user": request.user.id,
            "booked_by": request.user.id,
            "fees": fees,
            "time_slot_start": time_slot_start,
            "time_slot_end": time_slot_end,
        }
        appointment_serializer = OpdAppointmentSerializer(data=data)
        appointment_serializer.is_valid(raise_exception=True)
        appointment_serializer.save()
        return Response(data=appointment_serializer.data)

    @action(methods=['post'], detail=True)
    def update_status(self, request, pk):
        opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
        serializer = UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        opd_appointment.status = data.get('status')
        if data.get('status') == OpdAppointment.RESCHEDULED and request.user.user_type == 3:
            opd_appointment.time_slot_start = data.get("time_slot_start")
            opd_appointment.time_slot_end = data.get("time_slot_end")
        opd_appointment.save()
        opd_appointment_serializer = OpdAppointmentSerializer(opd_appointment)
        return Response(opd_appointment_serializer.data)
