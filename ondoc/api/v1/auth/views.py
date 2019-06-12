import base64
import json
import random
import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe

from ondoc.account import models as account_models
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from dal import autocomplete
from rest_framework import mixins, viewsets, status
from ondoc.api.v1.auth import serializers
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.authtoken.models import Token
from django.db.models import F, Sum, Max, Q, Prefetch, Case, When, Count
from django.forms.models import model_to_dict

from ondoc.common.models import UserConfig, PaymentOptions, AppointmentHistory, BlacklistUser, BlockedStates
from ondoc.common.utils import get_all_upcoming_appointments
from ondoc.coupon.models import UserSpecificCoupon, Coupon
from ondoc.lead.models import UserLead
from ondoc.sms.api import send_otp
from ondoc.doctor.models import DoctorMobile, Doctor, HospitalNetwork, Hospital, DoctorHospital, DoctorClinic, \
                                DoctorClinicTiming, ProviderSignupLead
from ondoc.authentication.models import (OtpVerifications, NotificationEndpoint, Notification, UserProfile,
                                         Address, AppointmentTransaction, GenericAdmin, UserSecretKey, GenericLabAdmin,
                                         AgentToken, DoctorNumber, LastLoginTimestamp)
from ondoc.notification.models import SmsNotification, EmailNotification
from ondoc.account.models import PgTransaction, ConsumerAccount, ConsumerTransaction, Order, ConsumerRefund, OrderLog, \
    UserReferrals, UserReferred, PgLogs
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ondoc.api.pagination import paginate_queryset
from ondoc.api.v1 import utils
from ondoc.doctor.models import OpdAppointment
from ondoc.api.v1.doctor.serializers import (OpdAppointmentSerializer, AppointmentFilterUserSerializer,
                                             UpdateStatusSerializer, CreateAppointmentSerializer,
                                             AppointmentRetrieveSerializer, OpdAppTransactionModelSerializer,
                                             OpdAppModelSerializer, OpdAppointmentUpcoming,
                                             NewAppointmentRetrieveSerializer)
from ondoc.api.v1.diagnostic.serializers import (LabAppointmentModelSerializer,
                                                 LabAppointmentRetrieveSerializer, LabAppointmentCreateSerializer,
                                                 LabAppTransactionModelSerializer, LabAppRescheduleModelSerializer,
                                                 LabAppointmentUpcoming)
from ondoc.api.v1.insurance.serializers import (InsuranceTransactionSerializer)
from ondoc.api.v1.diagnostic.views import LabAppointmentView
from ondoc.diagnostic.models import (Lab, LabAppointment, AvailableLabTest, LabNetwork)
from ondoc.payout.models import Outstanding
from ondoc.authentication.backends import JWTAuthentication
from ondoc.api.v1.utils import (IsConsumer, IsDoctor, opdappointment_transform, labappointment_transform,
                                ErrorCodeMapping, IsNotAgent, GenericAdminEntity)
from django.conf import settings
from collections import defaultdict
import copy
import logging
import jwt
from ondoc.insurance.models import InsuranceTransaction, UserInsurance, InsuredMembers
from decimal import Decimal
from ondoc.web.models import ContactUs
from ondoc.notification.tasks import send_pg_acknowledge

from ondoc.ratings_review import models as rate_models
from django.contrib.contenttypes.models import ContentType

import re
from ondoc.matrix.tasks import push_order_to_matrix



logger = logging.getLogger(__name__)
User = get_user_model()


def expire_otp(phone_number):
    OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)


class LoginOTP(GenericViewSet):

    serializer_class = serializers.OTPSerializer

    @transaction.atomic
    def generate(self, request, format=None):

        response = {'exists': 0}
        # if request.data.get("phone_number"):
        #     expire_otp(phone_number=request.data.get("phone_number"))
        serializer = serializers.OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone_number = data['phone_number']

        blocked_state = BlacklistUser.get_state_by_number(phone_number, BlockedStates.States.LOGIN)
        if blocked_state:
            return Response({'error': blocked_state.message}, status=status.HTTP_400_BAD_REQUEST)


        req_type = request.query_params.get('type')
        via_sms = data.get('via_sms', True)
        via_whatsapp = data.get('via_whatsapp', False)
        call_source = data.get('request_source')
        retry_send = request.query_params.get('retry', False)
        otp_message = OtpVerifications.get_otp_message(request.META.get('HTTP_PLATFORM'), req_type, version=request.META.get('HTTP_APP_VERSION'))
        if req_type == 'doctor':
            doctor_queryset = GenericAdmin.objects.select_related('doctor', 'hospital').filter(phone_number=phone_number, is_disabled=False)
            lab_queryset = GenericLabAdmin.objects.select_related('lab', 'lab_network').filter(
                Q(phone_number=phone_number, is_disabled=False),
                (Q(lab__isnull=True, lab_network__data_status=LabNetwork.QC_APPROVED) |
                 Q(lab__isnull=False,
                   lab__data_status=Lab.QC_APPROVED, lab__onboarding_status=Lab.ONBOARDED
                   )
                 )
                )
            provider_signup_queryset = ProviderSignupLead.objects.filter(phone_number=phone_number, user__isnull=False)

            if lab_queryset.exists() or doctor_queryset.exists() or provider_signup_queryset.exists():
                response['exists'] = 1
                send_otp(otp_message, phone_number, retry_send)

            # if queryset.exists():
            #     response['exists'] = 1
            #     send_otp("OTP for DocPrime login is {}", phone_number)

        else:
            send_otp(otp_message, phone_number, retry_send, via_sms=via_sms, via_whatsapp=via_whatsapp, call_source=call_source)
            if User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).exists():
                response['exists'] = 1

        return Response(response)

    def verify(self, request, format=None):

        serializer = serializers.OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({"message": "OTP Generated Sucessfuly."})


class UserViewset(GenericViewSet):
    serializer_class = serializers.UserSerializer
    @transaction.atomic
    def login(self, request, format=None):
        from ondoc.authentication.backends import JWTAuthentication
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

            # for new user, create a referral coupon entry
            self.set_referral(user)


        self.set_coupons(user)

        token_object = JWTAuthentication.generate_token(user)

        expire_otp(data['phone_number'])

        response = {
            "login": 1,
            "user_exists": user_exists,
            "user_id": user.id,
            "token": token_object['token'],
            "expiration_time": token_object['payload']['exp']
        }
        return Response(response)

    def set_coupons(self, user):
        UserSpecificCoupon.objects.filter(phone_number=user.phone_number, user__isnull=True).update(user=user)

    def set_referral(self, user):
        try:
            UserReferrals.objects.create(user=user)
        except Exception as e:
            logger.error(str(e))

    @transaction.atomic
    def logout(self, request):
        required_token = request.data.get("token", None)
        if required_token and request.user.is_authenticated:
            NotificationEndpoint.objects.filter(user=request.user, token=request.data.get("token")).delete()
        return Response({"message": "success"})

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
            user = User.objects.create(phone_number=data['phone_number'], is_phone_number_verified=True,
                                       user_type=User.DOCTOR)
            # doctor_mobile = DoctorMobile.objects.filter(number=phone_number, is_primary=True)
        if not hasattr(user, 'doctor'):
            doctor_mobile = DoctorNumber.objects.filter(phone_number=phone_number)
            if doctor_mobile.exists():
                doctor = doctor_mobile.first().doctor
                doctor.user = user
                doctor.save()

        GenericAdmin.update_user_admin(phone_number)
        GenericLabAdmin.update_user_lab_admin(phone_number)
        self.update_live_status(phone_number)

        token_object = JWTAuthentication.generate_token(user)
        expire_otp(data['phone_number'])

        if data.get("source"):
            LastLoginTimestamp.objects.create(user=user, source=data.get("source"))

        response = {
            "login": 1,
            "token": token_object['token'],
            "expiration_time": token_object['payload']['exp']
        }
        return Response(response)

    def update_live_status(self, phone):
        queryset = GenericAdmin.objects.select_related('doctor').filter(phone_number=phone)
        if queryset.first():
            for admin in queryset.distinct('doctor').all():
                if admin.doctor is not None:
                    if not admin.doctor.is_live:
                        if admin.doctor.data_status == Doctor.QC_APPROVED and admin.doctor.onboarding_status == Doctor.ONBOARDED:
                            admin.doctor.is_live = True
                            admin.doctor.live_at = datetime.datetime.now()
                            admin.doctor.save()
                elif admin.hospital:
                    for hosp_doc in admin.hospital.assoc_doctors.all():
                        if hosp_doc.data_status == Doctor.QC_APPROVED and hosp_doc.onboarding_status == Doctor.ONBOARDED:
                            hosp_doc.is_live = True
                            hosp_doc.live_at= datetime.datetime.now()
                            hosp_doc.save()


class NotificationEndpointViewSet(GenericViewSet):
    serializer_class = serializers.NotificationEndpointSerializer
    permission_classes = (IsNotAgent, )

    @transaction.atomic
    def save(self, request):
        serializer = serializers.NotificationEndpointSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        NotificationEndpoint.objects.filter(token=validated_data.get('token')).delete()
        notification_endpoint_data = {
            "user": request.user.id,
            "device_id": validated_data.get("device_id"),
            "platform": validated_data.get("platform"),
            "app_name": validated_data.get("app_name"),
            "app_version": validated_data.get("app_version"),
            "token": validated_data.get("token")
        }
        notification_endpoint_serializer = serializers.NotificationEndpointSerializer(data=notification_endpoint_data)
        notification_endpoint_serializer.is_valid(raise_exception=True)
        try:
            notification_endpoint_serializer.save()
        except IntegrityError:
            return Response(notification_endpoint_serializer.data)
        return Response(notification_endpoint_serializer.data)

    def delete(self, request):
        serializer = serializers.NotificationEndpointDeleteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        notification_endpoint = NotificationEndpoint.objects.filter(token=validated_data.get('token')).first()
        notification_endpoint.delete()
        return Response(data={"status": 1, "message": "deleted"})


class NotificationViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsNotAgent)

    def list(self, request):
        queryset = paginate_queryset(queryset=Notification.objects.filter(user=request.user),
                                     request=request)
        serializer = serializers.NotificationSerializer(queryset, many=True)
        return Response(serializer.data)


class WhatsappOptinViewSet(GenericViewSet):

    def update(self, request, *args, **kwargs):
        phone_number = request.data.get('phone_number')
        optin = request.data.get('optin')
        source = request.data.get('source')

        if optin not in [True, False]:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'optin must be boolean field.'})

        if not phone_number:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'phone_number is required.'})

        user_profile_obj = UserProfile.objects.filter(phone_number=phone_number)
        if not user_profile_obj:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'could not find the userprofile with number %s' % str(phone_number)})

        if source == 'WHATSAPP_SERVICE' and optin is False:
            user_profile_obj.update(whatsapp_optin=optin, whatsapp_is_declined=True)

        return Response()


class UserProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                         mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         GenericViewSet):

    serializer_class = serializers.UserProfileSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsConsumer)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        queryset = UserProfile.objects.filter(user=request.user)
        return queryset

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        serializer = [serializers.UserProfileSerializer(q, context= {'request':request}).data for q in qs]
        return Response(data=serializer)

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = {}
        data['name'] = request.data.get('name')
        data['gender'] = request.data.get('gender')
        # data['age'] = request.data.get('age')
        data['email'] = request.data.get('email')
        data['phone_number'] = request.data.get('phone_number')
        data['whatsapp_optin'] = request.data.get('whatsapp_optin')
        data['user'] = request.user.id
        first_profile = False

        if not queryset.exists():
            data.update({
                "is_default_user": True
            })
            first_profile = True

        if not bool(re.match(r"^[a-zA-Z ]+$", request.data.get('name'))):
            return Response({"error": "Invalid Name"}, status=status.HTTP_400_BAD_REQUEST)

        if request.data.get('age'):
            try:
                age = int(request.data.get("age"))
                data['dob'] = datetime.datetime.now() - relativedelta(years=age)
                data['dob'] = data['dob'].date()
            except:
                return Response({"error": "Invalid Age"}, status=status.HTTP_400_BAD_REQUEST)
        elif request.data.get('dob'):
            dob = request.data.get('dob')
            data['dob'] = dob
        else:
            # return Response({'age': {'code': 'required', 'message': 'This field is required.'}},
            #                 status=status.HTTP_400_BAD_REQUEST)
            data['dob'] = None


        if not data.get('phone_number'):
            data['phone_number'] = request.user.phone_number
        serializer = serializers.UserProfileSerializer(data=data, context= {'request':request})
        serializer.is_valid(raise_exception=True)
        serializer.validated_data
        if UserProfile.objects.filter(name__iexact=data['name'], user=request.user).exists():
            # return Response({
            #     "request_errors": {"code": "invalid",
            #                        "message": "Profile with the given name already exists."
            #                        }
            # }, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.data)
        serializer.save()
        # for new profile credit referral amount if any refrral code is used
        if first_profile and request.data.get('referral_code'):
            try:
                self.credit_referral(request.data.get('referral_code'), request.user)
            except Exception as e:
                logger.error(str(e))
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        data = {key: value for key, value in request.data.items()}
        # if data.get('age'):
        #     try:
        #         age = int(request.data.get("age"))
        #         data['dob'] = datetime.datetime.now() - relativedelta(years=age)
        #         data['dob'] = data['dob'].date()
        #     except:
        #         return Response({"error": "Invalid Age"}, status=status.HTTP_400_BAD_REQUEST)

        obj = self.get_object()

        if not bool(re.match(r"^[a-zA-Z ]+$", data.get('name'))):
            return Response({"error": "Invalid Name"}, status=status.HTTP_400_BAD_REQUEST)
        
        if data.get("name") and UserProfile.objects.exclude(id=obj.id).filter(name=data['name'],
                                                                              user=request.user).exists():
            return Response({
                "request_errors": {"code": "invalid",
                                   "message": "Profile with the given name already exists."
                                   }
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.UserProfileSerializer(obj, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Insurance work. User is made to update only whatsapp_optin and whatsapp_is_declined in case if userprofile
        # is covered under insuranc. Else profile under insurance  cannot be updated in any case.

        insured_member_obj = InsuredMembers.objects.filter(profile__id=obj.id).last()
        insured_member_profile = None
        insured_member_status = None
        if insured_member_obj:
            insured_member_profile = insured_member_obj.profile
            insured_member_status = insured_member_obj.user_insurance.status
        # if obj and hasattr(obj, 'id') and obj.id and insured_member_profile:

        if request.user and request.user.active_insurance and data.get('is_default_user') and data.get('is_default_user') != obj.is_default_user:
            return Response({
                "request_errors": {"code": "invalid",
                                   "message": "Any Profile or user associated with the insurance cannot change default user."
                                   }})

        if obj and hasattr(obj, 'id') and obj.id and insured_member_profile and not (insured_member_status == UserInsurance.CANCELLED or
                                                              insured_member_status == UserInsurance.EXPIRED):

            whatsapp_optin = data.get('whatsapp_optin')
            whatsapp_is_declined = data.get('whatsapp_is_declined')

            if (whatsapp_optin and whatsapp_optin in [True, False] and whatsapp_optin != insured_member_profile.whatsapp_optin) or \
                    (whatsapp_is_declined and whatsapp_is_declined in [True, False] and whatsapp_is_declined != insured_member_profile.whatsapp_is_declined):
                if whatsapp_optin:
                    insured_member_profile.whatsapp_optin = whatsapp_optin
                if whatsapp_is_declined:
                    insured_member_profile.whatsapp_is_declined = whatsapp_is_declined

                insured_member_profile.save()
                return Response(serializer.data)
            else:
                return Response({
                    "request_errors": {"code": "invalid",
                                       "message": "Profile cannot be changed which are covered under insurance."
                                       }
                }, status=status.HTTP_400_BAD_REQUEST)
        if data.get('is_default_user', None):
            UserProfile.objects.filter(user=obj.user).update(is_default_user=False)
        else:
            primary_profile = UserProfile.objects.filter(user=obj.user, is_default_user=True).first()
            if not primary_profile or obj.id == primary_profile.id:
                return Response({
                    "request_errors": {"code": "invalid",
                                       "message": "Atleast one profile should be selected as primary."
                                       }
                }, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def upload(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = serializers.UploadProfilePictureSerializer(instance, data=request.data, context= {'request':request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic()
    def credit_referral(self, referral_code, user):
        referral = UserReferrals.objects.filter(Q(code__iexact=referral_code), ~Q(user=user)).first()
        if referral and not UserReferred.objects.filter(user=user).exists():
            UserReferred.objects.create(user=user, referral_code=referral, used=False)
            ConsumerAccount.credit_referral(user, UserReferrals.SIGNUP_CASHBACK)

class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class ReferralViewSet(GenericViewSet):
    # authentication_classes = (JWTAuthentication, )
    # permission_classes = (IsAuthenticated, IsNotAgent)

    def retrieve(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status=status.HTTP_401_UNAUTHORIZED)
        if UserReferrals.objects.all():
            referral = UserReferrals.objects.filter(user=user).first()
            if not referral:
                referral = UserReferrals()
                referral.user = user
                referral.save()

        user_config = UserConfig.objects.filter(key="referral").first()
        help_flow = []
        share_text = ''
        share_url = ''
        if user_config:
            all_data = user_config.data
            help_flow = all_data.get('help_flow', [])
            share_text = all_data.get('share_text', '').replace('$referral_code', referral.code)
            share_url = all_data.get('share_url', '').replace('$referral_code', referral.code)
        return Response({"code": referral.code, "status": 1, 'help_flow': help_flow,
                         "share_text": share_text, "share_url": share_url})

    def retrieve_by_code(self, request, code):
        referral = UserReferrals.objects.filter(code__iexact=code).first()
        if referral:
            default_user_profile = UserProfile.objects.filter(user=referral.user, is_default_user=True).first()
            if default_user_profile:
                return Response({"name": default_user_profile.name, "status": 1})

        return Response({"status": 0}, status=status.HTTP_404_NOT_FOUND)


class UserAppointmentsViewSet(OndocViewSet):

    serializer_class = OpdAppointmentSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsConsumer, )

    def get_queryset(self):
        user = self.request.user
        return OpdAppointment.objects.filter(user=user)

    @transaction.non_atomic_requests
    def list(self, request):
        params = request.query_params
        doctor_serializer = self.doctor_appointment_list(request, params)
        lab_serializer = self.lab_appointment_list(request, params)
        combined_data = list()
        if doctor_serializer.data:
            combined_data.extend(doctor_serializer.data)
        if lab_serializer.data:
            combined_data.extend(lab_serializer.data)
        combined_data = sorted(combined_data, key=lambda x: x['time_slot_start'], reverse=True)
        temp_dict = dict()
        for data in combined_data:
            if not temp_dict.get(data["status"]):
                temp_dict[data["status"]] = [data]
            else:
                temp_dict[data["status"]].append(data)
        combined_data = list()
        status_six_data = list()
        for k, v in sorted(temp_dict.items(), key=lambda x: x[0]):
            if k==6:
                status_six_data.extend(v)
            else:
                combined_data.extend(v)
        combined_data.extend(status_six_data)
        combined_data = combined_data[:200]
        return Response(combined_data)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk=None):
        user = request.user
        input_serializer = serializers.AppointmentqueryRetrieveSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)
        appointment_type = input_serializer.validated_data.get('type')
        if appointment_type == 'lab':
            queryset = LabAppointment.objects.filter(pk=pk, user=user)
            serializer = LabAppointmentRetrieveSerializer(queryset, many=True, context={"request": request})
            return Response(serializer.data)
        elif appointment_type == 'doctor':
            queryset = OpdAppointment.objects.filter(pk=pk, user=user)
            # serializer = AppointmentRetrieveSerializer(queryset, many=True, context={"request": request})
            serializer = NewAppointmentRetrieveSerializer(queryset, many=True, context={"request": request})
            return Response(serializer.data)
        else:
            return Response({'Error': 'Invalid Request Type'})

    @transaction.atomic
    def update(self, request, pk=None):
        serializer = UpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        query_input_serializer = serializers.AppointmentqueryRetrieveSerializer(data=request.query_params)
        query_input_serializer.is_valid(raise_exception=True)
        source = ''
        responsible_user = None
        if validated_data.get('source', None):
            source = validated_data.get('source')
        if query_input_serializer.validated_data.get('source', None):
            source = query_input_serializer.validated_data.get('source')
        if request.user and hasattr(request.user, 'user_type'):
            responsible_user = request.user
            if not source:
                if request.user.user_type == User.DOCTOR:
                    source = AppointmentHistory.DOC_APP
                elif request.user.user_type == User.CONSUMER:
                    source = AppointmentHistory.CONSUMER_APP
        appointment_type = query_input_serializer.validated_data.get('type')
        if appointment_type == 'lab':
            # lab_appointment = get_object_or_404(LabAppointment, pk=pk)
            lab_appointment = LabAppointment.objects.select_for_update().filter(pk=pk).first()
            lab_appointment._source = source
            lab_appointment._responsible_user = responsible_user
            resp = dict()
            if not lab_appointment:
                resp["status"] = 0
                resp["message"] = "Invalid appointment Id"
                return Response(resp, status.HTTP_404_NOT_FOUND)
            allowed = lab_appointment.allowed_action(request.user.user_type, request)
            appt_status = validated_data.get('status')
            if appt_status not in allowed:
                resp = dict()
                resp['allowed'] = allowed
                resp['Error'] = 'Action Not Allowed'
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            updated_lab_appointment = self.lab_appointment_update(request, lab_appointment, validated_data)
            if updated_lab_appointment.get("status") is not None and updated_lab_appointment["status"] == 0:
                return Response(updated_lab_appointment, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(updated_lab_appointment)
        elif appointment_type == 'doctor':
            # opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
            opd_appointment = OpdAppointment.objects.select_for_update().filter(pk=pk).first()
            opd_appointment._source = source
            opd_appointment._responsible_user = responsible_user
            resp = dict()
            if not opd_appointment:
                resp["status"] = 0
                resp["message"] = "Invalid appointment Id"
                return Response(resp, status.HTTP_404_NOT_FOUND)
            allowed = opd_appointment.allowed_action(request.user.user_type, request)
            appt_status = validated_data.get('status')
            if appt_status not in allowed:
                resp['allowed'] = allowed
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            updated_opd_appointment = self.doctor_appointment_update(request, opd_appointment, validated_data)
            if updated_opd_appointment.get("status") is not None and updated_opd_appointment["status"] == 0:
                return Response(updated_opd_appointment, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(updated_opd_appointment)

    @transaction.atomic
    def lab_appointment_update(self, request, lab_appointment, validated_data):
        resp = dict()
        resp["status"] = 1
        if validated_data.get('status'):
            if validated_data['status'] == LabAppointment.CANCELLED:
                lab_appointment.cancellation_type = LabAppointment.PATIENT_CANCELLED
                lab_appointment.cancellation_reason = validated_data.get('cancellation_reason', None)
                lab_appointment.cancellation_comments = validated_data.get('cancellation_comment', '')
                lab_appointment.action_cancelled(request.data.get('refund', 1))
                resp = LabAppointmentRetrieveSerializer(lab_appointment, context={"request": request}).data
            elif validated_data.get('status') == LabAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    time_slot_start = utils.form_time_slot(
                        validated_data.get("start_date"),
                        validated_data.get("start_time"))
                    if lab_appointment.time_slot_start == time_slot_start:
                        resp = {
                            "status": 0,
                            "message": "Cannot Reschedule for same timeslot"
                        }
                        return resp
                    if lab_appointment.payment_type == OpdAppointment.INSURANCE and lab_appointment.insurance_id is not None:
                        user_insurance = UserInsurance.objects.get(id=lab_appointment.insurance_id)
                        if user_insurance :
                            insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                            if time_slot_start > user_insurance.expiry_date or not user_insurance.is_valid():
                                resp = {
                                    "status": 0,
                                    "message": "Appointment time is not covered under insurance"
                                }
                                return resp

                    test_ids = lab_appointment.lab_test.values_list('test__id', flat=True)
                    lab_test_queryset = AvailableLabTest.objects.select_related('lab_pricing_group__labs').filter(
                        lab_pricing_group__labs=lab_appointment.lab,
                        test__in=test_ids)
                    deal_price_calculation = Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                                  When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
                    agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                                    When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))
                    temp_lab_test = lab_test_queryset.values('lab_pricing_group__labs').annotate(total_mrp=Sum("mrp"),
                                                                             total_deal_price=Sum(deal_price_calculation),
                                                                             total_agreed_price=Sum(agreed_price_calculation))
                    # old_deal_price = lab_appointment.deal_price
                    # old_effective_price = lab_appointment.effective_price
                    coupon_discount = lab_appointment.discount
                    # coupon_price = self.get_appointment_coupon_price(old_deal_price, old_effective_price)
                    new_deal_price = temp_lab_test[0].get("total_deal_price")

                    if lab_appointment.home_pickup_charges:
                        new_deal_price += lab_appointment.home_pickup_charges

                    if new_deal_price <= coupon_discount:
                        new_effective_price = 0
                    else:
                        if lab_appointment.insurance_id is None:
                            new_effective_price = new_deal_price - coupon_discount
                        else:
                            new_effective_price = 0.0
                    # new_appointment = dict()

                    new_appointment = {
                        "id": lab_appointment.id,
                        "lab": lab_appointment.lab,
                        "user": lab_appointment.user,
                        "profile": lab_appointment.profile,
                        "price": temp_lab_test[0].get("total_mrp"),
                        "agreed_price": temp_lab_test[0].get("total_agreed_price", 0),
                        "deal_price": new_deal_price,
                        "effective_price": new_effective_price,
                        "time_slot_start": time_slot_start,
                        "profile_detail": lab_appointment.profile_detail,
                        "status": lab_appointment.status,
                        "payment_type": lab_appointment.payment_type,
                        "lab_test": lab_appointment.lab_test,
                        "discount": coupon_discount
                    }

                    resp = self.extract_payment_details(request, lab_appointment, new_appointment,
                                                        account_models.Order.LAB_PRODUCT_ID)
        return resp

    @transaction.atomic
    def doctor_appointment_update(self, request, opd_appointment, validated_data):
        if validated_data.get('status'):
            resp = dict()
            resp["status"] = 1
            if validated_data['status'] == OpdAppointment.CANCELLED:
                logger.warning("Starting to cancel for id - " + str(opd_appointment.id) + " timezone - " + str(timezone.now()))
                opd_appointment.cancellation_type = OpdAppointment.PATIENT_CANCELLED
                opd_appointment.cancellation_reason = validated_data.get('cancellation_reason', None)
                opd_appointment.cancellation_comments = validated_data.get('cancellation_comment', '')
                opd_appointment.action_cancelled(request.data.get("refund", 1))
                logger.warning(
                    "Ending for id - " + str(opd_appointment.id) + " timezone - " + str(timezone.now()))
                resp = AppointmentRetrieveSerializer(opd_appointment, context={"request": request}).data
            elif validated_data.get('status') == OpdAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    time_slot_start = utils.form_time_slot(
                        validated_data.get("start_date"),
                        validated_data.get("start_time"))
                    if opd_appointment.time_slot_start == time_slot_start:
                        resp = {
                            "status": 0,
                            "message": "Cannot Reschedule for same timeslot"
                        }
                        return resp

                    doctor_hospital = DoctorClinicTiming.objects.filter(doctor_clinic__doctor__is_live=True,
                                                                        doctor_clinic__hospital__is_live=True,
                                                                        doctor_clinic__doctor=opd_appointment.doctor,
                                                                        doctor_clinic__hospital=opd_appointment.hospital,
                                                                        day=time_slot_start.weekday(),
                                                                        start__lte=time_slot_start.hour,
                                                                        end__gte=time_slot_start.hour).first()
                    if doctor_hospital:
                        if opd_appointment.payment_type == OpdAppointment.INSURANCE and opd_appointment.insurance_id is not None:
                            user_insurance = UserInsurance.objects.get(id=opd_appointment.insurance_id)
                            if user_insurance:
                                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                                if doctor_hospital.mrp > insurance_threshold.opd_amount_limit or not user_insurance.is_valid():
                                    resp = {
                                        "status": 0,
                                        "message": "Appointment amount is not covered under insurance"
                                    }
                                    return resp
                                if time_slot_start > user_insurance.expiry_date or not user_insurance.is_valid():
                                    resp = {
                                        "status": 0,
                                        "message": "Appointment time is not covered under insurance"
                                    }
                                    return resp



                        old_deal_price = opd_appointment.deal_price
                        old_effective_price = opd_appointment.effective_price
                        coupon_discount = opd_appointment.discount
                        if coupon_discount > doctor_hospital.deal_price:
                            new_effective_price = 0
                        else:
                            if opd_appointment.insurance_id is None:
                                new_effective_price = doctor_hospital.deal_price - coupon_discount
                            else:
                                new_effective_price = 0.0
                        if opd_appointment.procedures.count():
                            doctor_details = opd_appointment.get_procedures()[0]
                            old_agreed_price = Decimal(doctor_details["agreed_price"])
                            new_fees = opd_appointment.fees - old_agreed_price + doctor_hospital.fees
                            new_deal_price = opd_appointment.deal_price
                            new_mrp = opd_appointment.mrp
                            new_effective_price = opd_appointment.effective_price
                        else:
                            new_fees = doctor_hospital.fees
                            new_deal_price = doctor_hospital.deal_price
                            new_mrp = doctor_hospital.mrp

                        new_appointment = {
                            "id": opd_appointment.id,
                            "doctor": opd_appointment.doctor,
                            "hospital": opd_appointment.hospital,
                            "profile": opd_appointment.profile,
                            "profile_detail": opd_appointment.profile_detail,
                            "user": opd_appointment.user,

                            "booked_by": opd_appointment.booked_by,
                            "fees": new_fees,
                            "deal_price": new_deal_price,
                            "effective_price": new_effective_price,
                            "mrp": new_mrp,
                            "time_slot_start": time_slot_start,
                            "payment_type": opd_appointment.payment_type,
                            "discount": coupon_discount
                        }
                        resp = self.extract_payment_details(request, opd_appointment, new_appointment,
                                                            account_models.Order.DOCTOR_PRODUCT_ID)
                    else:
                        resp = {
                            "status": 0,
                            "message": "No time slot available for the give day and time."
                        }

            if validated_data['status'] == OpdAppointment.COMPLETED:
                opd_appointment.action_completed()
                resp = AppointmentRetrieveSerializer(opd_appointment, context={"request": request}).data
            return resp

    def get_appointment_coupon_price(self, discounted_price, effective_price):
        coupon_price = discounted_price - effective_price
        return coupon_price

    @transaction.atomic
    def extract_payment_details(self, request, appointment_details, new_appointment_details, product_id):
        resp = dict()
        user = request.user

        if appointment_details.payment_type == OpdAppointment.PREPAID and isinstance(appointment_details,OpdAppointment) and not appointment_details.procedures.count():
            remaining_amount = 0
            consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance

            resp["is_agent"] = False
            if hasattr(request, 'agent') and request.agent:
                resp["is_agent"] = True
                balance = 0

            if balance + appointment_details.effective_price >= new_appointment_details.get('effective_price'):
                # Debit or Refund/Credit in Account
                if appointment_details.effective_price > new_appointment_details.get('effective_price'):
                    # TODO PM - Refund difference b/w effective price
                    consumer_account.credit_schedule(appointment_details, product_id, appointment_details.effective_price - new_appointment_details.get('effective_price'))
                    # consumer_account.credit_schedule(user_account_data, appointment_details.effective_price - new_appointment_details.get('effective_price'))
                else:
                    debit_balance = new_appointment_details.get('effective_price') - appointment_details.effective_price
                    if debit_balance:
                        consumer_account.debit_schedule(appointment_details, product_id, debit_balance)
                        # consumer_account.debit_schedule(user_account_data, debit_balance)

                # Update appointment
                if product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                    appointment_details.action_rescheduled_patient(new_appointment_details)
                    appointment_serializer = AppointmentRetrieveSerializer(appointment_details, context={"request": request})
                if product_id == account_models.Order.LAB_PRODUCT_ID:
                    appointment_details.action_rescheduled_patient(new_appointment_details)
                    appointment_serializer = LabAppointmentRetrieveSerializer(appointment_details, context={"request": request})
                resp['status'] = 1
                resp['data'] = appointment_serializer.data
                resp['payment_required'] = False
                return resp
            else:
                current_balance = consumer_account.balance + appointment_details.effective_price
                new_appointment_details['time_slot_start'] = str(new_appointment_details['time_slot_start'])
                action = ''
                temp_app_details = copy.deepcopy(new_appointment_details)

                if product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                    action = account_models.Order.OPD_APPOINTMENT_RESCHEDULE
                    opdappointment_transform(temp_app_details)
                elif product_id == account_models.Order.LAB_PRODUCT_ID:
                    action = Order.LAB_APPOINTMENT_RESCHEDULE
                    labappointment_transform(temp_app_details)

                order = account_models.Order.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=temp_app_details,
                    amount=new_appointment_details.get('effective_price') - current_balance,
                    wallet_amount=current_balance,
                    # reference_id=appointment_details.id,
                    payment_status=account_models.Order.PAYMENT_PENDING
                )
                new_appointment_details["payable_amount"] = new_appointment_details.get('effective_price') - balance
                resp['status'] = 1
                resp['data'], resp['payment_required'] = self.payment_details(request, new_appointment_details, product_id, order.id)
                return resp
        else:
            if product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                appointment_details.action_rescheduled_patient(new_appointment_details)
                appointment_serializer = AppointmentRetrieveSerializer(appointment_details,
                                                                       context={"request": request})
            if product_id == account_models.Order.LAB_PRODUCT_ID:
                appointment_details.action_rescheduled_patient(new_appointment_details)
                appointment_serializer = LabAppointmentRetrieveSerializer(appointment_details,
                                                                          context={"request": request})
            resp['status'] = 1
            resp['data'] = appointment_serializer.data
            resp['payment_required'] = False
            return resp

    def payment_details(self, request, appointment_details, product_id, order_id):
        payment_required = True
        pgdata = dict()
        user = request.user
        user_profile = user.profiles.filter(is_default_user=True).first()
        pgdata['custId'] = user.id
        pgdata['mobile'] = user.phone_number
        pgdata['email'] = user.email
        if not user.email:
            pgdata['email'] = "dummy_appointment@docprime.com"

        pgdata['productId'] = product_id
        base_url = "https://{}".format(request.get_host())
        pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['appointmentId'] = appointment_details.get('id')
        pgdata['orderId'] = order_id
        if user_profile:
            pgdata['name'] = user_profile.name
        else:
            pgdata['name'] = "DummyName"
        pgdata['txAmount'] = str(appointment_details['payable_amount'])

        secret_key = client_key = ""
        if product_id == Order.DOCTOR_PRODUCT_ID:
            secret_key = settings.PG_SECRET_KEY_P1
            client_key = settings.PG_CLIENT_KEY_P1
        elif product_id == Order.LAB_PRODUCT_ID:
            secret_key = settings.PG_SECRET_KEY_P2
            client_key = settings.PG_CLIENT_KEY_P2

        pgdata['hash'] = PgTransaction.create_pg_hash(pgdata, secret_key, client_key)

        return pgdata, payment_required

    def lab_appointment_list(self, request, params):
        user = request.user
        queryset = LabAppointment.objects.select_related('lab', 'profile', 'user')\
                                        .prefetch_related('lab__lab_image', 'lab__lab_documents', 'reports').filter(user=user)
        if queryset and params.get('profile_id'):
            queryset = queryset.filter(profile=params['profile_id'])
        range = params.get('range')
        if range and range == 'upcoming':
            queryset = queryset.filter(time_slot_start__gte=timezone.now(),
                                       status__in=LabAppointment.ACTIVE_APPOINTMENT_STATUS).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')
        queryset = paginate_queryset(queryset, request, 100)
        serializer = LabAppointmentModelSerializer(queryset, many=True, context={"request": request})
        return serializer

    def doctor_appointment_list(self, request, params):
        user = request.user
        queryset = OpdAppointment.objects.select_related('profile', 'doctor', 'hospital', 'user').prefetch_related('doctor__images').filter(user=user)

        if not queryset:
            return Response([])
        serializer = AppointmentFilterUserSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital = serializer.validated_data.get('hospital_id')
        profile = serializer.validated_data.get('profile_id')

        if profile:
            queryset = queryset.filter(profile=profile)

        if hospital:
            queryset = queryset.filter(hospital=hospital)

        if range == 'previous':
            queryset = queryset.filter(time_slot_start__lte=timezone.now()).order_by('-time_slot_start')
        elif range == 'upcoming':
            queryset = queryset.filter(
                status__in=OpdAppointment.ACTIVE_APPOINTMENT_STATUS,
                time_slot_start__gt=timezone.now()).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(),
                                       status=OpdAppointment.CREATED).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request, 100)
        serializer = OpdAppointmentSerializer(queryset, many=True,context={"request": request})
        return serializer


class AddressViewsSet(viewsets.ModelViewSet):
    serializer_class = serializers.AddressSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        return Address.objects.filter(user=request.user).order_by('address')

    def create(self, request, *args, **kwargs):
        data = request.data

        serializer = serializers.AddressSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        loc_position = utils.get_location(data.get('locality_location_lat'), data.get('locality_location_long'))
        land_position = utils.get_location(data.get('landmark_location_lat'), data.get('landmark_location_long'))
        address = None
        if land_position is None:
            if not Address.objects.filter(user=request.user).filter(**validated_data).filter(
                    locality_location__distance_lte=(loc_position, 0)).exists():
                validated_data["locality_location"] = loc_position
                validated_data["landmark_location"] = land_position
                validated_data['user'] = request.user
                address = Address.objects.create(**validated_data)
        else:
            if not Address.objects.filter(user=request.user).filter(**validated_data).filter(
                    locality_location__distance_lte=(loc_position, 0),
                    landmark_location__distance_lte=(land_position, 0)).exists() and not address:
                validated_data["locality_location"] = loc_position
                validated_data["landmark_location"] = land_position
                validated_data['user'] = request.user
                address = Address.objects.create(**validated_data)
        if not address:
            if land_position is None:
                address = Address.objects.filter(user=request.user).filter(**validated_data).filter(
                    locality_location__distance_lte=(loc_position, 0)).first()
            else:
                address = Address.objects.filter(user=request.user).filter(**validated_data).filter(
                    locality_location__distance_lte=(loc_position, 0),
                    landmark_location__distance_lte=(land_position, 0)).first()
        serializer = serializers.AddressSerializer(address)
        return Response(serializer.data)

    def update(self, request, pk=None):
        data = {key: value for key, value in request.data.items()}
        validated_data = dict()
        if data.get('locality_location_lat') and data.get('locality_location_long'):
            validated_data["locality_location"] = utils.get_location(data.get('locality_location_lat'), data.get('locality_location_long'))
        if data.get('landmark_location_lat') and data.get('landmark_location_long'):
            validated_data["landmark_location"] = utils.get_location(data.get('landmark_location_lat'), data.get('landmark_location_long'))
        data['user'] = request.user.id
        address = self.get_queryset().filter(pk=pk)
        if data.get("is_default"):
            add_default_qs = Address.objects.filter(user=request.user.id, is_default=True)
            if add_default_qs:
                add_default_qs.update(is_default=False)
        serializer = serializers.AddressSerializer(address.first(), data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data.update(serializer.validated_data)
        if address:
            address.update(**validated_data)
            address = address.first()
        else:
            validated_data["user"] = request.user
            address = Address.objects.create(**validated_data)
        resp_serializer = serializers.AddressSerializer(address)
        return Response(resp_serializer.data)

    def destroy(self, request, pk=None):
        address = get_object_or_404(Address, pk=pk)
        is_default_address = address.is_default

        address.delete()

        if is_default_address:
            temp_addr = Address.objects.filter(user=request.user.id).first()
            if temp_addr:
                temp_addr.is_default = True
                temp_addr.save()
        return Response({
            "status": 1
        })


class AppointmentTransactionViewSet(viewsets.GenericViewSet):

    serializer_class = None
    queryset = AppointmentTransaction.objects.none()

    def save(self, request):
        LAB_REDIRECT_URL = request.build_absolute_uri("/") + "lab/appointment/{}"
        OPD_REDIRECT_URL = request.build_absolute_uri("/") + "opd/appointment/{}"
        data = request.data

        coded_response = data.get("response")
        if isinstance(coded_response, list):
            coded_response = coded_response[0]
        coded_response += "=="
        decoded_response = base64.b64decode(coded_response).decode()
        response = json.loads(decoded_response)
        transaction_time = parse(response.get("txDate"))
        AppointmentTransaction.objects.create(appointment=response.get("appointmentId"),
                                              transaction_time=transaction_time,
                                              transaction_status=response.get("txStatus"),
                                              status_code=response.get("statusCode"),
                                              transaction_details=response)
        if response.get("statusCode") == 1 and response.get("productId") == 1:
            opd_appointment = OpdAppointment.objects.filter(pk=response.get("appointmentId")).first()
            if opd_appointment:
                otp = random.randint(1000, 9999)
                opd_appointment.payment_status = OpdAppointment.PAYMENT_ACCEPTED
                opd_appointment.status = OpdAppointment.BOOKED
                opd_appointment.otp = otp
                opd_appointment.save()
        elif response.get("statusCode") == 1 and response.get("productId") == 2:
            lab_appointment = LabAppointment.objects.filter(pk=response.get("appointmentId")).first()
            if lab_appointment:
                otp = random.randint(1000, 9999)
                lab_appointment.payment_status = OpdAppointment.PAYMENT_ACCEPTED
                lab_appointment.status = LabAppointment.BOOKED
                lab_appointment.otp = otp
                lab_appointment.save()
        if response.get("productId") == 2:
            REDIRECT_URL = LAB_REDIRECT_URL.format(response.get("appointmentId"))
        else:
            REDIRECT_URL = OPD_REDIRECT_URL.format(response.get("appointmentId"))
        return HttpResponseRedirect(redirect_to=REDIRECT_URL)


class UserIDViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    @transaction.non_atomic_requests
    def retrieve(self, request):
        data = {
            "user_id": request.user.id
        }
        return Response(data)


class TransactionViewSet(viewsets.GenericViewSet):

    serializer_class = serializers.TransactionSerializer
    queryset = PgTransaction.objects.none()

    @transaction.atomic()
    def save(self, request):
#         LAB_REDIRECT_URL = settings.BASE_URL + "/lab/appointment"
#         OPD_REDIRECT_URL = settings.BASE_URL + "/opd/appointment"
#         INSURANCE_REDIRECT_URL = settings.BASE_URL + "/insurance/complete"
#         INSURANCE_FAILURE_REDIRECT_URL = settings.BASE_URL + "/insurancereviews"
#         LAB_FAILURE_REDIRECT_URL = settings.BASE_URL + "/lab/%s/book?error_code=%s"
#         OPD_FAILURE_REDIRECT_URL = settings.BASE_URL + "/opd/doctor/%s/%s/bookdetails?error_code=%s"
#         ERROR_REDIRECT_URL = settings.BASE_URL + "/error?error_code=%s"
#         REDIRECT_URL = ERROR_REDIRECT_URL % ErrorCodeMapping.IVALID_APPOINTMENT_ORDER

        ERROR_REDIRECT_URL = settings.BASE_URL + "/cart?error_code=1&error_message=%s"
        REDIRECT_URL = ERROR_REDIRECT_URL % "Error processing payment, please try again."
        SUCCESS_REDIRECT_URL = settings.BASE_URL + "/order/summary/%s"
        LAB_REDIRECT_URL = settings.BASE_URL + "/lab/appointment"
        OPD_REDIRECT_URL = settings.BASE_URL + "/opd/appointment"
        PLAN_REDIRECT_URL = settings.BASE_URL + "/prime/success?user_plan="

        try:
            response = None
            coded_response = None
            data = request.data
            # Commenting below for testing
            try:
                coded_response = data.get("response")
                if isinstance(coded_response, list):
                    coded_response = coded_response[0]
                coded_response += "=="
                decoded_response = base64.b64decode(coded_response).decode()
                response = json.loads(decoded_response)
            except Exception as e:
                logger.error("Cannot decode pg data - " + str(e))

            # log pg data
            try:
                PgLogs.objects.create(decoded_response=response, coded_response=coded_response)
            except Exception as e:
                logger.error("Cannot log pg response - " + str(e))


            ## Check if already processes
            try:
                if response and response.get("orderNo"):
                    pg_txn = PgTransaction.objects.filter(order_no__iexact=response.get("orderNo")).first()
                    if pg_txn:
                        send_pg_acknowledge.apply_async((pg_txn.order_id, pg_txn.order_no,), countdown=1)
                        REDIRECT_URL = (SUCCESS_REDIRECT_URL % pg_txn.order_id) + "?payment_success=true"
                        return HttpResponseRedirect(redirect_to=REDIRECT_URL)
            except Exception as e:
               logger.error("Error in sending pg acknowledge - " + str(e))


            # For testing only
            # response = request.data
            success_in_process = False
            processed_data = {}

            try:
                pg_resp_code = int(response.get('statusCode'))
            except:
                logger.error("ValueError : statusCode is not type integer")
                pg_resp_code = None

            order_obj = Order.objects.select_for_update().filter(pk=response.get("orderId")).first()

            # TODO : SHASHANK_SINGH correct amount
            try:
                if order_obj and response and order_obj.amount != Decimal(
                        response.get('txAmount')) and order_obj.is_cod_order:
                    order_obj.amount = Decimal(response.get('txAmount'))
                    order_obj.save()
            except:
                pass

            if pg_resp_code == 1 and order_obj:
                response_data = None
                resp_serializer = serializers.TransactionSerializer(data=response)
                if resp_serializer.is_valid():
                    response_data = self.form_pg_transaction_data(resp_serializer.validated_data, order_obj)
                    # For Testing
                    if PgTransaction.is_valid_hash(response, product_id=order_obj.product_id):
                        pg_tx_queryset = None
                    # if True:
                        try:
                            with transaction.atomic():
                                pg_tx_queryset = PgTransaction.objects.create(**response_data)
                        except Exception as e:
                            logger.error("Error in saving PG Transaction Data - " + str(e))

                        try:
                            with transaction.atomic():
                                processed_data = order_obj.process_pg_order()
                                success_in_process = True
                        except Exception as e:
                            logger.error("Error in processing order - " + str(e))
                else:
                    logger.error("Invalid pg data - " + json.dumps(resp_serializer.errors))
            elif order_obj:
                try:
                    if response and response.get("orderNo") and response.get("orderId"):
                        send_pg_acknowledge.apply_async((response.get("orderId"), response.get("orderNo"),), countdown=1)
                except Exception as e:
                    logger.error("Error in sending pg acknowledge - " + str(e))

                try:
                    has_changed = order_obj.change_payment_status(Order.PAYMENT_FAILURE)
                    if has_changed:
                        self.send_failure_ops_email(order_obj)
                except Exception as e:
                    logger.error("Error sending payment failure email - " + str(e))

            if success_in_process:
                if processed_data.get("type") == "all":
                    REDIRECT_URL = (SUCCESS_REDIRECT_URL % order_obj.id) + "?payment_success=true"
                elif processed_data.get("type") == "doctor":
                    REDIRECT_URL = OPD_REDIRECT_URL + "/" + str(processed_data.get("id", "")) + "?payment_success=true"
                elif processed_data.get("type") == "lab":
                    REDIRECT_URL = LAB_REDIRECT_URL + "/" + str(processed_data.get("id","")) + "?payment_success=true"
                elif processed_data.get("type") == "insurance":
                    REDIRECT_URL = settings.BASE_URL + "/insurance/complete?payment_success=true&id=" + str(processed_data.get("id", ""))
                elif processed_data.get("type") == "plan":
                    REDIRECT_URL = PLAN_REDIRECT_URL + str(processed_data.get("id", "")) + "&payment_success=true"
        except Exception as e:
            logger.error("Error - " + str(e))

        try:
            if response and response.get("orderNo"):
                pg_txn = PgTransaction.objects.filter(order_no__iexact=response.get("orderNo")).first()
                if pg_txn:
                    send_pg_acknowledge.apply_async((pg_txn.order_id, pg_txn.order_no,), countdown=1)
        except Exception as e:
            logger.error("Error in sending pg acknowledge - " + str(e))


        # return Response({"url": REDIRECT_URL})
        return HttpResponseRedirect(redirect_to=REDIRECT_URL)

    def form_pg_transaction_data(self, response, order_obj):
        data = dict()
        user_id = order_obj.get_user_id()
        user = get_object_or_404(User, pk=user_id)
        data['user'] = user
        data['product_id'] = order_obj.product_id
        data['order_no'] = response.get('orderNo')
        data['order_id'] = order_obj.id
        data['reference_id'] = order_obj.reference_id
        data['type'] = PgTransaction.CREDIT
        data['amount'] = order_obj.amount

        data['payment_mode'] = response.get('paymentMode')
        data['response_code'] = response.get('responseCode')
        data['bank_id'] = response.get('bankTxId')
        transaction_time = parse(response.get("txDate"))
        data['transaction_date'] = transaction_time
        data['bank_name'] = response.get('bankName')
        data['currency'] = response.get('currency')
        data['status_code'] = response.get('statusCode')
        data['pg_name'] = response.get('pgGatewayName')
        data['status_type'] = response.get('txStatus')
        data['transaction_id'] = response.get('pgTxId')
        data['pb_gateway_name'] = response.get('pbGatewayName')

        return data

    @transaction.atomic
    def block_schedule_transaction(self, data):
        consumer_account = ConsumerAccount.objects.get_or_create(user=data["user"])
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=data["user"])

        appointment_amount, obj = self.get_appointment_amount(data)

        if consumer_account.balance < appointment_amount:
            return appointment_amount - consumer_account.balance
        else:
            obj.confirm_appointment(consumer_account, data, appointment_amount)

        return 0

    def get_appointment_amount(self, data):
        amount = 0
        if data["product"] == 2:
            obj = get_object_or_404(LabAppointment, pk=data['order'])
            amount = obj.price
        elif data["product"] == 1:
            obj = get_object_or_404(OpdAppointment, pk=data['order'])
            amount = obj.fees

        return amount, obj

    def send_failure_ops_email(self, order_obj):
        booking_type = "Insurance " if order_obj.product_id == Order.INSURANCE_PRODUCT_ID else ""
        html_body = "{}Payment failed for user with " \
                    "user id - {} and phone number - {}" \
                    ", order id - {}.".format(booking_type, order_obj.user.id, order_obj.user.phone_number, order_obj.id)

        # Push the order failure case to matrix.

        push_order_to_matrix.apply_async(({'order_id': order_obj.id},), countdown=5)

        for email in settings.ORDER_FAILURE_EMAIL_ID:
            EmailNotification.publish_ops_email(email, html_body, 'Payment failure for order')

class UserTransactionViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.UserTransactionModelSerializer
    queryset = ConsumerTransaction.objects.all()
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user
        tx_queryset = ConsumerTransaction.objects.filter(user=user).order_by('-id')
        consumer_account = ConsumerAccount.objects.filter(user=user).first()

        tx_serializable_data = list()
        consumer_balance = 0
        consumer_cashback = 0
        if tx_queryset.exists():
            tx_queryset = paginate_queryset(tx_queryset, request)
            tx_serializer = serializers.UserTransactionModelSerializer(tx_queryset, many=True)
            tx_serializable_data = tx_serializer.data

        if consumer_account:
            consumer_balance = consumer_account.balance
            consumer_cashback = consumer_account.cashback

        resp = dict()
        resp["user_transactions"] = tx_serializable_data
        resp["user_wallet_balance"] = consumer_balance
        resp["consumer_cashback"] = consumer_cashback
        return Response(data=resp)


class ConsumerAccountViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = ConsumerAccount.objects.all()
    serializer_class = serializers.ConsumerAccountModelSerializer


class OrderHistoryViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsConsumer,)

    @transaction.non_atomic_requests
    def list(self, request):
        # opd_action_data = list()
        # lab_action_data = list()
        available_lab_test = list()
        order_action_list = list()
        doc_hosp_query = Q()

        for order in Order.objects.filter(action_data__user=request.user.id, is_viewable=True,
                                          payment_status=Order.PAYMENT_PENDING).order_by('-created_at')[:5]:
            action_data = order.action_data
            action_data["product_id"] = order.product_id
            if order.product_id == Order.DOCTOR_PRODUCT_ID:
                # opd_action_data.append(action_data)
                doc_hosp_query = doc_hosp_query | (Q(doctor=action_data.get("doctor"), hospital=action_data.get("hospital")))
            elif order.product_id == Order.LAB_PRODUCT_ID:
                # lab_action_data.append(action_data)
                available_lab_test.extend(action_data.get("lab_test"))
            order_action_list.append(action_data)

        doc_hosp_details = defaultdict(dict)
        if doc_hosp_query:
            doc_hosp_obj = DoctorClinic.objects.prefetch_related('doctor', 'hospital', 'doctor__images').filter(doc_hosp_query)
            for data in doc_hosp_obj:
                doc_hosp_details[data.hospital.id][data.doctor.id] = {
                    "doctor_name": data.doctor.name,
                    "hospital_name": data.hospital.name,
                    "doctor_thumbnail": request.build_absolute_uri(data.doctor.images.first().name.url) if data.doctor.images.all().first() else None
                }

        lab_name = dict()
        lab_test_map = dict()
        if available_lab_test:
            test_ids = AvailableLabTest.objects.prefetch_related('lab_pricing_group__labs', 'test').filter(pk__in=available_lab_test)
            lab_test_map = dict()
            for data in test_ids:
                for lab_data in data.lab_pricing_group.labs.all():
                    lab_name[lab_data.id] = {
                        'name': lab_data.name,
                        "lab_thumbnail": request.build_absolute_uri(lab_data.get_thumbnail()) if lab_data.get_thumbnail() else None
                    }
                lab_test_map[data.id] = {"id": data.test.id,
                                         "name": data.test.name
                                         }
        orders = []

        for action_data in order_action_list:
            if action_data["product_id"] == Order.DOCTOR_PRODUCT_ID:
                if action_data["hospital"] not in doc_hosp_details or action_data["doctor"] not in doc_hosp_details[action_data["hospital"]]:
                    continue
                data = {
                    "doctor": action_data.get("doctor"),
                    "doctor_name": doc_hosp_details[action_data["hospital"]][action_data["doctor"]]["doctor_name"],
                    "hospital": action_data.get("hospital"),
                    "hospital_name": doc_hosp_details[action_data["hospital"]][action_data["doctor"]]["hospital_name"],
                    "doctor_thumbnail": doc_hosp_details[action_data["hospital"]][action_data["doctor"]][
                        "doctor_thumbnail"],
                    "profile_detail": action_data.get("profile_detail"),
                    "profile": action_data.get("profile"),
                    "user": action_data.get("user"),
                    "time_slot_start": action_data.get("time_slot_start"),
                    "start_date": action_data.get("time_slot_start"),
                    "start_time": 0.0,  # not required here we are only validating fees
                    "payment_type": action_data.get("payment_type"),
                    "type": "opd"
                }
                data.pop("time_slot_start")
                data.pop("start_date")
                data.pop("start_time")
                orders.append(data)
            elif action_data["product_id"] == Order.LAB_PRODUCT_ID:
                if action_data['lab'] not in lab_name:
                    continue
                data = {
                    "lab": action_data.get("lab"),
                    "lab_name": lab_name[action_data['lab']]["name"],
                    "test_ids": [lab_test_map[x]["id"] for x in action_data.get("lab_test")],
                    "lab_thumbnail": lab_name[action_data['lab']]["lab_thumbnail"],
                    "profile": action_data.get("profile"),
                    "time_slot_start": action_data.get("time_slot_start"),
                    "start_date": action_data.get("time_slot_start"),
                    "start_time": 0.0,  # not required here we are only validating fees
                    "payment_type": action_data.get("payment_type"),
                    "type": "lab"
                }
                data.pop("time_slot_start")
                data.pop("start_date")
                data.pop("start_time")
                data["test_ids"] = [lab_test_map[x] for x in action_data.get("lab_test")]
                orders.append(data)
        return Response(orders)


class HospitalDoctorAppointmentPermissionViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsDoctor,)

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user
        manageable_hosp_list = GenericAdmin.objects.filter(Q(is_disabled=False, user=user), (Q(permission_type=GenericAdmin.APPOINTMENT)
                                                                                              |
                                                                                            Q(super_user_permission=True)))\
                                                    .values_list('hospital', flat=True)
        doc_hosp_queryset = (DoctorClinic.objects
                             .select_related('doctor', 'hospital')
                             .prefetch_related('doctor__manageable_doctors', 'hospital__manageable_hospitals')
                             .filter(Q(Q(doctor__is_live=True) | Q(doctor__source_type=Doctor.PROVIDER)),
                                     Q(Q(hospital__is_live=True) | Q(hospital__source_type=Hospital.PROVIDER)))
                             .annotate(doctor_gender=F('doctor__gender'),
                                       hospital_building=F('hospital__building'),
                                       hospital_name=F('hospital__name'),
                                       doctor_name=F('doctor__name'),
                                       doctor_source_type=F('doctor__source_type'),
                                       doctor_is_live=F('doctor__is_live'),
                                       license=F('doctor__license'),
                                       is_license_verified=F('doctor__is_license_verified'),
                                       hospital_source_type=F('hospital__source_type'),
                                       hospital_is_live=F('hospital__is_live'),
                                       online_consultation_fees=F('doctor__online_consultation_fees')
                                       )
                             .filter(hospital_id__in=list(manageable_hosp_list))
                             .values('hospital', 'doctor', 'hospital_name', 'doctor_name', 'doctor_gender',
                                     'doctor_source_type', 'doctor_is_live', 'license',
                                     'is_license_verified', 'hospital_source_type', 'hospital_is_live',
                                     'online_consultation_fees').distinct('hospital', 'doctor')
                             )

        return Response(doc_hosp_queryset)


class UserLabViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsDoctor,)

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user
        user_lab_queryset = Lab.objects.filter(
                                              Q(Q(manageable_lab_admins__user=user,
                                                  manageable_lab_admins__is_disabled=False,
                                                  manageable_lab_admins__write_permission=True) |
                                                Q(network__manageable_lab_network_admins__user=user,
                                                  network__manageable_lab_network_admins__is_disabled=False,
                                                  network__manageable_lab_network_admins__write_permission=True
                                                 )
                                                )
                                                 |
                                                (
                                                 Q(manageable_lab_admins__user=user,
                                                   manageable_lab_admins__is_disabled=False,
                                                   manageable_lab_admins__super_user_permission=True)
                                                 ),
                                               Q(is_live=True)
                                               ).values('id', 'name')
        return Response(user_lab_queryset)


class HospitalDoctorBillingPermissionViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsDoctor,)

    @transaction.non_atomic_requests
    def list(self, request):
        user = request.user

        queryset = GenericAdmin.objects.select_related('doctor', 'hospital')\
                                       .filter(Q
                                                  (Q(user=user,
                                                     is_disabled=False,
                                                     permission_type__in=[GenericAdmin.BILLINNG, GenericAdmin.ALL],
                                                     write_permission=True
                                                     ),
                                                   (
                                                     Q(Q(entity_type=GenericAdminEntity.DOCTOR,
                                                       doctor__doctor_clinics__hospital__is_billing_enabled=False),
                                                       (Q(hospital__isnull=False, doctor__doctor_clinics__hospital=F('hospital'))
                                                        |
                                                        Q(hospital__isnull=True)
                                                        )
                                                      )
                                                     |
                                                     Q(
                                                         Q(entity_type=GenericAdminEntity.HOSPITAL),
                                                         (Q(doctor__isnull=False,
                                                            hospital__hospital_doctors__doctor=F('doctor'))
                                                          |
                                                          Q(doctor__isnull=True)
                                                          )
                                                      )
                                                   )
                                                )
                                                |
                                                Q(
                                                    is_disabled=False,
                                                    super_user_permission=True,
                                                    user=user
                                                )
                                               )\
                                        .annotate(doctor_ids=F('hospital__hospital_doctors__doctor'),
                                                  doctor_names=F('hospital__hospital_doctors__doctor__name'),
                                                  hospital_name=F('hospital__name'),
                                                  doctor_name=F('doctor__name'),
                                                  hospital_ids=F('doctor__doctor_clinics__hospital'),
                                                  hospital_names=F('doctor__doctor_clinics__hospital__name')) \
                                        .values('doctor_ids', 'doctor_name', 'doctor_names', 'doctor_id',
                                                'hospital_ids', 'hospital_name', 'hospital_names', 'hospital_id')

        # doc_hosp_queryset = (
        #     DoctorClinic.objects.filter(
        #         Q(
        #           doctor__manageable_doctors__user=user,
        #           doctor__manageable_doctors__is_disabled=False,
        #           doctor__manageable_doctors__permission_type=GenericAdmin.BILLINNG,
        #           doctor__manageable_doctors__read_permission=True) |
        #         Q(
        #           hospital__manageable_hospitals__user=user,
        #           hospital__manageable_hospitals__is_disabled=False,
        #           hospital__manageable_hospitals__permission_type=GenericAdmin.BILLINNG,
        #           hospital__manageable_hospitals__read_permission=True))
        #         .values('hospital', 'doctor', 'hospital__manageable_hospitals__hospital', 'doctor__manageable_doctors__doctor')
        #         .annotate(doc_admin_doc=F('doctor__manageable_doctors__doctor'),
        #                   doc_admin_hosp=F('doctor__manageable_doctors__hospital'),
        #                   hosp_admin_doc=F('hospital__manageable_hospitals__doctor'),
        #                   hosp_admin_hosp=F('hospital__manageable_hospitals__hospital'),
        #                   hosp_name=F('hospital__name'), doc_name=F('doctor__name'))
        #     )

        resp_data = defaultdict(dict)
        for data in queryset:
            if data['hospital_ids']:
                temp_tuple = (data['doctor_id'], data['doctor_name'])
                if temp_tuple not in resp_data:
                    temp_dict = {
                        "admin_id": data["doctor_id"],
                        "level": Outstanding.DOCTOR_LEVEL,
                        "doctor_name": data["doctor_name"],
                        "hospital_list": list()
                    }
                    temp_dict["hospital_list"].append({
                        "id": data["hospital_ids"],
                        "name": data["hospital_names"]
                    })
                    resp_data[temp_tuple] = temp_dict
                else:
                    temp_name = {
                        "id": data["hospital_ids"],
                        "name": data["hospital_names"]
                    }
                    if temp_name not in resp_data[temp_tuple]["hospital_list"]:
                        resp_data[temp_tuple]["hospital_list"].append(temp_name)

            # if data['hosp_admin_doc'] is None and data['hosp_admin_hosp'] is not None:
            else:
                temp_tuple = (data['hospital_id'], data['hospital_name'])
                if temp_tuple not in resp_data:
                    temp_dict = {
                        "admin_id": data["hospital_id"],
                        "level": Outstanding.HOSPITAL_LEVEL,
                        "hospital_name": data["hospital_name"],
                        "doctor_list": list()
                    }
                    temp_dict["doctor_list"].append({
                        "id": data["doctor_ids"],
                        "name": data["doctor_names"]
                    })
                    resp_data[temp_tuple] = temp_dict
                else:
                    temp_name = {
                        "id": data["doctor_ids"],
                        "name": data["doctor_names"]
                    }
                    if temp_name not in resp_data[temp_tuple]["doctor_list"]:
                        resp_data[temp_tuple]["doctor_list"].append(temp_name)

        resp_data = [v for k,v in resp_data.items()]

        return Response(resp_data)

    def appointment_doc_hos_list(self, request):
        data = request.query_params
        admin_id = int(data.get("admin_id"))
        level = int(data.get("level"))
        user = request.user
        resp_data = list()
        if level == Outstanding.DOCTOR_LEVEL:
            permission = GenericAdmin.objects.filter(user=user, doctor=admin_id, permission_type=GenericAdmin.BILLINNG,
                                                     read_permission=True, is_disabled=False).exist()
            if permission:
                resp_data = DoctorClinic.objects.filter(doctor=admin_id).values('hospital', 'hospital__name')
        elif level == Outstanding.HOSPITAL_LEVEL:
            permission = GenericAdmin.objects.filter(user=user, hospital=admin_id, permission_type=GenericAdmin.BILLINNG,
                                                     read_permission=True, is_disabled=False).exist()
            if permission:
                resp_data = DoctorClinic.objects.filter(hospital=admin_id).values('doctor', 'doctor__name')
        elif level == Outstanding.HOSPITAL_NETWORK_LEVEL:
            permission = GenericAdmin.objects.filter(user=user, hospital_network=admin_id, permission_type=GenericAdmin.BILLINNG,
                                                     read_permission=True, is_disabled=False).exist()
            if permission:
                resp_data = DoctorClinic.objects.get(hospital__network=admin_id).values('hospital', 'doctor',
                                                                                          'hospital_name', 'doctor_name')
        elif level == Outstanding.LAB_LEVEL:
            pass
        elif level == Outstanding.LAB_NETWORK_LEVEL:
            pass

        return Response(resp_data)


class OrderViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk):
        user = request.user
        params = request.query_params

        from_app = params.get("from_app", False)
        app_version = params.get("app_version", "1.0")

        order_obj = Order.objects.filter(pk=pk).first()

        if not (order_obj and order_obj.validate_user(user) and (
                order_obj.payment_status == Order.PAYMENT_PENDING or order_obj.is_cod_order)):
            return Response({"status": 0}, status.HTTP_404_NOT_FOUND)

        resp = dict()
        resp["status"] = 0

        if not order_obj:
            return Response(resp)

        # remove all cart_items => Workaround TODO: remove later
        if from_app and app_version and app_version <= "1.0":
            from ondoc.cart.models import Cart
            Cart.remove_all(user)

        resp["status"] = 1
        resp['data'], resp["payment_required"] = utils.payment_details(request, order_obj)
        resp['payment_options'], resp['invalid_payment_options'], resp['invalid_reason'] = PaymentOptions.filtered_payment_option(order_obj)
        return Response(resp)


class ConsumerAccountRefundViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsConsumer, )

    @transaction.atomic
    def refund(self, request):
        user = request.user
        consumer_account = ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)
        if consumer_account.balance > 0:
            ctx_obj = consumer_account.debit_refund()
            ConsumerRefund.initiate_refund(user, ctx_obj)
        resp = dict()
        resp["status"] = 1
        return Response(resp)


