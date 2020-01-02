import operator
from collections import defaultdict, OrderedDict
from uuid import UUID

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from config.settings.db_router import DatabaseInfo
from ondoc.account.models import Order, ConsumerAccount, PgTransaction
from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.doctor.city_match import city_match
from ondoc.api.v1.doctor.serializers import HospitalModelSerializer, AppointmentRetrieveDoctorSerializer, \
    OfflinePatientSerializer, CommonConditionsSerializer, RecordSerializer
from ondoc.api.v1.doctor.DoctorSearchByHospitalHelper import DoctorSearchByHospitalHelper
from ondoc.api.v1.procedure.serializers import CommonProcedureCategorySerializer, ProcedureInSerializer, \
    ProcedureSerializer, DoctorClinicProcedureSerializer, CommonProcedureSerializer, CommonIpdProcedureSerializer, \
    CommonHospitalSerializer, CommonCategoriesSerializer
from ondoc.authentication.models import UserProfile
from ondoc.cart.models import Cart
from ondoc.common.middleware import use_slave
from ondoc.crm.constants import constants
from ondoc.diagnostic.models import LabTestCategory
from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from ondoc.diagnostic import models as lab_models
from ondoc.insurance.models import UserInsurance, InsuredMembers
from ondoc.notification import tasks as notification_tasks
#from ondoc.doctor.models import Hospital, DoctorClinic,Doctor,  OpdAppointment
from ondoc.doctor.models import DoctorClinic, OpdAppointment, DoctorAssociation, DoctorQualification, Doctor, Hospital, \
    HealthInsuranceProvider, ProviderSignupLead, HospitalImage, CommonHospital, PracticeSpecialization, \
    SpecializationDepartmentMapping, DoctorPracticeSpecialization, DoctorClinicTiming, GoogleMapRecords
from ondoc.notification.models import EmailNotification
from django.utils.safestring import mark_safe
from ondoc.coupon.models import Coupon, CouponRecommender
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.account import models as account_models
from ondoc.location.models import EntityUrls, EntityAddress, DefaultRating
from ondoc.plus.models import PlusPlans, TempPlusUser
from ondoc.procedure.models import Procedure, ProcedureCategory, CommonProcedureCategory, ProcedureToCategoryMapping, \
    get_selected_and_other_procedures, CommonProcedure, CommonIpdProcedure, IpdProcedure, DoctorClinicIpdProcedure, \
    IpdProcedureFeatureMapping, IpdProcedureDetail, SimilarIpdProcedureMapping, IpdProcedureLead, Offer, \
    PotentialIpdCity
from ondoc.seo.models import NewDynamic
from . import serializers
from ondoc.api.v2.doctor import serializers as v2_serializers
from ondoc.api.pagination import paginate_queryset, paginate_raw_query, paginate_queryset_refactored_consumer_app
from ondoc.api.v1.utils import convert_timings, form_time_slot, IsDoctor, payment_details, aware_time_zone, \
    TimeSlotExtraction, GenericAdminEntity, get_opd_pem_queryset, offline_form_time_slots, ipd_query_parameters, \
    common_package_category
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.doctor.doctorsearch import DoctorSearchHelper
from django.db.models import Min, Prefetch
from django.contrib.gis.geos import Point, GEOSGeometry
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from ondoc.authentication.backends import JWTAuthentication, MatrixAuthentication
from django.utils import timezone
from django.db import transaction
from django.http import Http404, HttpResponse
from django.db.models import Q, Value, Case, When
from operator import itemgetter
from itertools import groupby,chain
from ondoc.api.v1.utils import RawSql, is_valid_testing_data, doctor_query_parameters
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import F, Count
from django.db.models.functions import StrIndex, Length
import datetime, logging, copy, re
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
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.db.models import Count, IntegerField, Avg
from ondoc.insurance.models import InsuranceThreshold
import logging
from ondoc.api.v1.auth import serializers as auth_serializers
from copy import deepcopy
from ondoc.common.models import GlobalNonBookable, AppointmentHistory, UserConfig
from ondoc.api.v1.common import serializers as common_serializers
from django.utils.text import slugify
from django.urls import reverse
import time
from ondoc.api.v1.ratings.serializers import GoogleRatingsGraphSerializer
logger = logging.getLogger(__name__)
import random
from ondoc.prescription import models as pres_models
from ondoc.api.v1.prescription import serializers as pres_serializers
from django.template.defaultfilters import slugify
from packaging.version import parse
from django.http import HttpResponse, HttpResponseRedirect
from geopy.geocoders import Nominatim
from django.shortcuts import render

