from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from ondoc.account import models as account_models
from . import serializers
from ondoc.api.v1.diagnostic.views import TimeSlotExtraction
from ondoc.api.pagination import paginate_queryset, paginate_raw_query
from ondoc.api.v1.utils import convert_timings, form_time_slot
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.doctor.doctorsearch import DoctorSearchHelper
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
from django.db.models import Case, When
import datetime
from operator import itemgetter
from itertools import groupby
from django.contrib.gis.db.models.functions import Distance
from ondoc.api.v1.utils import RawSql
from django.contrib.auth import get_user_model
from django.db.models import F
from collections import defaultdict
import datetime
import random
import copy

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
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OpdAppointmentSerializer

    def get_queryset(self):

        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.OpdAppointment.objects.filter(doctor=user.doctor)
        elif user.user_type == User.CONSUMER:
            return models.OpdAppointment.objects.filter(user=user)

    def list(self, request):
        user = request.user
        # x = (models.OpdAppointment.objects.filter(doctor__generic_admin__user=user, hospital__generic_admin__user=user))

        queryset = models.OpdAppointment.objects.filter(Q(doctor__manageable_doctors__user=user,
                                                        doctor__manageable_doctors__hospital=F('hospital'),
                                                        doctor__manageable_doctors__is_disabled=False) |
                                                        Q(hospital__manageable_hospitals__doctor__isnull=True,
                                                          hospital__manageable_hospitals__user=user,
                                                          hospital__manageable_hospitals__is_disabled=False)
                                                        ).distinct()


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

        if range == 'previous':
            queryset = queryset.filter(status__in=[models.OpdAppointment.COMPLETED,models.OpdAppointment.CANCELED]).order_by('-time_slot_start')
        elif range == 'upcoming':
            today = datetime.date.today()
            queryset = queryset.filter(
                status__in=[models.OpdAppointment.BOOKED, models.OpdAppointment.RESCHEDULED_PATIENT,
                            models.OpdAppointment.RESCHEDULED_DOCTOR, models.OpdAppointment.ACCEPTED],
                time_slot_start__date__gte=today).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status__in = [models.OpdAppointment.BOOKED,
                                                                                         models.OpdAppointment.RESCHEDULED_PATIENT
                                                                                         ]).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request)
        # whole_queryset = self.extract_whole_queryset(queryset, id_dict)
        serializer = serializers.OpdAppointmentSerializer(queryset, many=True, context={'request': request})
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
            payment_response = self.extract_payment_details(request, serializer_data.data, 1)
        return Response(payment_response)

    @transaction.atomic
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
                opd_appointment.action_completed()
        opd_appointment_serializer = serializers.OpdAppointmentSerializer(opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)


    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))
        doctor_hospital = models.DoctorHospital.objects.filter(
            doctor=data.get('doctor'), hospital=data.get('hospital'),
            day=time_slot_start.weekday(), start__lte=time_slot_start.hour,
            end__gte=time_slot_start.hour).first()
        profile_model = data.get("profile")
        profile_detail = {
            "name": profile_model.name,
            "gender": profile_model.gender,
            "dob": str(profile_model.dob)
        }
        req_data = request.data
        if data.get("payment_type") == models.OpdAppointment.INSURANCE:
            effective_price = doctor_hospital.fees
        elif data.get("payment_type") == models.OpdAppointment.COD:
            effective_price = doctor_hospital.deal_price
        else:
            # TODO PM - Logic for coupon
            effective_price = doctor_hospital.deal_price

        opd_data = {
            "doctor": data.get("doctor"),
            "hospital": data.get("hospital"),
            "profile": data.get("profile"),
            "profile_detail": profile_detail,
            "user": request.user,
            "booked_by": request.user,
            "fees": doctor_hospital.fees,
            "deal_price": doctor_hospital.deal_price,
            "effective_price": effective_price,
            "mrp": doctor_hospital.mrp,
            "time_slot_start": time_slot_start,
            "payment_type": data.get("payment_type")
        }
        resp = self.extract_payment_details(request, opd_data, 1)
        return Response(data=resp)

    def update(self, request, pk=None):
        opd_appointment = get_object_or_404(models.OpdAppointment, pk=pk)
        serializer = serializers.UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        allowed = opd_appointment.allowed_action(request.user.user_type, request)
        appt_status = validated_data['status']
        if appt_status not in allowed:
            resp = {}
            resp['allowed'] = allowed
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        if request.user.user_type == User.DOCTOR:
            req_status = validated_data.get('status')
            if req_status == models.OpdAppointment.RESCHEDULED_DOCTOR:
                updated_opd_appointment = opd_appointment.action_rescheduled_doctor()
            elif req_status == models.OpdAppointment.ACCEPTED:
                updated_opd_appointment = opd_appointment.action_accepted()

        opd_appointment_serializer = serializers.OpdAppointmentSerializer(updated_opd_appointment, context={'request':request})
        response = {
            "status": 1,
            "data": opd_appointment_serializer.data
        }
        return Response(response)

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

    @transaction.atomic
    def extract_payment_details(self, request, appointment_details, product_id):
        remaining_amount = 0
        user = request.user
        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance
        resp = {}

        can_use_insurance, insurance_fail_message = self.can_use_insurance(appointment_details)
        if can_use_insurance:
            appointment_details['effective_price'] = appointment_details['fees']
            appointment_details['payment_type'] = models.OpdAppointment.INSURANCE
        elif appointment_details['payment_type'] == models.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp

        if appointment_details['payment_type'] == models.OpdAppointment.PREPAID and \
            balance < appointment_details.get("effective_price"):

            temp_app_details = copy.deepcopy(appointment_details)
            self.json_transform(temp_app_details)

            account_models.Order.disable_pending_orders(temp_app_details, product_id,
                                                        account_models.Order.OPD_APPOINTMENT_CREATE)

            payable_amount = appointment_details.get("effective_price") - balance

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.OPD_APPOINTMENT_CREATE,
                action_data=temp_app_details,
                amount=payable_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            appointment_details["payable_amount"] = payable_amount
            resp["status"] = 1
            resp['data'], resp["payment_required"] = self.payment_details(request, appointment_details, product_id, order.id)

        else:
            opd_obj = models.OpdAppointment.create_appointment(appointment_details)

            if appointment_details["payment_type"] == models.OpdAppointment.PREPAID:
                user_account_data = {
                    "user": user,
                    "product_id": product_id,
                    "reference_id": opd_obj.id
                }
                consumer_account.debit_schedule(user_account_data, appointment_details.get("effective_price"))
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {"id": opd_obj.id, "type": serializers.OpdAppointmentSerializer.DOCTOR_TYPE}
        return resp

    def json_transform(self, app_data):
        app_data["deal_price"] = str(app_data["deal_price"])
        app_data["fees"] = str(app_data["fees"])
        app_data["effective_price"] = str(app_data["effective_price"])
        app_data["mrp"] = str(app_data["mrp"])
        app_data["time_slot_start"] = str(app_data["time_slot_start"])
        app_data["doctor"] = app_data["doctor"].id
        app_data["hospital"] = app_data["hospital"].id
        app_data["profile"] = app_data["profile"].id
        app_data["user"] = app_data["user"].id
        app_data["booked_by"] = app_data["booked_by"].id

    def payment_details(self, request, appointment_details, product_id, order_id):
        pgdata = dict()
        payment_required = True

        user = request.user
        # user_profile = user.profiles.get(pk=appointment_details['profile'].id)
        pgdata['custId'] = user.id
        pgdata['mobile'] = user.phone_number
        pgdata['email'] = user.email
        if not user.email:
            pgdata['email'] = "dummyemail@docprime.com"

        pgdata['productId'] = product_id
        base_url = (
            "https://{}".format(request.get_host()) if request.is_secure() else "http://{}".format(request.get_host()))
        pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['checkSum'] = ''
        pgdata['referenceId'] = ""
        pgdata['orderId'] = order_id
        pgdata['name'] = appointment_details['profile'].name
        pgdata['txAmount'] = appointment_details['payable_amount']

        return pgdata, payment_required

    def can_use_insurance(self, appointment_details):
        # Check if appointment can be covered under insurance
        # also return a valid message         
        return False, 'Not covered under insurance'

    def is_insured_cod(self, app_details):
        return False
        if insurance_utility.lab_is_insured(app_details):
            app_details["payment_type"] = doctor_model.OpdAppointment.INSURANCE
            app_details["effective_price"] = 0
            return True
        elif app_details["payment_type"] == doctor_model.OpdAppointment.COD:
            app_details["effective_price"] = 0
            return True
        else:
            return False