class RefreshJSONWebToken(GenericViewSet):

    def refresh(self, request):
        data = {}
        serializer = serializers.RefreshJSONWebTokenSerializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        if not serializer.is_valid():
            return Response({"error": "Cannot Refresh Token"}, status=status.HTTP_401_UNAUTHORIZED)
        data['token'] = serializer.validated_data['token']
        data['payload'] = serializer.validated_data['payload']
        return Response(data)


class OnlineLeadViewSet(GenericViewSet):
    serializer_class = serializers.OnlineLeadSerializer

    def create(self, request):
        resp = {}
        data = request.data

        if request.user_agent.is_mobile or request.user_agent.is_tablet:
            source = request.user_agent.os.family
        elif request.user_agent.is_pc:
            source = "WEB %s" % (data.get('source', ''))
        else:
            source = "Signup"

        data['source'] = source
        if not data.get('city_name'):
            data['city_name'] = 0
        serializer = serializers.OnlineLeadSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data.id:
            resp['status'] = 'success'
            resp['id'] = data.id
        return Response(resp)


class CareerViewSet(GenericViewSet):
    serializer_class = serializers.CareerSerializer

    def upload(self, request):
        resp = {}
        serializer = serializers.CareerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data.id:
            resp['status'] = 'success'
            resp['id'] = data.id
        return Response(resp)


class SendBookingUrlViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, )

    def send_booking_url(self, request):
        type = request.data.get('type')
        purchase_type = request.data.get('purchase_type', None)

        # agent_token = AgentToken.objects.create_token(user=request.user)
        user_token = JWTAuthentication.generate_token(request.user)
        token = user_token['token'].decode("utf-8") if 'token' in user_token else None
        user_profile = None

        if request.user.is_authenticated:
            user_profile = request.user.get_default_profile()
        if not user_profile:
            return Response({"status": 1})
        if purchase_type == 'insurance':
            SmsNotification.send_insurance_booking_url(token=token, phone_number=str(user_profile.phone_number))
            EmailNotification.send_insurance_booking_url(token=token, email=user_profile.email)
        elif purchase_type == 'endorsement':
            SmsNotification.send_endorsement_request_url(token=token, phone_number=str(user_profile.phone_number))
            EmailNotification.send_endorsement_request_url(token=token, email=user_profile.email)
        else:
            booking_url = SmsNotification.send_booking_url(token=token, phone_number=str(user_profile.phone_number))
            EmailNotification.send_booking_url(token=token, email=user_profile.email)

        return Response({"status": 1})


class OrderDetailViewSet(GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, )
    serializer_class = serializers.OrderDetailDoctorSerializer

    @transaction.non_atomic_requests
    def details(self, request, order_id):
        if not order_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        queryset = Order.objects.filter(id=order_id).first()
        if not queryset.validate_user(request.user):
            return Response({"status": 0}, status.HTTP_404_NOT_FOUND)

        if not queryset:
            return Response(status=status.HTTP_404_NOT_FOUND)
        resp = dict()

        if queryset.product_id == Order.DOCTOR_PRODUCT_ID:
            serializer = serializers.OrderDetailDoctorSerializer(queryset)
            resp = serializer.data
            procedure_ids = []
            if queryset.action_data:
                action_data = queryset.action_data
                if action_data.get('extra_details'):
                    extra_details = action_data.get('extra_details')
                    for data in extra_details:
                        if data.get('procedure_id'):
                            procedure_ids.append(int(data.get('procedure_id')))
            resp['procedure_ids'] = procedure_ids

        elif queryset.product_id == Order.LAB_PRODUCT_ID:
            serializer = serializers.OrderDetailLabSerializer(queryset)
            resp = serializer.data

        return Response(resp)

    @transaction.non_atomic_requests
    def summary(self, request, order_id):
        from ondoc.api.v1.cart import serializers as cart_serializers
        from ondoc.api.v1.utils import convert_datetime_str_to_iso_str

        if not order_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        order_data = Order.objects.filter(id=order_id).first()

        if not order_data:
            return Response({"message": "Invalid order ID"}, status.HTTP_404_NOT_FOUND)

        if not order_data.validate_user(request.user):
            return Response({"status": 0}, status.HTTP_404_NOT_FOUND)

        if not order_data:
            return Response(status=status.HTTP_404_NOT_FOUND)

        processed_order_data = []
        valid_for_cod_to_prepaid = order_data.is_cod_order
        child_orders = order_data.orders.all()

        class OrderCartItemMapper():
            def __init__(self, order_obj):
                self.data = order_obj.action_data
                self.order = order_obj

        for order in child_orders:
            item = OrderCartItemMapper(order)
            temp_time_slot_start = convert_datetime_str_to_iso_str(order.action_data["time_slot_start"])
            curr = {
                "mrp": order.action_data["mrp"] if "mrp" in order.action_data else order.action_data["agreed_price"],
                "deal_price": order.action_data["deal_price"],
                "effective_price": order.action_data["effective_price"],
                "data": cart_serializers.CartItemSerializer(item, context={"validated_data": None}).data,
                "booking_id": order.reference_id,
                "time_slot_start": temp_time_slot_start,
                "payment_type": order.action_data["payment_type"],

            }
            processed_order_data.append(curr)

        return Response({"data": processed_order_data, "valid_for_cod_to_prepaid": valid_for_cod_to_prepaid})


