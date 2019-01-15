from collections import defaultdict, OrderedDict
from uuid import UUID
from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.doctor.serializers import HospitalModelSerializer, AppointmentRetrieveDoctorSerializer, \
    OfflinePatientSerializer
from ondoc.api.v1.doctor.DoctorSearchByHospitalHelper import DoctorSearchByHospitalHelper
from ondoc.api.v1.procedure.serializers import CommonProcedureCategorySerializer, ProcedureInSerializer, \
    ProcedureSerializer, DoctorClinicProcedureSerializer, CommonProcedureSerializer
from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from ondoc.diagnostic import models as lab_models
from ondoc.notification import tasks as notification_tasks
#from ondoc.doctor.models import Hospital, DoctorClinic,Doctor,  OpdAppointment
from ondoc.doctor.models import DoctorClinic
from ondoc.notification.models import EmailNotification
from django.utils.safestring import mark_safe
from ondoc.coupon.models import Coupon
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.account import models as account_models
from ondoc.location.models import EntityUrls, EntityAddress, DefaultRating
from ondoc.procedure.models import Procedure, ProcedureCategory, CommonProcedureCategory, ProcedureToCategoryMapping, \
    get_selected_and_other_procedures, CommonProcedure
from ondoc.seo.models import NewDynamic
from . import serializers
from ondoc.api.pagination import paginate_queryset, paginate_raw_query
from ondoc.api.v1.utils import convert_timings, form_time_slot, IsDoctor, payment_details, aware_time_zone, \
    TimeSlotExtraction, GenericAdminEntity, get_opd_pem_queryset, offline_form_time_slots
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.doctor.doctorsearch import DoctorSearchHelper
from django.db.models import Min
from django.contrib.gis.geos import Point, GEOSGeometry
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from ondoc.authentication.backends import JWTAuthentication
from django.utils import timezone
from django.db import transaction
from django.http import Http404
from django.db.models import Q, Value, Case, When
from operator import itemgetter
from itertools import groupby,chain
from ondoc.api.v1.utils import RawSql, is_valid_testing_data, doctor_query_parameters
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import F, Count
from django.db.models.functions import StrIndex
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
from django.db.models import Avg
from django.db.models import Count
from ondoc.api.v1.auth import serializers as auth_serializers

