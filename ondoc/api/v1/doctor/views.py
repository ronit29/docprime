from ondoc.doctor import models
from . import serializers
from ondoc.api.v1.diagnostic.serializers import TimeSlotSerializer
from ondoc.api.pagination import paginate_queryset
from ondoc.api.v1.utils import convert_timings
from django.db.models import Min
from django.contrib.gis.geos import Point
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.http import Http404
from django.db.models import Q
import datetime
from operator import itemgetter
from itertools import groupby
from django.contrib.gis.db.models.functions import Distance
from django.contrib.auth import get_user_model
User = get_user_model()


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
#     filter_backends = (DjangoFilterBackend)
    permission_classes = (IsAuthenticated,)
#     #queryset = OpdAppointment.objects.all()
    serializer_class = serializers.OpdAppointmentSerializer
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
            return models.OpdAppointment.objects.filter(doctor=user.doctor)
        elif user.user_type == User.CONSUMER:
            return models.OpdAppointment.objects.filter(user=user)

    def list(self, request):
        queryset = self.get_queryset()
        if not queryset:
            return Response([])
        serializer = serializers.AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital_id = serializer.validated_data.get('hospital_id')
        profile_id = serializer.validated_data.get('profile_id')

        if profile_id:
            queryset = queryset.filter(profile=profile_id)

        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)

        if range=='previous':
            queryset = queryset.filter(time_slot_start__lte=timezone.now()).order_by('-time_slot_start')
        elif range=='upcoming':
            queryset = queryset.filter(
                status__in=[models.OpdAppointment.CREATED, models.OpdAppointment.RESCHEDULED, models.OpdAppointment.ACCEPTED],
                time_slot_start__gt=timezone.now()).order_by('time_slot_start')
        elif range =='pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status = models.OpdAppointment.CREATED).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request)
        serializer = serializers.OpdAppointmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = data.get("time_slot_start")

        doctor_hospital = models.DoctorHospital.objects.filter(doctor=data.get('doctor'), hospital=data.get('hospital'),
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

        appointment_serializer = serializers.OpdAppointmentSerializer(data=data)
        appointment_serializer.is_valid(raise_exception=True)
        appointment_serializer.save()
        resp = {}
        resp["status"] = 1
        resp["data"] = appointment_serializer.data
        return Response(data=resp)

    def update(self, request, pk=None):
        opd_appointment = get_object_or_404(models.OpdAppointment, pk=pk)
        serializer = serializers.UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        allowed = opd_appointment.allowed_action(request.user.user_type)
        appt_status = validated_data['status']
        if appt_status not in allowed:
            resp = {}
            resp['allowed'] = allowed
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        if request.user.user_type == User.DOCTOR:
            updated_opd_appointment = self.doctor_update(opd_appointment, validated_data)
        elif request.user.user_type == User.CONSUMER:
            updated_opd_appointment = self.consumer_update(opd_appointment, validated_data)

        opd_appointment_serializer = serializers.OpdAppointmentSerializer(updated_opd_appointment)
        response = {
            "status": 1,
            "data": opd_appointment_serializer.data
        }
        return Response(response)

    def doctor_update(self, opd_appointment, validated_data):
        status = validated_data.get('status')
        opd_appointment.status = validated_data.get('status')

        opd_appointment.save()
        return opd_appointment

    def consumer_update(self, opd_appointment, validated_data):
        opd_appointment.status = validated_data.get('status')
        if validated_data.get('status') == models.OpdAppointment.RESCHEDULED_PATIENT:
            opd_appointment.time_slot_start = validated_data.get("time_slot_start")
            opd_appointment.time_slot_end = validated_data.get("time_slot_end")
        opd_appointment.save()
        return opd_appointment


class DoctorProfileView(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):
        doctor = get_object_or_404(models.Doctor, pk=request.user.doctor.id)
        serializer = serializers.DoctorProfileSerializer(doctor, many=False)

        now = datetime.datetime.now()
        appointment_count = models.OpdAppointment.objects.filter(Q(doctor=request.user.doctor.id),
                                                                 ~Q(status=models.OpdAppointment.REJECTED)
                                                                 & ~Q(status=models.OpdAppointment.CANCELED),
                                                                 Q(time_slot_start__gte=now)).count()
        hospital_queryset = doctor.hospitals.distinct()
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True)

        temp_data = serializer.data
        temp_data["count"] = appointment_count
        temp_data['hospitals'] = hospital_serializer.data
        return Response(temp_data)


