import base64
import json
import random
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.http import HttpResponseRedirect
from django.db.models import Q
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework import mixins, viewsets, status
import math
import datetime
import time
import pytz
from ondoc.api.v1.auth import serializers
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from ondoc.sms.api import send_otp

from ondoc.doctor.models import DoctorMobile, Doctor, HospitalNetwork, Hospital, DoctorHospital
from ondoc.authentication.models import (OtpVerifications, NotificationEndpoint, Notification, UserProfile,
                                         UserPermission, Address, AppointmentTransaction)
from ondoc.account.models import PgTransaction, ConsumerAccount, ConsumerTransaction
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ondoc.api.pagination import paginate_queryset

from ondoc.doctor.models import OpdAppointment
from ondoc.api.v1.doctor.serializers import (OpdAppointmentSerializer, AppointmentFilterSerializer,
                                             UpdateStatusSerializer, CreateAppointmentSerializer,AppointmentRetrieveSerializer
                                             )
from ondoc.diagnostic.models import (LabAppointment)
from ondoc.api.v1.diagnostic.serializers import (LabAppointmentModelSerializer, LabAppointmentRetrieveSerializer)


User = get_user_model()


def expire_otp(phone_number):
    OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)

class LoginOTP(GenericViewSet):

    serializer_class = serializers.OTPSerializer

    @transaction.atomic
    def generate(self, request, format=None):

        response = {'exists':0}
        serializer = serializers.OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        phone_number = data['phone_number']
        send_otp("otp sent {}", phone_number)

        req_type = request.query_params.get('type')

        if req_type == 'doctor':
            if DoctorMobile.objects.filter(number=phone_number, is_primary=True).exists():
                response['exists']=1
        else:
            if User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).exists():
                response['exists']=1

        return Response(response)

    def verify(self, request, format=None):

        serializer = serializers.OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({"message" : "OTP Generated Sucessfuly."})


class UserViewset(GenericViewSet):
    serializer_class = serializers.UserSerializer
    @transaction.atomic
    def login(self, request, format=None):
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

        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0]),
            "user_exists": user_exists,
        }
        return Response(response)        

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
        doctor_list = [user.doctor.id]

        if not user:
            doctor = DoctorMobile.objects.get(number=phone_number, is_primary=True).doctor
            user = User.objects.create(phone_number=data['phone_number'], is_phone_number_verified=True, user_type=User.DOCTOR)
            doctor_list = [user.doctor.id]
            doctor.user = user
            doctor.save()

        token = Token.objects.get_or_create(user=user)
        pem_obj = DoctorPermission(doctor_list, request)
        pem_obj.create_permission()

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0])
        }
        return Response(response)


class NotificationEndpointViewSet(GenericViewSet):
    serializer_class = serializers.NotificationEndpointSerializer

    @transaction.atomic
    def save(self, request):
        serializer = serializers.NotificationEndpointSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        NotificationEndpoint.objects.filter(token=validated_data.get('token')).delete()
        notification_endpoint_data = {
            "user": request.user.id,
            "device_id": validated_data.get("device_id"),
            "token": validated_data.get("token")
        }
        notification_endpoint_serializer = serializers.NotificationEndpointSerializer(data=notification_endpoint_data)
        notification_endpoint_serializer.is_valid(raise_exception=True)
        notification_endpoint_serializer.save()
        return Response(notification_endpoint_serializer.data)

    def delete(self, request):
        serializer = serializers.NotificationEndpointDeleteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        notification_endpoint = NotificationEndpoint.objects.filter(token=validated_data.get('token')).first()
        notification_endpoint.delete()
        return Response(data={"status": 1, "message": "deleted"})


