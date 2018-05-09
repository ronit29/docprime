from datetime import datetime
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import mixins
from .serializers import OTPSerializer
from rest_framework.response import Response
from rest_framework import status
from ondoc.doctor.models import OpdAppointment, Doctor, Hospital, UserProfile, User, DoctorHospital
from .serializers import OpdAppointmentSerializer, SetAppointmentSerializer
from rest_framework.decorators import action
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated


from ondoc.sms.api import send_otp


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class OTP(APIView):

    def post(self, request, format=None):

        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        phone_number = data['phone_number']        
        send_otp("otp sent {}", phone_number)
        return Response({"message" : "OTP Generated Sucessfuly."})


class DoctorAppointmentsViewSet(OndocViewSet):
    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated,)
    queryset = OpdAppointment.objects.all()
    serializer_class = OpdAppointmentSerializer

    @action(methods=['post'], detail=False)
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