geolocator = Nominatim()

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
        return None

    def get_pem_queryset(self, user):
        queryset = get_opd_pem_queryset(user, models.OpdAppointment)
        return queryset

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user
        queryset = self.get_pem_queryset(user)
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
            queryset = queryset.filter(
                Q(status__in=[models.OpdAppointment.COMPLETED, models.OpdAppointment.CANCELLED]) | Q(time_slot_start__lt=timezone.now())).order_by(
                '-time_slot_start')
        elif range == 'upcoming':
            today = datetime.date.today()
            queryset = queryset.filter(
                status__in=[models.OpdAppointment.BOOKED, models.OpdAppointment.RESCHEDULED_PATIENT,
                            models.OpdAppointment.RESCHEDULED_DOCTOR, models.OpdAppointment.ACCEPTED],
                time_slot_start__date__gte=today).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status__in=[models.OpdAppointment.BOOKED,
                                                                                       models.OpdAppointment.RESCHEDULED_PATIENT
                                                                                       ]).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        if date:
            queryset = queryset.filter(time_slot_start__date=date)
        queryset = queryset.select_related('profile', 'merchant_payout') \
                           .prefetch_related('prescriptions', 'prescriptions__prescription_file', 'mask_number',
                              'profile__insurance', 'profile__insurance__user_insurance', 'eprescription')\
                           .distinct('id', 'time_slot_start')
        queryset = paginate_queryset(queryset, request)
        serializer = serializers.DoctorAppointmentRetrieveSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk=None):
        user = request.user
        queryset = self.get_pem_queryset(user)
        queryset = queryset.filter(pk=pk).distinct()
        if queryset:
            serializer = serializers.DoctorAppointmentRetrieveSerializer(queryset, many=True,
                                                                         context={'request': request})
            return Response(serializer.data)
        else:
            return Response([])

    @transaction.atomic
    def complete(self, request):
        user = request.user
        source = request.query_params.get('source', '')
        responsible_user = user
        serializer = serializers.OTPFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get('source'):
            source = validated_data.get('source')
        opd_appointment = models.OpdAppointment.objects.select_for_update().filter(pk=validated_data.get('id')).first()

        if not opd_appointment or opd_appointment.status==opd_appointment.CREATED:
            return Response({"message": "Invalid appointment id"}, status.HTTP_404_NOT_FOUND)
        opd_appointment._source = source if source in [x[0] for x in AppointmentHistory.SOURCE_CHOICES] else ''
        opd_appointment._responsible_user = responsible_user
        pem_queryset = auth_models.GenericAdmin.objects.filter(Q(user=user, is_disabled=False),
                                                               Q(Q(super_user_permission=True,
                                                                   hospital=opd_appointment.hospital,
                                                                   entity_type=GenericAdminEntity.HOSPITAL)
                                                                 |
                                                                 Q(super_user_permission=True,
                                                                   doctor=opd_appointment.doctor,
                                                                   entity_type=GenericAdminEntity.DOCTOR))
                                                               |
                                                               Q(Q(doctor=opd_appointment.doctor,
                                                                 hospital=opd_appointment.hospital)
                                                                 |
                                                                 Q(doctor__isnull=True,
                                                                   hospital=opd_appointment.hospital)
                                                                 )
                                                               ).first()
        if not pem_queryset:
            return Response({"message": "No Permissions"}, status.HTTP_403_FORBIDDEN)
        if request.user.user_type == User.DOCTOR:
            otp_valid_serializer = serializers.OTPConfirmationSerializer(data=request.data)
            otp_valid_serializer.is_valid(raise_exception=True)
            opd_appointment.action_completed()
        opd_appointment_serializer = serializers.DoctorAppointmentRetrieveSerializer(opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)

    @transaction.atomic
    def create_new(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data,
                                                             context={'request': request, 'data': request.data,
                                                                      'use_duplicate': True})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        data = request.data
        user = request.user

        if data and data.get('appointment_id') and data.get('cod_to_prepaid'):
            opd_app = OpdAppointment.objects.filter(id=data.get('appointment_id'),
                                                    payment_type=OpdAppointment.PREPAID)
            if opd_app:
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={"error": 'Appointment already created, Cannot Rebook.',
                                      "request_errors": {"message": 'Appointment already created, Cannot Rebook.'}})
            pg_order = Order.objects.filter(reference_id=validated_data.get('appointment_id')).first()
            cart_item_id = pg_order.action_data.get('cart_item_id', None)
            price_data = OpdAppointment.get_price_details(validated_data)
            fulfillment_data = [OpdAppointment.create_fulfillment_data(user, validated_data, price_data, cart_item_id)]

            resp = {}
            balance = 0
            cashback_balance = 0

            if validated_data.get('use_wallet'):
                consumer_account = ConsumerAccount.objects.get_or_create(user=user)
                consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)
                balance = consumer_account.balance
                cashback_balance = consumer_account.cashback

            total_balance = balance + cashback_balance
            payable_amount = Order.get_total_payable_amount(fulfillment_data)

            # utility to fetch and save visitor info for an parent order
            # visitor_info = None
            # try:
            #     from ondoc.api.v1.tracking.views import EventCreateViewSet
            #     with transaction.atomic():
            #         event_api = EventCreateViewSet()
            #         visitor_id, visit_id = event_api.get_visit(request)
            #         visitor_info = {"visitor_id": visitor_id, "visit_id": visit_id,
            #                         "from_app": request.data.get("from_app", None),
            #                         "app_version": request.data.get("app_version", None)}
            # except Exception as e:
            #     logger.log("Could not fecth visitor info - " + str(e))

            # create a Parent order to accumulate sub-orders
            process_immediately = False
            if validated_data.get('use_wallet') and total_balance >= payable_amount:
                cashback_amount = min(cashback_balance, payable_amount)
                wallet_amount = max(0, payable_amount - cashback_amount)
                pg_order.amount=0
                pg_order.wallet_amount=wallet_amount
                pg_order.cashback_amount=cashback_amount
                pg_order.payment_status=Order.PAYMENT_PENDING
                pg_order.user=user
                pg_order.product_id=1
                pg_order.save()

                process_immediately = True

            elif validated_data.get('use_wallet') and total_balance <= payable_amount:
                amount_from_pg = max(0, payable_amount - total_balance)
                required_amount = payable_amount
                cashback_amount = min(required_amount, cashback_balance)
                wallet_amount = 0
                if cashback_amount < required_amount:
                    wallet_amount = min(balance, required_amount - cashback_amount)
                pg_order.amount = amount_from_pg
                pg_order.wallet_amount = wallet_amount
                pg_order.cashback_amount = cashback_amount
                pg_order.payment_status = Order.PAYMENT_PENDING
                pg_order.user = user
                pg_order.product_id = 1
                pg_order.save()
                process_immediately = False

                push_order_to_matrix.apply_async(
                    ({'order_id': pg_order.id},),
                    eta=timezone.now() + timezone.timedelta(minutes=settings.LEAD_VALIDITY_BUFFER_TIME))
            else:
                amount_from_pg = payable_amount
                cashback_amount = 0
                wallet_amount = 0
                pg_order.amount = amount_from_pg
                pg_order.wallet_amount = wallet_amount
                pg_order.cashback_amount = cashback_amount
                pg_order.payment_status = Order.PAYMENT_PENDING
                pg_order.user = user
                pg_order.product_id = 1
                pg_order.save()
                process_immediately = False

            # building separate orders for all fulfillments
            fulfillment_data = copy.deepcopy(fulfillment_data)
            order_list = []
            order = None

            for appointment_detail in fulfillment_data:

                product_id = Order.DOCTOR_PRODUCT_ID if appointment_detail.get('doctor') else Order.LAB_PRODUCT_ID
                action = None
                if product_id == Order.DOCTOR_PRODUCT_ID:
                    appointment_detail = opdappointment_transform(appointment_detail)
                    action = Order.OPD_APPOINTMENT_CREATE

                if appointment_detail.get('payment_type') == OpdAppointment.PREPAID:
                    order = Order.objects.filter(reference_id=validated_data.get('appointment_id')).first()
                    order.product_id = product_id
                    order.action = action
                    order.action_data = appointment_detail
                    order.payment_status = Order.PAYMENT_PENDING
                    order.user = user
                    # order.parent = pg_order
                    order.cart_id = cart_item_id
                    order.save()
                if order:
                    order_list.append(order)

            if process_immediately:
                pg_order.refresh_from_db()
                appointment_ids = pg_order.process_pg_order(True)
                if appointment_ids.get('id') and price_data.get('coupon_list'):
                    coupon_id  = price_data.get('coupon_list')[0]
                    opd_app = OpdAppointment.objects.filter(id=appointment_ids.get('id')).first()
                    opd_app.coupon.add(coupon_id)
                    opd_app.save()


                resp["status"] = 1
                resp["payment_required"] = False
                resp["data"] = {
                    "orderId": pg_order.id,
                    "type": appointment_ids.get("type", "all"),
                    "id": appointment_ids.get("id", None)
                }
                resp["appointments"] = appointment_ids

            else:
                resp["status"] = 1
                resp['data'], resp["payment_required"] = payment_details(request, pg_order)
            return Response(resp)

        return Response({})


    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request, 'data' : request.data, 'use_duplicate' : True})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        data = request.data
        profile = validated_data.get('profile')
        plus_plan = validated_data.get('plus_plan', None)
        plus_user = request.user.active_plus_user
        if plus_plan and plus_user is None:
            is_verified = profile.verify_profile()
            if not is_verified:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"error": "Profile is not completed, Please update profile first to process further"})
        if plus_plan and plus_user is None:
            plus_user = TempPlusUser.objects.create(user=request.user, plan=plus_plan, profile=profile)
        user_insurance = request.user.active_insurance #UserInsurance.get_user_insurance(request.user)

        hospital = validated_data.get('hospital')
        doctor = validated_data.get('doctor')

        doctor_clinic = DoctorClinic.objects.filter(doctor=doctor, hospital=hospital).first()
        profile = validated_data.get('profile')
        if not plus_user:
            payment_type = validated_data.get('payment_type')
        else:
            payment_type = OpdAppointment.GOLD if plus_user.plan.is_gold else OpdAppointment.VIP
            validated_data['payment_type'] = payment_type
        if user_insurance:
            if user_insurance.status == UserInsurance.ONHOLD:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"error": 'Your documents from the last claim '
                                                                                   'are under verification.Please write to customercare@docprime.com for more information',
                                                                          "request_errors": {
                                                                              "message": 'Your documents from the last claim are under '
                                                                                         'verification. Please write to customercare@docprime.com for more information'}})

            if profile.is_insured_profile and doctor.is_enabled_for_insurance and doctor.enabled_for_online_booking and \
                    payment_type == OpdAppointment.COD and doctor_clinic and doctor_clinic.enabled_for_online_booking:
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={"error": 'Some error occured. Please try again after some time.',
                                      "request_errors": {"message": 'Some error occured. Please try again'
                                                                    ' after some time.'}})

            insurance_validate_dict = user_insurance.validate_insurance(validated_data)
            data['is_appointment_insured'] = insurance_validate_dict['is_insured']
            data['insurance_id'] = insurance_validate_dict['insurance_id']
            data['insurance_message'] = insurance_validate_dict['insurance_message']

            if data['is_appointment_insured']:
                data['payment_type'] = OpdAppointment.INSURANCE

                blocked_slots = hospital.get_blocked_specialization_appointments_slots(doctor, user_insurance)
                start_date = validated_data.get('start_date').date()
                if str(start_date) in blocked_slots:
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Some error occured. Please try '
                                                                                       'again after some time.',
                                                                              'request_errors': {
                                                                                  'message':'Some error occured.Please'
                                                                                            'try again after some time'}})

                appointment_date = validated_data.get('start_date')
                is_appointment_exist = hospital.get_active_opd_appointments(request.user, user_insurance, appointment_date.date())
                if request.user and request.user.is_authenticated and not hasattr(request, 'agent') and is_appointment_exist :
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Some error occured. Please try '
                                                                                       'again after some time.',
                                                                              'request_errors': {
                                                                                  'message':'Some error occured.Please'
                                                                                            'Try again after some time.'}})
        elif plus_user:
            plus_user_dict = plus_user.validate_plus_appointment(validated_data)
            data['is_vip_member'] = plus_user_dict.get('is_vip_member', False)
            data['cover_under_vip'] = plus_user_dict.get('cover_under_vip', False)
            data['plus_user_id'] = plus_user.id
            data['vip_amount'] = int(plus_user_dict.get('vip_amount_deducted'))
            data['amount_to_be_paid'] = int(plus_user_dict.get('amount_to_be_paid'))
            if data['cover_under_vip']:
                if plus_user.plan.is_gold:
                    data['payment_type'] = OpdAppointment.GOLD
                    data['is_gold_member'] = True
                else:
                    data['payment_type'] = OpdAppointment.VIP
                    data['is_gold_member'] = False
                validated_data['payment_type'] = data['payment_type']
            else:
                validated_data['payment_type'] = validated_data.get('payment_type')
        else:
            data['is_appointment_insured'], data['insurance_id'], data[
                'insurance_message'], data['is_vip_member'], data['cover_under_vip'], \
            data['plus_user_id'] = False, None, "", False, False, None
        cart_item_id = validated_data.get('cart_item').id if validated_data.get('cart_item') else None
        if not validated_data.get("part_of_integration"):
            if not models.OpdAppointment.can_book_for_free(request, validated_data, cart_item_id):
                return Response({'request_errors': {"code": "invalid",
                                                    "message": "Only {} active free bookings allowed per customer".format(
                                                        models.OpdAppointment.MAX_FREE_BOOKINGS_ALLOWED)}},
                                status=status.HTTP_400_BAD_REQUEST)

        #For Appointment History
        responsible_user = None
        if data.get('from_app') and data['from_app']:
            data['_source'] = AppointmentHistory.CONSUMER_APP
            responsible_user = request.user.id
        elif data.get('from_web') and data['from_web']:
            data['_source'] = AppointmentHistory.WEB
            responsible_user = request.user.id
        if responsible_user:
            data['_responsible_user'] = responsible_user

        if not plus_plan:
            if validated_data.get("existing_cart_item"):
                cart_item = validated_data.get("existing_cart_item")
                old_cart_obj = Cart.objects.filter(id=validated_data.get('existing_cart_item').id).first()
                payment_type = old_cart_obj.data.get('payment_type')
                if payment_type == OpdAppointment.INSURANCE and data['is_appointment_insured'] == False:
                    data['payment_type'] = OpdAppointment.PREPAID
                if payment_type == OpdAppointment.VIP and data['cover_under_vip'] == False:
                    data['payment_type'] = OpdAppointment.PREPAID
                # cart_item.data = request.data
                cart_item.data = data
                cart_item.save()
            else:
                cart_item, is_new = Cart.objects.update_or_create(id=cart_item_id, deleted_at__isnull=True, product_id=account_models.Order.DOCTOR_PRODUCT_ID,
                                                      user=request.user, defaults={"data": data})

        resp = None
        is_agent = False
        if hasattr(request, 'agent') and request.agent:
            user = User.objects.filter(id=request.agent).first()
            if user and not user.groups.filter(name=constants['APPOINTMENT_OTP_BYPASS_AGENT_TEAM']).exists():
                if payment_type == OpdAppointment.COD:
                    is_agent = True
                else:
                    resp = {'is_agent': True, "status": 1}
        if not resp and not plus_plan:
            resp = account_models.Order.create_order(request, [cart_item], validated_data.get("use_wallet"))

        if not resp and plus_plan:
            if kwargs.get('is_dummy'):
                return validated_data

            resp = account_models.Order.create_new_order(request, validated_data, False)

        if is_agent:
            resp['is_agent'] = True

        return Response(data=resp)

    def can_book_for_free(self, user):
        return models.OpdAppointment.objects.filter(user=user, deal_price=0)\
                   .exclude(status__in=[models.OpdAppointment.COMPLETED, models.OpdAppointment.CANCELLED]).count() < models.OpdAppointment.MAX_FREE_BOOKINGS_ALLOWED
    def update(self, request, pk=None):
        user = request.user
        source = request.query_params.get('source', '')
        responsible_user = user
        queryset = self.get_pem_queryset(user).distinct()
        # opd_appointment = get_object_or_404(queryset, pk=pk)
        opd_appointment = models.OpdAppointment.objects.filter(id=pk).first()
        if not opd_appointment:
            return Response({'error': 'Appointment Not Found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get('source'):
            source = validated_data.get('source')
        opd_appointment._source = source if source in [x[0] for x in AppointmentHistory.SOURCE_CHOICES] else ''
        opd_appointment._responsible_user = responsible_user
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


    def create_order(self, request, appointment_details, product_id, use_wallet=True):
        user = request.user
        balance = 0
        cashback_balance = 0

        if user and user.active_insurance and user.active_insurance.status == UserInsurance.ONHOLD:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'There is some problem, Please try again later'})

        if use_wallet:
            consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance
            cashback_balance = consumer_account.cashback

        total_balance = balance + cashback_balance
        resp = {}

        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            resp['is_agent'] = True

        insurance_effective_price = appointment_details['fees']

        can_use_insurance, insurance_id, insurance_fail_message = self.can_use_insurance(user, appointment_details)
        if can_use_insurance:
            appointment_details['insurance'] = insurance_id
            appointment_details['effective_price'] = appointment_details['fees']
            appointment_details['payment_type'] = models.OpdAppointment.INSURANCE

        elif appointment_details['payment_type'] == models.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp

        else:
            appointment_details['insurance'] = None

        appointment_action_data = copy.deepcopy(appointment_details)
        appointment_action_data = opdappointment_transform(appointment_action_data)

        account_models.Order.disable_pending_orders(appointment_action_data, product_id,
                                                    account_models.Order.OPD_APPOINTMENT_CREATE)

        if ((appointment_details['payment_type'] == models.OpdAppointment.PREPAID and
             total_balance < appointment_details.get("effective_price")) or resp['is_agent']):

            payable_amount = max(0, appointment_details.get("effective_price") - total_balance)
            required_amount = appointment_details.get("effective_price")
            cashback_amount = min(required_amount, cashback_balance)
            wallet_amount = 0
            if cashback_amount < required_amount:
                wallet_amount = min(balance, required_amount - cashback_amount)


            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.OPD_APPOINTMENT_CREATE,
                action_data=appointment_action_data,
                amount=payable_amount,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            appointment_details["payable_amount"] = payable_amount
            resp["status"] = 1
            resp['data'], resp["payment_required"] = payment_details(request, order)
            try:
                ops_email_data = dict()
                ops_email_data.update(order.appointment_details())
                ops_email_data["transaction_time"] = aware_time_zone(timezone.now())
                # EmailNotification.ops_notification_alert(ops_email_data, settings.OPS_EMAIL_ID,
                #                                          order.product_id,
                #                                          EmailNotification.OPS_PAYMENT_NOTIFICATION)
                # push_order_to_matrix.apply_async(
                #     ({'order_id': order.id, 'created_at': int(order.created_at.timestamp()),
                #       'timeslot': int(appointment_details['time_slot_start'].timestamp())},), countdown=5)

            except:
                pass
        else:
            wallet_amount = 0
            cashback_amount = 0

            if appointment_details['payment_type'] == models.OpdAppointment.PREPAID:
                cashback_amount = min(cashback_balance, appointment_details.get("effective_price"))
                wallet_amount = max(0, appointment_details.get("effective_price") - cashback_amount)

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.OPD_APPOINTMENT_CREATE,
                action_data=appointment_action_data,
                amount=0,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )

            appointment_object = order.process_order()
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {"id": appointment_object.id, "type": serializers.OpdAppointmentSerializer.DOCTOR_TYPE}

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

    def can_use_insurance(self, user, appointment_details):
        user_insurance_obj = UserInsurance.get_user_insurance(user)
        if not user_insurance_obj:
            return False, None, ''

        insurance_validate_dict = user_insurance_obj.validate_insurance(appointment_details)
        insurance_check = insurance_validate_dict['is_insured']
        insurance = insurance_validate_dict['insurance_id']
        fail_message = insurance_validate_dict['insurance_message']

        return insurance_check, insurance, fail_message
        # Check if appointment can be covered under insurance
        # also return a valid message         
        # return False, 'Not covered under insurance'

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
        queryset = models.OpdAppointment.objects.filter(Q(doctor__is_live=True, hospital__is_live=True)|
                                                        Q(doctor__source_type=Doctor.PROVIDER, hospital__source_type=models.Hospital.PROVIDER)).filter(
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
        doctor_mobile_live = auth_models.DoctorNumber.objects.filter(phone_number=request.user.phone_number, doctor__is_live=True)
        doctor = doctor_mobile_live.first().doctor if doctor_mobile_live.exists() else None
        if not doctor:
            doctor = request.user.doctor if hasattr(request.user, 'doctor') else None
        if not doctor:
            doctor_mobile_provider = auth_models.DoctorNumber.objects.filter(phone_number=request.user.phone_number, doctor__source_type=Doctor.PROVIDER)
            doctor = doctor_mobile_provider.first().doctor if doctor_mobile_provider.exists() else None
        if doctor and (doctor.is_live or doctor.source_type == Doctor.PROVIDER):
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

        provider_signup_lead = ProviderSignupLead.objects.filter(user=user).first()
        if provider_signup_lead:
            resp_data['consent'] = provider_signup_lead.is_docprime
            resp_data['role_type'] = provider_signup_lead.type
            resp_data['phone_number'] = provider_signup_lead.phone_number
            resp_data['email'] = provider_signup_lead.email
            resp_data['name'] = provider_signup_lead.name
            if not doctor:
                resp_data['source_type'] = Doctor.PROVIDER
            resp_data['is_provider_signup_lead'] = True
        else:
            resp_data['is_provider_signup_lead'] = False

        return Response(resp_data)

    def licence_update(self, request):
        serializer = serializers.DoctorLicenceBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        doctor = Doctor.objects.filter(Q(id=valid_data['doctor_id'].id,
                                       doctor_clinics__hospital__manageable_hospitals__user=request.user,
                                       doctor_clinics__hospital__manageable_hospitals__is_disabled=False),
                                       (Q(doctor_clinics__hospital__manageable_hospitals__permission_type=auth_models.GenericAdmin.APPOINTMENT)
                                        |
                                        Q(doctor_clinics__hospital__manageable_hospitals__super_user_permission=True))
                                       ).first()
        if not doctor:
            return Response({'error': 1}, status=status.HTTP_403_FORBIDDEN)

        try:
            doctor.license = valid_data['licence']
            doctor.save()
        except Exception as e :
            logger.error(str(e))
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status':1})


class DoctorProfileUserViewSet(viewsets.GenericViewSet):

    def prepare_response(self, response_data, selected_hospital, profile=None, product_id=None, coupon_code=None):
        # import operator
        # hospitals = sorted(response_data.get('hospitals'), key=itemgetter("hospital_id"))
        # [d['value'] for d in l if 'value' in d]
        hospital_ids = set(data['hospital_id'] for data in response_data.get('hospitals') if 'hospital_id' in data)
        doctor_clinic = DoctorClinic.objects.filter(hospital_id__in=hospital_ids).values('hospital_id').annotate(count=Count('doctor_id'))
        for hospital in response_data.get('hospitals'):
            for doctor_count in doctor_clinic:
                if doctor_count.get('hospital_id') == hospital.get('hospital_id'):
                    hospital['count'] = doctor_count.get('count')

        sorted_by_enable_booking = sorted(response_data.get('hospitals'), key=itemgetter('enabled_for_online_booking', 'count'),reverse=True)

        procedures = response_data.pop('procedures')
        availability = []
        coupon_recommender = CouponRecommender(self.request.user, profile, 'doctor', product_id, coupon_code, None)
        filters = dict()
        for key, group in groupby(sorted_by_enable_booking, lambda x: x['hospital_id']):
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
            hospital.pop("count", None)
            hospital.pop("discounted_fees", None)
            hospital['procedure_categories'] = procedures.get(key) if procedures else []

            filters['deal_price'] = hospital['deal_price']
            filters['doctor_id'] = response_data.get('id')
            filters['doctor_specializations_ids'] = response_data.get('doctor_specializations_ids', [])
            filters['hospital'] = dict()
            hospital_obj = filters['hospital']
            hospital_obj['id'] = hospital.get('hospital_id')
            hospital_obj['city'] = hospital.get('hospital_city')

            search_coupon = coupon_recommender.best_coupon(**filters)

            hospital['discounted_price'] = hospital['deal_price'] if not search_coupon else search_coupon.get_search_coupon_discounted_price(
            hospital['deal_price'])

            if key == selected_hospital:
                availability.insert(0, hospital)
            else:
                availability.append(hospital)
        response_data['hospitals'] = availability
        return response_data

    def construct_about_doctor(self, doctor, response_data, general_specialization, hospital):
        about_doctor = None
        person = None
        his_her = None
        doctor_assoc_list = list()
        members = None
        awards = list()
        hospital_obj = None
        specializations = list()
        if doctor.gender == 'f':
            person = 'She'
            his_her = 'her'
        elif doctor.gender == 'm':
            person = 'He'
            his_her = 'his'
        doc_spec = None
        startswith = None
        if hospital:
            doc_clinics_obj = doctor.doctor_clinics.filter(hospital_id=hospital.get('hospital_id'), doctor_id=doctor.id, hospital__is_live=True)
            if doc_clinics_obj:
                hospital_obj = doc_clinics_obj[0].hospital
        if doctor.name and general_specialization:
            about_doctor = 'Dr. ' + doctor.name
            if len(general_specialization) == 1:
                about_doctor += ' is a practising ' + general_specialization[0].name
            elif len(general_specialization) > 1:
                for data in general_specialization:
                    specializations.append(data.name)
                doc_spec = ', '.join(specializations[:-1])
                if specializations[-1].lower().startswith('a') or specializations[-1].lower().startswith('e') or \
                        specializations[-1].lower().startswith('i') or specializations[-1].lower().startswith('o') or \
                        specializations[-1].lower().startswith('u'):
                    startswith = 'an'
                else:
                    startswith = 'a'
                about_doctor += ' is a practising ' + doc_spec + ' and ' + startswith + ' ' + specializations[-1]
            if doctor.experience_years() and doctor.experience_years() > 0:
                about_doctor += ' with an experience of ' + str(doctor.experience_years()) + ' years'
            about_doctor += '.'
            if doctor.gender in ('m', 'f') and hospital_obj and hospital_obj.city:
                if hospital_obj.city:
                    about_doctor += ' ' + person + ' is located in ' + hospital_obj.city + '. '

        if doctor.name and hospital and  hospital_obj and hospital_obj.city and hospital_obj.state:
            if not about_doctor:
                about_doctor = 'Dr. ' + doctor.name
            else:
                about_doctor += '<br><br>Dr. ' + doctor.name
            if hospital_obj.city and hospital_obj.name:
                about_doctor += ' practices at the ' + hospital_obj.name + ' in ' + hospital_obj.city + '. '

            if hospital and hospital.get('hospital_name') and hospital.get('address'):
                about_doctor += 'The ' + hospital.get('hospital_name') + ' is situated at ' + hospital.get(
                    'address') + '. '

            doctor_assoc = doctor.associations.all()
            if doctor_assoc:
                for data in doctor_assoc:
                    doctor_assoc_list.append(data.name)
                # members = ' and '.join(doctor_assoc_list)

                if doctor_assoc_list:
                    if len(doctor_assoc_list) == 1:
                        members = doctor_assoc_list[0]
                    elif len(doctor_assoc_list) > 1:
                        members = ', '.join(doctor_assoc_list[:-1])
                        members += members + ' and ' + doctor_assoc_list[-1]
                about_doctor += doctor.name + ' is an esteemed member of ' + members + '.'

        doctor_qual = doctor.qualifications.all()
        if doctor_qual:
            if not about_doctor:
                about_doctor = ''
            else:
                about_doctor += '<br><br>'
            count = 0
            for data in doctor_qual:
                if count > 2:
                    count = 2
                qual_str = [' pursued ', ' completed ', ' has also done ']
                if data.qualification and data.qualification.name and data.college and data.college.name and data.passing_year:
                    about_doctor += person + qual_str[
                        count] + his_her + ' ' + data.qualification.name + ' in the year ' \
                                    + str(data.passing_year) + ' from ' + data.college.name + '. '
                    count = count + 1
        if doctor.name:
            if not about_doctor:
                about_doctor = ''
            else:
                about_doctor += '<br><br>'
            about_doctor += 'Dr. ' + doctor.name + ' is an experienced, skilled and awarded doctor in ' + his_her + ' field of specialization. '
            doc_awards_obj = doctor.awards.all()
            if doc_awards_obj:
                for data in doc_awards_obj:
                    awards.append(data.name)

            if awards:
                doc_awards = ', '.join(awards)
                about_doctor += doctor.name + ' has been awarded with ' + doc_awards + '. '

        doc_experience_details = response_data.get('experiences')
        if doc_experience_details:
            if not about_doctor:
                about_doctor = ''
            else:
                about_doctor += '<br><br>'
            if doc_experience_details[0].get('hospital') and doc_experience_details[0].get('start_year') and \
                    doc_experience_details[0].get('end_year'):
                about_doctor += person + ' worked at ' + doc_experience_details[0].get(
                    'hospital') + ' from ' + str(doc_experience_details[0].get('start_year')) + ' to ' + str(
                    doc_experience_details[0].get('end_year'))
            if len(doc_experience_details) > 1:
                exp_list = list()
                for data in doc_experience_details[1:-1]:
                    if data.get('hospital') and data.get('start_year') and data.get('end_year'):
                        exp_list.append(' from ' + str(data.get('start_year')) + ' to ' + str(
                            data.get('end_year')) + ' with ' + data.get('hospital'))
                if exp_list:
                    about_doctor += ', ' + ','.join(exp_list)
                if doc_experience_details[-1] and doc_experience_details[-1].get('hospital') and doc_experience_details[
                    -1].get('start_year') and doc_experience_details[-1].get('end_year'):
                    about_doctor += ' and from ' + str(doc_experience_details[-1].get('start_year')) + ' to ' + str(
                        doc_experience_details[-1].get('end_year')) + ' at ' + doc_experience_details[-1].get(
                        'hospital')
            about_doctor += '.'
        return about_doctor

    @transaction.non_atomic_requests
    @use_slave
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
                    return Response(status=status.HTTP_404_NOT_FOUND)

            entity_id = entity.entity_id
            response = self.retrieve(request, entity_id, entity)
            return response

        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    @use_slave
    def retrieve(self, request, pk, entity=None, *args, **kwargs):
        from ondoc.procedure.models import PotentialIpdLeadPracticeSpecialization
        serializer = serializers.DoctorDetailsRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get('appointment_id') and validated_data.get('cod_to_prepaid'):
            opd_app = OpdAppointment.objects.filter(id=validated_data.get('appointment_id'), payment_type=OpdAppointment.PREPAID)
            if opd_app:
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={"error": 'Appointment already created, Cannot Rebook.',
                                  "request_errors": {"message": 'Appointment already created, Cannot Rebook.'}})
        response_data = []
        category_ids = validated_data.get('procedure_category_ids', None)
        procedure_ids = validated_data.get('procedure_ids', None)
        selected_hospital = validated_data.get('hospital_id', None)
        profile_id = request.query_params.get('profile_id', None)
        product_id = request.query_params.get('product_id', None)
        coupon_code = request.query_params.get('coupon_code', None)
        doctor = (models.Doctor.objects
                  .prefetch_related('languages__language',
                                    'doctor_clinics__hospital__matrix_city',
                                    'doctor_clinics__procedures_from_doctor_clinic__procedure__parent_categories_mapping',
                                    'qualifications__qualification',
                                    'qualifications__specialization',
                                    'qualifications__college',
                                    'doctorpracticespecializations__specialization',
                                    'images',
                                    'rating',
                                    'associations',
                                    'awards',
                                    'doctor_clinics__hospital__hospital_place_details'
                                    )
                  .filter(pk=pk).first())
        # if not doctor or not is_valid_testing_data(request.user, doctor):
        #     return Response(status=status.HTTP_400_BAD_REQUEST)
        if not doctor or (not doctor.is_live and not doctor.is_internal):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not entity:
            entity = EntityUrls.objects.filter(entity_id=pk, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE, is_valid='t')
            if len(entity) > 0:
                entity = entity[0]
            else:
                entity = None    

        selected_procedure_ids, other_procedure_ids = get_selected_and_other_procedures(category_ids, procedure_ids, doctor, all=True)

        general_specialization = []
        spec_ids = list()
        spec_url_dict = dict()

        all_potential_spec = set(PotentialIpdLeadPracticeSpecialization.objects.all().values_list('practice_specialization', flat=True))
        is_congot = False

        for dps in doctor.doctorpracticespecializations.all():
            general_specialization.append(dps.specialization)
            spec_ids.append(dps.specialization.id)
            if dps.specialization.id in all_potential_spec:
                is_congot = True

        if spec_ids and entity:
            spec_urls = EntityUrls.objects.filter(specialization_id__in=spec_ids, sublocality_value=entity.sublocality_value,
                                          locality_value=entity.locality_value, is_valid=True, entity_type='Doctor', url_type='SEARCHURL')
            for su in spec_urls:
                spec_url_dict[su.specialization_id] = su.url

        serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False,
                                                                     context={"request": request
                                                                         ,
                                                                              "selected_procedure_ids": selected_procedure_ids
                                                                         ,
                                                                              "other_procedure_ids": other_procedure_ids
                                                                         , "category_ids": category_ids
                                                                         , "hospital_id": selected_hospital
                                                                         , "entity":entity
                                                                         ,  "spec_url_dict":spec_url_dict
                                                                              })

        response_data = self.prepare_response(serializer.data, selected_hospital, profile_id, product_id, coupon_code)

        hospital = None
        response_data['about_web'] = None
        response_data['is_congot'] = is_congot
        google_rating = dict()
        date = None

        if response_data and response_data.get('hospitals'):
            hospital = response_data.get('hospitals')[0]

        # for dps in doctor.doctorpracticespecializations.all():
        #     general_specialization.append(dps.specialization)
        if general_specialization:
            general_specialization = sorted(general_specialization, key=operator.attrgetter('doctor_count'),
                                            reverse=True)

        if not doctor.about and doctor.gender:
            about_doctor = self.construct_about_doctor(doctor, response_data, general_specialization, hospital)
            if about_doctor:
                response_data['about_web'] = '<p>' + about_doctor + '</p>'

        else:
            response_data['about'] = doctor.about
            response_data['about_web'] = doctor.about

        if entity:
            response_data['url'] = entity.url
            if entity.breadcrumb:
                breadcrumb = entity.breadcrumb
                breadcrumb = [{'url': '/', 'title': 'Home'}] + breadcrumb
                breadcrumb.append({'title': 'Dr. ' + doctor.name})
                response_data['breadcrumb'] = breadcrumb
            else:
                breadcrumb = [{'url':'/', 'title': 'Home'}, {'title':'Dr. ' + doctor.name}]
                response_data['breadcrumb'] = breadcrumb

        enabled_for_online_booking = False
        response_data['doctors'] = None
        doctor_clinics = doctor.doctor_clinics.all()
        if len(doctor_clinics)>0 and doctor.enabled_for_online_booking:
            for dc in doctor_clinics:
                if dc.enabled and dc.enabled_for_online_booking and dc.hospital.enabled_for_online_booking and dc.hospital.is_live:
                    enabled_for_online_booking = True

        if not enabled_for_online_booking:

            parameters = dict()
            specialization_id = ''
            doc = DoctorListViewSet()
            doctors_url = None
            spec_breadcrumb = None
            lat = None
            long = None

            if hospital:
                lat = hospital.get('lat')
                long = hospital.get('long')
            else:
                hospital = doctor.hospitals.first()
                if hospital and hospital.location:
                    lat = hospital.location.coords[1]
                    long = hospital.location.coords[0]

            if general_specialization and lat and long:
                specialization_id = general_specialization[0].pk

                parameters['specialization_ids'] = str(specialization_id)                
                parameters['latitude'] = lat
                parameters['longitude'] = long
                parameters['doctor_suggestions'] = 1
                
                kwargs['parameters'] = parameters
                response_data['doctors'] = doc.list(request, **kwargs)
                if response_data.get('doctors'):
                    breadcrumb = entity.breadcrumb if entity else None
                    if breadcrumb:
                        spec_breadcrumb = breadcrumb[-1]
                        if spec_breadcrumb and spec_breadcrumb.get('url') and not spec_breadcrumb.get('url').startswith('doctors') and spec_breadcrumb.get('url').endswith('sptlitcit'):
                                doctors_url = spec_breadcrumb.get('url')
                    response_data['doctors']['doctors_url'] = doctors_url

                    # response_data['doctors']['doctors_url'] = '/opd/searchresults?specializations=%s&lat=%s&long=%s' % (str(specialization_id), hospital.get('lat'), hospital.get('long'))
                else:
                    response_data['doctors']['doctors_url'] = None

        hospital = None
        potential_ipd = False
        all_cities = []
        all_ipd_cities = set(PotentialIpdCity.objects.all().values_list('city', flat=True))
        if doctor_clinics:
            for doc_clinic in doctor_clinics:
                if doc_clinic and doc_clinic.hospital:
                    if doc_clinic.hospital.is_live and doc_clinic.hospital.matrix_city and doc_clinic.hospital.matrix_city.id in all_ipd_cities:
                        potential_ipd = True
                    hospital = doc_clinic.hospital
                    if not all_cities:
                        all_cities = hospital.get_all_cities()
                    hosp_reviews_dict = dict()
                    hosp_reviews_dict[hospital.pk] = dict()
                    hosp_reviews_dict[hospital.pk]['google_rating'] = list()
                    ratings_graph = None
                    hosp_reviews = hospital.hospital_place_details.all()
                    # if hosp_reviews:
                    reviews_data = dict()
                    reviews_data['user_reviews'] = None
                    if hosp_reviews:
                        reviews_data['user_reviews'] = hosp_reviews[0].reviews.get('user_reviews')
                    reviews_data['user_avg_rating'] = hospital.google_avg_rating
                    reviews_data['user_ratings_total'] = hospital.google_ratings_count
                    ratings_graph = GoogleRatingsGraphSerializer(reviews_data, many=False,
                                                                 context={"request": request})

                    if reviews_data and reviews_data.get('user_reviews'):
                        for data in reviews_data.get('user_reviews'):
                            if data.get('time'):
                                date = time.strftime("%d %b %Y", time.gmtime(data.get('time')))

                            hosp_reviews_dict[hospital.pk]['google_rating'].append(
                                {'compliment': None, 'date': date, 'id': hosp_reviews[0].pk, 'is_live': hospital.is_live,
                                 'ratings': data.get('rating'),
                                 'review': data.get('text'), 'user': None, 'user_name': data.get('author_name')
                                 })
                    if reviews_data.get('user_avg_rating') and reviews_data.get('user_ratings_total'):
                        if not hosp_reviews_dict[hospital.pk].get('google_rating'):
                            hosp_reviews_dict[hospital.pk]['google_rating'].append(
                                {'compliment': None, 'date': None, 'id': None,
                                 'is_live': hospital.is_live,
                                 'ratings':None,
                                 'review': None, 'user': None, 'user_name': None
                                 })
                        hosp_reviews_dict[hospital.pk]['google_rating_graph'] = ratings_graph.data if ratings_graph else None
                    else:
                        hosp_reviews_dict[hospital.pk]['google_rating'] = None
                        hosp_reviews_dict[hospital.pk]['google_rating_graph'] = None

                    google_rating.update(hosp_reviews_dict)

        cod_to_prepaid = dict()
        doctor_id = None
        if pk:
            doctor_id = pk

        if validated_data and validated_data.get('cod_to_prepaid') and validated_data.get('appointment_id') and validated_data.get('hospital_id') and doctor_id:
            opd_appoint = OpdAppointment.objects.filter(id=validated_data['appointment_id'])
            if opd_appoint:
                opd_appoint = opd_appoint[0]
                cod_to_prepaid['profile_id'] = opd_appoint.profile.id if opd_appoint.profile else None
                cod_to_prepaid['time_slot_start'] = opd_appoint.time_slot_start
                cod_to_prepaid['time_slot_end'] = opd_appoint.time_slot_end
                cod_to_prepaid['user_id'] = opd_appoint.user.id if opd_appoint.user else None
                cod_to_prepaid['fees'] = opd_appoint.fees
                cod_to_prepaid['effective_price'] = opd_appoint.effective_price
                cod_to_prepaid['mrp'] = opd_appoint.mrp
                cod_to_prepaid['payment_status'] = opd_appoint.payment_status
                cod_to_prepaid['payment_type'] = opd_appoint.payment_type
                cod_to_prepaid['is_cod_to_prepaid'] = opd_appoint.is_cod_to_prepaid
                cod_to_prepaid['formatted_date'] = opd_appoint.time_slot_start.date() if opd_appoint.time_slot_start else None
                day = opd_appoint.time_slot_start.weekday()
                doc_clinic_timing = DoctorClinicTiming.objects.filter(doctor_clinic__doctor = doctor_id, doctor_clinic__hospital=validated_data.get('hospital_id'), day = day)
                if doc_clinic_timing:
                    cod_to_prepaid['deal_price'] = doc_clinic_timing[0].deal_price

        response_data['google_rating'] = google_rating
        response_data['potential_ipd'] = potential_ipd
        response_data['all_cities'] = all_cities
        response_data['cod_to_prepaid'] = cod_to_prepaid
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
            return (models.PrescriptionFile.objects
                    .select_related('prescription', 'prescription__appointment', 'prescription__appointment__doctor')
                    .prefetch_related('prescription__appointment__doctor__manageable_doctors',
                                      'prescription__appointment__hospital__manageable_hospitals')
                    .filter(
                        Q(Q(prescription__appointment__doctor__manageable_doctors__user=user,
                          prescription__appointment__doctor__manageable_doctors__hospital=F(
                              'prescription__appointment__hospital'),
                          prescription__appointment__doctor__manageable_doctors__permission_type__in=[
                              auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                          prescription__appointment__doctor__manageable_doctors__is_disabled=False) |
                        Q(prescription__appointment__doctor__manageable_doctors__user=user,
                          prescription__appointment__doctor__manageable_doctors__hospital__isnull=True,
                          prescription__appointment__doctor__manageable_doctors__permission_type__in=[
                              auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                          prescription__appointment__doctor__manageable_doctors__is_disabled=False) |
                        Q(prescription__appointment__hospital__manageable_hospitals__user=user,
                          prescription__appointment__hospital__manageable_hospitals__doctor__isnull=True,
                          prescription__appointment__hospital__manageable_hospitals__permission_type__in=[
                              auth_models.GenericAdmin.APPOINTMENT, auth_models.GenericAdmin.ALL],
                          prescription__appointment__hospital__manageable_hospitals__is_disabled=False)) |
                        Q(
                            Q(prescription__appointment__doctor__manageable_doctors__user=user,
                              prescription__appointment__doctor__manageable_doctors__super_user_permission=True,
                              prescription__appointment__doctor__manageable_doctors__is_disabled=False,
                              prescription__appointment__doctor__manageable_doctors__entity_type=GenericAdminEntity.DOCTOR, ) |
                            Q(prescription__appointment__hospital__manageable_hospitals__user=user,
                              prescription__appointment__hospital__manageable_hospitals__super_user_permission=True,
                              prescription__appointment__hospital__manageable_hospitals__is_disabled=False,
                              prescription__appointment__hospital__manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL)
                        )
                    )
                    .distinct())
            # return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)
        elif request.user.user_type == User.CONSUMER:
            return models.PrescriptionFile.objects.filter(prescription__appointment__user=request.user)
        else:
            return models.PrescriptionFile.objects.none()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        appointment = request.query_params.get("appointment")
        if not appointment:
            return Response(status=400)
        queryset = self.get_queryset().filter(prescription__appointment=int(appointment))
        serializer = serializers.PrescriptionFileSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = serializers.PrescriptionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        app = validated_data['appointment_obj']

        #resp_data = list()
        if validated_data.get('type') == serializers.PrescriptionSerializer.OFFLINE:
            pres_models.OfflinePrescription.objects.create(
                name=validated_data.get('name'),
                prescription_details=validated_data.get('prescription_details'),
                appointment=validated_data.get('appointment_obj')
            )
            resp_data = {'id': app.id,
                         'doctor': serializers.AppointmentRetrieveDoctorSerializer(app.doctor).data,
                         'time_slot_start': app.time_slot_start,
                         'hospital': serializers.HospitalModelSerializer(app.hospital).data,
                         'profile': OfflinePatientSerializer(app.user).data,
                         'prescriptions': app.get_prescriptions(request)
                         }

        else:
            if not self.prescription_permission(request.user, app):
                return Response({'msg': "You don't have permissions to manage this appointment"}, status=status.HTTP_403_FORBIDDEN)

            prescription_obj = models.Prescription.objects.filter(appointment=app).first()
            if prescription_obj:
                prescription = prescription_obj
            else:
                prescription = models.Prescription.objects.create(appointment=validated_data.get('appointment_obj'),
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
            # resp_data = prescription_file_serializer.data
            resp_data = serializers.DoctorAppointmentRetrieveSerializer(validated_data.get('appointment_obj'),
                                                                             context={'request': request}).data
            if validated_data.get('appointment_obj'):
                resp_data['prescriptions'] = validated_data.get('appointment_obj').get_prescriptions(request)

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
        return auth_models.GenericAdmin.objects.filter(Q(user=user, is_disabled=False),
                                                       Q(
                                                           Q(hospital=appointment.hospital)
                                                            |
                                                           Q(doctor=appointment.doctor)
                                                       )
                                                       ).exists()


class SearchedItemsViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        name = request.query_params.get("name")
        if not name:
            return Response({"conditions": [], "specializations": []})
        medical_conditions = models.CommonMedicalCondition.objects.select_related('condition').filter(
            Q(condition__search_key__icontains=' ' + name) |
            Q(condition__search_key__istartswith=name)
        ).annotate(search_index=StrIndex('condition__search_key',
                                         Value(name))).order_by('search_index')[:5]
        conditions_serializer = serializers.MedicalConditionSerializer(medical_conditions,
                                                                       many=True, context={'request': request})

        specializations = models.PracticeSpecialization.objects.filter(
            Q(search_key__icontains=' ' + name) |
            Q(search_key__istartswith=name)).annotate(search_index=StrIndex('search_key', Value(name))).order_by(
            'search_index').values("id", "name")[:5]

        procedures = Procedure.objects.annotate(no_of_parent_categories=Count('parent_categories_mapping')).filter(
            Q(search_key__icontains=' ' + name) |
            Q(search_key__istartswith=name), is_enabled=True, no_of_parent_categories__gt=0).annotate(
            search_index=StrIndex('search_key', Value(name))
            ).order_by('search_index')[:5]

        serializer = ProcedureInSerializer(procedures, many=True)
        procedures = serializer.data

        # procedure_categories = ProcedureCategory.objects.filter(
        #     Q(search_key__icontains=name) |
        #     Q(search_key__icontains=' ' + name) |
        #     Q(search_key__istartswith=name)).annotate(search_index=StrIndex('search_key', Value(name))
        #                                               ).order_by('search_index').values("id", "name")[:5]

        return Response({"conditions": conditions_serializer.data, "specializations": specializations,
                         "procedures": procedures
                            # , "procedure_categories": procedure_categories
                         })


    @transaction.non_atomic_requests
    @use_slave
    def common_conditions(self, request):
        city = None
        serializer = CommonConditionsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        city = city_match(validated_data.get('city'))
        spec_urls = dict()
        count = request.query_params.get('count', 10)
        count = int(count)
        if count <= 0:
            count = 10
        # medical_conditions = models.CommonMedicalCondition.objects.select_related('condition').prefetch_related('condition__specialization').all().order_by(
        #     "-priority")[:count]
        # conditions_serializer = serializers.MedicalConditionSerializer(medical_conditions, many=True,
        #                                                                context={'request': request})

        common_specializations = models.CommonSpecialization.get_specializations(count)
        common_spec_urls = list()

        if city:
            for data in common_specializations:
                if data.specialization and data.specialization.name:
                    common_spec_urls.append(slugify(data.specialization.name + '-in-' + city + '-sptcit'))

            entity_urls = EntityUrls.objects.filter(sitemap_identifier='SPECIALIZATION_CITY',
                                                    is_valid=True, url__in=common_spec_urls)

            for data in entity_urls:
                spec_urls[data.specialization_id] = data.url

        specializations_serializer = serializers.CommonSpecializationsSerializer(common_specializations, many=True,
                                                                                 context={'request': request,
                                                                                          'city': city,
                                                                                          'spec_urls': spec_urls})

        # common_procedure_categories = CommonProcedureCategory.objects.select_related('procedure_category').filter(
        #     procedure_category__is_live=True).all().order_by("-priority")[:10]
        # common_procedure_categories_serializer = CommonProcedureCategorySerializer(common_procedure_categories,
        #                                                                            many=True)
        #
        # common_procedures = CommonProcedure.objects.select_related('procedure').filter(
        #     procedure__is_enabled=True).all().order_by("-priority")[:10]
        # common_procedures_serializer = CommonProcedureSerializer(common_procedures, many=True)

        common_ipd_procedures = CommonIpdProcedure.objects.select_related('ipd_procedure').filter(
            ipd_procedure__is_enabled=True).all().order_by("-priority")[:10]
        common_ipd_procedures = list(common_ipd_procedures)
        common_ipd_procedure_ids = [t.ipd_procedure.id for t in common_ipd_procedures]
        ipd_entity_dict = {}
        if city:
            ipd_entity_qs = EntityUrls.objects.filter(ipd_procedure_id__in=common_ipd_procedure_ids,
                                                      sitemap_identifier='IPD_PROCEDURE_CITY',
                                                      is_valid=True,
                                                      locality_value__iexact=city.lower()).annotate(
                ipd_id=F('ipd_procedure_id')).values('ipd_id', 'url')
            ipd_entity_dict = {x.get('ipd_id'): x.get('url') for x in ipd_entity_qs}
        common_ipd_procedures_serializer = CommonIpdProcedureSerializer(common_ipd_procedures, many=True,
                                                                        context={'entity_dict': ipd_entity_dict,
                                                                                 'request': request})

        top_hospitals_data = Hospital.get_top_hospitals_data(request, validated_data.get('lat'), validated_data.get('long'))

        categories = []
        # need_to_hit_query = True
        #
        # if request.user and request.user.is_authenticated and not hasattr(request, 'agent') and request.user.active_insurance and request.user.active_insurance.insurance_plan and request.user.active_insurance.insurance_plan.plan_usages:
        #     if request.user.active_insurance.insurance_plan.plan_usages.get('package_disabled'):
        #         need_to_hit_query = False
        #
        # categories_serializer = None
        #
        # if need_to_hit_query:
        #     categories = LabTestCategory.objects.filter(is_live=True, is_package_category=True,
        #                                                 show_on_recommended_screen=True).order_by('-priority')[:15]
        #
        #     categories_serializer = CommonCategoriesSerializer(categories, many=True, context={'request': request})

        return Response({"conditions": [],
                         "specializations": specializations_serializer.data,
                         "procedure_categories": [],
                         "procedures": [],
                         "ipd_procedures": common_ipd_procedures_serializer.data,
                         "top_hospitals": top_hospitals_data,
                         'package_categories': common_package_category(self, request)})

    @transaction.non_atomic_requests
    def top_hospitals(self, request):
        logged_in_user = request.user
        serializer = CommonConditionsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
#        vip_user = None
 #       from_vip_page = True

#        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
#            vip_user = logged_in_user.active_plus_user
#        top_hospitals_data = Hospital.get_top_hospitals_data(request, validated_data.get('lat'), validated_data.get('long'), vip_user, from_vip_page)


        top_hospitals_data = Hospital.get_top_hospitals_data(request, validated_data.get('lat'), validated_data.get('long'))

        return Response({"top_hospitals": top_hospitals_data})


class DoctorListViewSet(viewsets.GenericViewSet):
    queryset = models.Doctor.objects.none()

    @transaction.non_atomic_requests
    def list_by_url(self, request, *args, **kwargs):
        url = request.GET.get('url', None)
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        rating = None
        reviews = None

        entity_url_qs = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                           entity_type='Doctor').order_by('-sequence')
        if len(entity_url_qs) > 0:
            entity = entity_url_qs[0]
            if not entity.is_valid:
                valid_qs = EntityUrls.objects.filter(is_valid=True, specialization_id=entity.specialization_id,
                                                     locality_id=entity.locality_id,
                                                     sublocality_id=entity.sublocality_id,
                                                     ipd_procedure_id=entity.ipd_procedure_id,
                                                     sitemap_identifier=entity.sitemap_identifier).order_by('-sequence')

                if valid_qs.exists():
                    corrected_url = valid_qs.first().url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

            if entity.sitemap_identifier =='DOCTORS_LOCALITY_CITY':
                default_rating_obj = DefaultRating.objects.filter(url=url).first()
                if not default_rating_obj:
                    rating = round(random.uniform(3.5, 4.9),1)
                    reviews = random.randint(100, 125)
                    DefaultRating.objects.create(ratings=rating, reviews=reviews, url=url)
                else:
                    rating = default_rating_obj.ratings
                    reviews = default_rating_obj.reviews

            elif entity.sitemap_identifier == 'SPECIALIZATION_LOCALITY_CITY':
                default_rating_obj = DefaultRating.objects.filter(url=url).first()
                if not default_rating_obj:
                    rating = round(random.uniform(3.5, 4.9), 1)
                    reviews = random.randint(10, 25)
                    DefaultRating.objects.create(ratings=rating, reviews=reviews, url=url)
                else:
                    rating = default_rating_obj.ratings
                    reviews = default_rating_obj.reviews

            extras = entity.additional_info
            if extras:
                # kwargs['specialization_id'] = entity.specialization_id
                # kwargs['url'] = url
                kwargs['parameters'] = doctor_query_parameters(entity, request.query_params)
                kwargs['ratings'] = rating
                kwargs['reviews'] = reviews
                kwargs['entity'] = entity
                response = self.list(request, **kwargs)
                return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    @use_slave
    def list(self, request, *args, **kwargs):
        if (request.query_params.get('procedure_ids') or request.query_params.get('procedure_category_ids')) \
                and request.query_params.get('is_insurance'):
            return Response({"result": [], "count": 0,
                         'specializations': [], 'conditions': [], "seo": {},
                         "breadcrumb": [], 'search_content': "",
                         'procedures': [], 'procedure_categories': []})

        parameters = request.query_params
        if kwargs.get("parameters"):
            parameters = kwargs.get("parameters")
        restrict_result_count = parameters.get('restrict_result_count', None)
        serializer = serializers.DoctorListSerializer(data=parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        specialization_id = None
        # if kwargs.get('extras'):
        #     validated_data['extras'] = kwargs['extras']
        if kwargs.get('entity'):
            entity = kwargs.get('entity')
            validated_data['url'] = entity.url
            validated_data['locality_value'] = entity.locality_value if entity.locality_value else None
            validated_data['sublocality_value'] = entity.sublocality_value if entity.sublocality_value else None
            validated_data['specialization'] = entity.specialization if entity.specialization else None
            validated_data['sublocality_latitude'] = entity.sublocality_latitude if entity.sublocality_latitude else None
            validated_data['sublocality_longitude'] = entity.sublocality_longitude if entity.sublocality_longitude else None
            validated_data['locality_latitude'] = entity.locality_latitude if entity.locality_latitude else None
            validated_data['locality_longitude'] = entity.locality_longitude if entity.locality_longitude else None
            validated_data['breadcrumb'] = entity.breadcrumb if entity.breadcrumb else None
            validated_data['sitemap_identifier'] = entity.sitemap_identifier if entity.sitemap_identifier else None
            validated_data['ipd_procedure'] = entity.ipd_procedure if entity.ipd_procedure else None
            specialization_id = entity.specialization_id if entity.specialization_id else None

        if kwargs.get('ratings'):
            validated_data['ratings'] = kwargs['ratings']
        if kwargs.get('reviews'):
            validated_data['reviews'] = kwargs['reviews']

        specialization_dynamic_content = ''
        top_content = None
        bottom_content = None

        ratings = None
        reviews = None
        result_count = 0

        # Insurance check for logged in user
        logged_in_user = request.user
        insurance_threshold = InsuranceThreshold.objects.all().order_by('-opd_amount_limit').first()
        insurance_data_dict = {
            'is_user_insured': False,
            'insurance_threshold_amount': insurance_threshold.opd_amount_limit if insurance_threshold else 5000
        }
        vip_data_dict = {
            'is_vip_member': False,
            'cover_under_vip': False,
            'vip_utilization': {},
            'is_enable_for_vip': False
        }

        vip_user = None

        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
            vip_user = logged_in_user.active_plus_user
            user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
            if user_insurance and user_insurance.is_valid() and not logged_in_user.active_plus_user:
                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                if insurance_threshold:
                    insurance_data_dict['insurance_threshold_amount'] = 0 if insurance_threshold.opd_amount_limit is None else \
                        insurance_threshold.opd_amount_limit
                    insurance_data_dict['is_user_insured'] = True
            if logged_in_user.active_plus_user:
                utilization_dict = logged_in_user.active_plus_user.get_utilization

                vip_data_dict['vip_utilization'] = utilization_dict
                vip_data_dict['is_vip_member'] = True
                vip_data_dict['cover_under_vip'] = False
                vip_data_dict['is_enable_for_vip'] = False
        validated_data['vip_user'] = vip_user
        validated_data['insurance_threshold_amount'] = insurance_data_dict['insurance_threshold_amount']
        validated_data['is_user_insured'] = insurance_data_dict['is_user_insured']

        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            query_string['query'] = paginate_raw_query(request, query_string['query'])
            db = DatabaseInfo.DEFAULT
            if settings.USE_SLAVE_DB:
                db = DatabaseInfo.SLAVE

            doctor_search_result = RawSql(query_string.get('query'), query_string.get('params'), db).fetch_all()

            if doctor_search_result:
                result_count = doctor_search_result[0]['result_count']
            # sa
            # saved_search_result = models.DoctorSearchResult.objects.create(results=doctor_search_result,
            #                                                                result_count=result_count)
        else:
            saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))
        # doctor_ids = paginate_queryset([data.get("doctor_id") for data in doctor_search_result], request)
        # temp_hospital_ids = paginate_queryset([data.get("hospital_id") for data in doctor_search_result], request)
        doctor_ids = [data.get("doctor_id") for data in doctor_search_result]
        temp_hospital_ids = [data.get("hospital_id") for data in doctor_search_result]
        hosp_entity_dict, hosp_locality_entity_dict = Hospital.get_hosp_and_locality_dict(temp_hospital_ids,
                                                                                          EntityUrls.SitemapIdentifier.DOCTORS_LOCALITY_CITY)
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(doctor_ids)])
        doctor_data = models.Doctor.objects.filter(
            id__in=doctor_ids).prefetch_related("hospitals", "doctor_clinics", "doctor_clinics__availability",
                                                "doctor_clinics__hospital",
                                                "doctorpracticespecializations", "doctorpracticespecializations__specialization",
                                                "images",
                                                "doctor_clinics__procedures_from_doctor_clinic__procedure__parent_categories_mapping",
                                                "qualifications__qualification","qualifications__college",
                                                "qualifications__specialization",
                                                "doctor_clinics__hospital__hospital_place_details", "rating"
                                                ).order_by(preserved)

        response = doctor_search_helper.prepare_search_response(doctor_data, doctor_search_result, request,
                                                                insurance_data=insurance_data_dict,
                                                                vip_data=vip_data_dict,
                                                                hosp_entity_dict=hosp_entity_dict,
                                                                hosp_locality_entity_dict=hosp_locality_entity_dict)

        entity_ids = [doctor_data['id'] for doctor_data in response]

        entity_data = dict()
        entity = EntityUrls.objects.filter(entity_id__in=entity_ids, sitemap_identifier='DOCTOR_PAGE',
                                           is_valid=True).values('entity_id', 'url', 'breadcrumb', 'location')
        spec_locality_url = None
        for data in entity:
            entity_data[data['entity_id']] = dict()
            entity_data[data['entity_id']]['url'] = data['url']
            #id_url_dict[data['entity_id']] = data['url']
            breadcrumb = data.get('breadcrumb')
            if breadcrumb:
                spec_locality_breadcrumb = breadcrumb[-1]
                spec_locality_url = spec_locality_breadcrumb.get('url')
                if not spec_locality_url.startswith('doctors') and spec_locality_url.endswith('sptlitcit'):
                    entity_data[data['entity_id']]['parent_url'] = spec_locality_url
                    entity_data[data['entity_id']]['location'] = data.get('location')

        title = ''
        description = ''
        seo = None
        breadcrumb = None
        ratings_title = ''
        specialization_name = None
        canonical_url = None
        url = None
        # if False and (validated_data.get('extras') or validated_data.get('specialization_ids')):
        temp_ipd_procedures = []
        if validated_data.get('ipd_procedure_ids'):
            temp_ipd_procedures = IpdProcedure.objects.filter(id__in=validated_data.get('ipd_procedure_ids', []))
        if validated_data.get('locality_value') or validated_data.get('sublocality_value'):
            location = None
            # breadcrumb_sublocality = None
            # breadcrumb_locality = None
            city = None
            breadcrumb = None
            locality = ''
            sublocality = ''
            specialization = None
            breadcrumb_locality_url = None


            if validated_data.get('locality_value'):
                locality = validated_data.get('locality_value')
                city = locality
            if validated_data.get('sublocality_value'):
                sublocality = validated_data.get('sublocality_value')
                if sublocality:
                    locality = sublocality + ' ' + locality

            # if validated_data.get('extras') and validated_data.get('extras').get('location_json'):
            #     if validated_data.get('extras').get('location_json').get('locality_value'):
            #         locality = validated_data.get('extras').get('location_json').get('locality_value')
            #         breadcrumb_locality = locality
            #         city = locality
            #     if validated_data.get('extras').get('location_json').get('sublocality_value'):
            #         sublocality = validated_data.get('extras').get('location_json').get('sublocality_value')
            #         if sublocality:
            #             breadcrumb_sublocality = sublocality
            #             locality = sublocality + ' ' + locality
            #     if validated_data.get('extras').get('location_json').get('breadcrum_url'):
            #         breadcrumb_locality_url = validated_data.get('extras').get('location_json').get('breadcrum_url')
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

            if validated_data.get('specialization'):
                specialization = validated_data.get('specialization')

            # if validated_data.get('extras') and validated_data.get('extras').get('specialization'):
            #     specializations = validated_data.get('extras').get('specialization')

            if validated_data.get('sitemap_identifier') == 'IPD_PROCEDURE_DOCTOR_CITY':
                title = '{ipd_procedure_name} Doctors in {city} | Best {ipd_procedure_name} Specialists'.format(
                    ipd_procedure_name=validated_data.get('ipd_procedure'), city=city)
                description = '{ipd_procedure_name} Doctors in {city} : Check {ipd_procedure_name} doctors in {city}. View address, reviews, cost estimate and more at Docprime.'.format(
                    ipd_procedure_name=validated_data.get('ipd_procedure'), city=city)

            if validated_data.get('sitemap_identifier') == 'SPECIALIZATION_CITY':
                title, description, ratings_title = self.get_spec_city_title_desc(specialization_id, city, specialization)

            elif validated_data.get('sitemap_identifier') == 'SPECIALIZATION_LOCALITY_CITY':
                title = specialization
                description = specialization
                if locality:
                    title += ' in ' + locality
                    description += ': Book best ' + specialization + '\'s appointment online ' + 'in ' + locality
                    ratings_title = title
                    title += ' | Book & Get Best Deal'
                    description += ' and get upto 50% off. View Address, fees and more for doctors '
                    description += 'in ' + city + '.'

            elif validated_data.get('sitemap_identifier') in ('DOCTORS_CITY', 'DOCTORS_LOCALITY_CITY'):
                title = 'Doctors'
                description = 'Doctors'
                if locality:
                    title += ' in '  + locality
                    description += ' in ' +locality
                if locality:
                    if sublocality == '':

                        description += ': Book best ' + 'Doctor' + ' appointment online ' + 'in ' + city
                    else:

                        description += ': Book best ' + 'Doctor' + ' appointment online ' + 'in '+ locality

                ratings_title = title
                title += ' | Book Doctors Online & Get Best Deal'

                description += ' and get upto 50% off. View Address, fees and more for doctors '
                if locality:
                    description += 'in '+ city
                description += '.'

            breadcrumb = validated_data.get('breadcrumb')

            if breadcrumb:
                breadcrumb = [{'url': '/', 'title': 'Home'}] + breadcrumb
            else:
                breadcrumb = [{'url': '/', 'title': 'Home'}]

            if validated_data.get('sitemap_identifier') == 'SPECIALIZATION_CITY':
                breadcrumb.append({'title': validated_data.get('specialization') + ' in ' + validated_data.get('locality_value'), 'url': None})
            elif validated_data.get('sitemap_identifier') == 'SPECIALIZATION_LOCALITY_CITY' and validated_data.get('sublocality_value'):
                breadcrumb.append({'title': validated_data.get('specialization') + ' in ' +
                                 validated_data.get('sublocality_value') + ' ' + validated_data.get('locality_value'), 'url': None})
            elif validated_data.get('sitemap_identifier') == 'DOCTORS_LOCALITY_CITY' and validated_data.get('sublocality_value'):
                breadcrumb.append({'title': 'Doctors in ' + validated_data.get('sublocality_value') + ' ' + validated_data.get('locality_value'), 'url': None})
            elif validated_data.get('sitemap_identifier') == 'IPD_PROCEDURE_DOCTOR_CITY':
                breadcrumb.append({'title': 'Procedures', 'url': 'ipd-procedures'})
                breadcrumb.append({'title': '{} Doctors in {}'.format(validated_data.get('ipd_procedure'),
                                                                      validated_data.get('locality_value')),
                                   'url': None})
            else:
                breadcrumb.append({'title': 'Doctors in ' + validated_data.get('locality_value'), 'url': None})

            # if breadcrumb_sublocality:
            #     breadcrumb =[ {
            #     'name': breadcrumb_locality,
            #     'url': breadcrumb_locality_url
            #     },
            #      {
            #             'name': breadcrumb_sublocality,
            #             'url': validated_data.get('url')
            #         }
            #     ]

            if title or description:
                if locality:
                    if not sublocality:
                        location = city
                    else:
                        location = locality
            if validated_data.get('sublocality_latitude', None):
                latitude = validated_data.get('sublocality_latitude')
                longitude = validated_data.get('sublocality_longitude')
            else:

                latitude = validated_data.get('locality_latitude', None)
                longitude = validated_data.get('locality_longitude', None)


            # if validated_data.get('extras', {}).get('location_json', {}).get('sublocality_latitude', None):
            #     latitude = validated_data.get('extras').get('location_json').get('sublocality_latitude')
            #     longitude = validated_data.get('extras').get('location_json').get('sublocality_longitude')
            # else:
            #     latitude = validated_data.get('extras', {}).get('location_json', {}).get('locality_latitude', None)
            #     longitude = validated_data.get('extras', {}).get('location_json', {}).get('locality_longitude', None)

            # seo = {
            #     "title": title,
            #     "description": description,
            #     "location" : location
            #     }
            search_url = validated_data.get('url')
            if search_url:
                object = NewDynamic.objects.filter(url_value=search_url, is_enabled=True).first()
                if object:
                    if object.meta_title :
                        title = object.meta_title
                    if object.meta_description:
                        description = object.meta_description
                    if object.top_content:
                        top_content = object.top_content
                    if object.bottom_content:
                        bottom_content = object.bottom_content

                # if not top_content and specialization_id:
                #     specialization_content = models.PracticeSpecializationContent.objects.filter(
                #         specialization__id=specialization_id).first()
                #     if specialization_content:
                #         top_content = specialization_content.content
                #
                # if top_content:
                #     top_content = str(top_content)
                #     top_content = top_content.replace('<location>', location)
                #     regex = re.compile(r'[\n\r\t]')
                #     top_content = regex.sub(" ", top_content)
                # if bottom_content:
                #     bottom_content = str(bottom_content)
                #     bottom_content = bottom_content.replace('<location>', location)
                #     regex = re.compile(r'[\n\r\t]')
                #     bottom_content = regex.sub(" ", bottom_content)

            seo = {
                "title": title,
                "description": description,
                "location": location,
                "image": static('web/images/dclogo-placeholder.png'),
                "schema": None
            }


                            # ,
                # 'schema': {
                #     "@context": "http://schema.org",
                #     "@type": "MedicalBusiness",
                #     "name": "%s in %s" % (specialization if specialization else 'Doctors', location),
                #     "address": {
                #         "@type": "PostalAddress",
                #         "addressLocality": location,
                #         "addressRegion": locality,
                #     },
                #     "location": {
                #         "@type": "Place",
                #         "geo": {
                #             "@type": "GeoCircle",
                #             "geoMidpoint": {
                #                 "@type": "GeoCoordinates",
                #                 "latitude": latitude,
                #                 "longitude": longitude
                #             }
                #         }
                #     },
                #     "priceRange": "0"
                # }
            # }


            # if object and object.top_content:
            #     specialization_content = object.top_content
            #     if specialization_content:
            #         content = str(specialization_content)
            #         content = content.replace('<location>', location)
            #         regex = re.compile(r'[\n\r\t]')
            #         content = regex.sub(" ", content)
            #         specialization_dynamic_content = content

            # else:
            #     if specialization_id:
            #         specialization_content = models.PracticeSpecializationContent.objects.filter(specialization__id=specialization_id).first()
            #         if specialization_content:
            #             content = str(specialization_content.content)
            #             content = content.replace('<location>', location)
            #             regex = re.compile(r'[\n\r\t]')
            #             content = regex.sub(" ", content)
            #             specialization_dynamic_content = content

        for resp in response:
            resp['url'] = None
            resp['schema']['url'] = None
            resp['parent_url'] = None

            doctor_entity = entity_data.get(resp['id'])
            if doctor_entity:
                if doctor_entity.get('url'):
                    resp['url'] = doctor_entity.get('url')
                    schema_url = None
                    if doctor_entity.get('url'):
                        schema_url = doctor_entity.get('url') if doctor_entity.get('url').startswith('/') else '/' + doctor_entity.get('url')

                    resp['schema']['url'] = request.build_absolute_uri(schema_url) if schema_url else None
                    resp['new_schema']['url'] = request.build_absolute_uri(schema_url) if schema_url else None
                parent_location = doctor_entity.get('location')
                parent_url = doctor_entity.get('parent_url')
                if parent_location and parent_url:
                    if resp.get('hospitals')[0] and resp.get('hospitals')[0].get("location"):
                        hospital_location = Point(resp.get('hospitals')[0].get("location").get('long'),resp.get('hospitals')[0].get("location").get('lat'), srid=4326)
                        if hospital_location.distance(parent_location)*100 < 1:
                            resp['parent_url'] = parent_url

        specializations = list(models.PracticeSpecialization.objects.filter(id__in=validated_data.get('specialization_ids',[])).values('id','name'))
        specialization_groups = list(models.SimilarSpecializationGroup.objects.filter(id__in=validated_data.get('group_ids', [])).values('id', 'name'))
        if validated_data.get('url'):
            canonical_url = validated_data.get('url')
        else:
            if validated_data.get('city'):
                city = city_match(validated_data.get('city'))

                if specializations:
                    specialization_name = specializations[0].get('name')
                    if not validated_data.get('locality'):
                        url = slugify(specialization_name + '-in-' + city + '-sptcit')
                    else:
                        url = slugify(specialization_name + '-in-' + validated_data.get('locality') + '-' +
                                                city + '-sptlitcit')
                elif temp_ipd_procedures:
                    temp_ipd = temp_ipd_procedures[0]
                    if temp_ipd:
                        url = slugify(temp_ipd.name + '-doctors-in-' + city + '-ipddp')
                else:
                    if not validated_data.get('locality'):
                        url = slugify('doctors' + '-in-' + city + '-sptcit')
                    else:
                        url = slugify('doctors' + '-in-' + validated_data.get('locality') + '-' +
                                                city + '-sptlitcit')

                entity = EntityUrls.objects.filter(url=url, url_type='SEARCHURL', entity_type='Doctor', is_valid=True)
                if entity:
                    canonical_url = entity[0].url
        if seo:
            seo['schema'] = self.get_schema(request, response) if validated_data['url'] and validated_data['url'] == 'dentist-in-gurgaon-sptcit' else None

        if restrict_result_count:
            response = response[:restrict_result_count]

        if parameters.get('doctor_suggestions') == 1:
            result = list()
            for data in response:
                if data.get('enabled_for_online_booking') == True and len(result)<3:
                    result.append(data)
                else:
                    break
            result = result if result else None
            return {"result": result, "count": result_count,
                             'specializations': specializations}

        validated_data.get('procedure_categories', [])
        procedures = list(Procedure.objects.filter(pk__in=validated_data.get('procedure_ids', [])).values('id', 'name'))
        ipd_procedures = list(IpdProcedure.objects.filter(pk__in=validated_data.get('ipd_procedure_ids', [])).values('id', 'name'))
        procedure_categories = list(ProcedureCategory.objects.filter(pk__in=validated_data.get('procedure_category_ids', [])).values('id', 'name'))
        conditions = list(models.MedicalCondition.objects.filter(id__in=validated_data.get('condition_ids',[])).values('id','name'));
        if validated_data.get('ratings'):
            ratings = validated_data.get('ratings')
        if validated_data.get('reviews'):
            reviews = validated_data.get('reviews')
        hospital_req_data = {}
        if validated_data.get('hospital_id'):
            hospital_req_data = Hospital.objects.filter(id__in=validated_data.get('hospital_id')).values('id',
                                                                                                         'name').first()

        similar_specializations = list()
        if validated_data.get('specialization_ids') and len(validated_data.get('specialization_ids')) == 1:
            spec = PracticeSpecialization.objects.filter(id=validated_data['specialization_ids'][0]).first()
            department_spec_list = list()
            departent_ids_list = list()
            similar_specializations_ids = list()
            if spec and spec.is_similar_specialization:
                for department in spec.department.all():
                    department_spec_mapping = department.specializationdepartmentmapping_set.all()
                    if department_spec_mapping:
                        department_spec_list.extend(department_spec_mapping.values_list('specialization', flat=True))
                    departent_ids_list.append(department.id)
            if department_spec_list:
                department_spec_list = set(department_spec_list)
                spec_dept_mapping_spec_ids = set(PracticeSpecialization.objects.filter(id__in=department_spec_list).prefetch_related(
                    "department", "department__departments",
                    "department__departments__specializationdepartmentmapping").
                    annotate( specialization_id=F('department__departments__specializationdepartmentmapping__specialization')).values_list('specialization_id', flat=True))

                doctors_spec_ids = PracticeSpecialization.objects.filter(id__in=spec_dept_mapping_spec_ids).prefetch_related("specialization__doctor__doctor_clinics",
                                                                        "specialization__doctor__doctor_clinics__hospital", "specialization__doctor",
                                                                        "specialization").annotate(bookable_doctors_count=Count(Q(specialization__doctor__enabled_for_online_booking=True,
                                                                         specialization__doctor__doctor_clinics__hospital__enabled_for_online_booking=True,
                                                                        specialization__doctor__doctor_clinics__enabled_for_online_booking=True,
                                                                        specialization__doctor__is_live=True, specialization__doctor__doctor_clinics__hospital__is_live=True))).\
                                                                        filter(bookable_doctors_count__gt=0).order_by('-bookable_doctors_count').values_list('id', flat=True)
                for id in doctors_spec_ids:
                    if not id in similar_specializations_ids:
                        similar_specializations_ids.append(id)

                if similar_specializations_ids:
                    if int(validated_data['specialization_ids'][0]) in similar_specializations_ids:
                        similar_specializations_ids.remove(int(validated_data['specialization_ids'][0]))
                    specialization_department = SpecializationDepartmentMapping.objects.filter(
                        specialization__id__in=similar_specializations_ids,
                        department__id__in=departent_ids_list).values('specialization__id', 'specialization__name', 'department__id', 'department__name')
                    spec_dept_details = dict()
                    for data in specialization_department:
                        if not spec_dept_details.get(data.get('specialization__id')):
                            spec_dept_details[data.get('specialization__id')] = {'specialization_id': data.get('specialization__id'), 'department_id': data.get('department__id'),
                                                        'specialization_name': data.get('specialization__name'), 'department_name': data.get('department__name')}
                    for id in similar_specializations_ids:
                        if spec_dept_details.get(id):
                            similar_specializations.append(spec_dept_details[id])

        return Response({"result": response, "count": result_count,
                         'specializations': specializations, 'conditions': conditions, "seo": seo,
                         "breadcrumb": breadcrumb, 'search_content': top_content,
                         'procedures': procedures, 'procedure_categories': procedure_categories,
                         'ratings': ratings, 'reviews': reviews, 'ratings_title': ratings_title,
                         'bottom_content': bottom_content, 'canonical_url': canonical_url,
                         'ipd_procedures': ipd_procedures, 'hospital': hospital_req_data,
                         'specialization_groups': specialization_groups,
                         'similar_specializations': similar_specializations})

    def get_schema(self, request, response):

        itemListElement = list()
        count = 1

        for resp in response[:20]:
            if resp.get('url'):
                itemListElement.append({"@type": "ListItem", "position": count,
                                    "url": request.build_absolute_uri("/" + resp.get('url'))})
                count += 1

        return {"@context": "http://schema.org",
                    "@type": "ItemList",
                 "itemListElement": itemListElement
                 }


    def get_spec_city_title_desc(self, specialization_id, city, specialization):

        specialization_metatags = dict()
        title=None
        description = None
        ratings_title = None

        specialization_metatags[279] = {
            'title': 'Best Dentist in ' + city + ' | Find Top Dentists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}

        specialization_metatags[291] = {
            'title': 'Best Dermatologist in ' + city + ' | Find Top Skin Specialists Near Me In ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby skin specialists details, address, availability & more.'}
        specialization_metatags[300] = {
            'title': 'Best Diabetologist in ' + city + ' | Find Top Diabetes Doctors Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby diabetes doctors details, address, availability & more.'}
        specialization_metatags[384] = {
            'title': 'Best Dietitian in ' + city + ' | Find Top Dietitians Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + 'near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[304] = {
            'title': 'Best Endocrinologist in ' + city + ' | Find Top Endocrinologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[270] = {
            'title': 'Best Cardiologist in ' + city + ' | Find Top Heart Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby heart specialists details, address, availability & more.'}
        specialization_metatags[309] = {
            'title': 'Best ENT Specialist in ' + city + ' | Find Top ENT Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ENT specialists details, address, availability & more.'}
        specialization_metatags[315] = {
            'title': 'Best Gastroenterologist in ' + city + ' | Find Top Gastroenterologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[358] = {
            'title': 'Best Gynecologist in ' + city + ' | Find Top Gynecologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[376] = {
            'title': 'Best Nephrologist in ' + city + ' | Find Top Kidney Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby kidney specialists details, address, availability & more.'}
        specialization_metatags[379] = {
            'title': 'Best Neurologist in ' + city + ' | Find Top Neurologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + 'near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[385] = {
            'title': 'Best Nutritionist in ' + city + ' | Find Top Nutritionists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + 'near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[334] = {
            'title': 'Best Immunologist in ' + city + ' | Find Top Allergy Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby allergy specialists details, address, availability & more.'}
        specialization_metatags[405] = {
            'title': 'Best Ophthalmologist in ' + city + ' | Find Top Ophthalmologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[284] = {
            'title': 'Best Orthodontist in ' + city + ' | Find Top Orthodontists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[426] = {
            'title': 'Best Pediatrician in ' + city + ' | Find Top Child Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby child specialists details, address, availability & more.'}
        specialization_metatags[454] = {
            'title': 'Best Physiotherapist in ' + city + ' | Find Top Physiotherapists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[474] = {
            'title': 'Best Psychiatrist in ' + city + ' | Find Top Psychiatrists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[482] = {
            'title': 'Best Psychologist in ' + city + ' | Find Top Psychologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags[487] = {
            'title': 'Best Pulmonologist in ' + city + ' | Find Top Lung Specialists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby lung specialists details, address, availability & more.'}
        specialization_metatags[501] = {
            'title': 'Best Sexologist in ' + city + ' | Find Top Sexologists Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}
        specialization_metatags['default'] = {
            'title': 'Best ' + specialization + 's' + ' in ' + city + ' | Find Top ' + specialization + ' Near Me in ' + city,
            'description': specialization + ' in ' + city + ': Search and find best ' + specialization + ' near you to book appointment online. Check nearby ' + specialization + ' details, address, availability & more.'}

        if specialization_id in (
        279, 291, 300, 384, 304, 270, 309, 315, 358, 376, 379, 385, 334, 405, 284, 426, 454, 474, 482, 487, 501):
            title = specialization_metatags[specialization_id].get('title')
            description = specialization_metatags[specialization_id].get('description')
            ratings_title = specialization + ' in ' + city
        else:
            title = specialization_metatags['default'].get('title')
            description = specialization_metatags['default'].get('description')
            ratings_title = specialization + ' in ' + city
        return title, description, ratings_title


    @transaction.non_atomic_requests
    def search_by_hospital(self, request):
        parameters = request.query_params
        serializer = serializers.DoctorListSerializer(data=parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        specialization_dynamic_content = ''
        doctor_search_helper = DoctorSearchByHospitalHelper(validated_data)
        # if not validated_data.get("search_id"):
        filtering_params = doctor_search_helper.get_filtering_params()
        order_by_field, rank_by = doctor_search_helper.get_ordering_params()
        page = int(request.query_params.get('page', 1))

        query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                              order_by_field, rank_by, page)
        db = DatabaseInfo.DEFAULT
        if settings.USE_SLAVE_DB:
            db = DatabaseInfo.SLAVE

        doctor_search_result = RawSql(query_string.get('query'),
                                      query_string.get('params'), db).fetch_all()

        result_count = 0
        if len(doctor_search_result)>0:
            result_count = doctor_search_result[0]['result_count']
            # sa
            # saved_search_result = models.DoctorSearchResult.objects.create(results=doctor_search_result,
            #                                                                result_count=result_count)
        # else:
        #     saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))

        doctor_ids = [data.get("doctor_id") for data in doctor_search_result]
        #preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(doctor_ids)])
        # doctor_data = models.Doctor.objects.filter(
        #     id__in=doctor_ids).prefetch_related("hospitals", "doctor_clinics", "doctor_clinics__availability",
        #                                         "doctor_clinics__hospital",
        #                                         "doctorpracticespecializations",
        #                                         "doctorpracticespecializations__specialization",
        #                                         "images",
        #                                         "doctor_clinics__procedures_from_doctor_clinic__procedure__parent_categories_mapping")

        result = doctor_search_helper.prepare_search_response(doctor_search_result, doctor_ids, request)

        # from collections import Counter
        # for hosp in response.items():
        #     hosp_specialization = list()
        #     doctors_in_hosp = hosp[1][0].get('doctors')
        #     for doctor in doctors_in_hosp:
        #         specialization = doctor.get('general_specialization')
        #         for spec in specialization:
        #             hosp_specialization.append(spec.get('name'))
        #     spec_dict = Counter(hosp_specialization)
        #     max_value = max(spec_dict.values())
        #     for spec_key in spec_dict.items():
        #         if spec_key[1] == max_value:
        #             hosp[1][0]['specialization'] = spec_key[0]
        #         if hosp[1][0].get('specialization'):
        #             break

        # result = list()
        # for data in response.values():
        #     result.append(data[0])

        validated_data.get('procedure_categories', [])
        procedures = list(Procedure.objects.filter(pk__in=validated_data.get('procedure_ids', [])).values('id', 'name'))
        procedure_categories = list(
            ProcedureCategory.objects.filter(pk__in=validated_data.get('procedure_category_ids', [])).values('id',
                                                                                                             'name'))
        conditions = list(
            models.MedicalCondition.objects.filter(id__in=validated_data.get('condition_ids', [])).values('id',
                                                                                                          'name'))
        specializations = list(
            models.PracticeSpecialization.objects.filter(id__in=validated_data.get('specialization_ids', [])).values(
                'id', 'name'))

        return Response(data={"result": result, "count": result_count,
                         'specializations': specializations, 'conditions': conditions,
                         'procedures': procedures, 'procedure_categories': procedure_categories})

    @transaction.non_atomic_requests
    def hosp_filtered_list(self, request):
        if (request.query_params.get('procedure_ids') or request.query_params.get('procedure_category_ids')) \
                and request.query_params.get('is_insurance'):
            return Response({"result": [], "count": 0})

        parameters = request.query_params
        entity = None
        if parameters.get('url'):
            url = parameters.get('url')
            entity = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                                      entity_type='Doctor').order_by('-sequence')[0]
            parameters = doctor_query_parameters(entity, request.query_params)

        serializer = serializers.DoctorListSerializer(data=parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if entity:
            validated_data['url'] = entity.url
            validated_data['locality_value'] = entity.locality_value if entity.locality_value else None
            validated_data['sublocality_value'] = entity.sublocality_value if entity.sublocality_value else None
            validated_data['specialization'] = entity.specialization if entity.specialization else None
            validated_data[
                'sublocality_latitude'] = entity.sublocality_latitude if entity.sublocality_latitude else None
            validated_data[
                'sublocality_longitude'] = entity.sublocality_longitude if entity.sublocality_longitude else None
            validated_data['locality_latitude'] = entity.locality_latitude if entity.locality_latitude else None
            validated_data['locality_longitude'] = entity.locality_longitude if entity.locality_longitude else None
            validated_data['breadcrumb'] = entity.breadcrumb if entity.breadcrumb else None
            validated_data['sitemap_identifier'] = entity.sitemap_identifier if entity.sitemap_identifier else None
            validated_data['ipd_procedure'] = entity.ipd_procedure if entity.ipd_procedure else None
        result_count = None
        response = list()

        # Insurance check for logged in user
        logged_in_user = request.user
        insurance_threshold = InsuranceThreshold.objects.all().order_by('-opd_amount_limit').first()
        insurance_data_dict = {
            'is_user_insured': False,
            'insurance_threshold_amount': insurance_threshold.opd_amount_limit if insurance_threshold else 5000
        }

        vip_data_dict = {
            'is_vip_member': False,
            'cover_under_vip': False,
            'vip_remaining_amount': 0,
            'is_enable_for_vip': False
        }

        vip_user = None

        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
            vip_user = logged_in_user.active_plus_user
            user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
            if user_insurance and user_insurance.is_valid() and not logged_in_user.active_plus_user:
                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                if insurance_threshold:
                    insurance_data_dict['insurance_threshold_amount'] = 0 if insurance_threshold.opd_amount_limit is None else \
                        insurance_threshold.opd_amount_limit
                    insurance_data_dict['is_user_insured'] = True
            if vip_user:
                utilization_dict = logged_in_user.active_plus_user.get_utilization

                vip_data_dict['vip_remaining_amount'] = utilization_dict.get(
                    'doctor_amount_available') if utilization_dict else 0
                vip_data_dict['is_vip_member'] = True
                vip_data_dict['cover_under_vip'] = False
                vip_data_dict['is_enable_for_vip'] = False

        validated_data['vip_user'] = vip_user
        validated_data['insurance_threshold_amount'] = insurance_data_dict['insurance_threshold_amount']
        validated_data['is_user_insured'] = insurance_data_dict['is_user_insured']

        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            doctor_search_result = RawSql(query_string.get('query'),
                                         query_string.get('params')).fetch_all()

        else:
            saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))

        temp_hospital_ids = set(data.get("hospital_id") for data in doctor_search_result)
        result_count = len(temp_hospital_ids)
        hosp_entity = EntityUrls.objects.filter(is_valid=True,
                                                        sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE,
                                                        entity_id__in=temp_hospital_ids)
        entity_data = dict()
        for data in hosp_entity:
            entity_data[data.entity_id] = dict()
            entity_data[data.entity_id]['url'] = data.url

        hospitals = Hospital.objects.filter(id__in=temp_hospital_ids).prefetch_related('hospital_doctors').annotate(
            bookable_doctors_count=Count(Q(enabled_for_online_booking=True,
                                     hospital_doctors__enabled_for_online_booking=True,
                                     hospital_doctors__doctor__enabled_for_online_booking=True,
                                     hospital_doctors__doctor__is_live=True, is_live=True))).order_by('-bookable_doctors_count')

        for data in hospitals:
            response.append({'id':data.id, 'name': data.name, 'url': entity_data[data.id]['url'] if entity_data and entity_data.get(data.id) and entity_data[data.id].get('url') else None})

        return Response({"result": response, "count": result_count})


    def speciality_filtered_list(self,request):
        if (request.query_params.get('procedure_ids') or request.query_params.get('procedure_category_ids')) \
                and request.query_params.get('is_insurance'):
            return Response({"result": [], "count": 0})

        parameters = request.query_params
        entity = None
        if parameters.get('url'):
            url = parameters.get('url')
            entity = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                                      entity_type='Doctor').order_by('-sequence')[0]
            parameters = doctor_query_parameters(entity, request.query_params)

        serializer = serializers.DoctorListSerializer(data=parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if entity:
            validated_data['url'] = entity.url
            validated_data['locality_value'] = entity.locality_value if entity.locality_value else None
            validated_data['sublocality_value'] = entity.sublocality_value if entity.sublocality_value else None
            validated_data['specialization'] = entity.specialization if entity.specialization else None
            validated_data[
                'sublocality_latitude'] = entity.sublocality_latitude if entity.sublocality_latitude else None
            validated_data[
                'sublocality_longitude'] = entity.sublocality_longitude if entity.sublocality_longitude else None
            validated_data['locality_latitude'] = entity.locality_latitude if entity.locality_latitude else None
            validated_data['locality_longitude'] = entity.locality_longitude if entity.locality_longitude else None
            validated_data['breadcrumb'] = entity.breadcrumb if entity.breadcrumb else None
            validated_data['sitemap_identifier'] = entity.sitemap_identifier if entity.sitemap_identifier else None
            validated_data['ipd_procedure'] = entity.ipd_procedure if entity.ipd_procedure else None
        result_count = None
        response = list()

        # Insurance check for logged in user
        logged_in_user = request.user
        insurance_threshold = InsuranceThreshold.objects.all().order_by('-opd_amount_limit').first()
        insurance_data_dict = {
            'is_user_insured': False,
            'insurance_threshold_amount': insurance_threshold.opd_amount_limit if insurance_threshold else 5000
        }

        vip_data_dict = {
            'is_vip_member': False,
            'cover_under_vip': False,
            'vip_remaining_amount': 0,
            'is_enable_for_vip': False
        }

        vip_user = None

        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
            vip_user = logged_in_user.active_plus_user
            user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
            if user_insurance and user_insurance.is_valid() and not logged_in_user.active_plus_user:
                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                if insurance_threshold:
                    insurance_data_dict['insurance_threshold_amount'] = 0 if insurance_threshold.opd_amount_limit is None else \
                        insurance_threshold.opd_amount_limit
                    insurance_data_dict['is_user_insured'] = True
            if vip_user:
                utilization_dict = logged_in_user.active_plus_user.get_utilization

                vip_data_dict['vip_remaining_amount'] = utilization_dict.get(
                    'doctor_amount_available') if utilization_dict else 0
                vip_data_dict['is_vip_member'] = True
                vip_data_dict['cover_under_vip'] = False
                vip_data_dict['is_enable_for_vip'] = False

        validated_data['vip_user'] = vip_user
        validated_data['insurance_threshold_amount'] = insurance_data_dict['insurance_threshold_amount']
        validated_data['is_user_insured'] = insurance_data_dict['is_user_insured']

        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            doctor_search_result = RawSql(query_string.get('query'),
                                         query_string.get('params')).fetch_all()

        else:
            saved_search_result = get_object_or_404(models.DoctorSearchResult, pk=validated_data.get("search_id"))

        doctor_ids = set(data.get("doctor_id") for data in doctor_search_result)

        doctors_spec = DoctorPracticeSpecialization.objects.filter(doctor__id__in=doctor_ids).prefetch_related("doctor__doctor_clinics",
                                                                                        "doctor__doctor_clinics__hospital",
                                                                                        "specialization").annotate(bookable_doctors_count=Count(Q(doctor__enabled_for_online_booking=True,
                                                                                        doctor__doctor_clinics__hospital__enabled_for_online_booking=True,
                                                                                        doctor__doctor_clinics__enabled_for_online_booking=True))).order_by('-bookable_doctors_count')
        specialization_ids = list()
        for data in doctors_spec:
            if not data.specialization.id in specialization_ids:
                specialization_ids.append(data.specialization.id)
        result_count = len(specialization_ids)
        practice_spec = PracticeSpecialization.objects.filter(id__in=specialization_ids)

        for data in practice_spec:
            response.append({'id': data.id, 'name': data.name})

        return Response({"result": response, "count": result_count})


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
        doctor_leave_serializer = v2_serializers.DoctorLeaveSerializer(
            models.DoctorLeave.objects.filter(doctor=validated_data.get("doctor_id"), deleted_at__isnull=True), many=True)

        timeslots = dict()
        obj = TimeSlotExtraction()

        for data in queryset:
            obj.form_time_slots(data.day, data.start, data.end, data.fees, True,
                                data.deal_price, data.mrp, data.dct_cod_deal_price(), True, on_call=data.type)

        timeslots = obj.get_timing_list()
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data,
                         "doctor_leaves": doctor_leave_serializer.data})


    @transaction.non_atomic_requests
    def list_new(self, request, *args, **kwargs):
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        dc_obj = models.DoctorClinic.objects.filter(doctor_id=validated_data.get('doctor_id'),
                                                            hospital_id=validated_data.get(
                                                                'hospital_id')).first()
        blocks = []
        blockeds_timeslot_set = set()
        if request.user and request.user.is_authenticated and \
                not hasattr(request, 'agent') and request.user.active_insurance:
            active_appointments = dc_obj.hospital.\
                get_active_opd_appointments(request.user, request.user.active_insurance)
            for apt in active_appointments:
                # blocks.append(str(apt.time_slot_start.date()))
                blockeds_timeslot_set.add(str(apt.time_slot_start.date()))

            if dc_obj and not hasattr(request, 'agent'):
                hospital = dc_obj.hospital
                appointment_slot_blocks = hospital.get_blocked_specialization_appointments_slots(dc_obj.doctor, request.user.active_insurance)
                blockeds_timeslot_set = blockeds_timeslot_set.union(set(appointment_slot_blocks))

        blocks.extend(list(blockeds_timeslot_set))

        if dc_obj:
            timeslots = dc_obj.get_timings(blocks)
        else:
            res_data = OrderedDict()
            for i in range(30):
                converted_date = (datetime.datetime.now() + datetime.timedelta(days=i))
                readable_date = converted_date.strftime("%Y-%m-%d")
                res_data[readable_date] = list()

            timeslots = {"time_slots": res_data, "upcoming_slots": []}

        # if request.user and request.user.is_authenticated and request.user.active_insurance:
        #     active_appointments = dc_obj.hospital.\
        #         get_active_opd_appointments(request.user, request.user.active_insurance)
        #     for apt in active_appointments:
        #         timeslots.get('time_slots', {}).pop(str(apt.time_slot_start.date()), None)

        # queryset = models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=validated_data.get('doctor_id'),
        #                                                     doctor_clinic__hospital=validated_data.get(
        #                                                         'hospital_id')).order_by("start")
        # temp_slots = slots.copy()
        # active_appointments = None
        # if user.active_insurance:
        #     active_appointments = OpdAppointment.get_insured_active_appointment(user.active_insurance)
        #     for appointment in active_appointments:
        #         for slot in temp_slots:
        #             if str(appointment.time_slot_start.date()) == slot and clinic_timings.first().doctor_clinic.hospital_id == appointment.hospital_id:
        #                 del slots[slot]

        doctor_queryset = (models.Doctor
                           .objects.prefetch_related("qualifications__qualification",
                                                     "qualifications__specialization")
                           .filter(pk=validated_data.get('doctor_id').id))
        doctor_serializer = serializers.DoctorTimeSlotSerializer(doctor_queryset, many=True)
        # doctor_leave_serializer = v2_serializers.DoctorLeaveSerializer(
        #     models.DoctorLeave.objects.filter(doctor=validated_data.get("doctor_id"), deleted_at__isnull=True), many=True)
        # global_leave_serializer = common_serializers.GlobalNonBookableSerializer(
        #     GlobalNonBookable.objects.filter(deleted_at__isnull=True, booking_type=GlobalNonBookable.DOCTOR), many=True)
        # total_leaves = dict()
        # total_leaves['global'] = global_leave_serializer.data
        # total_leaves['doctor'] = doctor_leave_serializer.data
        # timeslots = dict()
        # obj = TimeSlotExtraction()
        #
        # for data in queryset:
        #     obj.form_time_slots(data.day, data.start, data.end, data.fees, True,
        #                         data.deal_price, data.mrp, True, on_call=data.type)
        #
        # date = datetime.datetime.today().strftime('%Y-%m-%d')
        # # timeslots = obj.get_timing_list()
        # timeslots = obj.get_doctor_timing_slots(date, total_leaves, "doctor")
        return Response({"timeslots": timeslots["time_slots"], "upcoming_slots": timeslots["upcoming_slots"], "doctor_data": doctor_serializer.data})

    @transaction.non_atomic_requests
    @use_slave
    def list_v2(self, request, *args, **kwargs):
        doctor_id = request.query_params.get('doctor_id')
        hospital_id = request.query_params.get('hospital_id')

        try:
            doctor = Doctor.objects.filter(id=doctor_id).first()
            hospital = Hospital.objects.filter(id=hospital_id).first()
        except ValueError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'doctor id or hospital id is undefined.'})

        if not doctor or not hospital:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'doctor id or hospital id is not available.'})

        doctor_queryset = models.Doctor.objects.prefetch_related("qualifications__qualification", "qualifications__specialization")\
                                      .filter(pk=doctor_id)
        doctor_serializer = serializers.DoctorTimeSlotSerializer(doctor_queryset, many=True)
        doctor = doctor_queryset.first()

        dc_obj = models.DoctorClinic.objects.filter(doctor_id=doctor_id,
                                                    hospital_id=hospital_id).first()
        if not dc_obj:
            return HttpResponse(status=404)

        date = request.query_params.get('date')
        doctor_leaves = doctor.get_leaves()
        global_non_bookables = GlobalNonBookable.get_non_bookables()
        total_leaves = doctor_leaves + global_non_bookables

        blocks = []
        if request.user and request.user.is_authenticated and \
                not hasattr(request, 'agent') and request.user.active_insurance:
            active_appointments = dc_obj.hospital. \
                get_active_opd_appointments(request.user, request.user.active_insurance)
            for apt in active_appointments:
                blocks.append(str(apt.time_slot_start.date()))

        # if dc_obj.is_part_of_integration() and settings.MEDANTA_INTEGRATION_ENABLED:
        #     from ondoc.integrations import service
        #     pincode = None
        #     integration_dict = dc_obj.get_integration_dict()
        #     class_name = integration_dict['class_name']
        #     integrator_obj_id = integration_dict['id']
        #     integrator_obj = service.create_integrator_obj(class_name)
        #     clinic_timings = integrator_obj.get_appointment_slots(pincode, date, integrator_obj_id=integrator_obj_id,
        #                                                           blocks=blocks, dc_obj=dc_obj,
        #                                                           total_leaves=total_leaves)
        # else:
        clinic_timings = dc_obj.get_timings_v2(total_leaves, blocks)

        resp_data = {"timeslots": clinic_timings.get('timeslots', []),
                     "upcoming_slots": clinic_timings.get('upcoming_slots', []),
                     "is_integrated": clinic_timings.get('is_integrated', False),
                     "doctor_data": doctor_serializer.data}

        return Response(resp_data)


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
        if not opd_appointment or opd_appointment.status==models.OpdAppointment.CREATED:
            return Response({"message": "Invalid appointment id"}, status.HTTP_404_NOT_FOUND)
        source = validated_data.get('source') if validated_data.get('source') else request.query_params.get('source', '')
        responsible_user = request.user if request.user.is_authenticated else None
        opd_appointment._source = source if source in [x[0] for x in AppointmentHistory.SOURCE_CHOICES] else ''
        opd_appointment._responsible_user = responsible_user
        if opd_appointment:
            opd_appointment.action_completed()

            resp = {'success': 'Appointment Completed Successfully!',
                    'mrp': opd_appointment.mrp,
                    'payment_type': opd_appointment.payment_type,
                    'payment_status': opd_appointment.payment_status}
        return Response(resp)