class NotificationViewSet(GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        queryset = paginate_queryset(queryset=Notification.objects.filter(user=request.user),
                                     request=request)
        serializer = serializers.NotificationSerializer(queryset, many=True)
        return Response(serializer.data)


class UserProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                         mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         GenericViewSet):
    serializer_class = serializers.UserProfileSerializer
    queryset = UserProfile.objects.all()
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        queryset = UserProfile.objects.filter(user=request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = {}
        data.update(request.data)
        data['user'] = request.user.id
        if data.get('age'):
            try:
                age = int(data.get("age"))
                data['dob'] = datetime.datetime.now() - relativedelta(years=age)
                data['dob'] = data['dob'].date()
            except:
                return Response({"error": "Invalid Age"}, status=status.HTTP_400_BAD_REQUEST)
        if not data.get('phone_number'):
            data['phone_number'] = request.user.phone_number
        serializer = serializers.UserProfileSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        if not queryset.exists():
            serializer.validated_data['is_default_user'] = True
        serializer.save()
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        kwargs.update({
            "partial": True
        })
        return super().update(request, *args, **kwargs)


class UserPermissionViewSet(mixins.CreateModelMixin,
                            mixins.ListModelMixin,
                            GenericViewSet):
    queryset = DoctorHospital.objects.all()
    # serializer_class = serializers.UserPermissionSerializer

    def list(self, request, *args, **kwargs):
        params = request.query_params
        doctor_list = params['doctor_id'].split(",")
        dp_obj = DoctorPermission(doctor_list, request)
        permission_data = dp_obj.create_permission()
        return Response(permission_data)


class DoctorPermission(object):

    def __init__(self, doctor_list, request):
        self.doctor_list = doctor_list
        self.request = request

    def create_permission(self):
        hospital_queryset = (DoctorHospital.objects.
                             prefetch_related('hospital__hospital_admins', 'doctor', 'doctor__user').
                             filter(doctor__in=self.doctor_list))
        permission_data = self.form_data(hospital_queryset)
        serializer = serializers.UserPermissionSerializer(data=permission_data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return serializer.data

    @staticmethod
    def form_data(hospital_queryset):
        permission_data = list()
        for data in hospital_queryset:
            permission_dict = dict()
            permission_dict['user'] = data.doctor.user.id
            permission_dict['doctor'] = data.doctor.id
            permission_dict['hospital_network'] = None
            permission_dict['hospital'] = data.hospital.id
            permission_dict['permission_type'] = UserPermission.APPOINTMENT
            hospital_admins = data.hospital.hospital_admins.all()
            flag = False
            for admin in hospital_admins:
                if admin.permission_type == UserPermission.APPOINTMENT and admin.write_permission:
                    flag = True
                    break
            # if flag:
            #     permission_dict['read_permission'] = True
            # else:
            permission_dict['write_permission'] = True

            permission_data.append(permission_dict)
        return permission_data


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class UserAppointmentsViewSet(OndocViewSet):

    serializer_class = OpdAppointmentSerializer
    permission_classes = (IsAuthenticated,)
    def get_queryset(self):
        user = self.request.user
        return OpdAppointment.objects.filter(user=user)

    def list(self, request):
        params = request.query_params
        doctor_serializer = self.doctor_appointment_list(request, params)
        lab_serializer = self.lab_appointment_list(request, params)
        combined_data = list()
        if doctor_serializer.data:
            combined_data.extend(doctor_serializer.data)
        if lab_serializer.data:
            combined_data.extend(lab_serializer.data)
        combined_data = sorted(combined_data, key=lambda k: k['time_slot_start'])
        combined_data = combined_data[:20]
        return Response(combined_data)

    def retrieve(self, request, pk=None):
        user = request.user
        input_serializer = serializers.AppointmentqueryRetrieveSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)
        appointment_type = input_serializer.validated_data.get('type')
        if appointment_type == 'lab':
            queryset = LabAppointment.objects.filter(pk=pk)
            serializer = LabAppointmentRetrieveSerializer(queryset, many=True,context={"request": request})
            return Response(serializer.data)
        elif appointment_type == 'doctor':
            queryset = OpdAppointment.objects.filter(pk=pk)
            serializer = AppointmentRetrieveSerializer(queryset, many=True,context={"request": request})
            return Response(serializer.data)
        else:
            return Response({'Error':'Invalid Request Type'})

    def update(self, request, pk=None):
        serializer = UpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        query_input_serializer = serializers.AppointmentqueryRetrieveSerializer(data=request.query_params)
        query_input_serializer.is_valid(raise_exception=True)
        appointment_type = query_input_serializer.validated_data.get('type')
        if appointment_type == 'lab':
            lab_appointment = get_object_or_404(LabAppointment, pk=pk)
            allowed = lab_appointment.allowed_action(request.user.user_type)
            appt_status = validated_data.get('status')
            if appt_status not in allowed:
                resp = {}
                resp['allowed'] = allowed
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            updated_lab_appointment = self.lab_appointment_update(lab_appointment, validated_data)
            lab_appointment_serializer = LabAppointmentRetrieveSerializer(updated_lab_appointment,context={"request": request})
            response = {
                "status": 1,
                "data": lab_appointment_serializer.data
            }
            return Response(response)
        elif appointment_type == 'doctor':
            opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
            allowed = opd_appointment.allowed_action(request.user.user_type)
            appt_status = validated_data.get('status')
            if appt_status not in allowed:
                resp = {}
                resp['allowed'] = allowed
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            updated_opd_appointment = self.doctor_appointment_update(opd_appointment, validated_data)
            opd_appointment_serializer = AppointmentRetrieveSerializer(updated_opd_appointment,context={"request": request})
            response = {
               "status": 1,
               "data": opd_appointment_serializer.data
            }
            return Response(response)

    def lab_appointment_update(self, lab_appointment, validated_data):
        if validated_data.get('status'):
            if validated_data['status'] == LabAppointment.CANCELED:
                updated_lab_appointment = lab_appointment.action_cancelled(lab_appointment)
            if validated_data.get('status') == LabAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    updated_lab_appointment = lab_appointment.action_rescheduled_patient(lab_appointment,
                                                                                         validated_data)
        return updated_lab_appointment

    def doctor_appointment_update(self, opd_appointment, validated_data):
        if validated_data.get('status'):
            if validated_data['status'] == OpdAppointment.CANCELED:
                updated_opd_appointment = opd_appointment.action_cancelled(opd_appointment)
            if validated_data.get('status') == OpdAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    updated_opd_appointment = opd_appointment.action_rescheduled_patient(opd_appointment, validated_data)
        return updated_opd_appointment

    def lab_appointment_list(self, request, params):
        user = request.user
        queryset = LabAppointment.objects.select_related('lab').filter(profile__user=user)
        if queryset and params.get('profile_id'):
            queryset = queryset.filter(profile=params['profile_id'])
        queryset = paginate_queryset(queryset, request, 20)
        serializer = LabAppointmentModelSerializer(queryset, many=True, context={"request": request})
        return serializer

    def doctor_appointment_list(self, request, params):
        user = request.user
        queryset = OpdAppointment.objects.filter(user=user)

        if not queryset:
            return Response([])
        serializer = AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital_id = serializer.validated_data.get('hospital_id')
        profile_id = serializer.validated_data.get('profile_id')

        if profile_id:
            queryset = queryset.filter(profile=profile_id)

        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)

        if range == 'previous':
            queryset = queryset.filter(time_slot_start__lte=timezone.now()).order_by('-time_slot_start')
        elif range == 'upcoming':
            queryset = queryset.filter(
                status__in=[OpdAppointment.CREATED, OpdAppointment.RESCHEDULED_DOCTOR,
                            OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.ACCEPTED],
                time_slot_start__gt=timezone.now()).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(),
                                       status=OpdAppointment.CREATED).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request, 20)
        serializer = OpdAppointmentSerializer(queryset, many=True,context={"request": request})
        return serializer


