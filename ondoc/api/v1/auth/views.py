import base64
import json
import random
import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.http import HttpResponseRedirect
from ondoc.account import models as account_models
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework import mixins, viewsets, status
import datetime
from ondoc.api.v1.auth import serializers
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from django.db.models import F, Sum, Max, Q, Prefetch, Case, When
from django.forms.models import model_to_dict
from ondoc.sms.api import send_otp
from django.forms.models import model_to_dict
from ondoc.doctor.models import DoctorMobile, Doctor, HospitalNetwork, Hospital, DoctorHospital
from ondoc.authentication.models import (OtpVerifications, NotificationEndpoint, Notification, UserProfile,
                                         UserPermission, Address, AppointmentTransaction, GenericAdmin)
from ondoc.account.models import PgTransaction, ConsumerAccount, ConsumerTransaction, Order
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ondoc.api.pagination import paginate_queryset
from ondoc.api.v1 import utils
from ondoc.doctor.models import OpdAppointment
from ondoc.api.v1.doctor.serializers import (OpdAppointmentSerializer, AppointmentFilterSerializer,
                                             UpdateStatusSerializer, CreateAppointmentSerializer,
                                             AppointmentRetrieveSerializer, OpdAppTransactionModelSerializer,
                                             OpdAppModelSerializer)
from ondoc.api.v1.diagnostic.serializers import (LabAppointmentModelSerializer,
                                                 LabAppointmentRetrieveSerializer, LabAppointmentCreateSerializer,
                                                 LabAppTransactionModelSerializer, LabAppRescheduleModelSerializer)
from ondoc.diagnostic.models import (Lab, LabAppointment, AvailableLabTest)
from ondoc.api.v1.utils import IsConsumer, opdappointment_transform, labappointment_transform, ErrorCodeMapping
import decimal
import copy

User = get_user_model()


def expire_otp(phone_number):
    OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)

