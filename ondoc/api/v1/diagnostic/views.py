# from .serializers import (LabModelSerializer, LabTestListSerializer, LabCustomSerializer, AvailableLabTestSerializer,
#                           LabAppointmentModelSerializer, LabAppointmentCreateSerializer,
#                           LabAppointmentUpdateSerializer, LabListSerializer, CommonTestSerializer,
#                           PromotedLabsSerializer, CommonConditionsSerializer, TimeSlotSerializer,
#                           SearchLabListSerializer)
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.api.v1.auth.serializers import AddressSerializer

from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest)
from ondoc.account import models as account_models
from ondoc.authentication.models import UserProfile, Address
from ondoc.doctor import models as doctor_model
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.utils import form_time_slot, IsConsumer
from ondoc.api.pagination import paginate_queryset

from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Distance
from django.shortcuts import get_object_or_404

from django.db import transaction
from django.db.models import Count, Sum, Max, When, Case, F
from django.http import Http404
from rest_framework import status
from collections import OrderedDict
from django.utils import timezone
import random
import copy
import re

class SearchPageViewSet(viewsets.ReadOnlyModelViewSet):

    def list(self, request, *args, **kwargs):
        test_queryset = CommonTest.objects.all()
        conditions_queryset = CommonDiagnosticCondition.objects.prefetch_related('lab_test').all()
        lab_queryset = PromotedLab.objects.all()
        test_serializer = diagnostic_serializer.CommonTestSerializer(test_queryset, many=True)
        lab_serializer = diagnostic_serializer.PromotedLabsSerializer(lab_queryset, many=True)
        condition_serializer = diagnostic_serializer.CommonConditionsSerializer(conditions_queryset, many=True)
        temp_data = dict()
        temp_data['common_tests'] = test_serializer.data
        temp_data['preferred_labs'] = lab_serializer.data
        temp_data['common_conditions'] = condition_serializer.data

        return Response(temp_data)


