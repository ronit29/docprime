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
from ondoc.api.v1.utils import form_time_slot, IsConsumer, labappointment_transform, payment_details
from ondoc.api.pagination import paginate_queryset

from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Distance
from django.shortcuts import get_object_or_404

from django.db import transaction
from django.db.models import Count, Sum, Max, When, Case, F, Q
from django.http import Http404
from django.conf import settings
import hashlib
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
        lab_queryset = PromotedLab.objects.select_related('lab').filter(lab__is_live=True, lab__is_test_lab=False)
        test_serializer = diagnostic_serializer.CommonTestSerializer(test_queryset, many=True, context={'request': request})
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
            test_queryset = LabTest.objects.filter(
                Q(search_key__icontains=" " + search_key) | Q(search_key__istartswith=search_key))
            test_queryset = paginate_queryset(test_queryset, request)
            lab_queryset = Lab.objects.filter(is_live=True, is_test_lab=False).filter(
                Q(search_key__icontains=" " + search_key) | Q(search_key__istartswith=search_key)
            )
            lab_queryset = paginate_queryset(lab_queryset, request)
        else:
            test_queryset = self.queryset[:20]
            lab_queryset = Lab.objects.filter(is_live=True)[:20]

        test_serializer = diagnostic_serializer.LabTestListSerializer(test_queryset, many=True)
        lab_serializer = diagnostic_serializer.LabListSerializer(lab_queryset, many=True)
        temp_data['tests'] = test_serializer.data
        temp_data['labs'] = lab_serializer.data
        return Response(temp_data)