logger = logging.getLogger(__name__)
import random


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
        queryset = queryset.distinct()
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
        serializer = serializers.OTPFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        opd_appointment = models.OpdAppointment.objects.select_for_update().filter(pk=validated_data.get('id')).first()

        if not opd_appointment:
            return Response({"message": "Invalid appointment id"}, status.HTTP_404_NOT_FOUND)
        permission = auth_models.GenericAdmin.objects.filter(Q(is_disabled=False,
                                                                    user=user,
                                                                    doctor_id=opd_appointment.doctor.id,
                                                                    permission_type__in=[auth_models.GenericAdmin.APPOINTMENT,
                                                                                           auth_models.GenericAdmin.ALL])|
                                                                  Q(user=user,
                                                                    is_disabled=False,
                                                                    hospital_id=opd_appointment.hospital.id,
                                                                    permission_type__in=[auth_models.GenericAdmin.APPOINTMENT,
                                                                                               auth_models.GenericAdmin.ALL]
                                                                    )
                                                                  ).first()

        if not permission:
            return Response({"message": "UnAuthorized"}, status.HTTP_403_FORBIDDEN)
        if request.user.user_type == User.DOCTOR:
            otp_valid_serializer = serializers.OTPConfirmationSerializer(data=request.data)
            otp_valid_serializer.is_valid(raise_exception=True)
            opd_appointment.action_completed()
        opd_appointment_serializer = serializers.DoctorAppointmentRetrieveSerializer(opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)

    @staticmethod
    def get_procedure_prices(procedures, doctor, selected_hospital, dct):
        doctor_clinic = doctor.doctor_clinics.filter(hospital=selected_hospital).first()
        doctor_clinic_procedures = doctor_clinic.doctorclinicprocedure_set.filter(procedure__in=procedures).order_by(
            'procedure_id')
        total_deal_price, total_agreed_price, total_mrp = 0, 0, 0
        for doctor_clinic_procedure in doctor_clinic_procedures:
            total_agreed_price += doctor_clinic_procedure.agreed_price
            total_deal_price += doctor_clinic_procedure.deal_price
            total_mrp += doctor_clinic_procedure.mrp
        return total_deal_price + dct.deal_price, total_agreed_price + dct.fees, total_mrp + dct.mrp

    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        procedures = data.get('procedure_ids', [])
        # procedure_categories = data.get('procedure_category_ids', [])
        selected_hospital = data.get('hospital')
        doctor = data.get('doctor')
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

        extra_details = []
        effective_price = 0
        if not procedures:
            if data.get("payment_type") == models.OpdAppointment.INSURANCE:
                effective_price = doctor_clinic_timing.deal_price
            elif data.get("payment_type") in [models.OpdAppointment.COD, models.OpdAppointment.PREPAID]:
                coupon_discount, coupon_cashback, coupon_list = Coupon.get_total_deduction(data, doctor_clinic_timing.deal_price)
                if coupon_discount >= doctor_clinic_timing.deal_price:
                    effective_price = 0
                else:
                    effective_price = doctor_clinic_timing.deal_price - coupon_discount
            deal_price = doctor_clinic_timing.deal_price
            mrp = doctor_clinic_timing.mrp
            fees = doctor_clinic_timing.fees
        else:
            total_deal_price, total_agreed_price, total_mrp = self.get_procedure_prices(procedures, doctor,
                                                                                        selected_hospital,
                                                                                        doctor_clinic_timing)
            if data.get("payment_type") == models.OpdAppointment.INSURANCE:
                effective_price = total_deal_price
            elif data.get("payment_type") in [models.OpdAppointment.COD, models.OpdAppointment.PREPAID]:
                coupon_discount, coupon_cashback, coupon_list = Coupon.get_total_deduction(data, total_deal_price)
                if coupon_discount >= total_deal_price:
                    effective_price = 0
                else:
                    effective_price = total_deal_price - coupon_discount
            deal_price = total_deal_price
            mrp = total_mrp
            fees = total_agreed_price

            doctor_clinic = doctor.doctor_clinics.filter(hospital=selected_hospital).first()
            doctor_clinic_procedures = doctor_clinic.doctorclinicprocedure_set.filter(procedure__in=procedures).order_by('procedure_id')
            for doctor_clinic_procedure in doctor_clinic_procedures:
                temp_extra = {'procedure_id': doctor_clinic_procedure.procedure.id,
                              'procedure_name': doctor_clinic_procedure.procedure.name,
                              'deal_price': doctor_clinic_procedure.deal_price,
                              'agreed_price': doctor_clinic_procedure.agreed_price,
                              'mrp': doctor_clinic_procedure.mrp}
                extra_details.append(temp_extra)

        opd_data = {
            "doctor": data.get("doctor"),
            "hospital": data.get("hospital"),
            "profile": data.get("profile"),
            "profile_detail": profile_detail,
            "user": request.user,
            "booked_by": request.user,
            "fees": fees,
            "deal_price": deal_price,
            "effective_price": effective_price,
            "mrp": mrp,
            "extra_details": extra_details,
            "time_slot_start": time_slot_start,
            "payment_type": data.get("payment_type"),
            "coupon": coupon_list,
            "discount": int(coupon_discount),
            "cashback": int(coupon_cashback)
        }
        resp = self.create_order(request, opd_data, account_models.Order.DOCTOR_PRODUCT_ID)

        return Response(data=resp)

    def update(self, request, pk=None):
        user = request.user
        queryset = self.get_pem_queryset(user).distinct()
        opd_appointment = get_object_or_404(queryset, pk=pk)
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
    def create_order(self, request, appointment_details, product_id):
        remaining_amount = 0
        user = request.user
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

        can_use_insurance, insurance_fail_message = self.can_use_insurance(appointment_details)
        if can_use_insurance:
            appointment_details['effective_price'] = insurance_effective_price
            appointment_details['payment_type'] = models.OpdAppointment.INSURANCE
        elif appointment_details['payment_type'] == models.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp

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
                push_order_to_matrix.apply_async(
                    ({'order_id': order.id, 'created_at': int(order.created_at.timestamp()),
                      'timeslot': int(appointment_details['time_slot_start'].timestamp())},), countdown=5)

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
        doctor_mobile = auth_models.DoctorNumber.objects.filter(phone_number=request.user.phone_number)
        doctor = doctor_mobile.first().doctor if doctor_mobile.exists() else None
        if not doctor:
            doctor = request.user.doctor if hasattr(request.user, 'doctor') else None
        if doctor and doctor.is_live:
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

    def prepare_response(self, response_data, selected_hospital):
        import operator 
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
            if key == selected_hospital:
                availability.insert(0, hospital)
            else:
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
                    return Response(status=status.HTTP_404_NOT_FOUND)

            entity_id = entity.entity_id
            response = self.retrieve(request, entity_id, entity)
            return response

        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk, entity=None):
        serializer = serializers.DoctorDetailsRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        category_ids = validated_data.get('procedure_category_ids', None)
        procedure_ids = validated_data.get('procedure_ids', None)
        selected_hospital = validated_data.get('hospital_id', None)
        doctor = (models.Doctor.objects
                  .prefetch_related('languages__language',
                                    'doctor_clinics__hospital',
                                    'doctor_clinics__doctorclinicprocedure_set__procedure__parent_categories_mapping',
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
        if not doctor or (not doctor.is_live and not doctor.is_internal):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not entity:
            entity = EntityUrls.objects.filter(entity_id=pk, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE, is_valid='t')
            if len(entity) > 0:
                entity = entity[0]

        selected_procedure_ids, other_procedure_ids = get_selected_and_other_procedures(category_ids, procedure_ids,
                                                                                        doctor, all=True)
        serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False,
                                                                     context={"request": request
                                                                         ,
                                                                              "selected_procedure_ids": selected_procedure_ids
                                                                         ,
                                                                              "other_procedure_ids": other_procedure_ids
                                                                         , "category_ids": category_ids
                                                                         , "hospital_id": selected_hospital
                                                                         , "entity":entity 
                                                                              })

        response_data = self.prepare_response(serializer.data, selected_hospital)

        if entity:
            response_data['url'] = entity.url
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
    def common_conditions(self, request):
        count = request.query_params.get('count', 10)
        count = int(count)
        if count <=0:
            count = 10
        medical_conditions = models.CommonMedicalCondition.objects.select_related('condition').all().order_by("priority")[:count]
        conditions_serializer = serializers.MedicalConditionSerializer(medical_conditions, many=True, context={'request': request})

        common_specializations = models.CommonSpecialization.objects.select_related('specialization').all().order_by("priority")[:10]
        specializations_serializer = serializers.CommonSpecializationsSerializer(common_specializations, many=True, context={'request': request})

        common_procedure_categories = CommonProcedureCategory.objects.select_related('procedure_category').filter(procedure_category__is_live=True).all().order_by("priority")[:10]
        common_procedure_categories_serializer = CommonProcedureCategorySerializer(common_procedure_categories, many=True)

        common_procedures = CommonProcedure.objects.select_related('procedure').filter(procedure__is_enabled=True).all().order_by("priority")[:10]
        common_procedures_serializer = CommonProcedureSerializer(common_procedures, many=True)

        return Response({"conditions": conditions_serializer.data, "specializations": specializations_serializer.data,
                         "procedure_categories": common_procedure_categories_serializer.data,
                         "procedures": common_procedures_serializer.data})


class DoctorListViewSet(viewsets.GenericViewSet):
    queryset = models.Doctor.objects.all()

    @transaction.non_atomic_requests
    def list_by_url(self, request, *args, **kwargs):
        url = request.GET.get('url', None)
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        rating = None
        reviews = None

        entity_url_qs = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                           entity_type__iexact='Doctor').order_by('-sequence')
        if len(entity_url_qs) > 0:
            entity = entity_url_qs[0]
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
    def list(self, request, *args, **kwargs):
        parameters = request.query_params
        if kwargs.get("parameters"):
            parameters = kwargs.get("parameters")
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

        doctor_search_helper = DoctorSearchHelper(validated_data)
        if not validated_data.get("search_id"):
            filtering_params = doctor_search_helper.get_filtering_params()
            order_by_field, rank_by = doctor_search_helper.get_ordering_params()
            query_string = doctor_search_helper.prepare_raw_query(filtering_params,
                                                                  order_by_field, rank_by)
            doctor_search_result = RawSql(query_string.get('query'),
                                         query_string.get('params')).fetch_all()

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
                                                "images",
                                                "doctor_clinics__doctorclinicprocedure_set__procedure__parent_categories_mapping").order_by(preserved)

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
        ratings_title = ''
        # if False and (validated_data.get('extras') or validated_data.get('specialization_ids')):
        if validated_data.get('locality_value') or validated_data.get('sublocality_value'):
            location = None
            # breadcrumb_sublocality = None
            # breadcrumb_locality = None
            city = None
            breadcrumb = None
            locality = ''
            sublocality = ''
            specializations = ''
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
            specializations = None
            if validated_data.get('specialization'):
                specializations = validated_data.get('specialization')

            # if validated_data.get('extras') and validated_data.get('extras').get('specialization'):
            #     specializations = validated_data.get('extras').get('specialization')

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
            ratings_title = title
            if specializations:
                if not sublocality:
                    title += ' - Book Best ' + specializations +' Online'
                else:
                    title += ' | Book & Get Best Deal'

            else:
                 title += ' | Book Doctors Online & Get Best Deal'

            description += ' and get upto 50% off. View Address, fees and more for doctors '
            if locality:
                description += 'in '+ city
            description += '.'

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

            seo = {
                "title": title,
                "description": description,
                "location": location,
                "image": static('web/images/dclogo-placeholder.png'),
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

            search_url = validated_data.get('url')
            if search_url:
                object = NewDynamic.objects.filter(url_value=search_url, is_enabled=True).first()
                if object and object.top_content:
                    top_content = object.top_content
                if object and object.bottom_content:
                    bottom_content = object.bottom_content
                if not top_content and specialization_id:
                    specialization_content = models.PracticeSpecializationContent.objects.filter(
                        specialization__id=specialization_id).first()
                    if specialization_content:
                        top_content = specialization_content.content

                if top_content:
                    top_content = str(top_content)
                    top_content = top_content.replace('<location>', location)
                    regex = re.compile(r'[\n\r\t]')
                    top_content = regex.sub(" ", top_content)
                if bottom_content:
                    bottom_content = str(bottom_content)
                    bottom_content = bottom_content.replace('<location>', location)
                    regex = re.compile(r'[\n\r\t]')
                    bottom_content = regex.sub(" ", bottom_content)



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
            if id_url_dict.get(resp['id']):
                resp['url'] = id_url_dict[resp['id']]
                resp['schema']['url'] = id_url_dict[resp['id']]
            else:
                resp['url'] = None
                resp['schema']['url'] = None

        validated_data.get('procedure_categories', [])
        procedures = list(Procedure.objects.filter(pk__in=validated_data.get('procedure_ids', [])).values('id', 'name'))
        procedure_categories = list(ProcedureCategory.objects.filter(pk__in=validated_data.get('procedure_category_ids', [])).values('id', 'name'))
        specializations = list(models.PracticeSpecialization.objects.filter(id__in=validated_data.get('specialization_ids',[])).values('id','name'));
        conditions = list(models.MedicalCondition.objects.filter(id__in=validated_data.get('condition_ids',[])).values('id','name'));
        if validated_data.get('ratings'):
            ratings = validated_data.get('ratings')
        if validated_data.get('reviews'):
            reviews = validated_data.get('reviews')
        return Response({"result": response, "count": result_count,
                         'specializations': specializations, 'conditions': conditions, "seo": seo,
                         "breadcrumb": breadcrumb, 'search_content': top_content,
                         'procedures': procedures, 'procedure_categories': procedure_categories,
                         'ratings':ratings, 'reviews': reviews, 'ratings_title': ratings_title,
                         'bottom_content': bottom_content})

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
        doctor_search_result = RawSql(query_string.get('query'),
                                      query_string.get('params')).fetch_all()

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
        #                                         "doctor_clinics__doctorclinicprocedure_set__procedure__parent_categories_mapping")

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

    def feedback(self, request):
        resp = {}
        user = request.user
        subject_string = "Feedback Mail from " + str(user.phone_number)

        serializer = serializers.DoctorFeedbackBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        message = ''
        managers_string = ''
        manages_string = ''
        for key, value in valid_data.items():
            if isinstance(value, list):
                val = ' '.join(map(str, value))
            else:
                val = value
            message += str(key) + "  -  " + str(val) + "<br>"
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
        try:
            emails = ["rajivk@policybazaar.com", "sanat@docprime.com", "arunchaudhary@docprime.com",
                      "rajendra@docprime.com", "harpreet@docprime.com", "jaspreetkaur@docprime.com"]
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
        queryset = doctor.hospitals.filter(is_appointment_manager=False)
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
        queryset = auth_models.GenericAdmin.objects.select_related('doctor', 'hospital').prefetch_related('doctor__doctor_clinic')
        if valid_data.get('entity_type') == GenericAdminEntity.DOCTOR:
            query = queryset.exclude(user=request.user).filter(doctor_id=valid_data.get('id'),
                                    entity_type=GenericAdminEntity.DOCTOR
                                    # (
                                    #     Q(hospital__isnull=True)|
                                    #     Q(hospital__isnull=False, doctor__doctor_clinics__hospital=F('hospital'))
                                    # )
                                    ) \
                            .annotate(hospital_ids=F('hospital__id'), hospital_ids_count=Count('hospital__hospital_doctors__doctor'))\
                            .values('id', 'phone_number', 'name', 'is_disabled', 'permission_type', 'super_user_permission', 'hospital_ids',
                                    'hospital_ids_count', 'updated_at')
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
                                       # (
                                       #      Q(doctor__isnull=True) |
                                       #      Q(doctor__isnull=False, hospital__hospital_doctors__doctor=F('doctor'))
                                       # )

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
                    'phone_number': 'SELECT phone_number FROM doctor_number WHERE doctor_id = doctor.id'}) \
                    .values('name', 'id', 'assigned', 'phone_number')

            for x in response:
                if temp.get(x['phone_number']):
                    if x['doctor_ids'] not in temp[x['phone_number']]['doctor_ids']:
                        temp[x['phone_number']]['doctor_ids'].append(x['doctor_ids'])
                    if temp[x['phone_number']]['permission_type'] != x['permission_type']:
                        temp[x['phone_number']]['permission_type'] = auth_models.GenericAdmin.ALL
                else:
                    for doc in assoc_docs:
                        if (doc.get('phone_number') and doc.get('phone_number') == x['phone_number']):
                            x['is_doctor'] = True
                            x['name'] = doc.get('name')
                            x['id'] = doc.get('id')
                            x['assigned'] = doc.get('assigned')
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
                if not a_d.get('phone_number'):
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
        if hasattr(appnt.user, 'patient_mobiles'):
            for mob in appnt.user.patient_mobiles.all():
                phone_number.append({"phone_number": mob.phone_number, "is_default": mob.is_default})
        patient_profile['patient_numbers'] = phone_number

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
        ret_obj['hospital'] = HospitalModelSerializer(appnt.hospital).data
        ret_obj['doctor'] = AppointmentRetrieveDoctorSerializer(appnt.doctor).data
        ret_obj['is_docprime'] = False
        ret_obj['type'] = 'doctor'
        return ret_obj

    def list_patients(self, request):
        user = request.user
        serializer = serializers.GetOfflinePatientsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        queryset = models.OfflinePatients.objects.filter(Q(doctor__manageable_doctors__user=user,
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
            queryset = queryset.filter(updated_at__gte=valid_data.get('updated_at'))
        queryset = queryset.values('name', 'id', 'gender', 'doctor', 'hospital', 'age', 'dob', 'calculated_dob', 'updated_at',
                                   'share_with_hospital', 'sms_notification', 'medical_history',
                                   'referred_by', 'display_welcome_message', 'error'
                                   ).distinct()
        return Response(queryset)

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
                obj = {'doctor': data.get('doctor').id,
                       'hospital': data.get('hospital').id if data.get('hospital') else None,
                       'id': data.get('id'),
                       'error': True,
                       'error_message': "Patient With Same UUid exists!"}
                resp.append(obj)
                logger.error("Patient With Same UUid exists! " + str(data))
                continue
            patient_data = self.create_patient(request, data, data.get('hospital'), data.get('doctor'))
            patient = patient_data['patient']
            if patient_data['sms_list'] is not None:
                sms_list.append(patient_data['sms_list'])

            ret_obj = {}
            ret_obj['doctor'] = patient.doctor.id
            ret_obj['hospital'] = patient.hospital.id if patient.hospital else None
            ret_obj['id'] = patient.id
            ret_obj['error'] = patient.error
            ret_obj['error_message'] = patient.error_message
            resp.append(ret_obj)

            if sms_list:
                transaction.on_commit(lambda: models.OfflinePatients.after_commit_sms(sms_list))

        return Response(resp)

    @transaction.atomic
    def create_offline_appointments(self, request):
        serializer = serializers.OfflineAppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        patient = None
        sms_list = []
        resp = []
        appntment_ids = list(models.OfflineOPDAppointments.objects.values_list('id', flat=True))
        patient_ids = list(models.OfflinePatients.objects.values_list('id', flat=True))
        req_hosp_ids = [data.get('hospital').id if data.get('hospital') else None for data in valid_data.get('data')]
        clinic_queryset = [(dc.doctor.id, dc.hospital.id) for dc in
                           models.DoctorClinic.objects.filter(hospital__id__in=req_hosp_ids)]
        pem_queryset = [(ga.doctor.id if ga.doctor else None, ga.hospital.id if ga.hospital else None) for ga in auth_models.GenericAdmin.objects.filter(is_disabled=False, user=request.user).all()]
        doc_pem_list, hosp_pem_list = map(list, zip(*pem_queryset))

        for data in valid_data.get('data'):
            try:
                id = UUID(data.get('id'), version=4)
            except ValueError:
                obj = self.get_error_obj(data)
                obj['doctor_id'] = data.get('doctor').id
                obj['hospital_id'] = data.get('hospital').id
                obj['error_message'] = 'Invalid UUid - Offline Appointment Create!'
                resp.append(obj)
                logger.error("PROVIDER_REQUEST - Invalid UUid - Offline Appointment Create! " + str(data))
                continue
            if id in appntment_ids:
                obj = {'id': data.get('id'),
                       'error': True,
                       'error_message': "Appointment With Same UUid exists!"}
                obj['doctor_id'] = data.get('doctor').id
                obj['hospital_id'] = data.get('hospital').id
                resp.append(obj)
                logger.error("PROVIDER_REQUEST - Offline Appointment With Same UUid exists! " + str(data))
                continue
            if not data.get('patient'):
                obj = {'id': data.get('id'),
                       'error': True,
                       'error_message': "Patient not Recieved for Offline Appointment!"}
                obj['doctor_id'] = data.get('doctor').id
                obj['hospital_id'] = data.get('hospital').id
                resp.append(obj)
                logger.error("PROVIDER_REQUEST - Patient not Recieved for Offline Appointment! " + str(data))
                continue

            if not data.get('doctor').id in doc_pem_list and not data.get('hospital').id in hosp_pem_list:
                data['error'] = True
                data['error_message'] = 'User forbidden to create Appointment with selected doctor or hospital!'
            if (data.get('doctor').id, data.get('hospital').id) not in clinic_queryset:
                data['error'] = True
                data['error_message'] = 'Doctor is not associated with given hospital!'

            if not data.get('patient')['id'] in patient_ids:
                patient_data = self.create_patient(request, data['patient'], data['hospital'], data['doctor'])
            else:
                patient_data = self.update_patient(request, data['patient'], data['hospital'], data['doctor'])

            patient = patient_data['patient']
            if patient_data['sms_list'] is not None:
                sms_list.append(patient_data['sms_list'])
            time_slot_start = data.get('time_slot_start')
            try:
                appnt = models.OfflineOPDAppointments.objects.create(doctor=data.get('doctor'),
                                                                     id=id,
                                                                     hospital=data.get('hospital'),
                                                                     time_slot_start=time_slot_start,
                                                                     booked_by=request.user,
                                                                     user=patient,
                                                                     status=models.OfflineOPDAppointments.ACCEPTED,
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
            appntment_ids.append(appnt.id)
            patient_ids.append(patient.id)
            ret_obj = {}
            ret_obj['id'] = appnt.id
            ret_obj['patient_id'] = appnt.user.id
            ret_obj['error'] = appnt.error
            ret_obj['error_message'] = appnt.error_message

            ret_obj.update(self.get_offline_response_obj(appnt, request))

            resp.append(ret_obj)

        if sms_list:
            transaction.on_commit(lambda: models.OfflinePatients.after_commit_sms(sms_list))

        return Response(resp)

    def create_patient(self, request, data, hospital, doctor):
        if data.get('share_with_hospital') and not hospital:
            logger.error('PROVIDER_REQUEST - Hospital Not Given when Shared with Hospital Set'+ str(data))
        hosp = hospital if data.get('share_with_hospital') and hospital else None
        patient = models.OfflinePatients.objects.create(name=data.get('name'),
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
        if data.get('phone_number'):
            for num in data.get('phone_number'):
                models.PatientMobile.objects.create(patient=patient,
                                                    phone_number=num.get('phone_number'),
                                                    is_default=num.get('is_default', False))

                if 'is_default' in num and num['is_default']:
                    default_num = num['phone_number']
            if default_num and ('sms_notification' in data and data['sms_notification']):
                sms_number = default_num
        return {"sms_list": sms_number, 'display_welcome_message': patient.display_welcome_message, 'welcome_message': patient.welcome_message , "patient": patient}

    def update_patient(self, request, data, hospital, doctor):
        if data.get('share_with_hospital') and not hospital:
            logger.error('PROVIDER_REQUEST - Hospital Not Given when Shared with Hospital Set'+ str(data))
        hosp = hospital if data.get('share_with_hospital') and hospital else None
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
            patient.save()
            default_num = None
            sms_number = None

            if data.get('phone_number'):
                del_queryset = models.PatientMobile.objects.filter(patient=patient)
                if del_queryset.exists():
                    del_queryset.delete()
                for num in data.get('phone_number'):
                    models.PatientMobile.objects.create(patient=patient,
                                                        phone_number=num.get('phone_number'),
                                                        is_default=num.get('is_default', False))

                    if 'is_default' in num and num['is_default']:
                        default_num = num['phone_number']
                if default_num and ('sms_notification' in data and data['sms_notification']):
                    sms_number = default_num
            return {"sms_list": sms_number, 'display_welcome_message': patient.display_welcome_message, 'welcome_message': patient.welcome_message , "patient": patient}

    def update_offline_appointments(self, request):
        serializer = serializers.OfflineAppointmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        sms_list = []
        resp = []
        appntment_ids = models.OfflineOPDAppointments.objects.all()
        patient_ids = list(models.OfflinePatients.objects.values_list('id', flat=True))
        req_hosp_ids = [data.get('hospital').id if data.get('hospital') else None for data in valid_data.get('data')]
        clinic_queryset = [(dc.doctor.id, dc.hospital.id) for dc in models.DoctorClinic.objects.filter(hospital__id__in=req_hosp_ids)]
        pem_queryset = [(ga.doctor.id if ga.doctor else None, ga.hospital.id if ga.hospital else None) for ga in
                        auth_models.GenericAdmin.objects.filter(is_disabled=False, user=request.user).all()]
        doc_pem_list, hosp_pem_list = map(list, zip(*pem_queryset))

        for data in valid_data.get('data'):
            if not data.get('is_docprime'):
                try:
                    id = UUID(data.get('id'), version=4)
                except ValueError:
                    obj = self.get_error_obj(data)
                    obj['doctor_id'] = data.get('doctor').id
                    obj['hospital_id'] = data.get('hospital').id
                    obj['error_message'] = 'Invalid UUid - Offline Appointment Update!'
                    resp.append(obj)
                    logger.error("PROVIDER_REQUEST - Invalid UUid - Offline Appointment Update! " + str(data))
                    continue
                found = False
                for appnt in appntment_ids:
                    if id == appnt.id:
                        patient = def_number = None
                        found = True
                        if appnt.error:
                            obj = self.get_error_obj(data)
                            obj['error_message'] = 'Cannot Update an invalid/error appointment!'
                            obj.update(self.get_offline_response_obj(appnt, request))
                            resp.append(obj)
                            logger.error("PROVIDER_REQUEST - Updating a invalid/error Appointment! " + str(data))
                            break
                        if appnt.status == models.OfflineOPDAppointments.CANCELLED or appnt.status == models.OfflineOPDAppointments.NO_SHOW:
                            obj = self.get_error_obj(data)
                            obj['error_message'] = 'Cannot Update a Cancelled/NoShow appointment!'
                            obj.update(self.get_offline_response_obj(appnt, request))
                            resp.append(obj)
                            logger.error("PROVIDER_REQUEST - Updating a Cancelled/NoShow Appointment! " + str(data))
                            break
                        if not data.get('doctor').id in doc_pem_list and not data.get('hospital').id in hosp_pem_list:
                            data['error'] = True
                            data['error_message'] = 'User forbidden to update Appointment with selected doctor or hospital!'
                        if (data.get('doctor').id, data.get('hospital').id) not in clinic_queryset:
                            data['error'] = True
                            data['error_message'] = 'Doctor is not associated with given hospital!'
                        if data.get('status') and data.get('status') not in [models.OfflineOPDAppointments.NO_SHOW,
                                                                             models.OfflineOPDAppointments.RESCHEDULED_DOCTOR,
                                                                             models.OfflineOPDAppointments.CANCELLED,
                                                                             models.OfflineOPDAppointments.ACCEPTED]:
                            obj = self.get_error_obj(data)
                            obj['error_message'] = 'Invalid Appointment Status Recieved!'
                            obj.update(self.get_offline_response_obj(appnt, request))
                            resp.append(obj)
                            logger.error("PROVIDER_REQUEST - Invalid Appointment Status Recieved! " + str(data))
                            break
                        if data.get('patient'):
                            if not data.get('patient')['id'] in patient_ids:
                                patient_data = self.create_patient(request, data['patient'], data['hospital'],
                                                                   data['doctor'])
                                patient_ids.append(patient_data['patient'].id)

                            else:
                                patient_data = self.update_patient(request, data['patient'], data['hospital'],
                                                                   data['doctor'])

                            patient = patient_data['patient']
                            if patient_data['sms_list'] is not None:
                                sms_list.append(patient_data['sms_list'])
                            appnt.user = patient

                        else:
                            patient = appnt.user
                            if patient.sms_notification:
                                def_number = patient.patient_mobiles.filter(is_default=True).first()
                                if def_number:
                                    sms_list.append(def_number.phone_number)
                        appnt.doctor = data.get('doctor')
                        appnt.hospital = data.get('hospital')
                        appnt.error = data.get('error')
                        appnt.error_message = data.get('error_message')

                        if data.get("time_slot_start") and data.get('status') == models.OfflineOPDAppointments.RESCHEDULED_DOCTOR:
                            # time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))
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
                        ret_obj = {}
                        ret_obj['id'] = appnt.id
                        ret_obj['patient_id'] = appnt.user.id
                        ret_obj['error'] = appnt.error
                        ret_obj['status'] = appnt.status
                        ret_obj['error_message'] = appnt.error_message if appnt.error_message else None
                        ret_obj.update(self.get_offline_response_obj(appnt, request))
                        resp.append(ret_obj)
                        break
                if not found:
                    obj = self.get_error_obj(data)
                    obj['error_message'] = "Appointment not Found!"
                    resp.append(obj)
                    logger.error("PROVIDER_REQUEST - Offline Update Appointment is not Found! " + str(data))

        # if sms_list:
        #     transaction.on_commit(lambda: models.OfflinePatients.after_commit_sms(sms_list))

        return Response(resp)

    def offline_timings(self, request):
        user = request.user
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        dc_queryset = models.DoctorClinic.objects.filter(Q(
                                                   Q(doctor__manageable_doctors__user=user,
                                                     doctor__manageable_doctors__entity_type=GenericAdminEntity.DOCTOR,
                                                     doctor__manageable_doctors__is_disabled=False,
                                                     doctor__manageable_doctors__hospital__isnull=True)
                                                   |
                                                   Q(doctor__manageable_doctors__user=user,
                                                     doctor__manageable_doctors__entity_type=GenericAdminEntity.DOCTOR,
                                                     doctor__manageable_doctors__is_disabled=False,
                                                     doctor__manageable_doctors__hospital__isnull=False,
                                                     doctor__manageable_doctors__hospital=F('hospital'))
                                                   |
                                                   Q(hospital__manageable_hospitals__user=user,
                                                     hospital__manageable_hospitals__is_disabled=False,
                                                     hospital__manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL)
                                                   )
                                                  |
                                                  Q(
                                                      Q(doctor__manageable_doctors__user=user,
                                                        doctor__manageable_doctors__super_user_permission=True,
                                                        doctor__manageable_doctors__is_disabled=False,
                                                        doctor__manageable_doctors__entity_type=GenericAdminEntity.DOCTOR)
                                                      |
                                                      Q(hospital__manageable_hospitals__user=user,
                                                        hospital__manageable_hospitals__is_disabled=False,
                                                        hospital__manageable_hospitals__entity_type=GenericAdminEntity.HOSPITAL,
                                                        hospital__manageable_hospitals__super_user_permission=True)
                                                   )
                                                  ).distinct().values('id', 'doctor', 'hospital')
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
                doctor_leave_serializer = serializers.DoctorLeaveSerializer(
                    models.DoctorLeave.objects.filter(doctor=validated_data.get("doctor_id"), deleted_at__isnull=True),
                    many=True)

                timeslots = dict()
                obj = TimeSlotExtraction()

                for data in queryset:
                    obj.form_time_slots(data.day, data.start, data.end, data.fees, True,
                                        data.deal_price, data.mrp, True)

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

    def list_appointments(self, request):
        ONLINE = 1
        OFFLINE = 2
        INCOMPLETE = 1
        ELIGIBLE = 2
        INITIATED = 3
        PROCESSED = 4
        serializer = serializers.OfflineAppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        online_queryset = get_opd_pem_queryset(request.user, models.OpdAppointment)\
            .select_related('profile', 'merchant_payout')\
            .prefetch_related('prescriptions', 'prescriptions__prescription_file').distinct()

        offline_queryset = get_opd_pem_queryset(request.user, models.OfflineOPDAppointments)\
            .select_related('user')\
            .prefetch_related('user__patient_mobiles').distinct()
        start_date = valid_data.get('start_date')
        end_date = valid_data.get('end_date')
        updated_at = valid_data.get('updated_at')
        final_data = []
        if start_date and end_date:
            online_queryset = online_queryset.filter(time_slot_start__date__range=(start_date, end_date))\
                .order_by('time_slot_start')
            offline_queryset = offline_queryset.filter(time_slot_start__date__range=(start_date, end_date))\
                .order_by('time_slot_start')
        if updated_at:
            admin_queryset = auth_models.GenericAdmin.objects.filter(user=request.user, updated_at__gte=updated_at)
            if not admin_queryset.exists():
                online_queryset = online_queryset.filter(updated_at__gte=updated_at)
                offline_queryset = offline_queryset.filter(updated_at__gte=updated_at)
        final_data = sorted(chain(online_queryset, offline_queryset), key=lambda car: car.time_slot_start, reverse=False)

        final_result = []
        for app in final_data:
            instance = ONLINE if isinstance(app, models.OpdAppointment) else OFFLINE
            patient_name = is_docprime = effective_price = deal_price = patient_thumbnail = prescription = None
            error_flag = False
            error_message = ''
            phone_number = []
            allowed_actions = []
            payout_amount = billing_status = None
            if instance == OFFLINE:
                patient_profile = OfflinePatientSerializer(app.user).data
                is_docprime = False
                patient_name = app.user.name if hasattr(app.user, 'name') else None
                if hasattr(app.user, 'patient_mobiles'):
                    for mob in app.user.patient_mobiles.all():
                        phone_number.append({"phone_number": mob.phone_number, "is_default": mob.is_default})
                patient_profile['phone_numbers'] = phone_number
                error_flag = app.error if app.error else False
                error_message = app.error_message if app.error_message else ''
            else:
                is_docprime = True
                effective_price = app.effective_price
                deal_price = app.deal_price
                allowed_actions = app.allowed_action(User.DOCTOR, request)
                phone_number.append({"phone_number": app.user.phone_number, "is_default": True})
                patient_profile = auth_serializers.UserProfileSerializer(app.profile, context={'request': request}).data
                patient_thumbnail = patient_profile['profile_image']
                patient_profile['user_id'] = app.user.id if app.user else None
                patient_profile['profile_id'] = app.profile.id if hasattr(app, 'profile') else None
                patient_profile['phone_numbers'] = phone_number
                patient_name = app.profile.name if hasattr(app, 'profile') else None
                if app.time_slot_start <= timezone.now() and \
                        app.status not in [models.OpdAppointment.COMPLETED, models.OpdAppointment.CANCELLED, models.OpdAppointment.BOOKED]:
                    billing_status = INCOMPLETE
                elif app.status == models.OpdAppointment.COMPLETED and (not app.merchant_payout or app.merchant_payout.status not in \
                        [account_models.MerchantPayout.ATTEMPTED, account_models.MerchantPayout.PAID]):
                    billing_status = ELIGIBLE
                elif app.status == models.OpdAppointment.COMPLETED and (app.merchant_payout and app.merchant_payout.status == account_models.MerchantPayout.ATTEMPTED):
                    billing_status = INITIATED
                elif app.status == models.OpdAppointment.COMPLETED and (
                        app.merchant_payout and app.merchant_payout.status == account_models.MerchantPayout.PAID):
                    billing_status = PROCESSED

                payout_amount = app.merchant_payout.payable_amount if app.merchant_payout else app.fees
                prescription = app.get_prescriptions(request)
            # if app.super_user:
            #     pem_type = 3
            # elif not app.super_user and not app.appointment_pem and app.billing_pem:
            #     pem_type = 2
            # elif not app.super_user and app.appointment_pem and not app.billing_pem:
            #     pem_type = 1
            # elif not app.super_user and app.appointment_pem and app.billing_pem:
            #     pem_type = 3
            ret_obj = {}
            ret_obj['id'] = app.id
            ret_obj['deal_price'] = deal_price
            ret_obj['payout_amount'] = payout_amount
            ret_obj['effective_price'] = effective_price
            ret_obj['allowed_action'] = allowed_actions
            ret_obj['patient_name'] = patient_name
            ret_obj['updated_at'] = app.updated_at
            ret_obj['doctor_name'] = app.doctor.name
            ret_obj['doctor_id'] = app.doctor.id
            ret_obj['doctor_thumbnail'] = request.build_absolute_uri(app.doctor.get_thumbnail()) if app.doctor.get_thumbnail() else None
            ret_obj['hospital_id'] = app.hospital.id
            ret_obj['hospital_name'] = app.hospital.name
            ret_obj['time_slot_start'] = app.time_slot_start
            ret_obj['status'] = app.status
            ret_obj['billing_status'] = billing_status
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
            final_result.append(ret_obj)
            # if group.get(app.time_slot_start.strftime("%B %d, %Y")):
            #     group[app.time_slot_start.strftime("%B %d, %Y")].append(ret_obj)
            # else:
            #     group[app.time_slot_start.strftime("%B %d, %Y")] = [ret_obj]
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
        else:
            phone_number = patient.phone_number
        if data.get('type') == serializers.AppointmentMessageSerializer.REMINDER:
            if phone_number:
                try:
                    notification_tasks.send_appointment_reminder_message.apply_async(
                        kwargs={'number': phone_number,
                                'doctor': appnt.doctor.name,
                                'date': appnt.time_slot_start.strftime("%B %d, %Y")},
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