class LoginOTP(GenericViewSet):

    serializer_class = serializers.OTPSerializer

    @transaction.atomic
    def generate(self, request, format=None):

        response = {'exists': 0}
        if request.data.get("phone_number"):
            expire_otp(phone_number=request.data.get("phone_number"))
        serializer = serializers.OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        phone_number = data['phone_number']
        #
        # user = User.objects.filter(phone_number=phone_number, user_type=User.DOCTOR).first()
        # admin_queryset = GenericAdmin.objects.filter(user=user.id)
        # pem_obj = DoctorPermission(admin_queryset, request)
        # pem_obj.create_permission()


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

        GenericAdmin.update_user_admin(data['phone_number'])

        token = Token.objects.get_or_create(user=user)

        expire_otp(data['phone_number'])

        response = {
            "login":1,
            "token" : str(token[0]),
            "user_exists" : user_exists,
            "user_id" : user.id
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

        if not user:
            doctor = DoctorMobile.objects.get(number=phone_number, is_primary=True).doctor
            user = User.objects.create(phone_number=data['phone_number'], is_phone_number_verified=True, user_type=User.DOCTOR)
            doctor.user = user
            doctor.save()

        GenericAdmin.update_user_admin(phone_number)
        token = Token.objects.get_or_create(user=user)
        expire_otp(data['phone_number'])

        response = {
            "login": 1,
            "token": str(token[0])
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
        data['name'] = request.data.get('name')
        data['gender'] = request.data.get('gender')
        # data['age'] = request.data.get('age')
        data['email'] = request.data.get('email')
        data['phone_number'] = request.data.get('phone_number')
        data['user'] = request.user.id

        if not queryset.exists():
            data.update({
                "is_default_user": True
            })
        if request.data.get('age'):
            try:
                age = int(request.data.get("age"))
                data['dob'] = datetime.datetime.now() - relativedelta(years=age)
                data['dob'] = data['dob'].date()
            except:
                return Response({"error": "Invalid Age"}, status=status.HTTP_400_BAD_REQUEST)
        if not data.get('phone_number'):
            data['phone_number'] = request.user.phone_number
        serializer = serializers.UserProfileSerializer(data=data, context= {'request':request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        return super().update(request, partial=True, *args, **kwargs)

    def upload(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = serializers.UploadProfilePictureSerializer(instance, data=request.data, context= {'request':request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

#
# class UserPermissionViewSet(mixins.CreateModelMixin,
#                             mixins.ListModelMixin,
#                             GenericViewSet):
#     queryset = DoctorHospital.objects.all()
#     # serializer_class = serializers.UserPermissionSerializer
#
#     def list(self, request, *args, **kwargs):
#         params = request.query_params
#         doctor_list = params['doctor_id'].split(",")
#         dp_obj = DoctorPermission(doctor_list, request)
#         permission_data = dp_obj.create_permission()
#         return Response({'data':permission_data})


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class UserAppointmentsViewSet(OndocViewSet):

    serializer_class = OpdAppointmentSerializer
    permission_classes = (IsAuthenticated, IsConsumer, )
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
            queryset = LabAppointment.objects.filter(pk=pk, user=user)
            serializer = LabAppointmentRetrieveSerializer(queryset, many=True, context={"request": request})
            return Response(serializer.data)
        elif appointment_type == 'doctor':
            queryset = OpdAppointment.objects.filter(pk=pk, user=user)
            serializer = AppointmentRetrieveSerializer(queryset, many=True, context={"request": request})
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
                resp['Error'] = 'Action Not Allowed'
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            response = self.lab_appointment_update(request, lab_appointment, validated_data)
            return Response(response)
        elif appointment_type == 'doctor':
            opd_appointment = get_object_or_404(OpdAppointment, pk=pk)
            allowed = opd_appointment.allowed_action(request.user.user_type, request)
            appt_status = validated_data.get('status')
            if appt_status not in allowed:
                resp = {}
                resp['allowed'] = allowed
                return Response(resp, status=status.HTTP_400_BAD_REQUEST)
            updated_opd_appointment = self.doctor_appointment_update(request, opd_appointment, validated_data)
            response = updated_opd_appointment
            return Response(response)

    @transaction.atomic
    def lab_appointment_update(self, request, lab_appointment, validated_data):
        resp = {}
        if validated_data.get('status'):
            if validated_data['status'] == LabAppointment.CANCELED:
                lab_appointment.action_cancelled()
                resp = LabAppointmentRetrieveSerializer(lab_appointment, context={"request": request}).data
            if validated_data.get('status') == LabAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    time_slot_start = utils.form_time_slot(
                        validated_data.get("start_date"),
                        validated_data.get("start_time"))
                    test_ids = lab_appointment.lab_test.values_list('test__id', flat=True)
                    lab_test_queryset = AvailableLabTest.objects.select_related('lab').filter(lab=lab_appointment.lab,
                                                                                              test__in=test_ids)
                    deal_price_calculation = Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                                  When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
                    agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                                    When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))
                    temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"),
                                                                             total_deal_price=Sum(deal_price_calculation),
                                                                             total_agreed_price=Sum(agreed_price_calculation))
                    old_deal_price = lab_appointment.deal_price
                    old_effective_price = lab_appointment.effective_price
                    coupon_price = self.get_appointment_coupon_price(old_deal_price, old_effective_price)
                    new_deal_price = temp_lab_test[0].get("total_deal_price")
                    new_effective_price = new_deal_price - coupon_price
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
                        "lab_test": lab_appointment.lab_test
                    }

                    # new_appointment['id'] = lab_appointment.id
                    # new_appointment['deal_price'] = new_deal_price
                    # new_appointment['effective_price'] = new_effective_price
                    # new_appointment['agreed_price'] = temp_lab_test[0].get("total_agreed_price", 0)
                    # new_appointment['price'] = temp_lab_test[0].get("total_mrp")
                    # new_appointment['time_slot_start'] = time_slot_start
                    resp = self.extract_payment_details(request, lab_appointment, new_appointment,
                                                        account_models.Order.LAB_PRODUCT_ID)
        return resp

    def doctor_appointment_update(self, request, opd_appointment, validated_data):
        if validated_data.get('status'):
            resp = {}
            if validated_data['status'] == OpdAppointment.CANCELED:
                opd_appointment.action_cancelled(request.data.get("refund"))
                resp = AppointmentRetrieveSerializer(opd_appointment, context={"request": request}).data
            if validated_data.get('status') == OpdAppointment.RESCHEDULED_PATIENT:
                if validated_data.get("start_date") and validated_data.get('start_time'):
                    time_slot_start = utils.form_time_slot(
                        validated_data.get("start_date"),
                        validated_data.get("start_time"))
                    doctor_hospital = DoctorHospital.objects.filter(doctor=opd_appointment.doctor,
                                                                           hospital=opd_appointment.hospital,
                                                                           day=time_slot_start.weekday(),
                                                                           start__lte=time_slot_start.hour,
                                                                           end__gte=time_slot_start.hour).first()
                    if doctor_hospital:
                        old_deal_price = opd_appointment.deal_price
                        old_effective_price = opd_appointment.effective_price
                        # COUPON PROCESS to be Discussed
                        coupon_price = self.get_appointment_coupon_price(old_deal_price, old_effective_price)
                        new_appointment = dict()

                        new_effective_price = doctor_hospital.deal_price - coupon_price
                        new_appointment = {
                            "id": opd_appointment.id,
                            "doctor": opd_appointment.doctor,
                            "hospital": opd_appointment.hospital,
                            "profile": opd_appointment.profile,
                            "profile_detail": opd_appointment.profile_detail,
                            "user": opd_appointment.user,

                            "booked_by": opd_appointment.booked_by,
                            "fees": doctor_hospital.fees,
                            "deal_price": doctor_hospital.deal_price,
                            "effective_price": new_effective_price,
                            "mrp": doctor_hospital.mrp,
                            "time_slot_start": time_slot_start,
                            "payment_type": opd_appointment.payment_type
                        }


                        # new_appointment['id'] = opd_appointment.id
                        # new_appointment['deal_price'] = doctor_hospital.deal_price
                        # new_effective_price = doctor_hospital.deal_price - coupon_price
                        # new_appointment['effective_price'] = new_effective_price
                        # new_appointment['fees'] = doctor_hospital.fees
                        # new_appointment['mrp'] = doctor_hospital.mrp
                        # new_appointment['time_slot_start'] = time_slot_start
                        resp = self.extract_payment_details(request, opd_appointment, new_appointment,
                                                            account_models.Order.DOCTOR_PRODUCT_ID)
            return resp

    def get_appointment_coupon_price(self, discounted_price, effective_price):
        coupon_price = discounted_price - effective_price
        return coupon_price

    @transaction.atomic
    def extract_payment_details(self, request, appointment_details, new_appointment_details, product_id):
        remaining_amount = 0
        resp = {}
        user = request.user
        user_account_data = {
            "user": user,
            "product_id": product_id,
            "reference_id": appointment_details.id
        }
        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        if consumer_account.balance + appointment_details.effective_price >= new_appointment_details.get('effective_price'):
            # Debit or Refund/Credit in Account
            if appointment_details.effective_price > new_appointment_details.get('effective_price'):
                #TODO PM - Refund difference b/w effective price
                consumer_account.credit_schedule(user_account_data, appointment_details.effective_price - new_appointment_details.get('effective_price'))
            else:
                debit_balance = new_appointment_details.get('effective_price') - appointment_details.effective_price
                if debit_balance:
                    consumer_account.debit_schedule(user_account_data, debit_balance)

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
            balance = consumer_account.balance + appointment_details.effective_price
            new_appointment_details['time_slot_start'] = str(new_appointment_details['time_slot_start'])
            action = ''
            temp_app_details = copy.deepcopy(new_appointment_details)
            if product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                action = account_models.Order.OPD_APPOINTMENT_RESCHEDULE
                opdappointment_transform(temp_app_details)
                # appointment_data = LabAppointmentModelSerializer(appointment_details, context={'request': request})
                # temp_app_details.deal_price = str(appointment_details.deal_price)
                # temp_app_details.fees = str(appointment_details.fees)
                # temp_app_details.effective_price = str(appointment_details.effective_price)
                # temp_app_details.mrp = str(appointment_details.mrp)
                # appointment_data = OpdAppModelSerializer(appointment_details, context={'request': request})
                # temp_app_details = appointment_data.data
            elif product_id == account_models.Order.LAB_PRODUCT_ID:
                action = Order.LAB_APPOINTMENT_RESCHEDULE
                labappointment_transform(temp_app_details)
                # temp_app_details.price = str(appointment_details.price)
                # temp_app_details.agreed_price = str(appointment_details.agreed_price)
                # temp_app_details.deal_price = str(appointment_details.deal_price)
                # temp_app_details.effective_price = str(appointment_details.effective_price)
                # temp_app_details.time_slot_start = str(appointment_details.time_slot_start)
                # temp_app_details.time_slot_end = str(appointment_details.time_slot_end)
                # temp_app_details = model_to_dict(temp_app_details)
                # appointment_data = LabAppointmentModelSerializer(appointment_details, context={'request':request})
                # temp_app_details = appointment_data.data

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=action,
                action_data=temp_app_details,
                amount=new_appointment_details.get('effective_price') - balance,
                reference_id=appointment_details.id,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            new_appointment_details["payable_amount"] = new_appointment_details.get('effective_price') - balance
            resp['status'] = 1
            resp['data'], resp['payment_required'] = self.payment_details(request, new_appointment_details, product_id, order.id)
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
            pgdata['email'] = "dummy_appointment@policybazaar.com"

        pgdata['productId'] = product_id
        base_url = (
            "https://{}".format(request.get_host()) if request.is_secure() else "http://{}".format(request.get_host()))
        pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['checkSum'] = ''
        pgdata['appointmentId'] = appointment_details.get('id')
        pgdata['orderId'] = order_id
        if user_profile:
            pgdata['name'] = user_profile.name
        else:
            pgdata['name'] = "DummyName"
        pgdata['txAmount'] = appointment_details['payable_amount']

        return pgdata, payment_required

    def lab_appointment_list(self, request, params):
        user = request.user
        queryset = LabAppointment.objects.select_related('lab').filter(user=user)
        if queryset and params.get('profile_id'):
            queryset = queryset.filter(profile=params['profile_id'])
        range = params.get('range')
        if range and range == 'upcoming':
            queryset = queryset.filter(time_slot_start__gte=timezone.now(),
                                       status__in=LabAppointment.ACTIVE_APPOINTMENT_STATUS).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')
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
                status__in=OpdAppointment.ACTIVE_APPOINTMENT_STATUS,
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
        data = request.data
        serializer = serializers.AddressSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not Address.objects.filter(user=request.user).filter(**serializer.validated_data).exists():
            serializer.save()
        else:
            address = Address.objects.filter(user=request.user).filter(**serializer.validated_data).first()
            serializer = serializers.AddressSerializer(address)
        return Response(serializer.data)

    def update(self, request, pk=None):
        data = {key: value for key, value in request.data.items()}
        data['user'] = request.user.id
        address = self.get_queryset().filter(pk=pk).first()
        if data.get("is_default"):
            add_default_qs = Address.objects.filter(user=request.user.id, is_default=True)
            if add_default_qs:
                add_default_qs.update(is_default=False)
        serializer = serializers.AddressSerializer(address, data=data, context={"request": request})
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
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def retrieve(self, request):
        data = {
            "user_id": request.user.id
        }
        return Response(data)


class TransactionViewSet(viewsets.GenericViewSet):

    serializer_class = serializers.TransactionSerializer
    queryset = PgTransaction.objects.none()

    def save(self, request):
        LAB_REDIRECT_URL = request.build_absolute_uri("/") + "lab/appointment"
        OPD_REDIRECT_URL = request.build_absolute_uri("/") + "opd/appointment"
        LAB_FAILURE_REDIRECT_URL = request.build_absolute_uri("/") + "lab/%s/book?error_code=%s"
        OPD_FAILURE_REDIRECT_URL = request.build_absolute_uri("/") + "opd/doctor/%s/%s/bookdetails?error_code=%s"
        ERROR_REDIRECT_URL = request.build_absolute_uri("/") + "error?error_code=%s"
        REDIRECT_URL = ERROR_REDIRECT_URL % ErrorCodeMapping.IVALID_APPOINTMENT_ORDER

        try:
            data = request.data
            # Commenting below for testing
            coded_response = data.get("response")
            if isinstance(coded_response, list):
                coded_response = coded_response[0]
            coded_response += "=="
            decoded_response = base64.b64decode(coded_response).decode()
            response = json.loads(decoded_response)

            # For testing only
            # response = request.data
            appointment_obj = None

            try:
                pg_resp_code = int(response.get('statusCode'))
            except:
                pg_resp_code = None

            order_obj = Order.objects.filter(pk=response.get("orderId")).first()
            if pg_resp_code == 1:
                if not order_obj:
                    REDIRECT_URL = ERROR_REDIRECT_URL % ErrorCodeMapping.IVALID_APPOINTMENT_ORDER
                else:
                    response_data = self.form_pg_transaction_data(response, order_obj)
                    try:
                        pg_tx_queryset = PgTransaction.objects.create(**response_data)
                    except:
                        pass

                    try:
                        appointment_obj = self.block_pay_schedule_transaction(response_data, order_obj)
                    except:
                        pass

                    if int(response_data["product_id"]) == account_models.Order.LAB_PRODUCT_ID:
                        if appointment_obj:
                            LAB_REDIRECT_URL += "/" + str(appointment_obj.id)
                        REDIRECT_URL = LAB_REDIRECT_URL
                    elif int(response_data["product_id"]) == account_models.Order.DOCTOR_PRODUCT_ID:
                        if appointment_obj:
                            OPD_REDIRECT_URL += "/" + str(appointment_obj.id)
                        REDIRECT_URL = OPD_REDIRECT_URL
            else:
                if not order_obj:
                    REDIRECT_URL = ERROR_REDIRECT_URL % ErrorCodeMapping.IVALID_APPOINTMENT_ORDER
                else:
                    if order_obj.product_id == account_models.Order.LAB_PRODUCT_ID:
                        REDIRECT_URL = LAB_FAILURE_REDIRECT_URL % (
                        order_obj.action_data.get("lab"), response.get('statusCode'))
                    elif order_obj.product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                        REDIRECT_URL = OPD_FAILURE_REDIRECT_URL % (order_obj.action_data.get("doctor"),
                                                                   order_obj.action_data.get("hospital"),
                                                                   response.get('statusCode'))
        except:
            pass

        # return Response({"url": REDIRECT_URL})
        return HttpResponseRedirect(redirect_to=REDIRECT_URL)

    def form_pg_transaction_data(self, response, order_obj):
        data = dict()
        resp_serializer = serializers.TransactionSerializer(data=response)
        resp_serializer.is_valid(raise_exception=True)
        response = resp_serializer.validated_data
        # user = User.objects.get(pk=order_obj.action_data.get("user"))
        user = get_object_or_404(User, pk=order_obj.action_data.get("user"))
        data['user'] = user
        data['product_id'] = order_obj.product_id
        data['order_no'] = response.get('orderNo')
        data['order_id'] = order_obj.id
        data['reference_id'] = order_obj.reference_id
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
    def block_pay_schedule_transaction(self, pg_data, order_obj):

        consumer_account = ConsumerAccount.objects.get_or_create(user=pg_data["user"])
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=pg_data["user"])

        tx_amount = order_obj.amount

        consumer_account.credit_payment(pg_data, tx_amount)

        appointment_obj = None
        try:
            appointment_data = order_obj.action_data
            if order_obj.product_id == account_models.Order.DOCTOR_PRODUCT_ID:
                serializer = OpdAppTransactionModelSerializer(data=appointment_data)
                serializer.is_valid()
                appointment_data = serializer.validated_data
            elif order_obj.product_id == account_models.Order.LAB_PRODUCT_ID:
                serializer = LabAppTransactionModelSerializer(data=appointment_data)
                serializer.is_valid()
                appointment_data = serializer.validated_data

            appointment_obj = order_obj.process_order(consumer_account, pg_data, appointment_data)
        except:
            pass

        return appointment_obj

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


class UserTransactionViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.UserTransactionModelSerializer
    queryset = ConsumerTransaction.objects.all()
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        user = request.user
        queryset = ConsumerTransaction.objects.filter(user=user)
        if not queryset.exists():
            return Response({"status": 0,
                             "msg": "No transaction exists"
                             })
        queryset = paginate_queryset(queryset, request)
        serializer = serializers.UserTransactionModelSerializer(queryset, many=True)
        return Response(data=serializer.data)


class ConsumerAccountViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = ConsumerAccount.objects.all()
    serializer_class = serializers.ConsumerAccountModelSerializer


class OrderHistoryViewSet(GenericViewSet):
    permission_classes = (IsAuthenticated, IsConsumer,)

    def list(self, request):
        orders = []
        for order in Order.objects.filter(action_data__user=request.user.id, is_viewable=True,
                                          payment_status=Order.PAYMENT_PENDING):
            action_data = order.action_data
            if order.product_id == Order.DOCTOR_PRODUCT_ID:
                data = {
                    "doctor": action_data.get("doctor"),
                    "hospital": action_data.get("hospital"),
                    "profile_detail": action_data.get("profile_detail"),
                    "profile": action_data.get("profile"),
                    "user": action_data.get("user"),
                    "product_id": order.product_id,
                    "time_slot_start": action_data.get("time_slot_start"),
                    "start_date": action_data.get("time_slot_start"),
                    "start_time": 0.0,      # not required here we are only validating fees
                    "fees": action_data.get("effective_price")
                }
                serializer = CreateAppointmentSerializer(data=data, context={"request": request})
                serializer.is_valid(raise_exception=True)
                if not serializer.is_valid():
                    data.pop("time_slot_start")
                    data.pop("start_date")
                    data.pop("start_time")
                    data.pop("fees")
            elif order.product_id == Order.LAB_PRODUCT_ID:
                data = {
                    "lab": action_data.get("lab"),
                    "test_ids": action_data.get("test_ids"),
                    "profile": action_data.get("profile"),
                    "start_date": action_data.get("start_date"),
                    "start_time": action_data.get("start_time"),
                    "fees": action_data.get("effective_price"),
                    "product_id": order.product_id
                }
                serializer = LabAppointmentCreateSerializer(data=data, context={'request': request})
                if not serializer.is_valid():
                    data.pop("start_date")
                    data.pop("start_time")
                    data.pop("fees")
            orders.append(data)
        return Response(orders)