class LimitUser(UserRateThrottle):
    rate = '5/day'


class LimitAnon(AnonRateThrottle):
    rate = '5/day'


class DoctorContactNumberViewSet(viewsets.GenericViewSet):

    throttle_classes = (LimitUser, LimitAnon)

    def retrieve(self, request, doctor_id):

        hospital_id = request.query_params.get("hospital_id")
        doctor_obj = get_object_or_404(models.Doctor, pk=doctor_id)

        hospital = doctor_obj.hospitals.filter(id=hospital_id).first()
        spoc_details = hospital.spoc_details.all()
        if hospital and hospital.is_live and len(spoc_details)>0:
            for type in [auth_models.SPOCDetails.SPOC, auth_models.SPOCDetails.MANAGER, auth_models.SPOCDetails.OTHER, auth_models.SPOCDetails.OWNER]:
                for spoc in spoc_details:
                    if spoc.contact_type == type:
                        final = None
                        if spoc.std_code:
                            final = '0' + str(spoc.std_code).lstrip('0') + str(spoc.number).lstrip('0')
                        else:
                            final = '0' + str(spoc.number).lstrip('0')
                        if final:
                            return Response({'status': 1, 'number': final}, status.HTTP_200_OK)

        doctor_details = models.DoctorMobile.objects.filter(doctor=doctor_obj).values('is_primary','number','std_code').order_by('-is_primary').first()

        if doctor_details:
            final = str(doctor_details.get('number')).lstrip('0')
            if doctor_details.get('std_code'):
                final = '0'+str(doctor_details.get('std_code')).lstrip('0')+str(doctor_details.get('number')).lstrip('0')
            return Response({'status': 1, 'number': final}, status.HTTP_200_OK)

        return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)


class DoctorFeedbackViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    @staticmethod
    def get_doctor_and_hospital_data(message, doctor=None, hospital=None):
        if doctor:
            message += "doctor - "
            doc_dict = dict()
            doc_dict['id'] = doctor.id
            doc_dict['name'] = doctor.name
            doc_dict['url'] = settings.ADMIN_BASE_URL + reverse('admin:doctor_doctor_change',
                                                                kwargs={"object_id": doctor.id})
            message += str(doc_dict) + "<br>"
        if hospital:
            message += "hospital - "
            hosp_dict = dict()
            hosp_dict['id'] = hospital.id
            hosp_dict['name'] = hospital.name
            hosp_dict['url'] = settings.ADMIN_BASE_URL + reverse('admin:doctor_hospital_change',
                                                                kwargs={"object_id": hospital.id})
            message += str(hosp_dict) + "<br>"
        return message

    def feedback(self, request):
        resp = {}
        user = request.user
        serializer = serializers.DoctorFeedbackBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        if valid_data.get('is_cloud_lab_email'):
            receivers_data = UserConfig.objects.filter(key='feedback_cloudlab_email_receivers').first()
            emails = receivers_data.data if (receivers_data and type(receivers_data.data) is list) else list()
            subject_string = valid_data.get('subject_string')
            message = valid_data.get('feedback')
        else:
            valid_data.pop('subject_string', None)
            subject_string = "Feedback Mail from " + str(user.phone_number)
            message = ''
            managers_string = ''
            manages_string = ''
            doctor = valid_data.pop("doctor_id") if valid_data.get("doctor_id") else None
            hospital = valid_data.pop("hospital_id") if valid_data.get("hospital_id") else None
            for key, value in valid_data.items():
                if isinstance(value, list):
                    val = ' '.join(map(str, value))
                else:
                    val = value
                message += str(key) + "  -  " + str(val) + "<br>"
            if doctor or hospital:
                message = self.get_doctor_and_hospital_data(message, doctor, hospital)
            if hasattr(user, 'doctor') and user.doctor:
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
            emails = ["rajivk@policybazaar.com", "sanat@docprime.com", "arunchaudhary@docprime.com",
                      "rajendra@docprime.com", "harpreet@docprime.com", "jaspreetkaur@docprime.com"]
        try:
            for x in emails:
                notif_models.EmailNotification.publish_ops_email(str(x), mark_safe(message), subject_string)
            resp['status'] = "success"
        except:
            resp['status'] = "error"
        return Response(resp)


class HospitalAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = models.Hospital.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q).order_by('name')
        return qs


class PracticeSpecializationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = models.PracticeSpecialization.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q).order_by('name')
        return qs


class SimilarSpecializationGroupAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = models.SimilarSpecializationGroup.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q).order_by('name')
        return qs



class CreateAdminViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return auth_models.GenericAdmin.objects.none()

    def get_admin_obj(self, request, valid_data, doc, hosp, user, pem_type, entity_type):
        return auth_models.GenericAdmin.create_permission_object(user=user, doctor=doc,
                                                          name=valid_data.get('name', None),
                                                          phone_number=valid_data['phone_number'],
                                                          hospital=hosp,
                                                          permission_type=pem_type,
                                                          is_disabled=False,
                                                          super_user_permission=False,
                                                          write_permission=True,
                                                          created_by=request.user,
                                                          source_type=auth_models.GenericAdmin.APP,
                                                          entity_type=entity_type)

    def create(self, request):
        serializer = serializers.AdminCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        bill_pem = False
        app_pem = True
        if valid_data.get('billing_enabled'):
            bill_pem = True
        if not valid_data.get('appointment_enabled'):
            app_pem = False
        user_queryset = User.objects.filter(user_type=User.DOCTOR, phone_number=valid_data['phone_number']).first()
        user = None
        if user_queryset:
            user = user_queryset

        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            doct = models.Doctor.objects.get(id=valid_data['id'])
            if valid_data.get('assoc_hosp'):
                create_admins = []
                for hos in valid_data['assoc_hosp']:
                    if app_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doct, hos, user,
                                                                auth_models.GenericAdmin.APPOINTMENT, GenericAdminEntity.DOCTOR))
                    if bill_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doct, hos, user,
                                                                auth_models.GenericAdmin.BILLINNG,
                                                                GenericAdminEntity.DOCTOR))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error(str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                create_admins = []
                if app_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, doct, None, user,
                                                            auth_models.GenericAdmin.APPOINTMENT,
                                                            GenericAdminEntity.DOCTOR))
                if bill_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, doct, None, user,
                                                            auth_models.GenericAdmin.BILLINNG,
                                                            GenericAdminEntity.DOCTOR))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error(str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            hosp = models.Hospital.objects.get(id=valid_data['id'])
            name = valid_data.get('name', None)
            if valid_data['type'] == User.DOCTOR and valid_data.get('doc_profile'):
                name = valid_data['doc_profile'].name
                try:
                    auth_models.DoctorNumber.objects.create(phone_number=valid_data.get('phone_number'), doctor=valid_data.get('doc_profile'), hospital=hosp)
                except Exception as e:
                    logger.error(str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            valid_data['name'] = name
            if valid_data.get('assoc_doc'):
                create_admins = []
                for doc in valid_data['assoc_doc']:
                    if app_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doc, hosp, user,
                                                                auth_models.GenericAdmin.APPOINTMENT,
                                                                GenericAdminEntity.HOSPITAL))
                    if bill_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doc, hosp, user,
                                                                auth_models.GenericAdmin.BILLINNG,
                                                                GenericAdminEntity.HOSPITAL))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error(str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                create_admins = []
                if app_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, None, hosp, user,
                                                            auth_models.GenericAdmin.APPOINTMENT,
                                                            GenericAdminEntity.HOSPITAL))
                if bill_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, None, hosp, user,
                                                            auth_models.GenericAdmin.BILLINNG,
                                                            GenericAdminEntity.HOSPITAL))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error(str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif valid_data.get('entity_type') == GenericAdminEntity.LAB:
            lab = lab_models.Lab.objects.get(id=valid_data.get('id'))
            if app_pem:
                auth_models.GenericLabAdmin.objects.create(user=user,
                                                           phone_number=valid_data['phone_number'],
                                                           lab_network=None,
                                                           name=valid_data.get('name'),
                                                           lab=lab,
                                                           permission_type=auth_models.GenericLabAdmin.APPOINTMENT,
                                                           is_disabled=False,
                                                           super_user_permission=False,
                                                           write_permission=True,
                                                           read_permission=True,
                                                           source_type=auth_models.GenericLabAdmin.APP
                                                    )
            if bill_pem:
                auth_models.GenericLabAdmin.objects.create(user=user,
                                                           phone_number=valid_data['phone_number'],
                                                           lab_network=None,
                                                           name=valid_data.get('name'),
                                                           lab=lab,
                                                           permission_type=auth_models.GenericLabAdmin.BILLING,
                                                           is_disabled=False,
                                                           super_user_permission=False,
                                                           write_permission=True,
                                                           read_permission=True,
                                                           source_type=auth_models.GenericLabAdmin.APP
                                                           )
        return Response({'success': 'Created Successfully'})

    def assoc_doctors(self, request, pk=None):
        resp = None
        hospital = models.Hospital.objects.prefetch_related('assoc_doctors').filter(id=pk)
        if not hospital.exists():
            return Response({'error': "Hospital Not Found"}, status=status.HTTP_404_NOT_FOUND)

        queryset = hospital.first().assoc_doctors.annotate(phone_number=F('doctor_number__phone_number'))


        resp = queryset.extra(select={'assigned': 'CASE WHEN  ((SELECT COUNT(*) FROM doctor_number WHERE doctor_id = doctor.id) = 0) THEN 0 ELSE 1  END'})\
                       .values('name', 'id', 'assigned', 'phone_number')
        return Response(resp)

    def assoc_hosp(self, request, pk=None):
        doctor = get_object_or_404(models.Doctor.objects.prefetch_related('hospitals'), pk=pk)
        queryset = doctor.hospitals.filter(Q(is_appointment_manager=False), (Q(is_live=True) | Q(source_type=models.Hospital.PROVIDER)))
        return Response(queryset.values('name', 'id'))

    def list_entities(self, request):
        user = request.user
        opd_list = []
        opd_queryset = (models.Doctor.objects
                        .prefetch_related('manageable_doctors', 'qualifications')
                        .filter((Q(is_live=True)| Q(source_type=Doctor.PROVIDER)),
                                  Q(manageable_doctors__user=user,
                                  manageable_doctors__is_disabled=False,
                                  manageable_doctors__super_user_permission=True,
                                  manageable_doctors__entity_type=GenericAdminEntity.DOCTOR)).distinct('id'))
        doc_serializer = serializers.DoctorEntitySerializer(opd_queryset, many=True, context={'request': request})
        doc_data = doc_serializer.data
        if doc_data:
            opd_list = [i for i in doc_data]
        opd_queryset_hos = (models.Hospital.objects
                            .prefetch_related('manageable_hospitals')
                            .filter((Q(is_live=True)| Q(source_type=models.Hospital.PROVIDER)),
                                      Q(is_appointment_manager=True,
                                      manageable_hospitals__user=user,
                                      manageable_hospitals__is_disabled=False,
                                      manageable_hospitals__super_user_permission=True,
                                      manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL))
                            .distinct('id')
                            )
        hos_list = []
        hos_serializer = serializers.HospitalEntitySerializer(opd_queryset_hos, many=True, context={'request': request})
        hos_data = hos_serializer.data
        if hos_data:
            hos_list = [i for i in hos_data]
        result_data = opd_list + hos_list
        lab_queryset = lab_models.Lab.objects.prefetch_related('manageable_lab_admins')\
                                             .filter(is_live=True,
                                                     manageable_lab_admins__user=user,
                                                     manageable_lab_admins__is_disabled=False,
                                                     manageable_lab_admins__super_user_permission=True)\
                                             .distinct('id')

        lab_list = []
        laab_serializer = lab_serializers.LabEntitySerializer(lab_queryset, many=True, context={'request': request})
        lab_data = laab_serializer.data
        if lab_data:
            lab_list = [i for i in lab_data]
        result_data = result_data + lab_list
        return Response(result_data)

    def list_entity_admins(self, request):
        response = None
        temp = {}
        serializer = serializers.EntityListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = auth_models.GenericAdmin.objects.select_related('doctor', 'hospital').prefetch_related('doctor__doctor_clinics')
        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            query = queryset.exclude(user=request.user).filter(doctor_id=valid_data.get('id'),
                                    entity_type=GenericAdminEntity.DOCTOR
                                    ) \
                            .annotate(hospital_ids=F('hospital__id'), hospital_ids_count=Count('hospital__hospital_doctors__doctor'),
                                      license=F('doctor__license'), online_consultation_fees=F('doctor__online_consultation_fees'))\
                            .values('id', 'phone_number', 'name', 'is_disabled', 'permission_type', 'super_user_permission', 'hospital_ids',
                                    'hospital_ids_count', 'updated_at', 'license', 'online_consultation_fees')
            for x in query:
                if temp.get(x['phone_number']):
                    if x['hospital_ids'] not in temp[x['phone_number']]['hospital_ids']:
                        temp[x['phone_number']]['hospital_ids'].append(x['hospital_ids'])
                    if temp[x['phone_number']]['permission_type'] != x['permission_type']:
                        temp[x['phone_number']]['permission_type'] = auth_models.GenericAdmin.ALL
                else:
                    x['hospital_ids'] = [x['hospital_ids']] if x['hospital_ids'] else []
                    if len(x['hospital_ids']) > 0:
                        x['hospital_ids_count'] = len(x['hospital_ids'])
                    temp[x['phone_number']] = x
            response = list(temp.values())

        elif valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            response = queryset.filter(hospital_id=valid_data.get('id'), entity_type=GenericAdminEntity.HOSPITAL
                                       ) \
                .annotate(doctor_ids=F('doctor__id'), hospital_name=F('hospital__name'), doctor_ids_count=Count('hospital__hospital_doctors__doctor')) \
                .values('phone_number', 'name', 'is_disabled', 'permission_type', 'super_user_permission', 'doctor_ids',
                        'doctor_ids_count', 'hospital_id', 'hospital_name', 'updated_at')

            hos_queryset = models.Hospital.objects.prefetch_related('assoc_doctors').filter(id=valid_data.get('id'))
            if hos_queryset.exists():
                hos_obj = hos_queryset.first()
                hos_name = hos_obj.name
                assoc_docs = hos_obj.assoc_doctors.extra(select={
                    'assigned': 'CASE WHEN  ((SELECT COUNT(*) FROM doctor_number WHERE doctor_id = doctor.id) = 0) THEN 0 ELSE 1  END',
                    'phone_number': 'SELECT phone_number FROM doctor_number WHERE doctor_id = doctor.id',
                    'enabled': 'SELECT enabled FROM doctor_clinic WHERE doctor_id = doctor.id AND hospital_id='+str(hos_obj.id)})\
                    .values('name', 'id', 'assigned', 'phone_number', 'enabled', 'is_live', 'source_type', 'license',
                            'online_consultation_fees')

            for x in response:
                if temp.get(x['phone_number']):
                    if x['doctor_ids'] not in temp[x['phone_number']]['doctor_ids']:
                        temp[x['phone_number']]['doctor_ids'].append(x['doctor_ids'])
                    if temp[x['phone_number']]['permission_type'] != x['permission_type']:
                        temp[x['phone_number']]['permission_type'] = auth_models.GenericAdmin.ALL
                else:
                    for doc in assoc_docs:
                        if ((doc.get('is_live') and doc.get('enabled')) or doc.get('source_type') == Doctor.PROVIDER) and (doc.get('phone_number') and doc.get('phone_number') == x['phone_number']):
                            x['is_doctor'] = True
                            x['name'] = doc.get('name')
                            x['id'] = doc.get('id')
                            x['assigned'] = doc.get('assigned')
                            x['license'] = doc.get('license')
                            x['online_consultation_fees'] = doc.get('online_consultation_fees')
                            break
                    if not x.get('is_doctor'):
                        x['is_doctor'] = False
                    elif x.get('super_user_permission') and x.get('is_doctor'):
                        x['super_user_permission'] = False
                    x['doctor_ids'] = [x['doctor_ids']] if x['doctor_ids'] else []
                    if len(x['doctor_ids']) > 0:
                        x['doctor_ids_count'] = len(x['doctor_ids'])
                    temp[x['phone_number']] = x
            admin_final_list = list(temp.values())
            for a_d in assoc_docs:
                if ((a_d.get('is_live') and a_d.get('enabled')) or a_d.get('source_type') == Doctor.PROVIDER) and not a_d.get('phone_number'):
                    a_d['is_doctor'] = True
                    a_d['hospital_name'] = hos_name
                    admin_final_list.append(a_d)
            response = admin_final_list
        elif valid_data.get('entity_type') == GenericAdminEntity.LAB:
            query = auth_models.GenericLabAdmin.objects\
                .exclude(user=request.user)\
                .filter(lab_id=valid_data.get('id'))\
                .values('phone_number', 'name', 'updated_at', 'is_disabled', 'super_user_permission', 'permission_type')
            for x in query:
                if temp.get(x['phone_number']):
                    if temp[x['phone_number']]['permission_type'] != x['permission_type']:
                        temp[x['phone_number']]['permission_type'] = auth_models.GenericAdmin.ALL
                else:
                    temp[x['phone_number']] = x
            response = list(temp.values())
        if response:
            return Response(response)
        return Response([])

    def delete(self, request):
        serializer = serializers.AdminDeleteBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = auth_models.GenericAdmin.objects.filter(entity_type=valid_data['entity_type'],)
        if valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            queryset = queryset.filter(hospital_id=valid_data.get('id'), phone_number=valid_data.get('phone_number'))
        elif valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            queryset = queryset.filter(doctor_id=valid_data.get('id'), phone_number=valid_data.get('phone_number'))
        else:
            queryset = auth_models.GenericLabAdmin.objects.filter(lab_id=valid_data.get('id'), phone_number=valid_data.get('phone_number'))
        try:
            queryset.delete()
        except Exception as e:
            logger.error("Error Deleting Entity " + str(e))
            return Response({'error': 'something went wrong!'})
        return Response({'success': 'Deleted Successfully'})

    def update(self, request):
        serializer = serializers.AdminUpdateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        phone_number = valid_data.get('old_phone_number') if valid_data.get('old_phone_number') else valid_data.get('phone_number')
        bill_pem = False
        app_pem = True
        if valid_data.get('billing_enabled'):
            bill_pem = True
        if not valid_data.get('appointment_enabled'):
            app_pem = False
        user_queryset = User.objects.filter(user_type=User.DOCTOR, phone_number=valid_data['phone_number']).first()
        user = None
        if user_queryset:
            user = user_queryset
        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:

            delete_queryset = auth_models.GenericAdmin.objects.filter(phone_number=phone_number,
                                                                      entity_type=GenericAdminEntity.DOCTOR)
            if valid_data.get('remove_list'):
                delete_queryset = delete_queryset.filter(hospital_id__in=valid_data.get('remove_list'))
            else:
                delete_queryset = delete_queryset.filter(hospital_id=None)
            if len(delete_queryset) > 0:
                delete_queryset.delete()
            doct = models.Doctor.objects.get(id=valid_data['id'])
            if valid_data.get('assoc_hosp'):
                create_admins = []
                for hos in valid_data['assoc_hosp']:
                    if app_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doct, hos, user,
                                                                auth_models.GenericAdmin.APPOINTMENT, GenericAdminEntity.DOCTOR))
                    if bill_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doct, hos, user,
                                                                auth_models.GenericAdmin.BILLINNG,
                                                                GenericAdminEntity.DOCTOR))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error("Error Updating Entity Doctor " + str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                create_admins = []
                if app_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, doct, None, user,
                                                            auth_models.GenericAdmin.APPOINTMENT,
                                                            GenericAdminEntity.DOCTOR))
                if bill_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, doct, None, user,
                                                            auth_models.GenericAdmin.BILLINNG,
                                                            GenericAdminEntity.DOCTOR))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error("Error Updating Entity Doctor " + str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif valid_data.get('entity_type') == GenericAdminEntity.HOSPITAL:
            hosp = models.Hospital.objects.get(id=valid_data['id'])
            name = valid_data.get('name',  None)
            if valid_data['type'] == User.DOCTOR and valid_data.get('doc_profile'):
                name = valid_data['doc_profile'].name
                dn = auth_models.DoctorNumber.objects.filter(hospital=hosp, doctor=valid_data.get('doc_profile'))
                if dn.first():
                    try:
                        dn.update(phone_number=valid_data.get('phone_number'))
                        doctor = valid_data.get('doc_profile')
                        if valid_data.get('license'):
                            if doctor.license:
                                return Response({"error": "License for given doctor already exists"}, status=status.HTTP_400_BAD_REQUEST)
                            doctor.license = valid_data.get('license')
                        if valid_data.get("online_consultation_fees"):
                            doctor.online_consultation_fees = valid_data.get("online_consultation_fees")
                        doctor.save()
                    except Exception as e:
                        logger.error("Error Updating Entity Hospital " + str(e))
                        return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    try:
                        auth_models.DoctorNumber.objects.create(phone_number=valid_data.get('phone_number'),
                                                                doctor=valid_data.get('doc_profile'),
                                                                hospital=hosp)
                    except Exception as e:
                        logger.error("Error Updating Entity Hospital " + str(e))
                        return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            delete_queryset = auth_models.GenericAdmin.objects.filter(phone_number=phone_number,
                                                                      entity_type=GenericAdminEntity.HOSPITAL,
                                                                      super_user_permission=False)
            if valid_data.get('remove_list'):
                delete_queryset = delete_queryset.filter(doctor_id__in=valid_data.get('remove_list'))
            else:
                delete_queryset = delete_queryset.filter(doctor_id=None)
            if len(delete_queryset):
                delete_queryset.delete()

            if valid_data.get('assoc_doc'):
                create_admins = []
                for doc in valid_data['assoc_doc']:
                    if app_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doc, hosp, user,
                                                                auth_models.GenericAdmin.APPOINTMENT,
                                                                GenericAdminEntity.HOSPITAL))
                    if bill_pem:
                        create_admins.append(self.get_admin_obj(request, valid_data, doc, hosp, user,
                                                                auth_models.GenericAdmin.BILLINNG,
                                                                GenericAdminEntity.HOSPITAL))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error("Error Updating Entity Hospital " + str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                create_admins = []
                if app_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, None, hosp, user,
                                                            auth_models.GenericAdmin.APPOINTMENT,
                                                            GenericAdminEntity.HOSPITAL))
                if bill_pem:
                    create_admins.append(self.get_admin_obj(request, valid_data, None, hosp, user,
                                                            auth_models.GenericAdmin.BILLINNG,
                                                            GenericAdminEntity.HOSPITAL))
                try:
                    auth_models.GenericAdmin.objects.bulk_create(create_admins)
                except Exception as e:
                    logger.error("Error Updating Entity Hospital " + str(e))
                    return Response({'error': 'something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif valid_data.get('entity_type') == GenericAdminEntity.LAB:
            admin = auth_models.GenericLabAdmin.objects.filter(phone_number=phone_number, lab_id=valid_data.get('id'))
            if admin.exists():
                admin.update(user=user, name=valid_data.get('name'), phone_number=valid_data.get('phone_number'))
        return Response({'success': 'Created Successfully'})


class OfflineCustomerViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return None

    def get_error_obj(self, data):
        return {'id': data.get('id'),
                'error': True}

    def get_offline_response_obj(self, appnt, request):
        phone_number = []
        patient_profile = OfflinePatientSerializer(appnt.user).data
        patient_name = appnt.user.name if hasattr(appnt.user, 'name') else None
        patient_profile['phone_number'] = None
        if hasattr(appnt.user, 'patient_mobiles'):
            for mob in appnt.user.patient_mobiles.all():
                if mob.phone_number and not mob.encrypted_number:
                    phone_number.append({"phone_number": mob.phone_number, "is_default": mob.is_default})
                    if mob.is_default:
                        patient_profile['phone_number'] = mob.phone_number
                    patient_profile['patient_numbers'] = phone_number
                elif mob.encrypted_number:
                    phone_number.append({"phone_number": mob.encrypted_number, "is_default": mob.is_default})
                    if mob.is_default:
                        patient_profile['encrypt_phone_number'] = mob.encrypted_number
                    patient_profile['encrypt_numbers'] = phone_number
        # patient_profile['patient_numbers'] = phone_number
        mrp = appnt.fees if appnt.fees else 0
        # mrp = appnt.mrp if appnt.payment_type == appnt.COD else mrp_fees
        ret_obj = {}
        ret_obj['patient_name'] = patient_name
        # ret_obj['patient_number'] = phone_number
        ret_obj['profile'] = patient_profile
        ret_obj['patient_thumbnail'] = None
        ret_obj['deal_price'] = None
        ret_obj['effective_price'] = None
        ret_obj['allowed_action'] = []
        ret_obj['updated_at'] = appnt.updated_at
        ret_obj['doctor_name'] = appnt.doctor.name
        ret_obj['doctor_id'] = appnt.doctor.id
        ret_obj['doctor_thumbnail'] = request.build_absolute_uri(appnt.doctor.get_thumbnail()) if appnt.doctor.get_thumbnail() else None
        ret_obj['hospital_id'] = appnt.hospital.id
        ret_obj['hospital_name'] = appnt.hospital.name
        ret_obj['time_slot_start'] = appnt.time_slot_start
        ret_obj['status'] = appnt.status
        #RAJIV YADAV
        ret_obj['mrp'] = mrp
        ret_obj['hospital'] = HospitalModelSerializer(appnt.hospital).data
        ret_obj['doctor'] = AppointmentRetrieveDoctorSerializer(appnt.doctor).data
        ret_obj['is_docprime'] = False
        ret_obj['mask_data'] = None
        ret_obj['type'] = 'doctor'
        return ret_obj

    def validate_uuid(self, data):
        response = {}
        try:
            id = UUID(data.get('id'), version=4)
            response['id'] = id
        except ValueError:
            obj = self.get_error_obj(data)
            obj['doctor_id'] = data.get('doctor').id
            obj['hospital_id'] = data.get('hospital').id
            obj['error_message'] = 'Invalid UUid - Offline Appointment Create!'
            logger.error("PROVIDER_REQUEST - Invalid UUid - Offline Appointment Create! " + str(data))
            response['obj'] = obj
            response['continue'] = True
        return response

    def validate_permissions(self, data, doc_pem_list, hosp_pem_list, clinic_queryset):

        if not data.get('doctor').id in doc_pem_list and not data.get('hospital').id in hosp_pem_list:
            data['error'] = True
            data['error_message'] = 'User forbidden to create Appointment with selected doctor or hospital!'
        if (data.get('doctor').id, data.get('hospital').id) not in clinic_queryset:
            data['error'] = True
            data['error_message'] = 'Doctor is not associated with given hospital!'
        return data

    def validate_update_conditions(self, appnt, data, request):
        response = {}
        if appnt.error:
            obj = self.get_error_obj(data)
            obj['error_message'] = 'Cannot Update an invalid/error appointment!'
            obj.update(self.get_offline_response_obj(appnt, request))
            logger.info("PROVIDER_REQUEST - Updating a invalid/error Appointment! " + str(data))
            response['obj'] = obj
            response['break'] = True
        elif appnt.status == models.OfflineOPDAppointments.CANCELLED or appnt.status == models.OfflineOPDAppointments.NO_SHOW:
            obj = self.get_error_obj(data)
            obj['error_message'] = 'Cannot Update a Cancelled/NoShow appointment!'
            obj.update(self.get_offline_response_obj(appnt, request))
            logger.info("PROVIDER_REQUEST - Updating a Cancelled/NoShow Appointment! " + str(data))
            response['obj'] = obj
            response['break'] = True

        elif data.get('status') and data.get('status') not in [models.OfflineOPDAppointments.NO_SHOW,
                                                             models.OfflineOPDAppointments.RESCHEDULED_DOCTOR,
                                                             models.OfflineOPDAppointments.CANCELLED,
                                                             models.OfflineOPDAppointments.ACCEPTED,
                                                             models.OfflineOPDAppointments.COMPLETED]:
            obj = self.get_error_obj(data)
            obj['error_message'] = 'Invalid Appointment Status Recieved!'
            obj.update(self.get_offline_response_obj(appnt, request))
            logger.error("PROVIDER_REQUEST - Invalid Appointment Status Recieved! " + str(data))
            response['obj'] = obj
            response['break'] = True
        return response

    def validate_create_conditions(self, appntment_ids, data, request):
        response = {}
        if data.get('id') in appntment_ids:
            obj = {'id': data.get('id'),
                   'error': True,
                   'error_message': "Appointment With Same UUid exists!"}
            obj['doctor_id'] = data.get('doctor').id
            obj['hospital_id'] = data.get('hospital').id
            # logger.error("PROVIDER_REQUEST - Offline Appointment With Same UUid exists! " + str(data))
            response['obj'] = obj
            response['continue'] = True
        elif not data.get('patient'):
            obj = {'id': data.get('id'),
                   'error': True,
                   'error_message': "Patient not Recieved for Offline Appointment!"}
            obj['doctor_id'] = data.get('doctor').id
            obj['hospital_id'] = data.get('hospital').id
            logger.error("PROVIDER_REQUEST - Patient not Recieved for Offline Appointment! " + str(data))
            response['obj'] = obj
            response['continue'] = True
        return response

    def list_patients(self, request):
        user = request.user
        serializer = serializers.GetOfflinePatientsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = models.OfflinePatients.objects.prefetch_related('patient_mobiles')\
                                                 .select_related('doctor', 'hospital')\
                                                 .filter(Q(doctor__manageable_doctors__user=user,
                                                           doctor__manageable_doctors__entity_type=GenericAdminEntity.DOCTOR,
                                                           doctor__manageable_doctors__is_disabled=False,
                                                           )
                                                         |
                                                         Q(hospital__isnull=False,
                                                           hospital__manageable_hospitals__user=user,
                                                           hospital__manageable_hospitals__is_disabled=False,
                                                           hospital__manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL)
                                                         )
        if valid_data.get('doctor_id') and valid_data.get('hospital_id'):
            queryset = queryset.filter(Q(hospital__isnull=True, doctor=valid_data.get('doctor_id'))
                                                              |
                                                              Q(hospital__isnull=False,
                                                                hospital=valid_data.get('hospital_id'))
                                                            )
        if valid_data.get('updated_at'):
            admin_queryset = auth_models.GenericAdmin.objects.filter(user=request.user, updated_at__gte=valid_data.get('updated_at'))
            if not admin_queryset.exists():
                queryset = queryset.filter(updated_at__gte=valid_data.get('updated_at'))
        # queryset = queryset.values('name', 'id', 'gender', 'doctor', 'hospital', 'age', 'dob', 'calculated_dob', 'updated_at',
        #                            'share_with_hospital', 'sms_notification', 'medical_history',
        #                            'referred_by', 'display_welcome_message', 'error'
        #                            ).distinct()
        response = []
        for data in queryset.distinct().all():
            patient_dict = {}
            patient_dict['id'] = data.id
            patient_dict['name'] = data.name if data.name else None
            patient_dict['encrypted_name'] = data.encrypted_name if data.encrypted_name else None
            patient_dict['gender'] = data.gender if data.gender else None
            patient_dict['doctor'] = data.doctor.id if data.doctor else None
            patient_dict['hospital'] = data.hospital.id if data.hospital else None
            patient_dict['age'] = data.age if data.age else None
            patient_dict['dob'] = data.dob if data.dob else None
            patient_dict['calculated_dob'] = data.calculated_dob if data.calculated_dob else None
            patient_dict['updated_at'] = data.updated_at if data.updated_at else None
            patient_dict['share_with_hospital'] = data.share_with_hospital if data.share_with_hospital else None
            patient_dict['sms_notification'] = data.sms_notification if data.sms_notification else None
            patient_dict['medical_history'] = data.medical_history if data.medical_history else None
            patient_dict['referred_by'] = data.referred_by if data.referred_by else None
            patient_dict[
                'display_welcome_message'] = data.display_welcome_message if data.display_welcome_message else None
            patient_dict['error'] = data.error if data.error else None
            patient_numbers = []
            patient_dict['phone_number'] = None
            if hasattr(data, 'patient_mobiles'):
                for mob in data.patient_mobiles.all():
                    if mob.encrypted_number:
                        patient_numbers.append({"phone_number": mob.encrypted_number, "is_default": mob.is_default})
                        if mob.is_default:
                            patient_dict['encrypted_phone_number'] = mob.encrypted_number
                            patient_dict['encrypted_numbers'] = patient_numbers
                    else:
                        patient_numbers.append({"phone_number": mob.phone_number, "is_default": mob.is_default})
                        if mob.is_default:
                            patient_dict['phone_number'] = mob.phone_number
                            patient_dict['patient_numbers'] = patient_numbers
            # patient_dict['patient_numbers'] = patient_numbers
            response.append(patient_dict)
        return Response(response)

    @transaction.atomic
    def create_offline_patients(self, request):
        serializer = serializers.OfflinePatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        sms_list = []
        resp = []
        patient_ids = models.OfflinePatients.objects.values_list('id', flat=True)

        for data in valid_data['data']:
            if data.get('id') in patient_ids:
                # obj = {'doctor': data.get('doctor').id,
                #        'hospital': data.get('hospital').id if data.get('hospital') else None,
                #        'id': data.get('id'),
                #        'error': True,
                #        'error_message': "Patient With Same UUid exists!"}
                # resp.append(obj)
                # logger.error("Patient With Same UUid exists! " + str(data))
                # continue

                patient_data = self.update_patient(request, data, data.get('hospital'), data.get('doctor'))
            else:
                patient_data = self.create_patient(request, data, data.get('hospital'), data.get('doctor'))
            patient = patient_data['patient']
            if patient_data['sms_list'] is not None:
                sms_list.append(patient_data['sms_list'])

            ret_obj = {}
            ret_obj['doctor'] = patient.doctor.id if patient.doctor else None
            ret_obj['hospital'] = patient.hospital.id if patient.hospital else None
            ret_obj['id'] = patient.id
            ret_obj['error'] = patient.error
            ret_obj['error_message'] = patient.error_message
            resp.append(ret_obj)

            # if sms_list:
            #     transaction.on_commit(lambda: models.OfflineOPDAppointments.after_commit_create_sms(sms_list))

        return Response(resp)

    @transaction.atomic
    def create_offline_appointments(self, request):
        serializer = serializers.OfflineAppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        patient = None
        sms_list = []
        resp = []
        req_hosp_ids = []
        filter_appntment_ids = []
        patient_ids = []
        for data in valid_data.get('data'):
            if data.get('hospital'):
                req_hosp_ids.append(data.get('hospital').id)
            if data.get('id'):
                filter_appntment_ids.append(data.get('id'))
            if data.get('patient') and data['patient'].get('id'):
                patient_ids.append(data['patient']['id'])
        appointment_ids = list(models.OfflineOPDAppointments.objects.filter(id__in=filter_appntment_ids).values_list('id', flat=True))
        patient_ids = list(models.OfflinePatients.objects.filter(id__in=patient_ids).values_list('id', flat=True))
        clinic_queryset = [(dc.doctor.id, dc.hospital.id) for dc in
                           models.DoctorClinic.objects.filter(hospital__id__in=req_hosp_ids)]
        pem_queryset = [(ga.doctor.id if ga.doctor else None, ga.hospital.id if ga.hospital else None) for ga in auth_models.GenericAdmin.objects.filter(is_disabled=False, user=request.user).all()]
        doc_pem_list, hosp_pem_list = map(list, zip(*pem_queryset))

        for data in valid_data.get('data'):
            uuid_obj = self.validate_uuid(data)
            id = uuid_obj.get('id') if 'id' in uuid_obj and uuid_obj.get('id') else None
            if not id and 'continue' in uuid_obj and uuid_obj.get('continue'):
                resp.append(uuid_obj.get('obj'))
                continue
            data['id'] = id
            self.validate_permissions(data, doc_pem_list, hosp_pem_list, clinic_queryset)

            create_obj = self.validate_create_conditions(appointment_ids, data, request)
            if 'continue' in create_obj and create_obj.get('continue'):
                resp.append(create_obj.get('obj'))
                continue

            if not data.get('patient')['id'] in patient_ids:
                patient_data = self.create_patient(request, data['patient'], data['hospital'], data['doctor'])
                patient_ids.append(patient_data['patient'].id)
            else:
                patient_data = self.update_patient(request, data['patient'], data['hospital'], data['doctor'])
            patient = patient_data['patient']
            if patient_data.get('sms_list'):
                sms_list.append(patient_data['sms_list'])

            try:
                appnt = models.OfflineOPDAppointments.objects.create(doctor=data.get('doctor'),
                                                                     id=id,
                                                                     hospital=data.get('hospital'),
                                                                     time_slot_start=data.get('time_slot_start'),
                                                                     booked_by=request.user,
                                                                     user=patient,
                                                                     status=models.OfflineOPDAppointments.ACCEPTED,
                                                                     fees=data.get('fees'),
                                                                     error=data.get('error') if data.get('error') else False,
                                                                     error_message=data.get('error_message') if data.get('error_message') else None
                                                                              )
            except Exception as e:
                obj = {'id': data.get('id'),
                       'error': True,
                       'error_message': "Something Went Wrong!"}
                obj['doctor_id'] = data.get('doctor').id
                obj['hospital_id'] = data.get('hospital').id
                resp.append(obj)
                logger.error("Fialed Creating Appointment " + str(e))
                continue

            if patient_data.get('sms_list'):
                patient_data['sms_list']['appointment'] = appnt
            appointment_ids.append(appnt.id)
            ret_obj = {}
            ret_obj['id'] = appnt.id
            ret_obj['patient_id'] = appnt.user.id
            ret_obj['error'] = appnt.error
            ret_obj['error_message'] = appnt.error_message
            ret_obj.update(self.get_offline_response_obj(appnt, request))
            resp.append(ret_obj)

        if sms_list:
            transaction.on_commit(lambda: models.OfflineOPDAppointments.after_commit_create_sms(sms_list))

        return Response(resp)

    def create_patient(self, request, data, hospital, doctor):
        if data.get('share_with_hospital') and not hospital:
            logger.error('PROVIDER_REQUEST - Hospital Not Given when Shared with Hospital Set'+ str(data))
        hosp = hospital if data.get('share_with_hospital') and hospital else None
        encrypt_number = None
        if hosp and hasattr(hosp, 'encrypt_details') and hosp.encrypt_details.is_encrypted:
            encrypt_number = data.get('encrypt_number')
        patient = models.OfflinePatients.objects.create(name=data.get('name'),
                                                        encrypted_name=data.get('encrypted_name', None),
                                                        id=data.get('id'),
                                                        sms_notification=data.get('sms_notification', False),
                                                        gender=data.get('gender'),
                                                        dob=data.get("dob"),
                                                        calculated_dob=data.get("calculated_dob"),
                                                        age=data.get('age'),
                                                        referred_by=data.get('referred_by'),
                                                        medical_history=data.get('medical_history'),
                                                        welcome_message=data.get('welcome_message'),
                                                        display_welcome_message=data.get('display_welcome_message',
                                                                                         False),
                                                        doctor=doctor,
                                                        hospital=hosp,
                                                        created_by=request.user,
                                                        error=data.get('error') if data.get('error') else False,
                                                        error_message=data.get('error_message') if data.get(
                                                            'error_message') else False
                                                        )
        default_num = None
        sms_number = None
        if data.get('phone_number') and not encrypt_number:
            for num in data.get('phone_number'):
                models.PatientMobile.objects.create(patient=patient,
                                                    phone_number=num.get('phone_number'),
                                                    is_default=num.get('is_default', False)
                                                    )

                if 'is_default' in num and num['is_default']:
                    default_num = num['phone_number']
            if default_num and ('sms_notification' in data and data['sms_notification']):
                sms_number = {'phone_number': default_num,
                              'name': patient.name,
                              'welcome_message': data.get('welcome_message'),
                              'display_welcome_message': data.get('display_welcome_message', False)}
        if encrypt_number:
            for num in encrypt_number:
                models.PatientMobile.objects.create(patient=patient,
                                                    encrypted_number=num.get('phone_number'),
                                                    is_default=num.get('is_default', False)
                                                    )
                sms_number = None
        return {"sms_list": sms_number, "patient": patient}

    def update_patient(self, request, data, hospital, doctor):
        if data.get('share_with_hospital') and not hospital:
            logger.error('PROVIDER_REQUEST - Hospital Not Given when Shared with Hospital Set'+ str(data))
        hosp = hospital if data.get('share_with_hospital') and hospital else None
        encrypt_number = encrypted_name = None
        # if hosp and hosp.provider_encrypt:
        #     encrypt_number = data.get('encrypt_number')
        #     encrypted_name = data.get('encrypted_name')
        patient = models.OfflinePatients.objects.filter(id=data.get('id')).first()
        if patient:
            if data.get('gender'):
                patient.gender = data.get('gender')
            if data.get('dob'):
                patient.dob = data.get('dob')
            if data.get('calculated_dob'):
                patient.calculated_dob = data.get('calculated_dob')
            if data.get('referred_by'):
                patient.referred_by = data.get('referred_by')
            if data.get('medical_history'):
                patient.medical_history = data.get('medical_history')
            if data.get('sms_notification'):
                patient.sms_notification = data.get('sms_notification')
            if data.get('display_welcome_message'):
                patient.display_welcome_message = data.get('display_welcome_message')
            if data.get('share_with_hospital'):
                patient.share_with_hospital = data.get('share_with_hospital')
            if hosp:
                patient.hospital = hosp
            if doctor:
                patient.doctor = doctor
            if data.get('encrypted_name'):
                patient.encrypted_name = data.get('encrypted_name')
                patient.name = None
            if not data.get('encrypted_name'):
                patient.encrypted_name = None
                if data.get('name'):
                    patient.name = data.get('name')
            patient.save()
            default_num = None
            sms_number = None

            del_queryset = models.PatientMobile.objects.filter(patient=patient)

            if data.get('phone_number') and not data.get('encrypt_number'):
                del_queryset.delete()
                for num in data.get('phone_number'):
                    models.PatientMobile.objects.create(patient=patient,
                                                        phone_number=num.get('phone_number'),
                                                        is_default=num.get('is_default', False))

                    if 'is_default' in num and num['is_default']:
                        default_num = num['phone_number']
                if default_num and ('sms_notification' in data and data['sms_notification']):
                    sms_number = {'phone_number': default_num,
                                  'name': patient.name}
                    sms_number['welcome_message'] = data.get('welcome_message')
                    sms_number['display_welcome_message'] = False
            if data.get('encrypt_number'):
                del_queryset.delete()
                for num in data.get('encrypt_number'):
                    models.PatientMobile.objects.create(patient=patient,
                                                        encrypted_number=num.get('phone_number'),
                                                        is_default=num.get('is_default', False)
                                                        )
                    sms_number = None
            return {"sms_list": sms_number, "patient": patient}

    def update_offline_appointments(self, request):
        serializer = serializers.OfflineAppointmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        sms_list = []
        resp = []
        appnt_ids = []
        req_hosp_ids = []
        patient_ids  = []
        for data in valid_data.get('data'):
            if data.get('hospital'):
                req_hosp_ids.append(data.get('hospital').id)
            if data.get('id'):
                appnt_ids.append(data.get('id'))
            if data.get('patient') and data['patient'].get('id'):
                patient_ids.append(data['patient']['id'])
        appntment_ids = models.OfflineOPDAppointments.objects.select_related('doctor', 'hospital', 'user')\
                                                     .filter(id__in=appnt_ids).all()
        patient_ids = list(models.OfflinePatients.objects.filter(id__in=patient_ids).values_list('id', flat=True))
        clinic_queryset = [(dc.doctor.id, dc.hospital.id) for dc in models.DoctorClinic.objects.filter(hospital__id__in=req_hosp_ids)]
        pem_queryset = [(ga.doctor.id if ga.doctor else None, ga.hospital.id if ga.hospital else None) for ga in
                        auth_models.GenericAdmin.objects.filter(is_disabled=False, user=request.user).all()]
        doc_pem_list, hosp_pem_list = map(list, zip(*pem_queryset))

        for data in valid_data.get('data'):
            if not data.get('is_docprime'):
                uuid_obj = self.validate_uuid(data)
                id = uuid_obj.get('id') if 'id' in uuid_obj and uuid_obj.get('id') else None
                if not id and 'continue' in uuid_obj and uuid_obj.get('continue'):
                    resp.append(uuid_obj.get('obj'))
                    continue

                found = False
                for appnt in appntment_ids:
                    if id == appnt.id:
                        patient = def_number = action_cancel = action_add = action_reschedule = action_complete = None
                        found = True

                        self.validate_permissions(data, doc_pem_list, hosp_pem_list, clinic_queryset)

                        update_obj = self.validate_update_conditions(appnt, data, request)
                        if 'break' in update_obj and update_obj.get('break'):
                            resp.append(update_obj.get('obj'))
                            break
                        old_appnt = deepcopy(appnt)
                        if data.get('patient'):
                            if not data.get('patient')['id'] in patient_ids:
                                patient_data = self.create_patient(request, data['patient'], data['hospital'],
                                                                   data['doctor'])
                                patient_ids.append(patient_data['patient'].id)
                                action_cancel = True
                            else:
                                patient_data = self.update_patient(request, data['patient'], data['hospital'],
                                                                   data['doctor'])
                            patient = patient_data['patient']
                            if patient_data.get('sms_list'):
                                patient_data['sms_list']['old_appointment'] = old_appnt
                                sms_list.append(patient_data['sms_list'])
                            appnt.user = patient
                        else:
                            patient = appnt.user
                            patient_data = {}
                            if patient.sms_notification:
                                def_number = patient.patient_mobiles.filter(is_default=True).first()
                                if def_number:
                                    patient_data['sms_list'] = {'phone_number': def_number.phone_number,
                                                                'name': patient.name,
                                                                'old_appointment': old_appnt}
                                    sms_list.append(patient_data['sms_list'])

                        if appnt.doctor.id != data.get('doctor').id or appnt.hospital.id != data.get('hospital').id:
                            action_cancel = True
                        if not action_cancel and (data.get('time_slot_start') != appnt.time_slot_start):
                            action_reschedule = True
                        if data.get('status') == models.OfflineOPDAppointments.COMPLETED:
                            action_complete = True
                        appnt.doctor = data.get('doctor')
                        appnt.hospital = data.get('hospital')
                        appnt.fees = data.get('fees')
                        appnt.error = data.get('error', False)
                        appnt.error_message = data.get('error_message')
                        if data.get("time_slot_start"):
                            appnt.time_slot_start = data.get("time_slot_start")
                        if data.get('status'):
                            appnt.status = data.get('status')
                        try:
                            appnt.save()
                        except Exception as e:
                            obj = self.get_error_obj(data)
                            obj['error_message'] = 'Error Saving Appointment ' + str(e)
                            obj.update(self.get_offline_response_obj(appnt, request))
                            resp.append(obj)
                            break
                        if patient_data.get('sms_list'):
                            patient_data['sms_list']['appointment'] = appnt
                            patient_data['sms_list']['action_cancel'] = action_cancel
                            patient_data['sms_list']['action_reschedule'] = action_reschedule
                            patient_data['sms_list']['action_complete'] = action_complete
                        ret_obj = {}
                        ret_obj['id'] = appnt.id
                        ret_obj['patient_id'] = appnt.user.id
                        ret_obj['error'] = appnt.error
                        ret_obj['status'] = data.get('status') if data.get('status') else appnt.status
                        ret_obj['error_message'] = appnt.error_message if appnt.error_message else None
                        ret_obj.update(self.get_offline_response_obj(appnt, request))
                        resp.append(ret_obj)
                        break
                if not found:
                    obj = self.get_error_obj(data)
                    obj['error_message'] = "Appointment not Found!"
                    resp.append(obj)
                    logger.error("PROVIDER_REQUEST - Offline Update Appointment is not Found! " + str(data))

        if sms_list:
            models.OfflineOPDAppointments.after_commit_update_sms(sms_list)

        return Response(resp)

    def offline_timings(self, request):
        user = request.user
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        manageable_hosp_list = auth_models.GenericAdmin.get_manageable_hospitals(user)

        dc_queryset = models.DoctorClinic.objects.filter(hospital_id__in=manageable_hosp_list).distinct().values('id', 'doctor', 'hospital')
        if dc_queryset:
            dc_list = [(dc['id'], dc['doctor']) for dc in dc_queryset]
            dc_id_list, dc_doc_list = zip(*dc_list)

            if not validated_data.get('doctor_id') and not validated_data.get('hospital_id'):

                dct_queryset = models.DoctorClinicTiming.objects.filter(doctor_clinic__id__in=dc_id_list).values('doctor_clinic',
                                                                                                                 'day',
                                                                                                                 'start',
                                                                                                                 'end',
                                                                                                                 'fees',
                                                                                                                 'deal_price',
                                                                                                                 'mrp')
                dl_queryset = models.DoctorLeave.objects.filter(doctor_id__in=dc_doc_list, deleted_at__isnull=True).all()

                all_timing = {}
                for dclinic in dc_queryset:
                    key = str(dclinic['doctor']) + '_' + str(dclinic['hospital'])
                    for dclinictime in dct_queryset:
                        if dclinictime.get('doctor_clinic') == dclinic.get('id'):
                            if not key in all_timing:
                                timing = {}
                                for i in range(7):
                                    timing[i] = dict()
                                all_timing[key] = {}
                                for dl in dl_queryset:
                                    dl_data = None
                                    if dl.doctor_id == dclinic['doctor']:

                                        dl_data = {'interval': dl.interval,
                                                   'start_time': dl.start_time,
                                                   'end_time': dl.end_time,
                                                   'leave_start_time': dl.start_time_in_float(),
                                                   'leave_end_time': dl.end_time_in_float()}
                                    all_timing[key]['doctor_leaves'] = dl_data
                            else:
                                timing = all_timing[key]['timeslots']
                            timing_data = offline_form_time_slots(dclinictime, timing)
                            all_timing[key]['timeslots'] = timing_data
                return Response(all_timing)
            else:
                if not validated_data['doctor_id'].id in dc_doc_list:
                    return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
                queryset = models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=validated_data.get('doctor_id'),
                                                                    doctor_clinic__hospital=validated_data.get(
                                                                        'hospital_id')).order_by("start")
                doctor_leave_serializer = v2_serializers.DoctorLeaveSerializer(
                    models.DoctorLeave.objects.filter(doctor=validated_data.get("doctor_id"), deleted_at__isnull=True),
                    many=True)

                timeslots = dict()
                obj = TimeSlotExtraction()

                for data in queryset:
                    obj.form_time_slots(data.day, data.start, data.end, data.fees, True,
                                        data.deal_price, data.mrp, data.dct_cod_deal_price(), True)

                timeslots = obj.get_timing_list()
                for day, slots in timeslots.items():
                    day_timing = []
                    for slot_unit in slots:
                        day_timing.extend(slot_unit['timing'])
                    timeslots[day] = day_timing
                return Response({"timeslots": timeslots,
                                 "doctor_leaves": doctor_leave_serializer.data})

        else:
            return Response([])

    def get_app_billing_status(self, app):
        INCOMPLETE = 1
        ELIGIBLE = 2
        INITIATED = 3
        PROCESSED = 4
        billing_status = utr_number = None
        if app.time_slot_start <= timezone.now() and \
                app.status not in [models.OpdAppointment.COMPLETED, models.OpdAppointment.CANCELLED,
                                   models.OpdAppointment.BOOKED]:
            billing_status = INCOMPLETE
        elif app.status == models.OpdAppointment.COMPLETED and (
                not app.merchant_payout or app.merchant_payout.status not in \
                [account_models.MerchantPayout.ATTEMPTED, account_models.MerchantPayout.PAID]):
            billing_status = ELIGIBLE
        elif app.status == models.OpdAppointment.COMPLETED and (
                app.merchant_payout and app.merchant_payout.status == account_models.MerchantPayout.ATTEMPTED):
            billing_status = INITIATED
        elif app.status == models.OpdAppointment.COMPLETED and (
                app.merchant_payout and app.merchant_payout.status == account_models.MerchantPayout.PAID):
            billing_status = PROCESSED
            if app.merchant_payout and app.merchant_payout.utr_no:
                utr_number = app.merchant_payout.utr_no
        return (billing_status, utr_number)

    def get_lab_appointment_list(self, request, user, valid_data):
        from ondoc.diagnostic import models as lab_models
        from ondoc.api.v1.diagnostic.serializers import LabAppointmentTestMappingSerializer
        mask_data = None
        response = []
        manageable_lab_list = auth_models.GenericLabAdmin.objects.filter(is_disabled=False, user=user) \
            .values_list('lab', flat=True)
        appointment_queryset = lab_models.LabAppointment.objects\
                                                        .select_related('lab', 'merchant_payout', 'profile')\
                                                        .prefetch_related('lab__lab_documents', 'mask_number',
                                                                          'profile__insurance',
                                                                          'profile__insurance__user_insurance',
                                                                          'appointment_prescriptions', 'test_mappings',
                                                                          'test_mappings__test', 'reports', 'reports__files')\
                                                        .filter(lab_id__in=manageable_lab_list) \
                                                        .exclude(status=lab_models.LabAppointment.CREATED)\
                                                        .annotate(pem_type=Case(When(Q(lab__manageable_lab_admins__user=user) &
                                                                 Q(lab__manageable_lab_admins__super_user_permission=True) &
                                                                 Q(lab__manageable_lab_admins__is_disabled=False), then=Value(3)),
                                                            When(Q(lab__manageable_lab_admins__user=user) &
                                                                 Q(lab__manageable_lab_admins__super_user_permission=False) &
                                                                 Q(
                                                                     lab__manageable_lab_admins__permission_type=auth_models.GenericAdmin.BILLINNG) &
                                                                 ~Q(
                                                                     lab__manageable_lab_admins__permission_type=auth_models.GenericAdmin.APPOINTMENT) &
                                                                 Q(lab__manageable_lab_admins__is_disabled=False), then=Value(2)),
                                                            When(Q(lab__manageable_lab_admins__user=user) &
                                                                 Q(lab__manageable_lab_admins__super_user_permission=False) &
                                                                 Q(
                                                                     lab__manageable_lab_admins__permission_type=auth_models.GenericAdmin.BILLINNG) &
                                                                 Q(
                                                                     lab__manageable_lab_admins__permission_type=auth_models.GenericAdmin.APPOINTMENT) &
                                                                 Q(lab__manageable_lab_admins__is_disabled=False), then=Value(3)),
                                                            default=Value(1),
                                                            output_field=IntegerField()
                                                            )
                                                        ).distinct('id')

        appointment_id = valid_data.get('appointment_id')
        if appointment_id:
            appointment_queryset = appointment_queryset.filter(id=appointment_id)

        for app in appointment_queryset:
            address = ''
            mask_number = app.mask_number.all()
            if mask_number and mask_number[0]:
                mask_data = mask_number[0].build_data()
            if app.address:
                ad = app.address.get('address') if app.address.get('address') else ''
                loc = app.address.get('locality') if app.address.get('locality') else ''
                address = ad + ' ' + loc
            rep_dict = {}
            files = []
            for rep in app.reports.all():
                for file in rep.files.all():
                    url = request.build_absolute_uri(file.name.url) if file.name else None
                    files.append(url)
                rep_dict = {
                    "updated_at": rep.updated_at,
                    "details": rep.report_details,
                    "files": files
                }
            patient_profile = auth_serializers.UserProfileSerializer(app.profile, context={'request': request}).data
            patient_profile['profile_id'] = app.profile.id if hasattr(app, 'profile') else None
            patient_thumbnail = patient_profile['profile_image']
            billing_status, utr_number = self.get_app_billing_status(app)
            ret_obj = {}
            ret_obj['id'] = app.id
            ret_obj['deal_price'] = app.deal_price
            ret_obj['payout_amount'] = app.merchant_payout.payable_amount if app.merchant_payout else app.agreed_price
            ret_obj['effective_price'] = app.effective_price
            ret_obj['allowed_action'] = app.allowed_action(User.DOCTOR, request)
            ret_obj['patient_name'] = app.profile.name if hasattr(app, 'profile') else None
            ret_obj['updated_at'] = app.updated_at
            ret_obj['created_at'] = app.created_at
            ret_obj['lab_name'] = app.lab.name
            ret_obj['lab_id'] = app.lab.id
            ret_obj['lab_thumbnail'] = request.build_absolute_uri(
                    app.lab.get_thumbnail()) if app.lab.get_thumbnail() else None
            ret_obj['time_slot_start'] = app.time_slot_start
            ret_obj['status'] = app.status
            ret_obj['mrp'] = app.price
            ret_obj['mask_data'] = mask_data
            ret_obj['payment_type'] = app.payment_type
            ret_obj['billing_status'] = billing_status
            ret_obj['utr_number'] = utr_number
            ret_obj['profile'] = patient_profile
            ret_obj['permission_type'] = app.pem_type
            ret_obj['is_docprime'] = True
            ret_obj['patient_thumbnail'] = patient_thumbnail
            ret_obj['type'] = 'lab'
            ret_obj['address'] = address
            ret_obj['is_home_pickup'] = app.is_home_pickup
            ret_obj['home_pickup_charges'] = app.home_pickup_charges
            ret_obj['prescriptions'] = app.get_prescriptions(request)
            ret_obj['lab_test'] = LabAppointmentTestMappingSerializer(app.test_mappings.all(), many=True).data
            ret_obj['reports'] = rep_dict
            response.append(ret_obj)
        return response

    def list_appointments(self, request):
        ONLINE = 1
        OFFLINE = 2
        serializer = serializers.OfflineAppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        type = valid_data.get('type')
        if type == serializers.OfflineAppointmentFilterSerializer.LAB:
            lab_data = self.get_lab_appointment_list(request, request.user, valid_data)
            if valid_data.get('appointment_id') and not lab_data:
                return Response({"status": 0, "error": "data not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(lab_data)

        online_queryset = get_opd_pem_queryset(request.user, models.OpdAppointment) \
            .exclude(status=models.OpdAppointment.CREATED)\
            .select_related('profile', 'merchant_payout')\
            .prefetch_related('prescriptions', 'prescriptions__prescription_file', 'mask_number',
                              'profile__insurance', 'profile__insurance__user_insurance', 'eprescription').distinct('id', 'time_slot_start')

        offline_queryset = get_opd_pem_queryset(request.user, models.OfflineOPDAppointments)\
            .select_related('user')\
                .prefetch_related('user__patient_mobiles', 'eprescription', 'offline_prescription', 'partners_app_invoice').distinct('id')
        start_date = valid_data.get('start_date')
        end_date = valid_data.get('end_date')
        updated_at = valid_data.get('updated_at')
        appointment_id = valid_data.get('appointment_id')
        final_data = []
        if start_date and end_date:
            online_queryset = online_queryset.filter(time_slot_start__date__range=(start_date, end_date))\
                .order_by('time_slot_start')
            offline_queryset = offline_queryset.filter(time_slot_start__date__range=(start_date, end_date))\
                .order_by('time_slot_start')
        if updated_at:
            # admin_queryset = auth_models.GenericAdmin.objects.filter(user=request.user, updated_at__gte=updated_at)
            # if not admin_queryset.exists():
            online_queryset = online_queryset.filter(updated_at__gte=updated_at)
            offline_queryset = offline_queryset.filter(updated_at__gte=updated_at)

        if appointment_id:
            offline_id= True
            try:
                id = UUID(appointment_id, version=4)
            except ValueError:
                offline_id = False
            if not offline_id:
                final_data = online_queryset.filter(id=appointment_id)
                offline_queryset = None
            else:
                final_data = offline_queryset.filter(id=appointment_id)
                online_queryset = None
        if online_queryset and offline_queryset:
            final_data = sorted(chain(online_queryset, offline_queryset), key=lambda car: car.time_slot_start, reverse=False)

        if not final_data:
            final_data = online_queryset if online_queryset else offline_queryset
        final_result = []
        if appointment_id and not final_data:
            return Response({'error': 'Not Found'}, status=status.HTTP_404_NOT_FOUND)
        for app in final_data:
            instance = ONLINE if isinstance(app, models.OpdAppointment) else OFFLINE
            patient_name = is_docprime = effective_price = deal_price = patient_thumbnail = prescription = None
            if instance == OFFLINE and (hasattr(app.user, 'encrypted_name') and app.user.encrypted_name) and (
                    (request.META.get('HTTP_PLATFORM') == 'android' and not parse(request.META.get(
                        'HTTP_APP_VERSION')) > parse(settings.LIST_APPOINTMENTS_VERSION_CHECK_ANDROID_GT[0])) or
                    (request.META.get('HTTP_PLATFORM') == 'ios' and not parse(request.META.get(
                        'HTTP_APP_VERSION')) > parse(settings.LIST_APPOINTMENTS_VERSION_CHECK_IOS_GT[0]))):
                continue
            error_flag = False
            error_message = ''
            phone_number = []
            allowed_actions = []
            payout_amount = billing_status = utr_number = None
            mask_data = None
            mrp = None
            payment_type = None
            invoice_data = invoice = None
            if instance == OFFLINE:
                for inv in app.partners_app_invoice.all():
                    if inv.is_valid:
                        invoice = inv
                        break
                invoice_data = v2_serializers.PartnersAppInvoiceModelSerialier(invoice).data if invoice else None
                patient_profile = OfflinePatientSerializer(app.user).data
                is_docprime = False
                patient_name = app.user.name if hasattr(app.user, 'name') else None
                patient_profile['phone_number'] = None
                if hasattr(app.user, 'patient_mobiles'):
                    for mob in app.user.patient_mobiles.all():
                        if not mob.encrypted_number:
                            phone_number.append({"phone_number": mob.phone_number, "is_default": mob.is_default})
                            if mob.is_default:
                                patient_profile['phone_number'] = mob.phone_number
                                patient_profile['patient_numbers'] = phone_number
                        else:
                            phone_number.append({"phone_number": mob.encrypted_number, "is_default": mob.is_default})
                            if mob.is_default:
                                patient_profile['encrypted_phone_number'] = mob.encrypted_number
                                patient_profile['encrypt_number'] = phone_number
                # patient_profile['patient_numbers'] = phone_number
                error_flag = app.error if app.error else False
                error_message = app.error_message if app.error_message else ''
                prescription = app.get_prescriptions(request)

            else:
                is_docprime = True
                effective_price = app.effective_price
                # mrp = app.mrp
                mrp_fees = app.fees if app.fees else 0
                #RAJIV YADAV
                mrp = app.deal_price if app.payment_type == app.COD else mrp_fees
                payment_type = app.payment_type
                deal_price = app.deal_price
                mask_number = app.mask_number.all()
                if mask_number and mask_number[0]:
                    mask_data = mask_number[0].build_data()
                allowed_actions = app.allowed_action(User.DOCTOR, request)
                # phone_number.append({"phone_number": app.user.phone_number, "is_default": True})
                patient_profile = auth_serializers.UserProfileSerializer(app.profile, context={'request': request}).data
                patient_profile['profile_id'] = app.profile.id if hasattr(app, 'profile') else None
                patient_thumbnail = patient_profile['profile_image']
                patient_name = app.profile.name if hasattr(app, 'profile') else None
                billing_status, utr_number = self.get_app_billing_status(app)
                payout_amount = app.merchant_payout.payable_amount if app.merchant_payout else app.fees
                prescription = app.get_prescriptions(request)
            doc_number = None
            for number in app.doctor.doctor_number.all():
                if number.hospital == app.hospital:
                    doc_number = number.phone_number
                    break
            ret_obj = {}
            ret_obj['id'] = app.id
            ret_obj['deal_price'] = deal_price
            ret_obj['payout_amount'] = payout_amount
            ret_obj['effective_price'] = effective_price
            ret_obj['allowed_action'] = allowed_actions
            ret_obj['patient_name'] = patient_name
            ret_obj['updated_at'] = app.updated_at
            ret_obj['created_at'] = app.created_at
            ret_obj['doctor_name'] = app.doctor.name
            ret_obj['doctor_id'] = app.doctor.id
            ret_obj['doctor_number'] = doc_number
            ret_obj['doctor_thumbnail'] = request.build_absolute_uri(app.doctor.get_thumbnail()) if app.doctor.get_thumbnail() else None
            ret_obj['hospital_id'] = app.hospital.id
            ret_obj['hospital_name'] = app.hospital.name
            ret_obj['time_slot_start'] = app.time_slot_start
            ret_obj['status'] = app.status
            ret_obj['mrp'] = mrp
            ret_obj['mask_data'] = mask_data
            ret_obj['payment_type'] = payment_type
            ret_obj['billing_status'] = billing_status
            ret_obj['utr_number'] = utr_number
            ret_obj['profile'] = patient_profile
            ret_obj['permission_type'] = app.pem_type
            ret_obj['hospital'] = HospitalModelSerializer(app.hospital).data
            ret_obj['doctor'] = AppointmentRetrieveDoctorSerializer(app.doctor).data
            ret_obj['is_docprime'] = is_docprime
            ret_obj['patient_thumbnail'] = patient_thumbnail
            ret_obj['error'] = error_flag
            ret_obj['error_message'] = error_message
            ret_obj['type'] = 'doctor'
            ret_obj['prescriptions'] = prescription
            ret_obj['e_prescriptions'] = pres_serializers.PrescriptionPDFModelSerializer(app.eprescription, many=True, context={"request": request}).data
            ret_obj['invoice'] = invoice_data
            final_result.append(ret_obj)
        return Response(final_result)


class HospitalNetworkListViewset(viewsets.GenericViewSet):

    def list(self, request, hospital_network_id):
        parameters = request.query_params
        serializer = serializers.HospitalCardSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = models.Hospital.objects.prefetch_related('assoc_doctors', 'assoc_doctors__rating', 'assoc_doctors__doctorpracticespecializations',
                                                     'assoc_doctors__doctorpracticespecializations__specialization',
                                                     'assoc_doctors__doctorpracticespecializations__specialization__department').filter(network_id=hospital_network_id).annotate(doctor_count=Count('assoc_doctors', distinct=True) )
        resp1 = {}
        longitude = valid_data.get('longitude')
        latitude = valid_data.get('latitude')

        pnt = Point(float(longitude), float(latitude))

        if not queryset.exists():
            return Response([])

        if len(queryset) > 0:
            info = []
            network_name = None

            for data in queryset:
                resp = {}
                ratings = None

                location = data.location if data.location else None
                if location:
                    distance = pnt.distance(location)*100
                    resp['distance'] = distance
                else:
                    resp['distance'] = None

                all_doctors = data.assoc_doctors.all()
                empty = []
                for doctor_ratings in all_doctors:
                    final_ratings = [rating.ratings for rating in doctor_ratings.rating.all()]
                    empty.extend(final_ratings)

                ans=set()
                ans1=set()
                for doctor in all_doctors:
                     ans = [dps.specialization.name for dps in doctor.doctorpracticespecializations.all()]
                     ans1 = [dpn.name for dps in doctor.doctorpracticespecializations.all() for dpn in dps.specialization.department.all()]

                ratings_count = None
                if len(empty) > 0:
                    ratings_count = sum(empty)/len(empty)
                resp['hospital_specialization'] = ', '.join(ans) if len(ans) < 3 else 'Multispeciality'
                if ans1:
                    ans1 = set(filter(lambda v: v is not None, ans1))
                    resp['departments'] = ', '.join(ans1) if len(ans1) < 3 else '%s + %d  more.' %(', '.join(list(ans1)[:2]), len(ans1)-2)
                resp['hospital_ratings'] = ratings_count if ratings_count else None
                resp['id'] = data.id
                resp['city'] = data.city if data.city else None
                resp['state'] = data.state if data.state else None
                resp['country'] = data.country if data.country else None
                resp['address'] = data.get_hos_address()
                resp['name'] = data.name if data.name else None
                resp['number_of_doctors'] = data.doctor_count if data.doctor_count else None
                info.append(resp)

                if not network_name:
                    network_name = data.network.name if data.network else None
                    resp1 = {"network_name": network_name, "hospitals": info}

        return Response(resp1)


class AppointmentMessageViewset(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def send_message(self, request):
        serializer = serializers.AppointmentMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        appnt = data.get('appointment')
        patient = appnt.user
        obj = {"error": False}
        phone_number = None
        if not data.get('is_docprime'):
            if patient.sms_notification:
                def_number = patient.patient_mobiles.filter(is_default=True).first()
                if def_number:
                    phone_number = def_number.phone_number
            else:
                obj['error'] = True
                obj['message'] = 'Sms Notifications Not Enabled!'
                return Response(obj, status=status.HTTP_400_BAD_REQUEST)
            patient_name = patient.name
        else:
            phone_number = patient.phone_number
            patient_name = appnt.profile.name if appnt.profile else ''

        if data.get('type') == serializers.AppointmentMessageSerializer.REMINDER:
            if phone_number:
                try:
                    time = aware_time_zone(appnt.time_slot_start)
                    notification_tasks.send_appointment_reminder_message.apply_async(
                        kwargs={'number': phone_number,
                                'patient_name': patient_name,
                                'doctor': appnt.doctor.name,
                                'hospital_name': appnt.hospital.name,
                                'date': time.strftime("%B %d, %Y %I:%M %p")},
                        countdown=1)

                except Exception as e:
                    obj['error'] = True
                    obj['message'] = 'Error Sending Appointment Reminder Message!'
                    logger.error("Error Sending Appointment Reminder Message " + str(e))
            else:
                obj['error'] = True
                obj['message'] = 'No Default Number'
                return Response(obj, status=status.HTTP_400_BAD_REQUEST)
        if data.get('type') == serializers.AppointmentMessageSerializer.DIRECTIONS:
            if phone_number and appnt.hospital.location:
                try:
                    notification_tasks.send_appointment_location_message.apply_async(
                        kwargs={'number': phone_number,
                                'hospital_lat': appnt.hospital.location.y,
                                'hospital_long': appnt.hospital.location.x,
                                },
                        countdown=1)

                except Exception as e:
                    obj['error'] = True
                    obj['message'] = 'Error Sending Appointment Reminder Message!'
                    logger.error("Error Sending Appointment Reminder Message " + str(e))
            else:
                obj['error'] = True
                obj['message'] = 'No PhoneNumber/HospitaLocation Found'
                return Response(obj, status=status.HTTP_400_BAD_REQUEST)
        if not 'message' in obj:
            obj['message'] = "Message Sent Successfully"
        return Response(obj)

    def encryption_key_request_message(self, request):
        from ondoc.communications.models import ProviderAppNotification
        serializer = serializers.EncryptionKeyRequestMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj = {"error": False}
        try:
            action_user = request.user
            sms_notification = ProviderAppNotification(data.get('hospital_id'), action_user,
                                                       notif_models.NotificationAction.REQUEST_ENCRYPTION_KEY)
            sms_notification.send()
        except Exception as e:
            obj['error'] = True
            obj['message'] = 'Error Sending Encryption Key Request Message!'
            logger.error("Error Sending Encryption Key Request Message " + str(e))
        if not 'message' in obj:
            obj['message'] = "Message Sent Successfully"
        return Response(obj)


class HospitalViewSet(viewsets.GenericViewSet):

    @use_slave
    def near_you_hospitals(self, request):
        from numpy.distutils.fcompiler import str2bool
        return Response({})
        request_data = request.query_params
        serializer = serializers.HospitalNearYouSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        result_count = 0
        hospital_serializer = None
        if validated_data and validated_data.get('long') and validated_data.get('lat'):
            point_string = 'POINT(' + str(validated_data.get('long')) + ' ' + str(validated_data.get('lat')) + ')'
            pnt = GEOSGeometry(point_string, srid=4326)
            day = datetime.datetime.today().weekday()
            gold_request = str2bool(request_data.get('gold', 0))
            vip_request = validated_data.get('from_vip') or str2bool(request_data.get('vip', 0))

            hospital_queryset = Hospital.objects.prefetch_related('hospital_doctors', 'hospital_documents', 'matrix_city',
                                                                  Prefetch('hospital_doctors__availability',
                                                                           queryset=DoctorClinicTiming.objects.filter(day=day))). \
                filter(enabled_for_online_booking=True,
                       hospital_doctors__enabled_for_online_booking=True,
                       hospital_doctors__doctor__enabled_for_online_booking=True,
                       hospital_doctors__doctor__is_live=True, is_live=True).annotate(
                bookable_doctors_count=Count(Q(enabled_for_online_booking=True,
                                               hospital_doctors__enabled_for_online_booking=True,
                                               hospital_doctors__doctor__enabled_for_online_booking=True,
                                               hospital_doctors__doctor__is_live=True, is_live=True)),
                distance=Distance('location', pnt)).filter(bookable_doctors_count__gte=20).order_by('distance')

            # if validated_data.get('from_vip'):
            #     hospital_queryset = hospital_queryset.filter(enabled_for_prepaid=True)

            if gold_request:
                hospital_queryset = hospital_queryset.filter(enabled_for_gold=True)
            elif vip_request:
                hospital_queryset = hospital_queryset.filter(enabled_for_plus_plans=True)
            else:
                hospital_queryset = hospital_queryset.filter(enabled_for_prepaid=True)

            result_count = hospital_queryset.count()

            temp_hospital_ids = hospital_queryset.values_list('id', flat=True)
            hosp_entity_dict, hosp_locality_entity_dict = Hospital.get_hosp_and_locality_dict(temp_hospital_ids,
                                                                                              EntityUrls.SitemapIdentifier.HOSPITALS_LOCALITY_CITY)

            hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True, context={'request': request,
                                                                                                             'hosp_entity_dict': hosp_entity_dict})
            hospital_percentage_dict = dict()

            plan = PlusPlans.objects.prefetch_related('plan_parameters', 'plan_parameters__parameter').filter(is_gold=True, is_selected=True).first()
            if not plan:
                plan = PlusPlans.objects.prefetch_related('plan_parameters', 'plan_parameters__parameter').filter(is_gold=True).first()

            hospital_queryset = hospital_queryset[:20]
            if plan:
                convenience_amount_obj, convenience_percentage_obj = plan.get_convenience_object('DOCTOR')

                for hospital in hospital_queryset:
                    doctor_clinics = hospital.hospital_doctors.all()
                    percentage = 0
                    for doc in doctor_clinics:
                        doc_clinic_timing = doc.availability.all()[0] if doc.availability.all() else None
                        if doc_clinic_timing:
                            mrp = doc_clinic_timing.mrp
                            agreed_price = doc_clinic_timing.fees
                            if agreed_price and mrp:
                                percentage = max(((mrp-(agreed_price + plan.get_convenience_amount(agreed_price, convenience_amount_obj, convenience_percentage_obj)))/mrp)*100, percentage)
                    hospital_percentage_dict[hospital.id] = round(percentage, 2)

            # hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True,
            #                                                           context={"request": request})
            hospitals_result = hospital_serializer.data
            for data in hospitals_result:
                data['vip_percentage'] = hospital_percentage_dict[data.get('id')] if plan and hospital_percentage_dict.get(data.get('id')) else 0

            return Response({'count': result_count, 'hospitals': hospitals_result})
        return Response({})

    def list_by_url(self, request, url, *args, **kwargs):
        url = url.lower()
        entity = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                           entity_type='Hospital').order_by('-sequence').first()
        if not entity:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not entity.is_valid:
            valid_qs = EntityUrls.objects.filter(is_valid=True, ipd_procedure_id=entity.ipd_procedure_id,
                                                 locality_id=entity.locality_id,
                                                 sublocality_id=entity.sublocality_id,
                                                 sitemap_identifier=entity.sitemap_identifier).order_by('-sequence')

            if valid_qs.exists():
                corrected_url = valid_qs.first().url
                return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        kwargs['request_data'] = ipd_query_parameters(entity, request.query_params)
        kwargs['entity'] = entity
        response = self.list(request, entity.ipd_procedure_id, **kwargs)
        return response

    def list(self, request, ipd_pk=None, count=None, *args, **kwargs):
        request_data = request.query_params
        temp_request_data = kwargs.get('request_data')
        if temp_request_data:
            request_data = temp_request_data
        serializer = serializers.HospitalRequestSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        required_network = validated_data.get('network')
        ipd_procedure_obj = ipd_procedure_obj_id = ipd_procedure_obj_name = None
        if ipd_pk:
            ipd_procedure_obj = IpdProcedure.objects.filter(id=ipd_pk, is_enabled=True).first()
        if ipd_pk and not ipd_procedure_obj:
            return Response([], status=status.HTTP_404_NOT_FOUND)
        if ipd_procedure_obj:
            ipd_procedure_obj_id = ipd_procedure_obj.id
            ipd_procedure_obj_name = ipd_procedure_obj.name

        url = canonical_url = title = description = top_content = bottom_content = city = breadcrumb = None
        entity = kwargs.get('entity')
        if not entity and ipd_procedure_obj_name:
            if validated_data.get('city'):
                city = city_match(validated_data.get('city'))
                # IPD_PROCEDURE_COST_IN_IPDP
                temp_url = slugify(ipd_procedure_obj_name + '-hospitals-in-' + city + '-ipdhp')
                entity = EntityUrls.objects.filter(url=temp_url, url_type=EntityUrls.UrlType.SEARCHURL,
                                                   entity_type='Hospital',
                                                   is_valid=True,
                                                   locality_value__iexact=city).first()


        if entity:
            breadcrumb = deepcopy(entity.breadcrumb) if isinstance(entity.breadcrumb, list) else []
            breadcrumb.insert(0, {"title": "Home", "url": "/", "link_title": "Home"})
            breadcrumb.insert(1, {"title": "Hospitals", "url": "hospitals", "link_title": "Hospitals"})
            locality = entity.sublocality_value
            city = entity.locality_value
            url = entity.url
            canonical_url = entity.url
            if entity.sitemap_identifier == EntityUrls.SitemapIdentifier.IPD_PROCEDURE_HOSPITAL_CITY and ipd_procedure_obj_name:
                title = 'Best {ipd_procedure_name} Hospitals in {city} | Book Hospital & Get Discount'.format(
                    ipd_procedure_name=ipd_procedure_obj_name, city=city)

                description = '{ipd_procedure_name} Hospitals in {city} : Check {ipd_procedure_name} hospitals in {city}. View address, reviews, cost estimate and more at Docprime.'.format(
                    ipd_procedure_name=ipd_procedure_obj_name, city=city)
                breadcrumb.append({"title": "Procedures", "url": "ipd-procedures", "link_title": "Procedures"})
                temp = "{} Hospitals in {}".format(ipd_procedure_obj_name, city)
                breadcrumb.append({"title": temp, "url": None, "link_title": temp})
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.HOSPITALS_CITY:
                title = 'Best Hospitals in {city} | Find Top Hospitals Near Me in {city}'.format(city=city)
                description = 'Best Hospitals in {city}: Find list of verified top hospitals near me in {city}. View details, address, reviews, bed availability, cost and more at Docprime.'.format(
                    city=city)
                temp = "{} Hospitals".format(city)
                breadcrumb.append({"title": temp, "url": None, "link_title": temp})
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.HOSPITALS_LOCALITY_CITY:
                title = 'Best Hospitals in {locality}, {city} | List of Top Hospitals in {locality}'.format(
                    locality=locality, city=city)
                description = 'Best Hospitals in {locality}, {city}: Check List of verified Top hospitals in {locality}, {city}. View details, address, reviews, bed availability, cost and more at Docprime.'.format(
                    locality=locality, city=city)
                temp = "Hospitals in {}, {}".format(entity.sublocality_value, entity.locality_value)
                breadcrumb.append({"title": temp, "url": None, "link_title": temp})

        if url:
            new_dynamic_object = NewDynamic.objects.filter(url_value=url, is_enabled=True).first()
            if new_dynamic_object:
                if new_dynamic_object.meta_title:
                    title = new_dynamic_object.meta_title
                if new_dynamic_object.meta_description:
                    description = new_dynamic_object.meta_description
                if new_dynamic_object.top_content:
                    top_content = new_dynamic_object.top_content
                if new_dynamic_object.bottom_content:
                    bottom_content = new_dynamic_object.bottom_content

        lat = validated_data.get('lat')
        long = validated_data.get('long')
        min_distance = validated_data.get('min_distance')
        max_distance = validated_data.get('max_distance')
        max_distance = max_distance * 1000 if max_distance is not None else 10000
        min_distance = min_distance * 1000 if min_distance is not None else -1
        if required_network:
            max_distance = 2600000
        provider_ids = validated_data.get('provider_ids')
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)

        hospital_queryset = Hospital.objects.prefetch_related('hospitalcertification_set',
                                                              'hospitalcertification_set__certification',
                                                              'hospital_documents',
                                                              'hosp_availability',
                                                              'health_insurance_providers',
                                                              'network__hospital_network_documents',
                                                              'hospitalspeciality_set',
                                                              'hospital_doctors').exclude(location__dwithin=(
            Point(float(long),
                  float(lat)),
            D(m=min_distance))).filter(
            is_live=True,
            hospital_doctors__enabled=True,
            location__dwithin=(
                Point(float(long),
                      float(lat)),
                D(m=max_distance))).annotate(
            distance=Distance('location', pnt), bookable_doctors_count=Count(Q(enabled_for_online_booking=True,
                                           hospital_doctors__enabled_for_online_booking=True,
                                           hospital_doctors__doctor__enabled_for_online_booking=True,
                                           hospital_doctors__doctor__is_live=True, is_live=True))).order_by('-is_ipd_hospital', 'distance')
        if provider_ids:
            hospital_queryset = hospital_queryset.filter(health_insurance_providers__id__in=provider_ids)
        if ipd_pk:
            hospital_queryset = hospital_queryset.filter(
                hospital_doctors__ipd_procedure_clinic_mappings__ipd_procedure_id=ipd_pk,
                hospital_doctors__ipd_procedure_clinic_mappings__enabled=True)
        if required_network:
            hospital_queryset = hospital_queryset.filter(network=required_network)

        hospital_queryset = hospital_queryset.distinct()
        result_count = hospital_queryset.count()
        hospital_queryset = paginate_queryset_refactored_consumer_app(hospital_queryset, request, 50)
        hospital_queryset = list(hospital_queryset)
        if count:
            hospital_queryset = hospital_queryset[:count]
        temp_hospital_ids = [x.id for x in hospital_queryset]
        hosp_entity_dict, hosp_locality_entity_dict = Hospital.get_hosp_and_locality_dict(temp_hospital_ids,
                                                                                          EntityUrls.SitemapIdentifier.HOSPITALS_LOCALITY_CITY)
        top_hospital_serializer = serializers.TopHospitalForIpdProcedureSerializer(hospital_queryset, many=True,
                                                                                   context={'request': request,
                                                                                            'hosp_entity_dict': hosp_entity_dict,
                                                                                            'hosp_locality_entity_dict': hosp_locality_entity_dict})
        network_info = {}
        if required_network:
            network_info = {'id': required_network.id, 'name': required_network.name}

        return Response({'count': result_count, 'result': top_hospital_serializer.data,
                         'ipd_procedure': {'id': ipd_procedure_obj_id, 'name': ipd_procedure_obj_name},
                         'health_insurance_providers': [{'id': x.id, 'name': x.name} for x in
                                                        HealthInsuranceProvider.objects.all()],
                         'seo': {'url': url, 'title': title, 'description': description, 'location': city},
                         'search_content': top_content, 'bottom_content': bottom_content,
                         'canonical_url': canonical_url, 'breadcrumb': breadcrumb, 'network': network_info})

    @transaction.non_atomic_requests
    def retrieve_by_url(self, request):

        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        entity = EntityUrls.objects.filter(url=url, sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE).order_by(
            '-is_valid')
        if len(entity) > 0:
            entity = entity[0]
            if not entity.is_valid:
                valid_entity_url_qs = EntityUrls.objects.filter(
                    sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE, entity_id=entity.entity_id,
                    is_valid='t')
                if valid_entity_url_qs.exists():
                    corrected_url = valid_entity_url_qs[0].url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url, 'status': 301})
                else:
                    return Response(status=status.HTTP_404_NOT_FOUND)

            # entity_id = entity.entity_id
            response = self.retrive(request, entity.entity_id, entity)
            return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @use_slave
    def retrive(self, request, pk, entity=None):
        serializer = serializers.HospitalDetailRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        hospital_obj = Hospital.objects.prefetch_related('service', 'network',
                                                         'hosp_availability',
                                                         'hospital_documents',
                                                         'hospital_helpline_numbers',
                                                         'network__hospital_network_documents',
                                                         'hospitalcertification_set',
                                                         'hospitalcertification_set__certification',
                                                         'hosp_availability',
                                                         'question_answer',
                                                         'hospitalspeciality_set', Prefetch('imagehospital',
                                                                                            HospitalImage.objects.all().order_by(
                                                                                                '-cover_image'))).filter(id=pk, is_live=True).first()
        if not hospital_obj:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        response = {}
        title = None
        description = None
        canonical_url = None
        h1_title = None

        if not entity:
            entity = EntityUrls.objects.filter(entity_id=hospital_obj.id,
                                               sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE).order_by('-is_valid')
            if len(entity) > 0:
                entity = entity[0]

        hosp_serializer = serializers.HospitalDetailIpdProcedureSerializer(hospital_obj, context={'request': request,
                                                                                                  'validated_data': validated_data,
                                                                                                  "entity": entity}).data

        response = hosp_serializer
        if entity:
            response['url'] = entity.url
            if entity.breadcrumb:
                breadcrumb = [{'url': '/', 'title': 'Home', 'link_title': 'Home'}
                    , {"title": "Hospitals", "url": "hospitals", "link_title": "Hospitals"}
                              ]
                if entity.locality_value:
                    # breadcrumb.append({'url': request.build_absolute_uri('/'+ entity.locality_value), 'title': entity.locality_value, 'link_title': entity.locality_value})
                    breadcrumb = breadcrumb + entity.breadcrumb

                breadcrumb.append({'title':  hospital_obj.name, 'url': None, 'link_title': None})
                response['breadcrumb'] = breadcrumb
            else:

                breadcrumb = [{'url': '/', 'title': 'Home', 'link_title': 'Home'},
                              {"title": "Hospitals", "url": "hospitals", "link_title": "Hospitals"}]
            #     if entity.locality_value:
            #         breadcrumb.append({"title": "{} Hospitals".format(entity.locality_value),
            #                            "url": "hospitals/hospitals-in-{}-hspcit".format(entity.locality_value),
            #                            "link_title": "{} Hospitals".format(entity.locality_value)})
            #     if entity.sublocality_value:
            #         breadcrumb.append({"title": "{}".format(entity.sublocality_value),
            #                            "url": "hospitals/hospitals-in-{}-{}-hsplitcit".format(entity.sublocality_value,
            #                                                                                   entity.locality_value),
            #                            "link_title": "{}".format(entity.sublocality_value)})
                breadcrumb.append({'title': hospital_obj.name, 'url': None, 'link_title': None})
                response['breadcrumb'] = breadcrumb

            if hospital_obj.name and entity.locality_value:
                title = hospital_obj.name
                description = hospital_obj.name
                if entity.sublocality_value:
                    title += " " + entity.sublocality_value
                    description += " " + entity.sublocality_value

                title += ' | Book Appointment, Check Doctors List, Reviews, Contact Number'
                description += """: Get free booking on first appointment. Check {} Doctors List, Reviews, Contact Number, Address, Procedures and more.""".format(hospital_obj.name)
            canonical_url = entity.url
        else:
            response['breadcrumb'] = None
        new_dynamic = NewDynamic.objects.filter(url_value=canonical_url, is_enabled=True).first()
        if new_dynamic:
            if new_dynamic.meta_title:
                title = new_dynamic.meta_title
            if new_dynamic.meta_description:
                description = new_dynamic.meta_description
            if new_dynamic.h1_title:
                h1_title = new_dynamic.h1_title
        schema = self.build_schema_for_hospital(hosp_serializer, hospital_obj, canonical_url)
        listing_schema = self.build_listing_schema_for_hospital(hosp_serializer)
        breadcrumb_schema = self.build_breadcrumb_schema_for_hospital(response['breadcrumb']) if response.get('breadcrumb') else None
        all_schema = [x for x in [schema, listing_schema, breadcrumb_schema] if x]
        response['certifications'] = [{"certification_id": data.certification.id, "certification_name": data.certification.name} for data in hospital_obj.hospitalcertification_set.all() if data.certification]

        response['seo'] = {'title': title, "description": description, "schema": schema,
                           "h1_title": h1_title, 'all_schema': all_schema}
        response['canonical_url'] = canonical_url
        return Response(response)

    def build_listing_schema_for_hospital(self, serialized_data):
        try:
            schema = {
                "@context": "https://schema.org",
                "@type": "ItemList",
            }
            list_items = []
            for indx, doc in enumerate(serialized_data.get('doctors', {}).get('result', [])):
                item = {"@type": "ListItem", "position": indx + 1, "url": doc.get('new_schema', {}).get('url')}
                list_items.append(item)
            schema["itemListElement"] = list_items
        except Exception as e:
            logger.error(str(e))
            schema = None
        return schema

    def build_breadcrumb_schema_for_hospital(self, breadcrumb):
        try:
            schema = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList"
            }
            list_items = []
            for indx, doc in enumerate(breadcrumb):
                if doc.get('url'):
                    item = {
                        "@type": "ListItem",
                        "position": indx + 1,
                        "item": {"@id": "{}/{}".format(settings.BASE_URL.strip('/'), doc.get('url').strip('/')), "name": doc.get('title')}
                    }
                    list_items.append(item)
            schema["itemListElement"] = list_items
        except Exception as e:
            logger.error(str(e))
            schema = None
        return schema

    def build_schema_for_hospital(self, serialized_data, hospital, url):
        try:
            from ondoc.doctor.models import HospitalTiming
            min_fee, max_fee = None, None
            for x in serialized_data.get("doctors", {}).get("result", []):
                if not min_fee or min_fee > x["deal_price"]:
                    min_fee = x["deal_price"]
                if not max_fee or max_fee < x["deal_price"]:
                    max_fee = x["deal_price"]
            fee_range = None
            if min_fee and max_fee and min_fee != max_fee:
                fee_range = "INR {} - INR {}".format(min_fee, max_fee)
            elif min_fee or max_fee:
                fee_range = "INR {}".format(min_fee if min_fee else max_fee)

            def time_float_to_str(t):
                h, m, s = 0, 0, 0
                h = t // 1
                m = int((t * 10) % 10)
                if m == 5:
                    m = 30
                result = "{:0>2}:{:0>2}:{:0>2}".format(h, m, s)
                return result

            available_days = {}
            opens_at, closes_at = None, None
            num_day = dict(HospitalTiming.DAY_CHOICES)
            for x in hospital.hosp_availability.all():
                available_days[x.day] = num_day[x.day]
                if not opens_at and not closes_at:
                    opens_at = time_float_to_str(x.start)
                    closes_at = time_float_to_str(x.end)

            schema = {
                "@type": "Hospital",
                "@context": "https://schema.org/",
                "currenciesAccepted": "INR",
                "priceRange": fee_range,
                "name": serialized_data['name'],
                "url": "{}/{}".format(settings.BASE_URL, url) if url and isinstance(url, str) else None,
                "medicalSpecialty": "Multi-Speciality" if serialized_data["multi_speciality"] else None,
                "description": serialized_data['new_about'] if serialized_data['new_about'] else serialized_data[
                    'about'],
                "telephone": serialized_data["contact_number"],
                "logo": serialized_data["logo"],
                "geo": {
                    "@type": "GeoCoordinates",
                    "@context": "https://schema.org",
                    "latitude": serialized_data['lat'],
                    "longitude": serialized_data['long']
                } if serialized_data['lat'] and serialized_data['long'] else None,
                "hasMap": {
                    "@type": "Map",
                    "@context": "https://schema.org",
                    "url": "https://maps.google.com/maps?f=d&amp;hl=en&amp;addr={},{}".format(serialized_data['lat'],
                                                                                              serialized_data['long'])
                },
                "image": serialized_data["images"][0]["original"] if len(serialized_data["images"]) > 0 else None,
                "photo": [{
                    "@type": "CreativeWork",
                    "@context": "https://schema.org",
                    "url": x["original"]
                } for x in serialized_data["images"]],
                "address": {
                    "@type": "PostalAddress",
                    "@context": "https://schema.org",
                    "streetAddress": hospital.get_hos_address(),
                    "addressLocality": hospital.city,
                    "addressRegion": hospital.state,
                    "postalCode": hospital.pin_code
                },
                "availableService": {
                    "@type": "MedicalTherapy",
                    "@context": "https://schema.org",
                    "name": [y["name"] for x in serialized_data['ipd_procedure_categories'] for y in
                             x["ipd_procedures"]]
                },
                "member": [x["new_schema"] for x in serialized_data["doctors"]["result"]],
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "@context": "https://schema.org",
                    "worstRating": "1",
                    "ratingValue": serialized_data.get('rating_graph', {}).get('avg_rating'),
                    "bestRating": "5",
                    "ratingCount": serialized_data.get('rating_graph', {}).get('rating_count'),
                },
                "review": [
                    {
                        "@type": "Review",
                        "reviewBody": x["compliment"],
                        "datePublished": x["date"],
                        "author": {
                            "@type": "Person",
                            "name": x["user_name"]
                        }
                    } for x in serialized_data["rating"]
                ],
                "openingHoursSpecification": [
                    {
                        "@type": "OpeningHoursSpecification",
                        "dayOfWeek": list(available_days.values()),
                        "opens": opens_at,
                        "closes": closes_at
                    }
                ],
            }
        except Exception as e:
            logger.error(str(e))
            schema = None
        return schema