class LabList(viewsets.ReadOnlyModelViewSet):
    queryset = AvailableLabTest.objects.all()
    serializer_class = diagnostic_serializer.LabModelSerializer
    lookup_field = 'id'

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
        queryset = AvailableLabTest.objects.select_related().filter(lab_pricing_group__labs__id=lab_id,
                                                                    lab_pricing_group__labs__is_test_lab=False,
                                                                    lab_pricing_group__labs__is_live=True,
                                                                    test__in=test_ids)
        lab_obj = Lab.objects.filter(id=lab_id, is_live=True).first()
        test_serializer = diagnostic_serializer.AvailableLabTestSerializer(queryset, many=True,
                                                                           context={"lab": lab_obj})
        day_now = timezone.now().weekday()
        timing_queryset = list()
        lab_serializable_data = list()
        lab_timing = None
        lab_timing_data = list()
        if lab_obj:
            if lab_obj.always_open:
                lab_timing = "7:00 AM - 7:00 PM"
                lab_timing_data = [{
                    "start": 7.0,
                    "end": 19.0
                }]
            else:
                timing_queryset = lab_obj.lab_timings.filter(day=day_now)
                lab_timing, lab_timing_data = self.get_lab_timing(timing_queryset)
            lab_serializer = diagnostic_serializer.LabModelSerializer(lab_obj, context={"request": request})
            lab_serializable_data = lab_serializer.data
        temp_data = dict()
        temp_data['lab'] = lab_serializable_data
        temp_data['tests'] = test_serializer.data
        temp_data['lab_timing'], temp_data["lab_timing_data"] = lab_timing, lab_timing_data

        return Response(temp_data)

    def get_lab_timing(self, queryset):
        lab_timing = ''
        lab_timing_data = list()
        temp_list = list()
        for qdata in queryset:
            temp_list.append({"start": qdata.start, "end": qdata.end})

        temp_list = sorted(temp_list, key=lambda k: k["start"])

        index = 0
        while index < len(temp_list):
            temp_dict = dict()
            x = index
            if not lab_timing:
                lab_timing += self.convert_time(temp_list[index]["start"]) + " - "
            else:
                lab_timing += " | " + self.convert_time(temp_list[index]["start"]) + " - "
            temp_dict["start"] = temp_list[index]["start"]
            while x + 1 < len(temp_list) and temp_list[x]["end"] >= temp_list[x+1]["start"]:
                x += 1
            index = x
            lab_timing += self.convert_time(temp_list[index]["end"])
            temp_dict["end"] = temp_list[index]["end"]
            lab_timing_data.append(temp_dict)
            index += 1

        return lab_timing, lab_timing_data

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

        DEFAULT_DISTANCE = 20000
        MAX_SEARCHABLE_DISTANCE = 50000

        default_long = 77.071848
        default_lat = 28.450367
        min_distance = parameters.get('min_distance')
        max_distance = parameters.get('max_distance')*1000 if parameters.get('max_distance') else DEFAULT_DISTANCE
        max_distance = min(max_distance, MAX_SEARCHABLE_DISTANCE)
        long = parameters.get('long', default_long)
        lat = parameters.get('lat', default_lat)
        ids = parameters.get('ids', [])
        min_price = parameters.get('min_price')
        max_price = parameters.get('max_price')
        name = parameters.get('name')

        # queryset = AvailableLabTest.objects.select_related('lab').exclude(enabled=False).filter(lab_pricing_group__labs__is_live=True,
        #                                                                                         lab_pricing_group__labs__is_test_lab=False)
        queryset = Lab.objects.select_related().filter(is_test_lab=False, is_live=True,
                                                       lab_pricing_group__isnull=False)

        if lat is not None and long is not None:
            point_string = 'POINT('+str(long)+' '+str(lat)+')'
            pnt = GEOSGeometry(point_string, srid=4326)
            queryset = queryset.filter(location__distance_lte=(pnt, max_distance))
            if min_distance:
                min_distance = min_distance*1000  # input is  coming in km
                queryset = queryset.filter(location__distance_gte=(pnt, min_distance))

        if name:
            queryset = queryset.filter(name__icontains=name)

        if ids:
            queryset = queryset.filter(lab_pricing_group__available_lab_tests__test_id__in=ids,
                lab_pricing_group__available_lab_tests__enabled=True)


        if ids:
            deal_price_calculation = Case(When(lab_pricing_group__available_lab_tests__custom_deal_price__isnull=True,
                                               then=F('lab_pricing_group__available_lab_tests__computed_deal_price')),
                                          When(lab_pricing_group__available_lab_tests__custom_deal_price__isnull=False,
                                               then=F('lab_pricing_group__available_lab_tests__custom_deal_price')))

            queryset = (
                queryset.values('id').annotate(price=Sum(deal_price_calculation),
                                               count=Count('id'),
                                               distance=Max(Distance('location', pnt)),
                                               name=Max('name')).filter(count__gte=len(ids)))
            if min_price:
                queryset = queryset.filter(price__gte=min_price)

            if max_price:
                queryset = queryset.filter(price__lte=max_price)

        else:
            queryset = queryset.annotate(distance=Distance('location', pnt)).values('id', 'name', 'distance')
            # queryset = (
            #     queryset.values('lab_pricing_group__labs__id'
            #                     ).annotate(count=Count('id'),
            #                                distance=Max(Distance('lab_pricing_group__labs__location', pnt)),
            #                                name=Max('lab_pricing_group__labs__name')).filter(count__gte=len(ids)))

        queryset = self.apply_sort(queryset, parameters)
        return queryset

    @staticmethod
    def apply_sort(queryset, parameters):
        order_by = parameters.get("order_by")
        if order_by is not None:
            if order_by == "fees" and parameters.get('ids'):
                queryset = queryset.order_by("price", "distance")
            elif order_by == 'distance':
                queryset = queryset.order_by("distance")
            elif order_by == 'name':
                queryset = queryset.order_by("name")
            else:
                queryset = queryset.order_by("distance")
        else:
            queryset = queryset.order_by("distance")
        return queryset

    def form_lab_whole_data(self, queryset):
        ids = [value.get('id') for value in queryset]
        # ids, id_details = self.extract_lab_ids(queryset)
        labs = Lab.objects.prefetch_related('lab_documents', 'lab_image', 'lab_timings').filter(id__in=ids)
        resp_queryset = list()
        temp_var = dict()
        for obj in labs:
            temp_var[obj.id] = obj
        day_now = timezone.now().weekday()
        for row in queryset:
            row["lab"] = temp_var[row["id"]]

            if row["lab"].always_open:
                lab_timing = "00:00 AM - 23:45 PM"
                lab_timing_data = [{
                    "start": 0.0,
                    "end": 23.75
                }]
            else:
                timing_queryset = row["lab"].lab_timings.all()
                timing_data = list()
                for data in timing_queryset:
                    if data.day == day_now:
                        timing_data.append(data)
                lab_timing, lab_timing_data = self.get_lab_timing(timing_data)
            lab_timing_data = sorted(lab_timing_data, key=lambda k: k["start"])
            row["lab_timing"] = lab_timing
            row["lab_timing_data"] = lab_timing_data
            resp_queryset.append(row)

        return resp_queryset

    def extract_lab_ids(self, queryset):
        ids = list()
        temp_dict = dict()
        for obj in queryset:
            ids.append(obj['lab_pricing_group__labs__id'])
            temp_dict[obj['lab_pricing_group__labs__id']] = obj
        return ids, temp_dict


