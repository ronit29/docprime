from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from ondoc.diagnostic import models as lab_models
from ondoc.doctor.models import Hospital, Doctor
from ondoc.notification.models import EmailNotification
from django.utils.safestring import mark_safe
from ondoc.coupon.models import Coupon
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.account import models as account_models
from ondoc.location.models import EntityUrls, EntityAddress
from . import serializers
from ondoc.api.pagination import paginate_queryset, paginate_raw_query
from ondoc.api.v1.utils import convert_timings, form_time_slot, IsDoctor, payment_details, aware_time_zone, TimeSlotExtraction, GenericAdminEntity
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
from rest_framework.authentication import TokenAuthentication
from ondoc.authentication.backends import JWTAuthentication
from django.utils import timezone
from django.db import transaction
from django.http import Http404
from django.db.models import Q, Value
from django.db.models import Case, When
from operator import itemgetter
from itertools import groupby
from ondoc.api.v1.utils import RawSql, is_valid_testing_data, doctor_query_parameters
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import F
from django.db.models.functions import StrIndex
import datetime
import copy
import re
import hashlib
from ondoc.api.v1.utils import opdappointment_transform
from ondoc.location import models as location_models
from ondoc.ratings_review import models as rating_models
from ondoc.api.v1.diagnostic import serializers as lab_serializers
from ondoc.notification import models as notif_models
User = get_user_model()
from rest_framework.throttling import UserRateThrottle
from rest_framework.throttling import AnonRateThrottle
from ondoc.matrix.tasks import push_order_to_matrix
from dal import autocomplete


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
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OpdAppointmentSerializer

    def get_queryset(self):

        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.OpdAppointment.objects.filter(doctor=user.doctor, doctor__is_live=True, hospital__is_live=True)
        elif user.user_type == User.CONSUMER:
            return models.OpdAppointment.objects.filter(user=user, doctor__is_live=True, hospital__is_live=True)

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user
        queryset = models.OpdAppointment.objects.filter(hospital__is_live=True, doctor__is_live=True).filter(
            Q(doctor__manageable_doctors__user=user,
              doctor__manageable_doctors__hospital=F('hospital'),
              doctor__manageable_doctors__is_disabled=False,
              doctor__manageable_doctors__permission_type__in=[auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL]) |
            Q(hospital__manageable_hospitals__doctor__isnull=True,
              hospital__manageable_hospitals__user=user,
              hospital__manageable_hospitals__is_disabled=False,
              hospital__manageable_hospitals__permission_type__in=[auth_models.GenericAdmin.APPOINTMENT,
                                                               auth_models.GenericAdmin.ALL])
            ).distinct()
        if not queryset:
            return Response([])
        serializer = serializers.AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital = serializer.validated_data.get('hospital_id')
        profile = serializer.validated_data.get('profile_id')
        doctor = serializer.validated_data.get('doctor_id')
        date = serializer.validated_data.get('date')

        if profile:
            queryset = queryset.filter(profile=profile)

        if hospital:
            queryset = queryset.filter(hospital=hospital)

        if doctor:
            queryset = queryset.filter(doctor=doctor)

        if range == 'previous':
            queryset = queryset.filter(status__in=[models.OpdAppointment.COMPLETED, models.OpdAppointment.CANCELLED]).order_by('-time_slot_start')
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

        if date:
            queryset = queryset.filter(time_slot_start__date=date)

        queryset = paginate_queryset(queryset, request)
        serializer = serializers.DoctorAppointmentRetrieveSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk=None):
        user = request.user
        queryset = models.OpdAppointment.objects.filter(hospital__is_live=True, doctor__is_live=True).filter(
            Q(doctor__manageable_doctors__user=user,
              doctor__manageable_doctors__hospital=F('hospital'),
              doctor__manageable_doctors__is_disabled=False) |
            Q(hospital__manageable_hospitals__doctor__isnull=True,
              hospital__manageable_hospitals__user=user,
              hospital__manageable_hospitals__is_disabled=False),
            Q(pk=pk)).distinct()
        if queryset:
            serializer = serializers.DoctorAppointmentRetrieveSerializer(queryset, many=True, context={'request':request})
            return Response(serializer.data)
        else:
            return Response([])

    @transaction.atomic
    def complete(self, request):
        serializer = serializers.OTPFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # opd_appointment = get_object_or_404(models.OpdAppointment, pk=validated_data.get('id'))
        opd_appointment = models.OpdAppointment.objects.select_for_update().filter(pk=validated_data.get('id')).first()
        if not opd_appointment:
            return Response({"message": "Invalid appointment id"}, status.HTTP_404_NOT_FOUND)

        permission_queryset = (auth_models.GenericAdmin.objects.filter(doctor=opd_appointment.doctor.id).
                               filter(hospital=opd_appointment.hospital_id))
        if permission_queryset:
            perm_data = permission_queryset.first()
            if request.user.user_type == User.DOCTOR and perm_data.write_permission:
                otp_valid_serializer = serializers.OTPConfirmationSerializer(data=request.data)
                otp_valid_serializer.is_valid(raise_exception=True)
                opd_appointment.action_completed()
        opd_appointment_serializer = serializers.DoctorAppointmentRetrieveSerializer(opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)

    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))
        doctor_clinic_timing = models.DoctorClinicTiming.objects.filter(
            doctor_clinic__doctor=data.get('doctor'),
            doctor_clinic__hospital=data.get('hospital'),
            doctor_clinic__doctor__is_live=True, doctor_clinic__hospital__is_live=True,
            day=time_slot_start.weekday(), start__lte=data.get("start_time"),
            end__gte=data.get("start_time")).first()
        profile_model = data.get("profile")
        profile_detail = {
            "name": profile_model.name,
            "gender": profile_model.gender,
            "dob": str(profile_model.dob)
        }
        req_data = request.data

        coupon_list = []
        coupon_discount = 0
        if data.get("coupon_code"):
            coupon_list = list(Coupon.objects.filter(code__in=data.get("coupon_code")).values_list('id', flat=True))
            obj = models.OpdAppointment()
            for coupon in data.get("coupon_code"):
                coupon_discount += obj.get_discount(coupon, doctor_clinic_timing.deal_price)

        if data.get("payment_type") == models.OpdAppointment.INSURANCE:
            effective_price = doctor_clinic_timing.deal_price
        elif data.get("payment_type") in [models.OpdAppointment.COD, models.OpdAppointment.PREPAID]:
            if coupon_discount >= doctor_clinic_timing.deal_price:
                effective_price = 0
            else:
                effective_price = doctor_clinic_timing.deal_price - coupon_discount

        opd_data = {
            "doctor": data.get("doctor"),
            "hospital": data.get("hospital"),
            "profile": data.get("profile"),
            "profile_detail": profile_detail,
            "user": request.user,
            "booked_by": request.user,
            "fees": doctor_clinic_timing.fees,
            "deal_price": doctor_clinic_timing.deal_price,
            "effective_price": effective_price,
            "mrp": doctor_clinic_timing.mrp,
            "time_slot_start": time_slot_start,
            "payment_type": data.get("payment_type"),
            "coupon": coupon_list,
            "discount": coupon_discount
        }
        resp = self.extract_payment_details(request, opd_data, account_models.Order.DOCTOR_PRODUCT_ID)
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
                opd_appointment.action_rescheduled_doctor()
            elif req_status == models.OpdAppointment.ACCEPTED:
                opd_appointment.action_accepted()

        opd_appointment_serializer = serializers.DoctorAppointmentRetrieveSerializer(opd_appointment, context={'request':request})
        response = {
            "status": 1,
            "data": opd_appointment_serializer.data
        }
        return Response(response)

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

        temp_app_details = copy.deepcopy(appointment_details)
        temp_app_details = opdappointment_transform(temp_app_details)

        account_models.Order.disable_pending_orders(temp_app_details, product_id,
                                                    account_models.Order.OPD_APPOINTMENT_CREATE)
        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            resp['is_agent'] = True
            balance = 0

        if (appointment_details['payment_type'] == models.OpdAppointment.PREPAID and
             balance < appointment_details.get("effective_price")):

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
            resp['data'], resp["payment_required"] = payment_details(request, order)
            try:
                ops_email_data = dict()
                ops_email_data.update(order.appointment_details())
                ops_email_data["transaction_time"] = aware_time_zone(timezone.now())
                EmailNotification.ops_notification_alert(ops_email_data, settings.OPS_EMAIL_ID,
                                                         order.product_id,
                                                         EmailNotification.OPS_PAYMENT_NOTIFICATION)
                push_order_to_matrix.apply_async(({'order_id': order.id, 'created_at':int(order.created_at.timestamp()),
                                                   'timeslot':int(appointment_details['time_slot_start'].timestamp())}, ), countdown=5)

            except:
                pass
        else:
            opd_obj = models.OpdAppointment.create_appointment(appointment_details)
            if appointment_details["payment_type"] == models.OpdAppointment.PREPAID:
                consumer_account.debit_schedule(opd_obj, product_id, appointment_details.get("effective_price"))
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {"id": opd_obj.id, "type": serializers.OpdAppointmentSerializer.DOCTOR_TYPE}
        return resp

    def payment_details(self, request, appointment_details, product_id, order_id):
        payment_required = True
        user = request.user
        if user.email:
            uemail = user.email
        else:
            uemail = "dummyemail@docprime.com"
        base_url = "https://{}".format(request.get_host())
        surl = base_url + '/api/v1/user/transaction/save'
        furl = base_url + '/api/v1/user/transaction/save'

        pgdata = {
            'custId': user.id,
            'mobile': user.phone_number,
            'email': uemail,
            'productId': product_id,
            'surl': surl,
            'furl': furl,
            'referenceId': "",
            'orderId': order_id,
            'name': appointment_details['profile'].name,
            'txAmount': str(appointment_details['payable_amount']),

        }

        pgdata['hash'] = account_models.PgTransaction.create_pg_hash(pgdata, settings.PG_SECRET_KEY_P1,
                                                                     settings.PG_CLIENT_KEY_P1)
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
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return models.OpdAppointment.objects.all()

    @transaction.non_atomic_requests
    def retrieve(self, request):
        from django.contrib.staticfiles.templatetags.staticfiles import static
        resp_data = dict()
        today = datetime.date.today()
        queryset = models.OpdAppointment.objects.filter(doctor__is_live=True, hospital__is_live=True).filter(
            (Q(doctor__manageable_doctors__user=request.user,
               doctor__manageable_doctors__hospital=F('hospital'),
               doctor__manageable_doctors__is_disabled=False) |
             Q(hospital__manageable_hospitals__doctor__isnull=True,
               hospital__manageable_hospitals__user=request.user,
               hospital__manageable_hospitals__is_disabled=False)),
            Q(status=models.OpdAppointment.ACCEPTED,
              time_slot_start__date=today)
            ).distinct().count()
        lab_appointment_count = lab_models.LabAppointment.objects.filter(
            Q(lab__network__isnull=True, lab__manageable_lab_admins__user=request.user,
              lab__manageable_lab_admins__is_disabled=False) |
            Q(lab__network__isnull=False,
              lab__network__manageable_lab_network_admins__user=request.user,
              lab__network__manageable_lab_network_admins__is_disabled=False),
            Q(status=lab_models.LabAppointment.ACCEPTED,
              time_slot_start__date=today)).distinct().count()
        if hasattr(request.user, 'doctor') and request.user.doctor:
            doctor = request.user.doctor
            doc_serializer = serializers.DoctorProfileSerializer(doctor, many=False,
                                                                 context={"request": request})
            resp_data = doc_serializer.data
            resp_data["is_doc"] = True
        else:
            resp_data["is_doc"] = False
            resp_data["name"] = 'Admin'
            admin_image_url = static('doctor_images/no_image.png')
            admin_image = ''
            if admin_image_url:
                admin_image = request.build_absolute_uri(admin_image_url)
            resp_data["thumbnail"] = admin_image

        # Check access_type START
        user = request.user
        OPD_ONLY = 1
        LAB_ONLY = 2
        OPD_AND_LAB = 3

        generic_admin = auth_models.GenericAdmin.objects.filter(user=user,
                                                is_disabled=False)
        generic_lab_admin = auth_models.GenericLabAdmin.objects.filter(user=user,
                                                                is_disabled=False)

        if generic_admin.exists() and generic_lab_admin.exists():
            resp_data["access_type"] = OPD_AND_LAB
        elif generic_admin.exists():
            resp_data["access_type"] = OPD_ONLY
        elif generic_lab_admin.exists():
            resp_data["access_type"] = LAB_ONLY
        # Check access_type END

        resp_data["count"] = queryset
        resp_data['lab_appointment_count'] = lab_appointment_count

        generic_super_user_admin=generic_admin.filter(super_user_permission=True)
        if generic_super_user_admin.exists():
            resp_data['is_super_user'] = True

        generic_super_user_lab_admin=generic_lab_admin.filter(super_user_permission=True)
        if generic_super_user_lab_admin.exists():
            resp_data['is_super_user_lab'] = True



        return Response(resp_data)