class AddressViewsSet(viewsets.ModelViewSet):
    serializer_class = serializers.AddressSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        return Address.objects.filter(user=request.user)

    def create(self, request, *args, **kwargs):
        data = dict(request.data)
        data["user"] = request.user.id
        # Added recently
        if 'is_default' not in data:
            if not Address.objects.filter(user=request.user.id).exists():
                data['is_default'] = True

        serializer = serializers.AddressSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request, pk=None):
        data = request.data
        data['user'] = request.user.id
        queryset = get_object_or_404(Address, pk=pk)
        if data.get("is_default"):
            add_default_qs = Address.objects.filter(user=request.user.id, is_default=True)
            if add_default_qs:
                add_default_qs.update(is_default=False)
        serializer = serializers.AddressSerializer(queryset, data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        address = get_object_or_404(Address, pk=pk)

        if address.is_default:
            temp_addr = Address.objects.filter(user=request.user.id).first()
            if temp_addr:
                temp_addr.is_default = True
                temp_addr.save()

        # address = Address.objects.filter(pk=pk).first()
        address.delete()
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
        if response.get("statusCode") == 1 and response.get("productId") == 2:
            opd_appointment = OpdAppointment.objects.filter(pk=response.get("appointmentId")).first()
            if opd_appointment:
                otp = random.randint(1000, 9999)
                opd_appointment.payment_status = OpdAppointment.PAYMENT_ACCEPTED
                opd_appointment.otp = otp
                opd_appointment.save()
        elif response.get("statusCode") == 1 and response.get("productId") == 1:
            lab_appointment = LabAppointment.objects.filter(pk=response.get("appointmentId")).first()
            if lab_appointment:
                otp = random.randint(1000, 9999)
                lab_appointment.payment_status = OpdAppointment.PAYMENT_ACCEPTED
                lab_appointment.otp = otp
                lab_appointment.save()
        if response.get("productId") == 1:
            REDIRECT_URL = LAB_REDIRECT_URL.format(response.get("appointmentId"))
        else:
            REDIRECT_URL = OPD_REDIRECT_URL.format(response.get("appointmentId"))
        return HttpResponseRedirect(redirect_to=REDIRECT_URL)


class UserIDViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def retrieve(self, request):
        data = {
            "user_id": request.user.id
        }
        return Response(data)


class TransactionViewSet(viewsets.GenericViewSet):

    serializer_class = None
    queryset = PgTransaction.objects.none()

    def save(self, request):
        LAB_REDIRECT_URL = request.build_absolute_uri("/") + "lab/appointment/{}"
        OPD_REDIRECT_URL = request.build_absolute_uri("/") + "opd/appointment/{}"
        data = request.data
        #
        # coded_response = data.get("response")
        # if isinstance(coded_response, list):
        #     coded_response = coded_response[0]
        # coded_response += "=="
        # decoded_response = base64.b64decode(coded_response).decode()
        # response = json.loads(decoded_response)

        response = request.data

        response_data = self.form_pg_transaction_data(response)

        pg_tx_queryset = PgTransaction.objects.create(**response_data)

        self.block_pay_schedule_transaction(response_data)

        if response_data["product"] == 1:
                REDIRECT_URL = LAB_REDIRECT_URL.format(response_data["order"])
        else:
                REDIRECT_URL = OPD_REDIRECT_URL.format(response_data["order"])

        return Response({"url": REDIRECT_URL})
        # return HttpResponseRedirect(redirect_to=REDIRECT_URL)

    def form_pg_transaction_data(self, response):
        data = dict()
        # user = User.objects.get(pk=response.get("customerId"))
        user = get_object_or_404(User, pk=response.get("customerId"))
        data['user'] = user
        data['product'] = response.get('productId')
        data['order'] = response.get('orderNo')
        data['type'] = PgTransaction.CREDIT

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
    def block_pay_schedule_transaction(self, data):

        consumer_account = ConsumerAccount.objects.get_or_create(user=data["user"])
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=data["user"])

        appointment_charge, appointment_obj = self.get_appointment_amount(data)
        tx_amount = appointment_charge

        consumer_account.credit_payment(data, tx_amount)

        if appointment_obj and consumer_account.balance >= appointment_charge:
            appointment_obj.payment_confirmation(consumer_account, data, appointment_charge)

    # @transaction.atomic
    # def block_cancel_refund_transaction(self, data):
    #     consumer_account = ConsumerAccount.objects.select_for_update().filter(user=data["user"]).first()
    #     if not consumer_account:
    #         consumer_account = ConsumerAccount.objects.select_for_update().create(user=data["user"])
    #
    #     cancel_amount = self.get_cancel_amount(data)
    #
    #     self.credit_cancellation(data, cancel_amount)
    #
    #     refund_amount = cancel_amount + consumer_account.balance
    #
    #     self.debit_refund(data, refund_amount)
    #     consumer_account.balance = 0
    #     consumer_account.save()
    #     return refund_amount

    # @transaction.atomic
    # def block_cancel_reschedule_transaction(self, data):
    #     consumer_account = ConsumerAccount.objects.select_for_update().filter(user=data["user"]).first()
    #     if not consumer_account:
    #         consumer_account = ConsumerAccount.objects.select_for_update().create(user=data["user"])
    #
    #     cancel_amount = self.get_cancel_amount(data)
    #     consumer_account.balance += cancel_amount
    #     self.credit_cancellation(data, cancel_amount)
    #     cancel_amount.save()

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

    # def get_cancel_amount(self, data):
    #     consumer_tx = ConsumerTransaction.objects.filter(user=data["user"],
    #                                                      product=data["product"],
    #                                                      order=data["order"],
    #                                                      type=PgTransaction.DEBIT,
    #                                                      action=ConsumerTransaction.SALE).order_by("created_at").last()
    #     return consumer_tx.amount
    #
    def get_appointment_amount(self, data):
        amount = 0
        if data["product"] == 2:
            obj = get_object_or_404(LabAppointment, pk=data['order'])
            amount = obj.price
        elif data["product"] == 1:
            obj = get_object_or_404(OpdAppointment, pk=data['order'])
            amount = obj.fees

        return amount, obj
    #
    # def credit_payment(self, data, amount):
    #     action = ConsumerTransaction.PAYMENT
    #     consumer_tx_data = self.form_consumer_tx_data(data, amount, action, PgTransaction.CREDIT)
    #     ConsumerTransaction.objects.create(**consumer_tx_data)
    #
    # def credit_cancellation(self, data, amount):
    #     action = ConsumerTransaction.CANCELLATION
    #     consumer_tx_data = self.form_consumer_tx_data(data, amount, action, PgTransaction.CREDIT)
    #     ConsumerTransaction.objects.create(**consumer_tx_data)
    #
    # def debit_refund(self, data, amount):
    #     action = ConsumerTransaction.REFUND
    #     consumer_tx_data = self.form_consumer_tx_data(data, amount, action, PgTransaction.DEBIT)
    #     ConsumerTransaction.objects.create(**consumer_tx_data)
    #
    # def debit_schedule(self, data, amount):
    #     action = ConsumerTransaction.SALE
    #     consumer_tx_data = self.form_consumer_tx_data(data, amount, action, PgTransaction.DEBIT)
    #     ConsumerTransaction.objects.create(**consumer_tx_data)
    #
    # def form_consumer_tx_data(self, data, amount, action, tx_type):
    #     consumer_tx_data = dict()
    #     consumer_tx_data['user'] = data['user']
    #     consumer_tx_data['product'] = data['product']
    #     consumer_tx_data['order'] = data['order']
    #     consumer_tx_data['transaction_id'] = data.get('transaction_id')
    #     consumer_tx_data['type'] = tx_type
    #     consumer_tx_data['action'] = action
    #     consumer_tx_data['amount'] = amount
    #     return consumer_tx_data


class ConsumerAccountViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = ConsumerAccount.objects.all()
    serializer_class = serializers.ConsumerAccountModelSerializer
