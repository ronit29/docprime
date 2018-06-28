from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from . import serializers
from ondoc.api.v1.diagnostic.views import TimeSlotExtraction
from ondoc.api.pagination import paginate_queryset, paginate_raw_query
from ondoc.api.v1.utils import convert_timings
from ondoc.api.v1.doctor.doctorsearch import DoctorSearchHelper
from django.db.models import Min
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
from django.db.models import Case, When
import datetime
from operator import itemgetter
from itertools import groupby
from ondoc.api.v1.utils import RawSql
from django.contrib.auth import get_user_model
from django.db.models import F
from collections import defaultdict

import json
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

    def get_queryset(self):

        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.OpdAppointment.objects.filter(doctor=user.doctor)
        elif user.user_type == User.CONSUMER:
            return models.OpdAppointment.objects.filter(user=user)
    # queryset = auth_models.UserPermission.objects.all()

    def list(self, request):

        user_permission = (auth_models.UserPermission.objects.
                           filter(user=request.user, doctor__appointments__hospital=F('hospital'),
                                  doctor__appointments__doctor=F('doctor')).
                           prefetch_related('doctor__appointments', 'doctor', 'hospital', 'user').
                           values('permission_type', 'read_permission', 'write_permission', 'delete_permission',
                                  'doctor__appointments__id'))

        ids, id_dict = self.extract_appointment_ids(user_permission)

        queryset = models.OpdAppointment.objects.filter(id__in=ids)

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
            queryset = queryset.filter(status__in = [models.OpdAppointment.COMPLETED,models.OpdAppointment.CANCELED]).order_by('-time_slot_start')
        elif range=='upcoming':
            today = datetime.date.today()
            queryset = queryset.filter(
                status__in=[models.OpdAppointment.BOOKED, models.OpdAppointment.RESCHEDULED_PATIENT,
                            models.OpdAppointment.RESCHEDULED_DOCTOR, models.OpdAppointment.ACCEPTED],
                time_slot_start__date__gte=today).order_by('time_slot_start')
        elif range =='pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status__in = [models.OpdAppointment.BOOKED,
                                                                                         models.OpdAppointment.RESCHEDULED_PATIENT
                                                                                         ]).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request)
        whole_queryset = self.extract_whole_queryset(queryset, id_dict)
        serializer = serializers.OpdAppointmentSerializer(queryset, many=True, context={'request':request})
        # serializer = serializers.OpdAppointmentPermissionSerializer(whole_queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        queryset = models.OpdAppointment.objects.filter(pk=pk).filter(doctor=user.doctor)
        if queryset:
            serializer = serializers.AppointmentRetrieveSerializer(queryset, many=True, context={'request':request})
            return Response(serializer.data)
        else:
            return Response([])


    def payment_retry(self, request, pk=None):
        queryset = models.OpdAppointment.objects.filter(pk=pk)
        payment_response = dict()
        if queryset:
            serializer_data = serializers.OpdAppointmentSerializer(queryset.first(), context={'request':request})
            payment_response = self.payment_details(request, serializer_data.data, 1)
        return Response(payment_response)


    def complete(self, request):
        serializer = serializers.OTPFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        opd_appointment = get_object_or_404(models.OpdAppointment, pk=validated_data.get('id'))
        permission_queryset = (auth_models.UserPermission.objects.filter(doctor=opd_appointment.doctor.id).
                               filter(hospital=opd_appointment.hospital_id))
        if permission_queryset:
            perm_data = permission_queryset.first()
            if request.user.user_type == User.DOCTOR and perm_data.write_permission:
                otp_valid_serializer = serializers.OTPConfirmationSerializer(data=request.data)
                otp_valid_serializer.is_valid(raise_exception=True)
                opd_appointment.status = models.OpdAppointment.COMPLETED
                opd_appointment.save()
        opd_appointment_serializer = serializers.OpdAppointmentSerializer(opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)


    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = serializers.CreateAppointmentSerializer.form_time_slot(data.get("start_date"),
                                                                                 data.get("start_time"))
        # time_slot_start = data.get("time_slot_start")

        doctor_hospital = models.DoctorHospital.objects.filter(doctor=data.get('doctor'), hospital=data.get('hospital'),
            day=time_slot_start.weekday(),start__lte=time_slot_start.hour, end__gte=time_slot_start.hour).first()
        fees = doctor_hospital.fees

        profile_detail = dict()
        # profile_model = auth_models.UserProfile.objects.get()
        profile_model = data.get("profile")
        profile_detail["name"] = profile_model.name
        profile_detail["gender"] = profile_model.gender
        profile_detail["dob"] = str(profile_model.dob)
        # profile_detail["profile_image"] = profile_model.profile_image

        data = {
            "doctor": data.get("doctor").id,
            "hospital": data.get("hospital").id,
            "profile": data.get("profile").id,
            "profile_detail": json.dumps(profile_detail),
            "user": request.user.id,
            "booked_by": request.user.id,
            "fees": fees,
            "time_slot_start": time_slot_start,
            #"time_slot_end": time_slot_end,
        }

        appointment_serializer = serializers.OpdAppointmentSerializer(data=data, context={'request':request})
        appointment_serializer.is_valid(raise_exception=True)
        appointment_serializer.save()
        resp = {}
        resp["status"] = 1
        resp["data"] = appointment_serializer.data
        resp["payment_details"] = self.payment_details(request, appointment_serializer.data, 1)
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

        opd_appointment_serializer = serializers.OpdAppointmentSerializer(updated_opd_appointment, context={'request':request})
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

    def extract_appointment_ids(self, appointment_data):
        id_dict = defaultdict(dict)
        id_list = list()
        for data in appointment_data:
            temp = dict()
            temp["appointment"] = data['doctor__appointments__id']
            temp["permission_type"] = data['permission_type']
            temp["read_permission"] = data['read_permission']
            temp["write_permission"] = data['write_permission']
            temp["delete_permission"] = data['delete_permission']
            # temp["permission"] = data['permission']
            id_dict[data['doctor__appointments__id']] = temp
            id_list.append(data['doctor__appointments__id'])
        return id_list, id_dict

    def extract_whole_queryset(self, queryset, id_dict):
        whole_queryset = list()
        for data in queryset:
            temp = id_dict[data.id]
            temp['appointment'] = data
            whole_queryset.append(temp)
        return whole_queryset

    def payment_details(self, request, appointment_details, product_id):
        details = dict()
        pgdata = dict()
        user = request.user
        user_profile = user.profiles.filter(is_default_user=True).first()
        pgdata['custId'] = user.id
        pgdata['mobile'] = user.phone_number
        pgdata['email'] = user.email
        if not user.email:
            pgdata['email'] = "dummy_appointment@policybazaar.com"

        pgdata['productId'] = product_id
        base_url = (
            "https://{}".format(request.get_host()) if request.is_secure() else "http://{}".format(request.get_host()))
        pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['checkSum'] = ''
        pgdata['appointmentId'] = appointment_details['id']
        if user_profile:
            pgdata['name'] = user_profile.name
        else:
            pgdata['name'] = "DummyName"
        pgdata['txAmount'] = appointment_details['fees']

        if pgdata:
            details['required'] = True
            details['pgdata'] = pgdata
        else:
            details['required'] = False

        return details