class IpdProcedureViewSet(viewsets.GenericViewSet):

    def ipd_procedure_detail_by_url(self, request, url, *args, **kwargs):
        url = url.lower()
        entity_url_qs = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.PAGEURL,
                                                  entity_type='IpdProcedure').order_by('-sequence')
        if not entity_url_qs.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        entity = entity_url_qs.first()
        if not entity.is_valid:
            valid_qs = EntityUrls.objects.filter(is_valid=True, ipd_procedure_id=entity.ipd_procedure_id,
                                                 locality_id=entity.locality_id,
                                                 sublocality_id=entity.sublocality_id,
                                                 sitemap_identifier=entity.sitemap_identifier).order_by('-sequence')

            if valid_qs.exists():
                corrected_url = valid_qs.first().url
                return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        kwargs['request_data'] = ipd_query_parameters(entity, request.query_params)
        kwargs['entity'] = entity
        response = self.ipd_procedure_detail(request, entity.ipd_procedure_id, **kwargs)
        return response

    @use_slave
    def ipd_procedure_detail(self, request, pk, *args, **kwargs):
        request_data = request.query_params
        temp_request_data = kwargs.get('request_data')
        if temp_request_data:
            request_data = temp_request_data
        serializer = serializers.IpdDetailsRequestDetailRequestSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        ipd_procedure = IpdProcedure.objects.prefetch_related(
            Prefetch('feature_mappings',
                     IpdProcedureFeatureMapping.objects.select_related('feature').all().order_by('-feature__priority')),
            Prefetch('ipdproceduredetail_set',
                     IpdProcedureDetail.objects.select_related('detail_type').all().order_by('-detail_type__priority')),
            Prefetch('similar_ipds',
                     SimilarIpdProcedureMapping.objects.select_related('similar_ipd_procedure').all().order_by(
                         '-order')),
            Prefetch('ipd_offers', Offer.objects.select_related('coupon', 'hospital', 'network').filter(is_live=True)),
        ).filter(is_enabled=True, id=pk).first()
        if ipd_procedure is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = canonical_url = title = description = top_content = bottom_content = city = breadcrumb = None

        entity = kwargs.get('entity')
        if not entity:
            if validated_data.get('city'):
                city = city_match(validated_data.get('city'))
                # IPD_PROCEDURE_COST_IN_IPDP
                temp_url = slugify(ipd_procedure.name + '-cost-in-' + city + '-ipdp')
                entity = EntityUrls.objects.filter(url=temp_url, url_type=EntityUrls.UrlType.PAGEURL,
                                                   entity_type='IpdProcedure', is_valid=True,
                                                   locality_value__iexact=city).first()

        if entity:
            city = entity.locality_value
            url = entity.url
            title = '{ipd_procedure_name} Cost in {city} | Book & Get Upto 50% Off'.format(
                ipd_procedure_name=ipd_procedure.name, city=city)
            canonical_url = entity.url
            description = '{ipd_procedure_name} Cost in {city} : Check {ipd_procedure_name} doctors , hospitals, address & contact number in {city}.'.format(
                ipd_procedure_name=ipd_procedure.name, city=city)
        similar_ipds_entity_dict = {}
        if city:
            similar_ipd_ids = [x.similar_ipd_procedure.id for x in ipd_procedure.similar_ipds.all()]
            temp_qs = EntityUrls.objects.filter(ipd_procedure_id__in=similar_ipd_ids, is_valid=True, locality_value=city)
            similar_ipds_entity_dict = {x.ipd_procedure_id: x.url for x in temp_qs}
        if url:
            new_dynamic_object = NewDynamic.objects.filter(url_value=url, is_enabled=True).first()
            if new_dynamic_object:
                if new_dynamic_object.meta_title:
                    title = new_dynamic_object.meta_title
                if new_dynamic_object.meta_description:
                    description = new_dynamic_object.meta_description
                if new_dynamic_object.top_content:
                    top_content = new_dynamic_object.top_content
                if new_dynamic_object.bottom_content:
                    bottom_content = new_dynamic_object.bottom_content

        breadcrumb = list()
        breadcrumb.append({"title": "Home", "url": "/", "link_title": "Home"})
        breadcrumb.append({"title": "Procedures", "url": "ipd-procedures", "link_title": "Procedures"})
        if city:
            breadcrumb.append({"title": "{} Cost in {}".format(ipd_procedure.name, city), "url": None, "link_title": None})

        near_by = validated_data.get('near_by', False)
        hospital_request_data = {}
        doctor_search_parameters = {'ipd_procedure_ids': str(pk),
                                    'longitude': validated_data.get('long'),
                                    'latitude': validated_data.get('lat'),
                                    'sort_on': 'experience',
                                    'city': city,
                                    'restrict_result_count': 3}
        if near_by:
            hospital_request_data.update({'max_distance': 1000000})
            doctor_search_parameters.update({'max_distance': 1000000})
        hospital_view_set = HospitalViewSet()
        hospital_result = hospital_view_set.list(request, pk, 2, request_data=hospital_request_data)
        doctor_result_data = {}
        doctor_list_viewset = DoctorListViewSet()
        doctor_result = doctor_list_viewset.list(request, parameters=doctor_search_parameters)
        doctor_result_data = doctor_result.data
        ipd_procedure_serializer = serializers.IpdProcedureDetailSerializer(ipd_procedure, context={'request': request,
                                                                                                    'similar_ipds_entity_dict': similar_ipds_entity_dict,
                                                                                                    'doctor_result_data': doctor_result_data})
        return Response(
            {'about': ipd_procedure_serializer.data, 'hospitals': hospital_result.data, 'doctors': doctor_result_data,
             'seo': {'url': url, 'title': title, 'description': description, 'location': city},
             'search_content': top_content, 'bottom_content': bottom_content, 'canonical_url': canonical_url,
             'breadcrumb': breadcrumb})

    def create_lead(self, request):
        from ondoc.procedure.models import IpdProcedureLead
        serializer = serializers.IpdProcedureLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        validated_data['status'] = IpdProcedureLead.NEW
        obj_created = IpdProcedureLead(**validated_data)
        obj_created.save()
        return Response(serializers.IpdProcedureLeadSerializer(obj_created).data)

    def update_lead(self, request):
        serializer = serializers.IpdLeadUpdateSerializerPopUp(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        temp_id = validated_data.pop('id')
        # IpdProcedureLead.objects.filter(id=temp_id).update(**validated_data)
        obj = IpdProcedureLead.objects.filter(id=temp_id).first()
        if obj:
            for x in list(validated_data.keys()):
                setattr(obj, x, validated_data[x])
            obj.save()
        return Response({'message': 'Success'})

    @use_slave
    def list_by_alphabet(self, request):
        import re
        alphabet = request.query_params.get('alphabet')
        city = request.query_params.get('city')
        if city:
            city = city_match(city)
        if not alphabet or not re.match(r'^[a-zA-Z]$', alphabet):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        response = {}
        ipdp_count = 0
        entity_dict = {}
        ipd_procedures = list(IpdProcedure.objects.filter(is_enabled=True, name__istartswith=alphabet).order_by('name').values('id', 'name'))
        ipd_procedure_ids = [x.get('id') for x in ipd_procedures]
        entity_qs = EntityUrls.objects.filter(url_type=EntityUrls.UrlType.PAGEURL,
                                              entity_type='IpdProcedure',
                                              is_valid=True,
                                              ipd_procedure_id__in=ipd_procedure_ids,
                                              locality_value__iexact=city)
        if entity_qs:
            entity_dict = {x.ipd_procedure_id: x.url for x in entity_qs}
        for ipd_procedure in ipd_procedures:
            ipd_procedure['url'] = entity_dict.get(ipd_procedure.get('id'), None)
        ipdp_count = len(ipd_procedures)
        response['count'] = ipdp_count
        response['ipd_procedures'] = ipd_procedures

        return Response(response)


class IpdProcedureSyncViewSet(viewsets.GenericViewSet):

    authentication_classes = (MatrixAuthentication,)

    def sync_lead(self, request):
        from ondoc.crm.constants import matrix_status_to_ipd_lead_status_mapping
        serializer = serializers.IpdLeadUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        temp_status = validated_data.get('status')
        temp_planned_date = validated_data.get('planned_date')
        temp_status = matrix_status_to_ipd_lead_status_mapping.get(temp_status)
        to_be_updated_dict = {}
        if temp_status:
            to_be_updated_dict['status'] = temp_status
        if temp_planned_date:
            to_be_updated_dict['planned_date'] = temp_planned_date
        IpdProcedureLead.objects.filter(matrix_lead_id=validated_data.get('matrix_lead_id')).update(**to_be_updated_dict)
        return Response({'message': 'Success'})


class RecordAPIView(viewsets.GenericViewSet):
    """This class defines the create behavior of our rest api."""
    def list(self, request):
        params = request.query_params
        lat = params.get('lat', 28.450367)
        long = params.get('long', 77.071848)
        radius = int(params.get('radius')) if params.get('radius') else 2000
        response = dict()

        queryset = GoogleMapRecords.objects.all()
        if lat and long and radius:
            point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
            pnt = GEOSGeometry(point_string, srid=4326)
            queryset = queryset.filter(location__distance_lte=(pnt, radius))

        serializer = serializers.RecordSerializer(queryset, many=True,
                                                              context={"request": request})
        serialized_data = serializer.data
        response['map_data'] = serialized_data
        response['labels'] = list(queryset.values('label').distinct())

        return Response(response)


# View to see all points
def record_map(request):
    return render(request, "home.html")


# create a new location
def create_record(request):
    from ondoc.crm.admin.doctor import GoogleMapRecordForm
    form = GoogleMapRecordForm(request.POST or None)

    if form.is_valid():
        instance = form.save(commit=False)
        # get coordinates
        location = geolocator.geocode(instance.location)
        instance.latitude = location.latitude
        instance.longitude = location.longitude
        instance.save()
        return HttpResponseRedirect('/')

    context = {
        "form": form
    }

    return render(request, "doctor/create.html", context)