class DoctorProfileUserViewSet(viewsets.GenericViewSet):

    def prepare_response(self, response_data):
        hospitals = sorted(response_data.get('hospitals'), key=itemgetter("hospital_id"))
        availability = []
        for key, group in groupby(hospitals, lambda x: x['hospital_id']):
            hospital_groups = list(group)
            hospital_groups = sorted(hospital_groups, key=itemgetter("discounted_fees"))
            hospital = hospital_groups[0]
            timings = convert_timings(hospital_groups)
            hospital.update({
                "timings": timings
            })
            hospital.pop("start", None)
            hospital.pop("end", None)
            hospital.pop("day",  None)
            hospital.pop("discounted_fees", None)
            availability.append(hospital)
        response_data['hospitals'] = availability
        return response_data

    @transaction.non_atomic_requests
    def retrieve_by_url(self, request):
        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        entity = location_models.EntityUrls.objects.filter(url=url, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).order_by('-is_valid')
        if entity.exists():
            entity = entity.first()
            if not entity.is_valid:
                valid_entity_url_qs = location_models.EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE,
                                                                           entity_id=entity.entity_id, is_valid='t')
                if valid_entity_url_qs.exists():
                    corrected_url = valid_entity_url_qs.first().url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

            entity_id = entity.entity_id
            response = self.retrieve(request, entity_id)
            return response

        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk):
        response_data = []
        doctor = (models.Doctor.objects
                  .prefetch_related('languages__language',
                                    'doctor_clinics__hospital',
                                    'qualifications__qualification',
                                    'qualifications__specialization',
                                    'qualifications__college',
                                    'doctorpracticespecializations__specialization',
                                    'images',
                                    'rating'
                                    )
                  .filter(pk=pk).first())
        # if not doctor or not is_valid_testing_data(request.user, doctor):
        #     return Response(status=status.HTTP_400_BAD_REQUEST)
        if doctor:
            serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False,
                                                                     context={"request": request})

            entity = EntityUrls.objects.filter(entity_id=serializer.data['id'], url_type='PAGEURL', is_valid='t',
                                                entity_type__iexact='Doctor').values('url')
            response_data = self.prepare_response(serializer.data)

            response_data['url'] = entity.first()['url'] if len(entity) == 1 else None
        return Response(response_data)


