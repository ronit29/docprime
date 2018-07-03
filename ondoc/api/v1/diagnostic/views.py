from .serializers import (LabModelSerializer, LabTestListSerializer, LabCustomSerializer, AvailableLabTestSerializer,
                          LabAppointmentModelSerializer, LabAppointmentCreateSerializer,
                          LabAppointmentUpdateSerializer, LabListSerializer, CommonTestSerializer,
                          PromotedLabsSerializer, CommonConditionsSerializer, TimeSlotSerializer,
                          SearchLabListSerializer, LabProfileSerializer)
from ondoc.api.v1.auth.serializers import AddressSerializer

from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest)
from ondoc.account import models as account_models
from ondoc.authentication.models import UserProfile, Address
from ondoc.doctor import models as doctor_model
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.utils import form_time_slot
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


class SearchPageViewSet(viewsets.ReadOnlyModelViewSet):

    def list(self, request, *args, **kwargs):
        test_queryset = CommonTest.objects.all()
        conditions_queryset = CommonDiagnosticCondition.objects.all()
        lab_queryset = PromotedLab.objects.all()
        test_serializer = CommonTestSerializer(test_queryset, many=True)
        lab_serializer = PromotedLabsSerializer(lab_queryset, many=True)
        condition_serializer = CommonConditionsSerializer(conditions_queryset, many=True)
        temp_data = dict()
        temp_data['common_tests'] = test_serializer.data
        temp_data['preferred_labs'] = lab_serializer.data
        temp_data['common_conditions'] = condition_serializer.data

        return Response(temp_data)