class LabAppointmentView(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    queryset = LabAppointment.objects.all()
    serializer_class = diagnostic_serializer.LabAppointmentModelSerializer
    authentication_classes = (TokenAuthentication, )
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
        lab_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab_pricing_group__labs').annotate(total_mrp=Sum("mrp"),
                                                                                     total_deal_price=Sum(
                                                                                         deal_price_calculation),
                                                                                     total_agreed_price=Sum(
                                                                                         agreed_price_calculation))
        total_agreed = total_deal_price = total_mrp = effective_price = home_pickup_charges = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_agreed = temp_lab_test[0].get("total_agreed_price", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)
            effective_price = total_deal_price
            if data["is_home_pickup"] and data["lab"].is_home_collection_enabled:
                effective_price += data["lab"].home_pickup_charges
                home_pickup_charges = data["lab"].home_pickup_charges
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
            "home_pickup_charges": home_pickup_charges,
            "time_slot_start": start_dt,
            "is_home_pickup": data["is_home_pickup"],
            "profile_detail": profile_detail,
            "status": LabAppointment.BOOKED,
            "payment_type": data["payment_type"],
            "lab_test": [x["id"] for x in lab_test_queryset.values("id")]
        }
        if data.get("is_home_pickup") is True:
            address = Address.objects.filter(pk=data.get("address").id).first()
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
            appointment_details["effective_price"] += appointment_details["home_pickup_charges"]
            appointment_details['payment_type'] = doctor_model.OpdAppointment.INSURANCE
        elif appointment_details['payment_type'] == doctor_model.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp

        temp_appointment_details = copy.deepcopy(appointment_details)
        temp_appointment_details = labappointment_transform(temp_appointment_details)

        account_models.Order.disable_pending_orders(temp_appointment_details, product_id,
                                                    account_models.Order.LAB_APPOINTMENT_CREATE)

        if request.agent:
            balance = 0
        if ((appointment_details['payment_type'] == doctor_model.OpdAppointment.PREPAID and
                balance < appointment_details.get("effective_price")) or request.agent):

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
            resp['data'], resp['payment_required'] = payment_details(request, order)
            # resp['data'], resp['payment_required'] = self.get_payment_details(request, appointment_details, product_id,order.id)
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


class LabTimingListView(mixins.ListModelMixin,
                        viewsets.GenericViewSet):

    # authentication_classes = (TokenAuthentication,)
    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        params = request.query_params

        for_home_pickup = True if int(params.get('pickup', 0)) else False
        lab = params.get('lab')
        lab_queryset = Lab.objects.filter(pk=lab, is_live=True).prefetch_related('lab_timings').first()
        if not lab_queryset or (for_home_pickup and not lab_queryset.is_home_collection_enabled):
            return Response([])

        obj = TimeSlotExtraction()

        if not for_home_pickup and lab_queryset.always_open:
            for day in range(0, 7):
                obj.form_time_slots(day, 0.0, 23.45, None, True)
        # New condition for home pickup timing from 7 to 7
        elif for_home_pickup:
            for day in range(0, 7):
                obj.form_time_slots(day, 7.0, 19.0, None, True)
        else:
            lab_timing_queryset = lab_queryset.lab_timings.all()
            for data in lab_timing_queryset:
                if for_home_pickup == data.for_home_pickup:
                    obj.form_time_slots(data.day, data.start, data.end, None, True)

        resp_list = obj.get_timing_list()
        return Response(resp_list)


class AvailableTestViewSet(mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs__is_live=True).all()
    serializer_class = diagnostic_serializer.AvailableLabTestSerializer

    def retrieve(self, request, lab_id):
        params = request.query_params
        queryset = AvailableLabTest.objects.select_related().filter(lab_pricing_group__labs=lab_id, lab_pricing_group__labs__is_live=True, enabled=True)
        if not queryset:
            return Response([])
        lab_obj = Lab.objects.filter(pk=lab_id).first()
        if params.get('test_name'):
            search_key = re.findall(r'[a-z0-9A-Z.]+', params.get('test_name'))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            queryset = queryset.filter(
                Q(test__search_key__istartswith=search_key) | Q(test__search_key__icontains=" "+search_key))

        queryset = queryset[:20]

        serializer = diagnostic_serializer.AvailableLabTestSerializer(queryset, many=True,
                                                                      context={"lab": lab_obj})
        return Response(serializer.data)


class TimeSlotExtraction(object):
    MORNING = "Morning"
    AFTERNOON = "Afternoon"
    EVENING = "Evening"
    TIME_SPAN = 15  # In minutes
    timing = dict()
    price_available = dict()

    def __init__(self):
        for i in range(7):
            self.timing[i] = dict()
            self.price_available[i] = dict()

    def form_time_slots(self, day, start, end, price=None, is_available=True,
                        deal_price=None, mrp=None, is_doctor=False):
        start = float(start)
        end = float(end)
        time_span = self.TIME_SPAN

        float_span = (time_span / 60)
        if not self.timing[day].get('timing'):
            self.timing[day]['timing'] = dict()
            self.timing[day]['timing'][self.MORNING] = OrderedDict()
            self.timing[day]['timing'][self.AFTERNOON] = OrderedDict()
            self.timing[day]['timing'][self.EVENING] = OrderedDict()
        temp_start = start
        while temp_start <= end:
            day_slot, am_pm = self.get_day_slot(temp_start)
            time_str = self.form_time_string(temp_start, am_pm)
            self.timing[day]['timing'][day_slot][temp_start] = time_str
            price_available = {"price": price, "is_available": is_available}
            if is_doctor:
                price_available.update({
                    "mrp": mrp,
                    "deal_price": deal_price
                })
            self.price_available[day][temp_start] = price_available
            temp_start += float_span

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

        if day_time_hour > 12:
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