class DoctorHospitalView(mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )

    queryset = models.DoctorClinic.objects.filter(doctor__is_live=True, hospital__is_live=True)
    serializer_class = serializers.DoctorHospitalSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=user.doctor, doctor_clinic__doctor__is_live=True, doctor_clinic__hospital__is_live=True).select_related(
                "doctor_clinic__doctor", "doctor_clinic__hospital")

    @transaction.non_atomic_requests
    def list(self, request):
        resp_data = list()
        if hasattr(request.user, 'doctor') and request.user.doctor:
            doct_hosp_queryset = self.get_queryset().values(
                'doctor_clinic__hospital').annotate(min_fees=Min('fees')).order_by('doctor_clinic__hospital')
            hospital_list = list()
            for data in doct_hosp_queryset:
                hospital_list.append(data.get('doctor_clinic__hospital'))

            hospital_qs = models.Hospital.objects.filter(id__in=hospital_list).order_by('id')
            i = 0
            for data in doct_hosp_queryset:
                data['hospital'] = hospital_qs[i]
                i += 1

            serializer = serializers.DoctorHospitalListSerializer(doct_hosp_queryset, many=True,
                                                                  context={"request": request})
            resp_data = serializer.data

        return Response(resp_data)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk):
        temp_data = list()
        if hasattr(request.user, 'doctor') and request.user.doctor:
            queryset = self.get_queryset().filter(doctor_clinic__hospital=pk)
            if queryset.count() == 0:
                raise Http404("No Hospital matches the given query.")

            schedule_serializer = serializers.DoctorHospitalScheduleSerializer(queryset, many=True)
            if queryset:
                hospital_queryset = queryset.first().doctor_clinic.hospital
                hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset,
                                                                          context={"request": request})

            temp_data = dict()
            temp_data['hospital'] = hospital_serializer.data if queryset else []
            temp_data['schedule'] = schedule_serializer.data

        return Response(temp_data)