class LabTestList(viewsets.ReadOnlyModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class = diagnostic_serializer.LabTestListSerializer
    lookup_field = 'id'
    filter_backends = (SearchFilter,)
    # filter_fields = ('name',)
    search_fields = ('name',)

    def list(self, request, *args, **kwargs):
        name = request.query_params.get('name')
        temp_data = dict()
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            test_queryset = LabTest.objects.filter(search_key__icontains=search_key)
            test_queryset = paginate_queryset(test_queryset, request)
            lab_queryset = Lab.objects.filter(search_key__icontains=search_key)
            lab_queryset = paginate_queryset(lab_queryset, request)
            test_serializer = diagnostic_serializer.LabTestListSerializer(test_queryset, many=True)
            lab_serializer = diagnostic_serializer.LabListSerializer(lab_queryset, many=True)
            temp_data['tests'] = test_serializer.data
            temp_data['labs'] = lab_serializer.data

        return Response(temp_data)


class LabList(viewsets.ReadOnlyModelViewSet):
    # queryset = self.form_queryset()
    queryset = AvailableLabTest.objects.all()
    serializer_class = diagnostic_serializer.LabModelSerializer
    lookup_field = 'id'
    # filter_backends = (DjangoFilterBackend, )
    # filter_fields = ('name', 'deal_price', )

    def list(self, request, **kwargs):
        parameters = request.query_params
        queryset = self.get_lab_list(parameters)
        count = queryset.count()
        paginated_queryset = paginate_queryset(queryset, request)
        response_queryset = self.form_lab_whole_data(paginated_queryset)
        serializer = diagnostic_serializer.LabCustomSerializer(response_queryset, many=True,
                                         context={"request": request})
        return Response({"result": serializer.data,
                         "count": count})

    def retrieve(self, request, lab_id):
        test_ids = (request.query_params.get("test_ids").split(",") if request.query_params.get('test_ids') else [])
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id, test__in=test_ids)
        test_serializer = diagnostic_serializer.AvailableLabTestSerializer(queryset, many=True)
        lab_obj = Lab.objects.filter(id=lab_id).first()
        day_now = timezone.now().weekday()
        timing_queryset = lab_obj.labtiming_set.filter(day=day_now)
        lab_serializer = diagnostic_serializer.LabModelSerializer(lab_obj, context={"request": request})
        temp_data = dict()
        temp_data['lab'] = lab_serializer.data
        temp_data['tests'] = test_serializer.data
        temp_data['lab_timing'] = ''
        temp_data['lab_timing'] = self.get_lab_timing(timing_queryset)

        return Response(temp_data)

    def get_lab_timing(self, queryset):
        temp_str = ''
        for qdata in queryset:
            start = self.convert_time(qdata.start)
            end = self.convert_time(qdata.end)
            if not temp_str:
                temp_str += start + " - " + end
            else:
                temp_str += " | " + start + " - " + end
        return temp_str

    def convert_time(self, time):
        hour = int(time)
        min = int((time - hour) * 60)
        am_pm = ''
        if time < 12:
            am_pm = 'AM'
        else:
            am_pm = 'PM'
            hour -= 12
        min_str = self.convert_min(min)
        return str(hour) + ":" + min_str + " " + am_pm

    def convert_min(self, min):
        min_str = str(min)
        if min/10 < 1:
            min_str = '0' + str(min)
        return min_str

    def get_lab_list(self, parameters):
        # distance in meters
        serializer = diagnostic_serializer.SearchLabListSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data

        DEFAULT_DISTANCE = 10000

        default_long = 77.071848
        default_lat = 28.450367
        min_distance = parameters.get('min_distance')
        max_distance = parameters.get('max_distance', DEFAULT_DISTANCE)
        long = parameters.get('long', default_long)
        lat = parameters.get('lat', default_lat)
        ids = parameters.get('ids', [])
        min_price = parameters.get('min_price')
        max_price = parameters.get('max_price')

        queryset = AvailableLabTest.objects

        if ids:
            queryset = queryset.filter(test__in=ids)

        if lat is not None and long is not None:
            point_string = 'POINT('+str(long)+' '+str(lat)+')'
            pnt = GEOSGeometry(point_string, srid=4326)
            queryset = queryset.filter(lab__location__distance_lte=(pnt, max_distance))
            if min_distance:
                queryset = queryset.filter(lab__location__distance_gte=(pnt, min_distance))

        if ids:
            queryset = (
                queryset.values('lab').annotate(price=Sum('mrp'), count=Count('id'),
                                                distance=Max(Distance('lab__location', pnt)),
                                                name=Max('lab__name')).filter(count__gte=len(ids)))
        else:
            queryset = (
                queryset.values('lab').annotate(count=Count('id'),
                                                distance=Max(Distance('lab__location', pnt)),
                                                name=Max('lab__name')).filter(count__gte=len(ids)))

        if min_price and ids:
            queryset = queryset.filter(price__gte=min_price)

        if max_price and ids:
            queryset = queryset.filter(price__lte=max_price)

        queryset = self.apply_custom_filters(queryset, parameters)
        return queryset

    @staticmethod
    def apply_custom_filters(queryset, parameters):
        order_by = parameters.get("order_by")
        if order_by is not None:
            if order_by == "fees" and parameters.get('ids'):
                queryset = queryset.order_by("price")
            elif order_by == 'distance':
                queryset = queryset.order_by("distance")
            elif order_by == 'name':
                queryset = queryset.order_by("name")
        return queryset

    def form_lab_whole_data(self, queryset):
        ids, id_details = self.extract_lab_ids(queryset)
        labs = Lab.objects.prefetch_related('lab_image').filter(id__in=ids)
        resp_queryset = list()
        temp_var = dict()
        for obj in labs:
            # temp_var = id_details[obj.id]
            temp_var[obj.id] = obj
            # resp_queryset.append(temp_var)

        for row in queryset:
            row["lab"] = temp_var[row["lab"]]
            resp_queryset.append(row)

        return resp_queryset

    def extract_lab_ids(self, queryset):
        ids = list()
        temp_dict = dict()
        for obj in queryset:
            ids.append(obj['lab'])
            temp_dict[obj['lab']] = obj
        return ids, temp_dict