class DoctorProfileView(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):
        doctor = get_object_or_404(models.Doctor, pk=request.user.doctor.id)
        serializer = serializers.DoctorProfileSerializer(doctor, many=False,
                                                         context={"request": request})

        now = datetime.datetime.now()
        appointment_count = models.OpdAppointment.objects.filter(Q(doctor=request.user.doctor.id),
                                                                 ~Q(status=models.OpdAppointment.CANCELED),
                                                                 Q(time_slot_start__gte=now)).count()
        hospital_queryset = doctor.hospitals.distinct()
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True)
        clinic_queryset = doctor.availability.order_by('hospital_id', 'fees').distinct('hospital_id')
        clinic_serializer = serializers.DoctorHospitalSerializer(clinic_queryset, many=True,
                                                                 context={"request": request})

        temp_data = serializer.data
        temp_data["count"] = appointment_count
        temp_data['hospitals'] = hospital_serializer.data
        temp_data['clinic'] = clinic_serializer.data
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

        serializer = serializers.DoctorHospitalListSerializer(queryset, many=True,
                                                              context={"request": request})
        return Response(serializer.data)

    def retrieve(self, request, pk):
        user = request.user

        queryset = self.get_queryset().filter(hospital=pk)
        if len(queryset) == 0:
            raise Http404("No Hospital matches the given query.")

        schedule_serializer = serializers.DoctorHospitalScheduleSerializer(queryset, many=True)
        hospital_queryset = queryset.first().hospital
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset,
                                                                  context={"request": request})

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
        # self.get_queryset().update(deleted_at=timezone.now())        Now user can apply more than one leave
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

    def common_conditions(self, request):
        medical_conditions = models.MedicalCondition.objects.values("id", "name")[:10]
        specializations = models.Specialization.objects.values("id", "name")[:10]
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
        doctor_leave_serializer = serializers.DoctorLeaveSerializer(
            models.DoctorLeave.objects.filter(doctor=validated_data.get("doctor_id"), deleted_at__isnull=True), many=True)

        timeslots = dict()
        obj = TimeSlotExtraction()

        for data in queryset:
            obj.form_time_slots(data.day, data.start, data.end, data.fees, True,
                                data.deal_price, data.mrp, True)

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
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data,
                         "doctor_leaves": doctor_leave_serializer.data})