class DoctorBlockCalendarViewSet(OndocViewSet):

    serializer_class = serializers.DoctorLeaveSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, DoctorPermission,)
    INTERVAL_MAPPING = {models.DoctorLeave.INTERVAL_MAPPING.get(key): key for key in
                        models.DoctorLeave.INTERVAL_MAPPING.keys()}

    def get_queryset(self):
        user = self.request.user
        return models.DoctorLeave.objects.filter(doctor=user.doctor.id, deleted_at__isnull=True, doctor__is_live=True)

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        if not request.user.doctor:
            return Response([])
        queryset = self.get_queryset()
        serializer = serializers.DoctorLeaveSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, 'doctor') or not request.user.doctor:
            return Response([])
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
        if not hasattr(request.user, 'doctor') or not request.user.doctor:
            return Response([])
        current_time = timezone.now()
        doctor_leave = models.DoctorLeave.objects.get(pk=pk, doctor__is_live=True)
        doctor_leave.deleted_at = current_time
        doctor_leave.save()
        return Response({
            "status": 1
        })


class PrescriptionFileViewset(OndocViewSet):
    serializer_class = serializers.PrescriptionFileSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        request = self.request
        if request.user.user_type == User.DOCTOR:
            user = request.user
            return (models.PrescriptionFile.objects.filter(
                Q(prescription__appointment__doctor__manageable_doctors__user=user,
                  prescription__appointment__doctor__manageable_doctors__hospital=F(
                      'prescription__appointment__hospital'),
                  prescription__appointment__doctor__manageable_doctors__permission_type__in=[auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                  prescription__appointment__doctor__manageable_doctors__is_disabled=False) |
                Q(prescription__appointment__hospital__manageable_hospitals__user=user,
                  prescription__appointment__hospital__manageable_hospitals__doctor__isnull=True,
                  prescription__appointment__hospital__manageable_hospitals__permission_type__in=[auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                  prescription__appointment__hospital__manageable_hospitals__is_disabled=False)).
                    distinct())
            # return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)
        elif request.user.user_type == User.CONSUMER:
            return models.PrescriptionFile.objects.filter(prescription__appointment__user=request.user)
        else:
            return models.PrescriptionFile.objects.none()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        appointment = int(request.query_params.get("appointment"))
        if not appointment:
            return Response(status=400)
        queryset = self.get_queryset().filter(prescription__appointment=appointment)
        serializer = serializers.PrescriptionFileSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = serializers.PrescriptionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        #resp_data = list()
        if not self.prescription_permission(request.user, validated_data.get('appointment')):
            return Response({'msg': "You don't have permissions to manage this appointment"},
                            status=status.HTTP_403_FORBIDDEN)

        if models.Prescription.objects.filter(appointment=validated_data.get('appointment')).exists():
            prescription = models.Prescription.objects.filter(appointment=validated_data.get('appointment')).first()
        else:
            prescription = models.Prescription.objects.create(appointment=validated_data.get('appointment'),
                                                                  prescription_details=validated_data.get(
                                                                      'prescription_details'))
        prescription_file_data = {
            "prescription": prescription.id,
            "name": validated_data.get('name')
        }
        prescription_file_serializer = serializers.PrescriptionFileSerializer(data=prescription_file_data,
                                                                                  context={"request": request})
        prescription_file_serializer.is_valid(raise_exception=True)
        prescription_file_serializer.save()
        resp_data = prescription_file_serializer.data
        return Response(resp_data)

    def remove(self, request):
        serializer_data = serializers.PrescriptionFileDeleteSerializer(data=request.data, context={'request': request})
        serializer_data.is_valid(raise_exception=True)
        validated_data = serializer_data.validated_data
        if self.prescription_permission(request.user, validated_data.get('appointment')):
            response = {
                "status": 0,
                "id": validated_data['id']
            }
            if validated_data.get('id'):
                get_object_or_404(models.PrescriptionFile, pk=validated_data['id'])
                delete_queryset = self.get_queryset().filter(pk=validated_data['id'])
                delete_queryset.delete()
                response['status'] = 1
        else:
            response = []

        return Response(response)

    def prescription_permission(self, user, appointment):
        return auth_models.GenericAdmin.objects.filter(user=user, hospital=appointment.hospital,
                                                permission_type__in=[auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                                                write_permission=True).exists()


class SearchedItemsViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        name = request.query_params.get("name")
        if not name:
            return Response({"conditions": [], "specializations": []})
        medical_conditions = models.CommonMedicalCondition.objects.select_related('condition').filter(
            Q(condition__search_key__icontains=name) |
            Q(condition__search_key__icontains=' ' + name) |
            Q(condition__search_key__istartswith=name)
        ).annotate(search_index=StrIndex('condition__search_key',
                                         Value(name))).order_by('search_index')[:5]
        conditions_serializer = serializers.MedicalConditionSerializer(medical_conditions,
                                                                       many=True, context={'request': request})

        specializations = models.PracticeSpecialization.objects.filter(
            Q(search_key__icontains=name) |
            Q(search_key__icontains=' ' + name) |
            Q(search_key__istartswith=name)).annotate(search_index=StrIndex('search_key', Value(name))).order_by(
            'search_index').values("id", "name")[:5]

        return Response({"conditions": conditions_serializer.data, "specializations": specializations})

    @transaction.non_atomic_requests
    def common_conditions(self, request):
        count = request.query_params.get('count', 10)
        count = int(count)
        if count <=0:
            count = 10
        medical_conditions = models.CommonMedicalCondition.objects.select_related('condition').all().order_by("priority")[:count]
        conditions_serializer = serializers.MedicalConditionSerializer(medical_conditions, many=True, context={'request': request})

        common_specializations = models.CommonSpecialization.objects.select_related('specialization').all().order_by("priority")[:10]
        specializations_serializer = serializers.CommonSpecializationsSerializer(common_specializations, many=True, context={'request': request})
        return Response({"conditions": conditions_serializer.data, "specializations": specializations_serializer.data})


class DoctorListViewSet(viewsets.GenericViewSet):
    queryset = models.Doctor.objects.all()

    @transaction.non_atomic_requests
    def list_by_url(self, request, *args, **kwargs):
        url = request.GET.get('url', None)
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()

        entity_url_qs = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                           entity_type__iexact='Doctor').order_by('-sequence')
        if entity_url_qs.exists():
            entity = entity_url_qs.first()
            if not entity.is_valid:
                valid_qs = EntityUrls.objects.filter(url_type=EntityUrls.UrlType.SEARCHURL, is_valid=True,
                                          entity_type__iexact='Doctor', specialization_id=entity.specialization_id,
                                          locality_id=entity.locality_id, sublocality_id=entity.sublocality_id,
                                          sitemap_identifier=entity.sitemap_identifier).order_by('-sequence')

                if valid_qs.exists():
                    corrected_url = valid_qs.first().url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

            extras = entity.additional_info
            if extras:
                kwargs['extras'] = extras
                kwargs['specialization_id'] = entity.specialization_id
                kwargs['url'] = url
                kwargs['parameters'] = doctor_query_parameters(extras, request.query_params)
                response = self.list(request, **kwargs)
                return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        parameters = request.query_params
        if kwargs.get("parameters"):
            parameters = kwargs.get("parameters")
        serializer = serializers.DoctorListSerializer(data=parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if kwargs.get('extras'):
            validated_data['extras'] = kwargs['extras']
        if kwargs.get('url'):
            validated_data['url'] = kwargs['url']

        specialization_id = kwargs.get('specialization_id', None)
        specialization_dynamic_content = ''

        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            doctor_search_result = RawSql(query_string).fetch_all()
            result_count = len(doctor_search_result)
            # sa
            # saved_search_result = models.DoctorSearchResult.objects.create(results=doctor_search_result,
            #                                                                result_count=result_count)
        else:
            saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))
        doctor_ids = paginate_queryset([data.get("doctor_id") for data in doctor_search_result], request)
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(doctor_ids)])
        doctor_data = models.Doctor.objects.filter(
            id__in=doctor_ids).prefetch_related("hospitals", "doctor_clinics", "doctor_clinics__availability",
                                                "doctor_clinics__hospital",
                                                "doctorpracticespecializations", "doctorpracticespecializations__specialization",
                                                "experiences", "images", "qualifications",
                                                "qualifications__qualification", "qualifications__specialization",
                                                "qualifications__college").order_by(preserved)

        response = doctor_search_helper.prepare_search_response(doctor_data, doctor_search_result, request)

        entity_ids = [doctor_data['id'] for doctor_data in response]

        id_url_dict = dict()
        entity = EntityUrls.objects.filter(entity_id__in=entity_ids, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Doctor').values('entity_id', 'url')
        for data in entity:
            id_url_dict[data['entity_id']] = data['url']

        title = ''
        description = ''
        seo = None
        breadcrumb = None

        # if False and (validated_data.get('extras') or validated_data.get('specialization_ids')):
        if validated_data.get('extras'):
            location = None
            breadcrumb_sublocality = None
            breadcrumb_locality = None
            city = None
            breadcrumb = None
            locality = ''
            sublocality = ''
            specializations = ''
            if validated_data.get('extras') and validated_data.get('extras').get('location_json'):
                if validated_data.get('extras').get('location_json').get('locality_value'):
                    locality = validated_data.get('extras').get('location_json').get('locality_value')
                    breadcrumb_locality = locality
                    city = locality
                if validated_data.get('extras').get('location_json').get('sublocality_value'):
                    sublocality = validated_data.get('extras').get('location_json').get('sublocality_value')
                    if sublocality:
                        breadcrumb_sublocality = sublocality
                        locality = sublocality + ' ' + locality
                if validated_data.get('extras').get('location_json').get('breadcrum_url'):
                    breadcrumb_locality_url = validated_data.get('extras').get('location_json').get('breadcrum_url')
            #
            # if validated_data.get('specialization_ids'):
            #     specialization_name_obj = models.PracticeSpecialization.objects.filter(
            #         id__in=validated_data.get('specialization_ids', [])).values(
            #         'name')
            #     specialization_list = []
            #
            #     for names in specialization_name_obj:
            #         specialization_list.append(names.get('name'))
            #
            #     specializations = ', '.join(specialization_list)
            # else:
            #     if validated_data.get('extras').get('specialization'):
            #         specializations = validated_data.get('extras').get('specialization')
            #     else:
            #         specializations = ''
            specializations = None
            if validated_data.get('extras') and validated_data.get('extras').get('specialization'):
                specializations = validated_data.get('extras').get('specialization')

            if specializations:
                title = specializations
                description = specializations

            else:
                title = 'Doctors'
                description = 'Doctors'
            if locality:
                title += ' in '  + locality
                description += ' in ' +locality
            if specializations:

                if locality:
                    if sublocality == '':

                        description += ': Book best ' + specializations + '\'s appointment online ' +  'in ' + city
                    else:

                        description += ': Book best ' + specializations + '\'s appointment online ' + 'in '+ locality

            else:
                if locality:
                    if sublocality == '':

                        description += ': Book best ' + 'Doctor' + ' appointment online ' + 'in ' + city
                    else:

                        description += ': Book best ' + 'Doctor' + ' appointment online ' + 'in '+ locality
            if specializations:
                if not sublocality:
                    title += '- Book Best ' + specializations +' Online'
                else:
                    title += ' | Book & Get Best Deal'

            else:
                 title += ' | Book Doctors Online & Get Best Deal'

            description += ' and get upto 50% off. View Address, fees and more for doctors '
            if locality:
                description += 'in '+ city
            description += '.'

            if breadcrumb_sublocality:
                breadcrumb =[ {
                'name': breadcrumb_locality,
                'url': breadcrumb_locality_url
                },
                 {
                        'name': breadcrumb_sublocality,
                        'url': validated_data.get('url')
                    }
                ]

            if title or description:
                if locality:
                    if not sublocality:
                        location = city
                    else:
                        location = locality

            if validated_data.get('extras', {}).get('location_json', {}).get('sublocality_latitude', None):
                latitude = validated_data.get('extras').get('location_json').get('sublocality_latitude')
                longitude = validated_data.get('extras').get('location_json').get('sublocality_longitude')
            else:
                latitude = validated_data.get('extras', {}).get('location_json', {}).get('locality_latitude', None)
                longitude = validated_data.get('extras', {}).get('location_json', {}).get('locality_longitude', None)

            # seo = {
            #     "title": title,
            #     "description": description,
            #     "location" : location
            #     }

            seo = {
                "title": title,
                "description": description,
                "location": location,
                'schema': {
                    "@context": "http://schema.org",
                    "@type": "MedicalBusiness",
                    "name": "%s in %s" % (specializations if specializations else 'Doctors', location),
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": location,
                        "addressRegion": locality,
                    },
                    "location": {
                        "@type": "Place",
                        "geo": {
                            "@type": "GeoCircle",
                            "geoMidpoint": {
                                "@type": "GeoCoordinates",
                                "latitude": latitude,
                                "longitude": longitude
                            }
                        }
                    },
                    "priceRange": "0"
                }
            }

            if specialization_id:
                specialization_content = models.PracticeSpecializationContent.objects.filter(specialization__id=specialization_id).first()
                if specialization_content:
                    content = str(specialization_content.content)
                    content = content.replace('<location>', location)
                    regex = re.compile(r'[\n\r\t]')
                    content = regex.sub(" ", content)
                    specialization_dynamic_content = content

        for resp in response:
            if id_url_dict.get(resp['id']):
                resp['url'] = id_url_dict[resp['id']]
                resp['schema']['url'] = id_url_dict[resp['id']]
            else:
                resp['url'] = None
                resp['schema']['url'] = None

        specializations = list(models.PracticeSpecialization.objects.filter(id__in=validated_data.get('specialization_ids',[])).values('id','name'));
        conditions = list(models.MedicalCondition.objects.filter(id__in=validated_data.get('condition_ids',[])).values('id','name'));
        return Response({"result": response, "count": result_count,
                         'specializations': specializations,'conditions':conditions, "seo": seo, "breadcrumb":breadcrumb, 'search_content': specialization_dynamic_content})