class DoctorProfileUserViewSet(viewsets.GenericViewSet):

    def prepare_response(self, response_data):
        hospitals = sorted(response_data.get('hospitals'), key=itemgetter("hospital_id"))
        availability = []
        for key, group in groupby(hospitals, lambda x: x['hospital_id']):
            hospital_groups = list(group)
            hospital = hospital_groups[0]
            timings = convert_timings(hospital_groups)
            hospital.update({
                "timings": timings
            })
            hospital.pop("start", None)
            hospital.pop("end", None)
            hospital.pop("day",  None)
            availability.append(hospital)
        response_data['hospitals'] = availability
        return response_data

    def retrieve(self, request, pk):
        doctor = (models.Doctor.objects
                  .prefetch_related('languages__language',
                                    'availability__hospital',
                                    'qualifications__qualification',
                                    'qualifications__specialization',
                                    )
                  .filter(pk=pk).first())
        if not doctor:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False)
        response_data = self.prepare_response(serializer.data)
        return Response(response_data)


class DoctorHospitalView(mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    permission_classes = (IsAuthenticated,)

    queryset = models.DoctorHospital.objects.all()
    serializer_class = serializers.DoctorHospitalSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.DoctorHospital.objects.filter(doctor=user.doctor)

    def list(self, request):
        user = request.user
        queryset = self.get_queryset().values('hospital').annotate(min_fees=Min('fees'))

        serializer = serializers.DoctorHospitalListSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk):
        user = request.user

        queryset = self.get_queryset().filter(hospital=pk)
        if len(queryset) == 0:
            raise Http404("No Hospital matches the given query.")

        schedule_serializer = serializers.DoctorHospitalScheduleSerializer(queryset, many=True)
        hospital_queryset = queryset.first().hospital
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset)

        temp_data = dict()
        temp_data['hospital'] = hospital_serializer.data
        temp_data['schedule'] = schedule_serializer.data

        return Response(temp_data)


class DoctorBlockCalendarViewSet(OndocViewSet):

    serializer_class = serializers.DoctorLeaveSerializer
    permission_classes = (IsAuthenticated, DoctorPermission,)
    INTERVAL_MAPPING = {models.DoctorLeave.INTERVAL_MAPPING.get(key): key for key in
                        models.DoctorLeave.INTERVAL_MAPPING.keys()}

    def get_queryset(self):
        user = self.request.user
        return models.DoctorLeave.objects.filter(doctor=user.doctor.id, deleted_at__isnull=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = serializers.DoctorLeaveSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = serializers.DoctorBlockCalenderSerialzer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor_leave_data = {
            "doctor": request.user.doctor.id,
            "start_time": self.INTERVAL_MAPPING[validated_data.get("interval")][0],
            "end_time": self.INTERVAL_MAPPING[validated_data.get("interval")][1],
            "start_date": validated_data.get("start_date"),
            "end_date": validated_data.get("end_date")
        }
        doctor_leave_serializer = serializers.DoctorLeaveSerializer(data=doctor_leave_data)
        doctor_leave_serializer.is_valid(raise_exception=True)
        self.get_queryset().update(deleted_at=timezone.now())
        doctor_leave_serializer.save()
        return Response(doctor_leave_serializer.data)

    def destroy(self, request, pk=None):
        current_time = timezone.now()
        doctor_leave = models.DoctorLeave.objects.get(pk=pk)
        doctor_leave.deleted_at = current_time
        doctor_leave.save()
        return Response({
            "status": 1
        })


class PrescriptionFileViewset(OndocViewSet):
    serializer_class = serializers.PrescriptionFileSerializer

    permission_classes = (IsAuthenticated, DoctorPermission,)

    def get_queryset(self):
        request = self.request
        return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = serializers.PrescriptionFileSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = serializers.PrescriptionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if models.Prescription.objects.filter(appointment=validated_data.get('appointment')).exists():
            prescription = models.Prescription.objects.filter(appointment=validated_data.get('appointment')).first()
        else:
            prescription = models.Prescription.objects.create(appointment=validated_data.get('appointment'),
                                                              prescription_details=validated_data.get(
                                                                  'prescription_details'))
        prescription_file_data = {
            "prescription": prescription.id,
            "file": validated_data.get('file')
        }
        prescription_file_serializer = serializers.PrescriptionFileSerializer(data=prescription_file_data)
        prescription_file_serializer.is_valid(raise_exception=True)
        prescription_file_serializer.save()
        return Response(prescription_file_serializer.data)


class SearchedItemsViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)

    def list(self, request, *args, **kwargs):
        medical_conditions = models.MedicalCondition.objects.all().values("id", "name")
        specializations = models.Specialization.objects.all().values("id", "name")
        return Response({"conditions": medical_conditions, "specializations": specializations})


class DoctorListViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)
    queryset = models.Doctor.objects.all()

    def prepare_response(self, response_data):
        """Helper function to prepare response expected by client"""

        for data in response_data:
            timings = []
            hospitals = sorted(data.get('hospitals'), key=itemgetter("fees"))
            for ndx, value in enumerate(hospitals):
                if ndx == 0:
                    timings.append({
                        'start': value.get("start"),
                        "end": value.get("end"),
                        "day": value.get("day"),
                        "hospital_id": value.get("hospital_id")
                    })
                else:
                    if timings[len(timings) - 1].get("hospital_id") == value.get("hospital_id"):
                        timings.append({
                            'start': value.get("start"),
                            "end": value.get("end"),
                            "day": value.get("day"),
                            "hospital_id": value.get("hospital_id")
                        })
            hospital = hospitals[0] if len(hospitals) > 0 else {}
            hospital.update({
                "timings": convert_timings(timings)
            })
            hospital.pop("start", None)
            hospital.pop("end", None)
            hospital.pop("day", None)
            data['hospitals'] = [hospital, ]
        return response_data

    def get_filtering_params(self, data):
        """Helper function that prepare dynamic query for filtering"""
        HOSPITAL_TYPE_MAPPING = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}
        filtering_params = {}
        if data.get("specialization_ids"):
            filtering_params.update({
                "qualifications__specialization__id__in": data.get("specialization_ids")
            })
        if data.get("sits_at"):
            filtering_params.update({
                "availability__hospital__hospital_type__in": [HOSPITAL_TYPE_MAPPING.get(sits_at) for sits_at in
                                                              data.get("sits_at")]
            })
        if data.get("min_fees"):
            filtering_params.update({
                "availability__fees__gte": data.get("min_fees")
            })
        if data.get("max_fees"):
            filtering_params.update({
                "availability__fees__lte": data.get("max_fees")
            })
        if data.get("is_female"):
            filtering_params.update({
                "gender": "f"
            })
        if data.get("is_available"):
            current_time = timezone.now()
            filtering_params.update({
                "availability__day": current_time.day,
                "availability__end__gte": current_time.hour
            })
        return filtering_params

    def list(self, request, *args, **kwargs):
        MAX_DISTANCE = 10000
        serializer = serializers.DoctorListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        point = Point(validated_data.get("longitude"),
                      validated_data.get("latitude"), srid=4326)
        filtering_params = self.get_filtering_params(validated_data)
        order_by_field = 'distance'
        if validated_data.get('sort_on'):
            if validated_data.get('sort_on') == 'experience':
                order_by_field = '-practicing_since'
            if validated_data.get('sort_on') == 'fees':
                order_by_field = "min_fees"

        queryset = (models.Doctor
                    .objects.prefetch_related("qualifications", "qualifications__specialization",
                                              "qualifications__qualification", "availability__doctor",
                                              "availability__hospital", "experiences__doctor")
                    .filter(availability__hospital__location__distance_lte=(point, MAX_DISTANCE))
                    .filter(**filtering_params)
                    .annotate(distance=Min(Distance('availability__hospital__location', point)),
                              min_fees=Min('availability__fees'))
                    .order_by(order_by_field)
                    )
        queryset = paginate_queryset(queryset, request)
        search_result_serializer = serializers.DoctorProfileUserViewSerializer(queryset, many=True)
        response_data = self.prepare_response(search_result_serializer.data)
        return Response(response_data)


class DoctorAvailabilityTimingViewSet(viewsets.ViewSet):

    def list(self, request, *args, **kwargs):
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        queryset = models.DoctorHospital.objects.filter(doctor=validated_data.get('doctor_id'),
                                                        hospital=validated_data.get('hospital_id'))
        doctor_queryset = (models.Doctor
                           .objects.prefetch_related("qualifications__qualification",
                                                     "qualifications__specialization")
                           .filter(pk=validated_data.get('doctor_id').id))
        doctor_serializer = serializers.DoctorTimeSlotSerializer(doctor_queryset, many=True)
        timeslots = dict()
        for i in range(0, 7):
            timeslots[i] = dict()
        timeslot_serializer = TimeSlotSerializer(queryset, context={'timing': timeslots}, many=True)
        data = timeslot_serializer.data
        for i in range(7):
            if timeslots[i].get('timing'):
                temp_list = list()
                temp_list = [[k, v] for k, v in timeslots[i]['timing'][0].items()]
                timeslots[i]['timing'][0] = temp_list
                temp_list = [[k, v] for k, v in timeslots[i]['timing'][1].items()]
                timeslots[i]['timing'][1] = temp_list
                temp_list = [[k, v] for k, v in timeslots[i]['timing'][2].items()]
                timeslots[i]['timing'][2] = temp_list
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data})