class LabAppointmentView(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    queryset = LabAppointment.objects.all()
    serializer_class = diagnostic_serializer.LabAppointmentModelSerializer
    permission_classes = (IsAuthenticated, IsConsumer, )
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('profile', 'lab',)

    def list(self, request, *args, **kwargs):
        user = request.user
        queryset = LabAppointment.objects.filter(profile__user=user)
        serializer = diagnostic_serializer.LabAppointmentModelSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, **kwargs):
        serializer = diagnostic_serializer.LabAppointmentCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        appointment_data = self.form_lab_app_data(request, serializer.validated_data)
        resp = self.extract_payment_details(request, appointment_data, account_models.Order.LAB_PRODUCT_ID)
        return Response(data=resp)

    def form_lab_app_data(self, request, data):
        deal_price_calculation = Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                      When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
        agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                        When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))
        lab_test_queryset = AvailableLabTest.objects.filter(lab=data["lab"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"),
                                                                 total_deal_price=Sum(deal_price_calculation),
                                                                 total_agreed_price=Sum(agreed_price_calculation))
        total_agreed = total_deal_price = total_mrp = effective_price = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_agreed = temp_lab_test[0].get("total_agreed_price", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)
            effective_price = temp_lab_test[0].get("total_deal_price")
            # TODO PM - call coupon function to calculate effective price
        start_dt = form_time_slot(data["start_date"], data["start_time"])
        profile_detail = {
            "name": data["profile"].name,
            "gender": data["profile"].gender,
            "dob": str(data["profile"].dob),
        }
        # otp = random.randint(1000, 9999)
        appointment_data = {
            "lab": data["lab"],
            "user": request.user,
            "profile": data["profile"],
            "price": total_mrp,
            "agreed_price": total_agreed,
            "deal_price": total_deal_price,
            "effective_price": effective_price,
            "time_slot_start": start_dt,
            "profile_detail": profile_detail,
            "status": LabAppointment.BOOKED,
            "payment_type": data["payment_type"],
            "lab_test": [x["id"] for x in lab_test_queryset.values("id")]
        }
        if data.get("is_home_pickup") is True:
            address = Address.objects.filter(pk=data.get("address")).first()
            address_serialzer = AddressSerializer(address)
            appointment_data.update({
                "address": address_serialzer.data,
                "is_home_pickup": True
            })

        return appointment_data

    def extract_payment_details(self, request, appointment_details, product_id):
        remaining_amount = 0
        user = request.user
        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance
        resp = {}

        can_use_insurance, insurance_fail_message = self.can_use_insurance(appointment_details)

        if can_use_insurance:
            appointment_details['effective_price'] = appointment_details['agreed_price']
            appointment_details['payment_type'] = doctor_model.OpdAppointment.INSURANCE
        elif appointment_details['payment_type'] == doctor_model.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp

        if appointment_details['payment_type'] == doctor_model.OpdAppointment.PREPAID and \
                balance < appointment_details.get("effective_price"):
            temp_appointment_details = copy.deepcopy(appointment_details)
            self.json_transform(temp_appointment_details)

            account_models.Order.disable_pending_orders(temp_appointment_details, product_id,
                                                        account_models.Order.LAB_APPOINTMENT_CREATE)

            payable_amount = appointment_details.get("effective_price") - balance

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.LAB_APPOINTMENT_CREATE,
                action_data=temp_appointment_details,
                amount=payable_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            appointment_details["payable_amount"] = payable_amount
            resp["status"] = 1
            resp['data'], resp['payment_required'] = self.get_payment_details(request, appointment_details, product_id,
                                                                              order.id)
        else:

            lab_appointment = LabAppointment.create_appointment(appointment_details)
            if appointment_details["payment_type"] == doctor_model.OpdAppointment.PREPAID:
                user_account_data = {
                    "user": user,
                    "product_id": product_id,
                    "reference_id": lab_appointment.id
                }
                consumer_account.debit_schedule(user_account_data, appointment_details.get("effective_price"))
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {"id": lab_appointment.id,
                            "type": diagnostic_serializer.LabAppointmentModelSerializer.LAB_TYPE}
        return resp
    
    def get_payment_details(self, request, appointment_details, product_id, order_id):
        pgdata = dict()
        payment_required = True
        user = request.user
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
        pgdata['appointmentId'] = ""
        pgdata['orderId'] = order_id
        pgdata['name'] = appointment_details["profile"].name
        pgdata['txAmount'] = appointment_details['payable_amount']

        return pgdata, payment_required

    def json_transform(self, app_data):
        app_data["price"] = str(app_data["price"])
        app_data["agreed_price"] = str(app_data["agreed_price"])
        app_data["deal_price"] = str(app_data["deal_price"])
        app_data["effective_price"] = str(app_data["effective_price"])
        app_data["time_slot_start"] = str(app_data["time_slot_start"])
        app_data["lab"] = app_data["lab"].id
        app_data["user"] = app_data["user"].id
        app_data["profile"] = app_data["profile"].id

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

    # def payment_retry(self, request, pk=None):
    #     queryset = LabAppointment.objects.filter(pk=pk)
    #     payment_response = dict()
    #     if queryset:
    #         serializer_data = LabAppointmentModelSerializer(queryset.first(), context={'request':request})
    #         payment_response = self.payment_details(request, serializer_data.data, 1)
    #     return Response(payment_response)

    # def update(self, request, pk):
    #     data = request.data
    #     lab_appointment_obj = get_object_or_404(LabAppointment, pk=pk)
    #     serializer = LabAppointmentUpdateSerializer(lab_appointment_obj, data=data,
    #                                                 context={'lab_id': lab_appointment_obj.lab})
    #     serializer.is_valid(raise_exception=True)
    #     # allowed = lab_appointment_obj.allowed_action(request.user.user_type)
    #     allowed = lab_appointment_obj.allowed_action(3)
    #     if data.get('status') not in allowed:
    #         resp = dict()
    #         resp['allowed'] = allowed
    #         return Response(resp, status=status.HTTP_400_BAD_REQUEST)
    #
    #     lab_appointment_queryset = serializer.save()
    #     serializer = LabAppointmentModelSerializer(lab_appointment_queryset)
    #     return Response(serializer.data)

    # def payment_details(self, request, appointment_details, product_id):
    #     details = dict()
    #     pgdata = dict()
    #     user = request.user
    #     user_profile = user.profiles.filter(is_default_user=True).first()
    #     pgdata['custId'] = user.id
    #     pgdata['mobile'] = user.phone_number
    #     pgdata['email'] = user.email
    #     if not user.email:
    #         pgdata['email'] = "dummy_appointment@policybazaar.com"
    #     base_url = (
    #         "https://{}".format(request.get_host()) if request.is_secure() else "http://{}".format(request.get_host()))
    #     pgdata['productId'] = product_id
    #     pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
    #     pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
    #     pgdata['checkSum'] = ''
    #     pgdata['appointmentId'] = appointment_details['id']
    #     if user_profile:
    #         pgdata['name'] = user_profile.name
    #     else:
    #         pgdata['name'] = "DummyName"
    #     pgdata['txAmount'] = appointment_details['price']
    #
    #     if pgdata:
    #         details['required'] = True
    #         details['pgdata'] = pgdata
    #     else:
    #         details['required'] = False
    #     return details


class LabTimingListView(mixins.ListModelMixin,
                        viewsets.GenericViewSet):

    # authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        params = request.query_params

        flag = True if int(params.get('pickup', 0)) else False
        queryset = LabTiming.objects.filter(lab=params.get('lab'), pickup_flag=flag)
        if not queryset:
            return Response([])

        obj = TimeSlotExtraction()

        for data in queryset:
            obj.form_time_slots(data.day, data.start, data.end, None, True)

        # resp_dict = obj.get_timing()
        resp_list = obj.get_timing_list()

        return Response(resp_list)


class AvailableTestViewSet(mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    queryset = AvailableLabTest.objects.all()
    serializer_class = diagnostic_serializer.AvailableLabTestSerializer

    def retrieve(self, request, lab_id):
        params = request.query_params
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id)

        if not queryset:
            raise Http404("No data available")

        if params.get('test_name'):
            search_key = re.findall(r'[a-z0-9A-Z.]+', params.get('test_name'))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            queryset = queryset.filter(test__search_key__icontains=search_key)

        queryset = queryset[:20]

        serializer = diagnostic_serializer.AvailableLabTestSerializer(queryset, many=True)
        return Response(serializer.data)


class TimeSlotExtraction(object):
    MORNING = "Morning"
    AFTERNOON = "Afternoon"
    EVENING = "Evening"
    TIME_SPAN = 15
    timing = dict()
    price_available = dict()

    def __init__(self):
        for i in range(7):
            self.timing[i] = dict()
            self.price_available[i] = dict()
        # self.extract_time_slot(queryset)

    # def extract_time_slot(self, queryset):
    #     for obj in queryset:
    #         self.form_time_slots(obj.day, obj.start, obj.end, obj.)

    def form_time_slots(self, day, start, end, price=None, is_available=True,
                        deal_price=None, mrp=None, is_doctor=False):
        start = float(start)
        end = float(end)
        # day = obj.day
        # timing = self.context['timing']
        time_span = self.TIME_SPAN

        int_span = (time_span / 60)
        # timing = dict()
        if not self.timing[day].get('timing'):
            self.timing[day]['timing'] = dict()
            self.timing[day]['timing'][self.MORNING] = OrderedDict()
            self.timing[day]['timing'][self.AFTERNOON] = OrderedDict()
            self.timing[day]['timing'][self.EVENING] = OrderedDict()

        num_slots = int(60 / time_span)
        if 60 % time_span != 0:
            num_slots += 1
        h = start
        while h < end:
        # for h in range(start, end):
            for i in range(0, num_slots):
                temp_h = h + i * int_span
                day_slot, am_pm = self.get_day_slot(temp_h)
                time_str = self.form_time_string(temp_h, am_pm)
                self.timing[day]['timing'][day_slot][temp_h] = time_str
                price_available = {"price": price, "is_available": is_available}
                if is_doctor:
                    price_available.update({
                        "mrp": mrp,
                        "deal_price": deal_price
                    })
                self.price_available[day][temp_h] = price_available
            h += 1

    def get_day_slot(self, time):
        am = 'AM'
        pm = 'PM'
        if time < 12:
            return self.MORNING, am
        elif time < 16:
            return self.AFTERNOON, pm
        else:
            return self.EVENING, pm

    def form_time_string(self, time, am_pm):

        day_time_hour = int(time)
        day_time_min = (time - day_time_hour) * 60

        if time >= 12:
            day_time_hour -= 12

        day_time_hour_str = str(int(day_time_hour))
        if int(day_time_hour) < 10:
            day_time_hour_str = '0' + str(int(day_time_hour))

        day_time_min_str = str(int(day_time_min))
        if int(day_time_min) < 10:
            day_time_min_str = '0' + str(int(day_time_min))

        time_str = day_time_hour_str + ":" + day_time_min_str + " " + am_pm

        return time_str

    def get_timing_list(self):
        whole_timing_data = dict()
        for i in range(7):
            whole_timing_data[i] = list()
            pa = self.price_available[i]
            if self.timing[i].get('timing'):
                # data = self.format_data(self.timing[i]['timing'][self.MORNING], pa)
                whole_timing_data[i].append(self.format_data(self.timing[i]['timing'][self.MORNING], self.MORNING, pa))
                whole_timing_data[i].append(self.format_data(self.timing[i]['timing'][self.AFTERNOON], self.AFTERNOON, pa))
                whole_timing_data[i].append(self.format_data(self.timing[i]['timing'][self.EVENING], self.EVENING, pa))

        return whole_timing_data

    def format_data(self, data, day_time, pa):
        data_list = list()
        for k, v in data.items():
            if 'mrp' in pa[k].keys() and 'deal_price' in pa[k].keys():
                data_list.append({"value": k, "text": v, "price": pa[k]["price"],
                                  "mrp": pa[k]['mrp'], 'deal_price': pa[k]['deal_price'],
                                  "is_available": pa[k]["is_available"]})
            else:
                data_list.append({"value": k, "text": v, "price": pa[k]["price"],
                                  "is_available": pa[k]["is_available"]})
        format_data = dict()
        format_data['title'] = day_time
        format_data['timing'] = data_list
        return format_data