class DoctorAvailabilityTimingViewSet(viewsets.ViewSet):

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        queryset = models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=validated_data.get('doctor_id'),
                                                            doctor_clinic__hospital=validated_data.get(
                                                                'hospital_id')).order_by("start")
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

        timeslots = obj.get_timing_list()
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data,
                         "doctor_leaves": doctor_leave_serializer.data})


class HealthTipView(viewsets.GenericViewSet):

    def get_queryset(self):
        return models.HealthTip.objects.all()

    @transaction.non_atomic_requests
    def list(self, request):
        data = self.get_queryset()
        serializer = serializers.HealthTipSerializer(data, many=True)
        return Response(serializer.data)


class ConfigView(viewsets.GenericViewSet):

    def retrieve(self, request):
        serializer_data = serializers.ConfigGetSerializer(data=request.data, context={'request': request})
        serializer_data.is_valid(raise_exception=True)
        validated_data = serializer_data.validated_data
        return Response({})


class DoctorAppointmentNoAuthViewSet(viewsets.GenericViewSet):

    @transaction.atomic
    def complete(self, request):
        resp = {}
        serializer = serializers.OpdAppointmentCompleteTempSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        # opd_appointment = get_object_or_404(models.OpdAppointment, pk=validated_data.get('opd_appointment'))
        opd_appointment = models.OpdAppointment.objects.select_for_update().filter(pk=validated_data.get('opd_appointment')).first()
        if not opd_appointment:
            return Response({"message": "Invalid appointment id"}, status.HTTP_404_NOT_FOUND)

        if opd_appointment:
            opd_appointment.action_completed()

            resp = {'success': 'Appointment Completed Successfully!'}
        return Response(resp)