class LabTestList(viewsets.ReadOnlyModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class = LabTestListSerializer
    lookup_field = 'id'
    filter_backends = (SearchFilter,)
    # filter_fields = ('name',)
    search_fields = ('name',)

    def list(self, request, *args, **kwargs):
        name = request.query_params.get('name')
        temp_data = dict()
        if name:
            test_queryset = LabTest.objects.filter(name__icontains=name)
            lab_queryset = Lab.objects.filter(name__icontains=name)
            test_serializer = LabTestListSerializer(test_queryset, many=True)
            lab_serializer = LabListSerializer(lab_queryset, many=True)
            temp_data['tests'] = test_serializer.data
            temp_data['labs'] = lab_serializer.data

        return Response(temp_data)


class LabList(viewsets.ReadOnlyModelViewSet):
    # queryset = self.form_queryset()
    queryset = AvailableLabTest.objects.all()
    serializer_class = LabModelSerializer
    lookup_field = 'id'
    # filter_backends = (DjangoFilterBackend, )
    # filter_fields = ('name', 'deal_price', )

    def list(self, request, **kwargs):
        parameters = request.query_params
        queryset = self.get_lab_list(parameters)
        count = queryset.count()
        paginated_queryset = paginate_queryset(queryset, request)
        response_queryset = self.form_lab_whole_data(paginated_queryset)
        serializer = LabCustomSerializer(response_queryset, many=True,
                                         context={"request": request})
        return Response({"result": serializer.data,
                         "count": count})

    def retrieve(self, request, lab_id):
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id)

        if len(queryset) == 0:
            raise Http404("No labs available")

        test_serializer = AvailableLabTestSerializer(queryset, many=True)
        lab_queryset = queryset[0].lab
        day_now = timezone.now().weekday()
        timing_queryset = lab_queryset.labtiming_set.filter(day=day_now)
        lab_serializer = LabProfileSerializer(lab_queryset, context={"request": request})
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
        serializer = SearchLabListSerializer(data=parameters)
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

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        queryset = self.apply_custom_filters(queryset, parameters)
        return queryset

    @staticmethod
    def apply_custom_filters(queryset, parameters):
        order_by = parameters.get("order_by")
        if order_by is not None:
            if order_by == "price" and parameters.get('ids'):
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
    serializer_class = LabAppointmentModelSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('profile', 'lab',)

    def list(self, request, *args, **kwargs):
        user = request.user
        queryset = LabAppointment.objects.filter(profile__user=user)
        serializer = LabAppointmentModelSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, **kwargs):
        serializer = LabAppointmentCreateSerializer(data=request.data, context={'request': request})
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
            "lab": data["lab"].id,
            "user": request.user.id,
            "profile": data["profile"].id,
            "price": total_mrp,
            "agreed_price": total_agreed,
            "deal_price": total_deal_price,
            "effective_price": effective_price,
            "time_slot_start": str(start_dt),
            "profile_detail": profile_detail,
            # "payment_status": OpdAppointment.PAYMENT_ACCEPTED,
            "status": LabAppointment.BOOKED,
            "payment_type": data["payment_type"],
            # "test_ids": data["test_ids"]
            "lab_test": [x["id"] for x in lab_test_queryset.values("id")]
            # "otp": otp
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
        effective_price = appointment_details["effective_price"]

        insured_cod_flag = self.is_insured_cod(appointment_details)

        if insured_cod_flag or balance >= effective_price:
            otp = random.randint(1000, 9999)
            appointment_details["otp"] = otp
            appointment_details["payment_status"] = doctor_model.OpdAppointment.PAYMENT_ACCEPTED
            appointment_details["status"] = doctor_model.OpdAppointment.BOOKED
            lab_serializer = LabAppointmentModelSerializer(data=appointment_details)
            lab_serializer.is_valid(raise_exception=True)
            lab_appointment = lab_serializer.save()

            user_account_data = {
                "user": user,
                "product_id": product_id,
                "reference_id": lab_appointment.id
            }
            lab_appointment_data = LabAppointmentModelSerializer(lab_appointment).data
            if not insured_cod_flag:
                consumer_account.debit_schedule(user_account_data, effective_price)
            resp["status"] = 1
            resp["data"] = {"id": lab_appointment_data.get("id"), "type": lab_appointment_data.get("type")}
        else:
            appointment_details["effective_price"] = effective_price
            account_models.Order.disable_pending_orders(appointment_details, product_id,
                                                        account_models.Order.LAB_APPOINTMENT_CREATE)
            temp_appointment_details = copy.deepcopy(appointment_details)
            temp_appointment_details["price"] = str(appointment_details["price"])
            temp_appointment_details["agreed_price"] = str(appointment_details["agreed_price"])
            temp_appointment_details["deal_price"] = str(appointment_details["deal_price"])
            temp_appointment_details["effective_price"] = str(appointment_details["effective_price"])

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.LAB_APPOINTMENT_CREATE,
                action_data=temp_appointment_details,
                amount=effective_price - balance,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            appointment_details["payable_amount"] = effective_price - balance
            resp['pg_details'] = self.get_payment_details(request, appointment_details, product_id, order.id)
        return resp

    def get_payment_details(self, request, appointment_details, product_id, order_id):
        details = dict()
        pgdata = dict()
        if appointment_details["payable_amount"] != 0:
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
            pgdata['appointmentId'] = ""
            pgdata['order_id'] = order_id
            if user_profile:
                pgdata['name'] = user_profile.name
            else:
                pgdata['name'] = "DummyName"
            pgdata['txAmount'] = appointment_details['payable_amount']

        if pgdata:
            details['required'] = True
            details['pgdata'] = pgdata
        else:
            details['required'] = False

        return details

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
    serializer_class = AvailableLabTestSerializer

    def retrieve(self, request, lab_id):
        params = request.query_params
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id)

        if not queryset:
            raise Http404("No data available")

        if params.get('test_name'):
            queryset = queryset.filter(test__name__contains=params['test_name'])

        queryset = queryset[:20]

        serializer = AvailableLabTestSerializer(queryset, many=True)
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

    def form_time_slots(self, day, start, end, price=None, is_available=True):
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
                self.price_available[day][temp_h] = {"price": price, "is_available": is_available}
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
            data_list.append({"value": k, "text": v, "price": pa[k]["price"], "is_available": pa[k]["is_available"]})
        format_data = dict()
        format_data['title'] = day_time
        format_data['timing'] = data_list
        return format_data