class DoctorProfileView(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):
        doctor = get_object_or_404(models.Doctor, pk=request.user.doctor.id)
        serializer = serializers.DoctorProfileSerializer(doctor, many=False,
                                                         context={"request": request})

        now = datetime.datetime.now()
        today = datetime.date.today()
        appointment_count = models.OpdAppointment.objects.filter(Q(doctor=request.user.doctor.id),
                                                                 ~Q(status=models.OpdAppointment.CANCELED),
                                                                 ~Q(status=models.OpdAppointment.COMPLETED),
                                                                 ~Q(status=models.OpdAppointment.CREATED),
                                                                 Q(time_slot_start__date=today)).count()
        hospital_queryset = doctor.hospitals.distinct()
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True)
        clinic_queryset = doctor.availability.order_by('hospital_id', 'fees').distinct('hospital_id')
        clininc_serializer = serializers.DoctorHospitalSerializer(clinic_queryset, many=True)

        temp_data = serializer.data
        temp_data["count"] = appointment_count
        temp_data['hospitals'] = hospital_serializer.data
        temp_data['clinic'] = clininc_serializer.data
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
        serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False,
                                                                 context={"request": request})
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

    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        request = self.request
        if request.user.user_type == User.DOCTOR:
            return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)
        elif request.user.user_type == User.CONSUMER:
            return models.PrescriptionFile.objects.filter(prescription__appointment__user=request.user)
        else:
            return models.PrescriptionFile.objects.none()

    def list(self, request, *args, **kwargs):
        appointment = request.query_params.get("appointment")
        if not appointment:
            return Response(status=400)
        queryset = self.get_queryset().filter(prescription__appointment=appointment)
        serializer = serializers.PrescriptionFileSerializer(queryset, many=True, context={"request": request})
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
        prescription_file_serializer = serializers.PrescriptionFileSerializer(data=prescription_file_data,
                                                                              context={"request": request})
        prescription_file_serializer.is_valid(raise_exception=True)
        prescription_file_serializer.save()
        return Response(prescription_file_serializer.data)

    def remove(self, request):
        serializer_data = serializers.PrescriptionFileDeleteSerializer(data=request.data, context={'request': request})
        serializer_data.is_valid(raise_exception=True)
        validated_data = serializer_data.validated_data
        response = {
            "status": 0,
            "id": validated_data['id']
        }
        if validated_data.get('id'):
            get_object_or_404(models.PrescriptionFile, pk=validated_data['id'])
            delete_queryset = self.get_queryset().filter(pk=validated_data['id'])
            delete_queryset.delete()
            response['status'] = 1
            return Response(response)
        else:
            return Response(response)


class SearchedItemsViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)

    def list(self, request, *args, **kwargs):
        name = request.query_params.get("name")
        if not name:
            return Response({"conditions": [], "specializations": []})
        medical_conditions = models.MedicalCondition.objects.filter(
            name__icontains=name).values("id", "name")[:5]
        specializations = models.Specialization.objects.filter(
            name__icontains=name).values("id", "name")[:5]
        return Response({"conditions": medical_conditions, "specializations": specializations})


class DoctorListViewSet(viewsets.GenericViewSet):
    queryset = models.Doctor.objects.all()

    def list(self, request, *args, **kwargs):
        serializer = serializers.DoctorListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            doctor_search_result = RawSql(query_string).fetch_all()
            result_count = len(doctor_search_result)
            saved_search_result = models.DoctorSearchResult.objects.create(results=doctor_search_result,
                                                                           result_count=result_count)
        else:
            saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))
        doctor_ids = paginate_queryset([data.get("doctor_id") for data in saved_search_result.results], request)
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(doctor_ids)])
        doctor_data = models.Doctor.objects.filter(
            id__in=doctor_ids).prefetch_related("hospitals", "availability", "availability__hospital",
                                                "experiences", "images", "qualifications",
                                                "qualifications__qualification", "qualifications__specialization",
                                                "qualifications__college").order_by(preserved)
        response = doctor_search_helper.prepare_search_response(doctor_data, saved_search_result.results, request)
        return Response({"result": response, "count": saved_search_result.result_count,
                         "search_id": saved_search_result.id})


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
        obj = TimeSlotExtraction()

        for data in queryset:
            obj.form_time_slots(data.day, data.start, data.end, data.fees, True)

        # resp_dict = obj.get_timing()
        timeslots = obj.get_timing_list()




        # for i in range(0, 7):
        #     timeslots[i] = dict()
        # timeslot_serializer = TimeSlotSerializer(queryset, context={'timing': timeslots}, many=True)
        # data = timeslot_serializer.data
        # for i in range(7):
        #     if timeslots[i].get('timing'):
        #         temp_list = list()
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][0].items()]
        #         timeslots[i]['timing'][0] = temp_list
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][1].items()]
        #         timeslots[i]['timing'][1] = temp_list
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][2].items()]
        #         timeslots[i]['timing'][2] = temp_list
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data})