class LimitUser(UserRateThrottle):
    rate = '5/day'


class LimitAnon(AnonRateThrottle):
    rate = '5/day'


class DoctorContactNumberViewSet(viewsets.GenericViewSet):

    throttle_classes = (LimitUser, LimitAnon)

    def retrieve(self, request, doctor_id):

        doctor_obj = get_object_or_404(models.Doctor, pk=doctor_id)

        doctor_details = models.DoctorMobile.objects.filter(doctor=doctor_obj).values('is_primary','number','std_code').order_by('-is_primary').first()

        if not doctor_details:
            return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)
        else:
            final = str(doctor_details.get('number'))
            if doctor_details.get('std_code'):
                final = '0'+str(doctor_details.get('std_code'))+' '+str(doctor_details.get('number'))
            return Response({'status': 1, 'number': final}, status.HTTP_200_OK)


class DoctorFeedbackViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def feedback(self, request):
        resp = {}
        user = request.user
        serializer = serializers.DoctorFeedbackBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        message = ''
        for key, value in valid_data.items():
            if isinstance(value, list):
                val = ' '.join(map(str, value))
            else:
                val = value
            message += str(key) + "  -  " + str(val) + "<br>"
        if user.doctor:
            managers_list = []
            for managers in user.doctor.manageable_doctors.all():
                info = {}
                info['hospital_id'] = (str(managers.hospital_id)) if managers.hospital_id else "<br>"
                info['hospital_name'] = (str(managers.hospital.name)) if managers.hospital else "<br>"
                info['user_id'] = (str(managers.user_id) ) if managers.user else "<br>"
                info['user_number'] = (str(managers.phone_number)) if managers.phone_number else "<br>"
                info['type'] = (str(dict(auth_models.GenericAdmin.type_choices)[managers.permission_type])) if managers.permission_type else "<br>"
                managers_list.append(info)
            managers_string = "<br>".join(str(x) for x in managers_list)
        if managers_string:
            message = message + "<br><br> User's Managers <br>"+ managers_string

        manages_list = []
        for manages in user.manages.all():
            info = {}
            info['hospital_id'] = (str(manages.hospital_id)) if manages.hospital_id else "<br>"
            info['hospital_name'] = (str(manages.hospital.name)) if manages.hospital else "<br>"
            info['doctor_name'] = (str(manages.doctor.name)) if manages.doctor else "<br>"
            info['user_id'] = (str(user.id)) if user else "<br>"
            info['doctor_number'] = (str(manages.doctor.mobiles.filter(is_primary=True).first().number)) if(manages.doctor and manages.doctor.mobiles.filter(is_primary=True)) else "<br>"
            manages_list.append(info)
        manages_string = "<br>".join(str(x) for x in manages_list)
        if manages_string:
            message = message + "<br><br> User Manages <br>"+ manages_string
        try:
            emails = ["rajivk@policybazaar.com", "sanat@docprime.com", "arunchaudhary@docprime.com", "rajendra@docprime.com", "harpreet@docprime.com"]
            for x in emails:
                notif_models.EmailNotification.publish_ops_email(str(x), mark_safe(message), 'Feedback Mail')
            resp['status'] = "success"
        except:
            resp['status'] = "error"
        return Response(resp)


class HospitalAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Hospital.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q).order_by('name')
        return qs


class CreateAdminViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return auth_models.GenericAdmin.objects.none()

    def create(self, request):
        serializer = serializers.AdminCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        pem_type = auth_models.GenericAdmin.APPOINTMENT
        if valid_data.get('billing_enabled') and valid_data.get('appointment_enabled'):
            pem_type = auth_models.GenericAdmin.ALL
        elif valid_data.get('billing_enabled') and not valid_data.get('appointment_enabled'):
            pem_type = auth_models.GenericAdmin.BILLINNG

        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            doct = Doctor.objects.get(id=valid_data['id'])
            if valid_data.get('assoc_hosp'):
                create_admins = []
                for hos in valid_data['assoc_hosp']:
                    user=None

                    user_queryset = User.objects.filter(user_type=User.DOCTOR, phone_number=valid_data['phone_number']).first()
                    if user_queryset:
                        user = user_queryset
                    ad = auth_models.GenericAdmin.create_permission_object(user=user, doctor=doct,
                                                                      phone_number=valid_data['phone_number'],
                                                                      hospital=hos,
                                                                      permission_type=pem_type,
                                                                      is_disabled=False,
                                                                      super_user_permission=False,
                                                                      write_permission=True,
                                                                      created_by=request.user,
                                                                      source_type=auth_models.GenericAdmin.APP,
                                                                      entity_type=GenericAdminEntity.DOCTOR)
                    create_admins.append(ad)
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    return Response({'error': 'something went wrong!'})

        elif valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            hosp = Hospital.objects.get(id=valid_data['id'])
            if valid_data['type'] == User.DOCTOR:
                try:
                    auth_models.DoctorNumber.objects.create(phone_number=valid_data.get('number'), doctor=valid_data.get('profile'))
                except Exception as e:
                    return Response({'error': 'something went wrong!'})
            if valid_data.get('assoc_doc'):
                create_admins = []
                for doc in valid_data['assoc_doc']:
                    user=None

                    user_queryset = User.objects.filter(user_type=User.DOCTOR, phone_number=valid_data['phone_number']).first()
                    if user_queryset:
                        user = user_queryset
                    ad = auth_models.GenericAdmin.create_permission_object(user=user, doctor=doc,
                                                                      phone_number=valid_data['phone_number'], hospital=hosp,
                                                                      permission_type=pem_type,
                                                                      is_disabled=False,
                                                                      super_user_permission=False,
                                                                      write_permission=True,
                                                                      created_by=request.user,
                                                                      source_type=auth_models.GenericAdmin.APP,
                                                                      entity_type=GenericAdminEntity.HOSPITAL)
                    create_admins.append(ad)
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    return Response({'error': 'something went wrong!'})

        return Response({'success': 'Created Successfully'})

    def assoc_doctors(self, request, pk=None):
        hospital = get_object_or_404(Hospital, pk=pk)
        queryset = hospital.assoc_doctors
        return Response(queryset.extra(select={'assigned': 'CASE WHEN  ((SELECT COUNT(*) FROM doctor_number WHERE doctor_id = doctor.id) = 0) THEN 0 ELSE 1  END'}).values('name', 'id', 'assigned'))

    def assoc_hosp(self, request, pk=None):
        doctor = get_object_or_404(Doctor, pk=pk)
        queryset = doctor.prefetch_related('hospitals').hospitals.filter(is_appointment_manager=False)
        return Response(queryset.values('name', 'id'))


    def list_entities(self, request):
        user = request.user
        opd_list = []
        opd_queryset = (models.Doctor.objects
                        .prefetch_related('manageable_doctors', 'qualifications')
                        .filter(
                                      is_live=True,
                                      manageable_doctors__user=user,
                                      manageable_doctors__is_disabled=False,
                                      manageable_doctors__super_user_permission=True,
                                      manageable_doctors__entity_type=GenericAdminEntity.DOCTOR).distinct('id'))
        doc_serializer = serializers.DoctorEntitySerializer(opd_queryset, many=True, context={'request': request})
        doc_data = doc_serializer.data
        if doc_data:
            opd_list = [i for i in doc_data]
        opd_queryset_hos = (models.Hospital.objects
                            .prefetch_related('manageable_hospitals')
                            .filter(
                                      is_live=True,
                                      is_appointment_manager=True,
                                      manageable_hospitals__user=user,
                                      manageable_hospitals__is_disabled=False,
                                      manageable_hospitals__super_user_permission=True,
                                      manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL)
                            .distinct('id')
                            )
        hos_list = []
        hos_serializer = serializers.HospitalEntitySerializer(opd_queryset_hos, many=True, context={'request': request})
        hos_data = hos_serializer.data
        if hos_data:
            hos_list = [i for i in hos_data]
        result_data = opd_list + hos_list
        lab_queryset = lab_models.Lab.objects.prefetch_related('manageable_lab_admins').filter(is_live= True,
                                manageable_lab_admins__user=user,
                                manageable_lab_admins__is_disabled=False,
                                manageable_lab_admins__super_user_permission=True).distinct('id')

        lab_list = []
        laab_serializer = lab_serializers.LabEntitySerializer(lab_queryset, many=True, context={'request': request})
        lab_data = laab_serializer.data
        if lab_data:
            lab_list = [i for i in lab_data]
        result_data = result_data + lab_list
        return Response(result_data)

    def list_entity_admins(self, request):
        serializer = serializers.EntityListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = auth_models.GenericAdmin.objects.select_related('doctor', 'hospital').exclude(user=request.user)
        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            query = queryset.filter(doctor_id=valid_data.get('id'))\
                .annotate(hospital_name=F('hospital__name'))\
                .values('phone_number', 'name', 'super_user_permission', 'is_disabled', 'permission_type', 'hospital', 'hospital_name')
        elif valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            query = queryset.filter(hospital_id=valid_data.get('id'))\
                .annotate(doctor_name=F('doctor__name')) \
                .values('phone_number', 'name', 'super_user_permission', 'is_disabled', 'permission_type', 'doctor', 'doctor_name')
        elif valid_data.get('entity_type') == GenericAdminEntity.LAB:
            query = auth_models.GenericLabAdmin.objects\
                .exclude(user=request.user)\
                .filter(lab_id=valid_data.get('id'))\
                .values('phone_number', 'name', 'super_user_permission', 'is_disabled', 'permission_type')
        if query:
            return Response(query)
        return Response([])