class UserTokenViewSet(GenericViewSet):

    @transaction.non_atomic_requests
    def details(self, request):
        token = request.query_params.get("token")
        if not token:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        agent_token = AgentToken.objects.filter(token=token, is_consumed=False, expiry_time__gte=timezone.now()).first()
        if agent_token:
            token_object = JWTAuthentication.generate_token(agent_token.user)
            # agent_token.is_consumed = True
            agent_token.save()
            return Response({"status": 1, "token": token_object['token'], 'order_id': agent_token.order_id})
        else:
            return Response({"status": 0}, status=status.HTTP_400_BAD_REQUEST)


class ContactUsViewSet(GenericViewSet):

    def create(self, request):
        serializer = serializers.ContactUsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        ContactUs.objects.create(**validated_data)
        return Response({'message': 'success'})


class DoctorNumberAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Doctor.objects.all()
        # dn = DoctorNumber.objects.values_list('doctor', flat=True)
        #
        # qs = Doctor.objects.exclude(id__in=dn)
        if self.q:
            qs = qs.filter(name__icontains=self.q).order_by('name')
        return qs

class UserLeadViewSet(GenericViewSet):

    def create(self,request):
        resp = {}
        serializer = serializers.UserLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if validated_data:
            resp['name'] = validated_data.get('name')
            resp['message'] = validated_data.get('message')
            resp['phone_number'] = validated_data.get('phone_number')
            resp['gender'] = validated_data.get('gender')

            ul_obj = UserLead.objects.create(**resp)
            resp['status'] = "success"


        return Response(resp)


class UserRatingViewSet(GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsConsumer )

    def get_queryset(self):
        return None

    def list_ratings(self,request):
        resp = []
        user = request.user
        queryset = rate_models.RatingsReview.objects.select_related('content_type')\
                                                    .prefetch_related('content_object', 'compliment')\
                                                    .filter(user=user).order_by('-updated_at')
        if len(queryset):
            for obj in queryset:
                compliments_string = ''
                address = ''
                c_list = []
                cid_list = []
                if obj.content_type == ContentType.objects.get_for_model(Doctor):
                    name = obj.content_object.get_display_name()
                    if obj.appointment_id:
                        appointment = OpdAppointment.objects.select_related('hospital').filter(id=obj.appointment_id).first()
                        if appointment:
                            address = appointment.hospital.get_hos_address()
                elif obj.content_type == ContentType.objects.get_for_model(Lab):
                    name = obj.content_object.name
                    address = obj.content_object.get_lab_address()
                else:
                    name = obj.content_object.name
                    address = obj.content_object.get_hos_address()
                for cm in obj.compliment.all():
                    c_list.append(cm.message)
                    cid_list.append(cm.id)
                if c_list:
                    compliments_string = (', ').join(c_list)
                rating_obj = {}
                rating_obj['id'] = obj.id
                rating_obj['ratings'] = obj.ratings
                rating_obj['address'] = address
                rating_obj['review'] = obj.review
                rating_obj['entity_name'] = name
                rating_obj['entity_id'] = obj.object_id
                rating_obj['date'] = obj.updated_at.strftime('%b %d, %Y')
                rating_obj['compliments'] = compliments_string
                rating_obj['compliments_list'] = cid_list
                rating_obj['appointment_id'] = obj.appointment_id
                rating_obj['appointment_type'] = obj.appointment_type
                rating_obj['icon'] = request.build_absolute_uri(obj.content_object.get_thumbnail())
                resp.append(rating_obj)
        return Response(resp)


class AppointmentViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def upcoming_appointments(self, request):
        all_appointments = []
        try:
            user_id = request.user.id
            all_appointments = get_all_upcoming_appointments(user_id)
        except Exception as e:
            logger.error(str(e))
        return Response(all_appointments)

    def get_queryset(self):
        return OpdAppointment.objects.none()


class DoctorScanViewSet(GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, IsNotAgent)

    # @transaction.atomic
    def doctor_qr_scan(self, request, pk):
        opdapp_obj = OpdAppointment.objects.filter(pk=pk).first()
        request_url = request.data.get('url')
        type = request.data.get('type')
        user = request.user

        if not opdapp_obj:
            return Response('Opd Appointment does not exist', status.HTTP_400_BAD_REQUEST)

        if not user == opdapp_obj.user:    
            return Response('Unauthorized User', status.HTTP_401_UNAUTHORIZED)

        if not request_url:
            return Response('URL not given', status.HTTP_400_BAD_REQUEST)

        if not type == 'doctor':
            return Response('Invalid type', status.HTTP_400_BAD_REQUEST)

        if not len(opdapp_obj.doctor.qr_code.all()):
            return Response('QRCode not enabled for this doctor', status.HTTP_400_BAD_REQUEST)


        appt_status = opdapp_obj.status
        url = opdapp_obj.doctor.qr_code.first().data
        complete_with_qr_scanner = True

        if not url:
            return Response('URL not found', status.HTTP_400_BAD_REQUEST)

        url = url.get('url', None)
        if not request_url == url:
            return Response('Invalid url', status.HTTP_400_BAD_REQUEST)

        if not appt_status == OpdAppointment.ACCEPTED or not complete_with_qr_scanner == True:
            return Response('Bad request', status.HTTP_400_BAD_REQUEST)


        opdapp_obj.action_completed()
        resp = AppointmentRetrieveSerializer(opdapp_obj, context={"request": request})
        return Response(resp.data)


class TokenFromUrlKey(viewsets.GenericViewSet):

    def get_token(self, request):
        from ondoc.authentication.models import ClickLoginToken
        serializer = serializers.TokenFromUrlKeySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data.get("auth_token")
        key = data.get("key")
        if token:
            return Response({'status': 1, 'token': token})
        elif key:
            obj = ClickLoginToken.objects.filter(url_key=key).first()
            if obj:
                obj.is_consumed = True
                obj.save()
                LastLoginTimestamp.objects.create(user=obj.user, source="d_sms")
                return Response({'status': 1, 'token': obj.token})
            else:
                return Response({'status': 0, 'token': None, 'message': 'key not found'}, status=status.HTTP_404_NOT_FOUND)
