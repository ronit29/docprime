from .serializers import (LabModelSerializer, LabTestListSerializer, LabCustomSerializer, AvailableLabTestSerializer,
                          LabAppointmentModelSerializer, LabAppointmentCreateSerializer,
                          LabAppointmentUpdateSerializer, LabListSerializer, CommonTestSerializer,
                          PromotedLabsSerializer, CommonConditionsSerializer, TimeSlotSerializer,
                          AddressSerializer, SearchLabListSerializer)
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest)
from ondoc.authentication.models import UserProfile, Address

from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend
from django_filters import filters

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Distance
from django.shortcuts import get_object_or_404

from django.db.models import Count, Sum, Max
from django.http import Http404
from rest_framework import status
from collections import OrderedDict
from django.utils import timezone
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
        test_queryset = LabTest.objects.all()
        lab_queryset = Lab.objects.all()
        temp_data = dict()
        if name:
            test_queryset = test_queryset.filter(name__icontains=name)
            lab_queryset = lab_queryset.filter(name__icontains=name)
            test_serializer = LabTestListSerializer(test_queryset, many=True)
            lab_serializer = LabListSerializer(lab_queryset, many=True)
            temp_data['tests'] = test_serializer.data
            temp_data['labs'] = lab_serializer.data

        return Response(temp_data)


class LabList(viewsets.ReadOnlyModelViewSet):
    # queryset = self.form_queryset()
    authentication_classes = (TokenAuthentication,)
    queryset = AvailableLabTest.objects.all()
    serializer_class = LabModelSerializer
    lookup_field = 'id'
    # filter_backends = (DjangoFilterBackend, )
    # filter_fields = ('name', 'deal_price', )

    def list(self, request, **kwargs):
        parameters = request.query_params
        queryset = self.get_lab_list(parameters)

        whole_queryset = self.form_lab_whole_data(queryset)

        serializer = LabCustomSerializer(whole_queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, lab_id):
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id)

        if len(queryset) == 0:
            raise Http404("No labs available")

        test_serializer = AvailableLabTestSerializer(queryset, many=True)
        lab_queryset = queryset[0].lab
        day_now = timezone.now().weekday()
        timing_queryset = lab_queryset.labtiming_set.filter(day=day_now)
        lab_serializer = LabModelSerializer(lab_queryset)
        temp_data = dict()
        temp_data['lab'] = lab_serializer.data
        temp_data['tests'] = test_serializer.data
        temp_data['lab_timing'] = ''
        temp_data['lab_timing'] = self.get_lab_timing(timing_queryset)

        return Response(temp_data)
        # return Response(serializer.data)

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

        if min_price:
            queryset = queryset.filter(mrp__gte=min_price)

        if max_price:
            queryset = queryset.filter(mrp__lte=max_price)

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
        for obj in labs:
            temp_var = id_details[obj.id]
            temp_var['lab'] = obj
            resp_queryset.append(temp_var)

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
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('profile', 'lab',)

    def list(self, request, *args, **kwargs):
        user = request.user
        queryset = LabAppointment.objects.filter(profile__user=user)
        serializer = LabAppointmentModelSerializer(queryset, many=True)
        return Response(serializer.data)

    # def retrieve(self, request, app_id, **kwargs):
    #     queryset = LabAppointment.objects.get(pk=app_id)
    #     serializer = LabAppointmentModelSerializer(queryset)
    #     return Response(serializer.data)

    def create(self, request, **kwargs):
        serializer = LabAppointmentCreateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        lab_appointment_queryset = serializer.save()
        serializer = LabAppointmentModelSerializer(lab_appointment_queryset)
        return Response(serializer.data)

    def update(self, request, pk):
        data = request.data
        lab_appointment_obj = get_object_or_404(LabAppointment, pk=pk)
        # lab_appointment_obj = LabAppointment.objects.get(pk=pk)
        serializer = LabAppointmentUpdateSerializer(lab_appointment_obj, data=data,
                                                    context={'lab_id': lab_appointment_obj.lab})
        serializer.is_valid(raise_exception=True)
        # allowed = lab_appointment_obj.allowed_action(request.user.user_type)
        allowed = lab_appointment_obj.allowed_action(3)
        if data.get('status') not in allowed:
            resp = dict()
            resp['allowed'] = allowed
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        lab_appointment_queryset = serializer.save()
        serializer = LabAppointmentModelSerializer(lab_appointment_queryset)
        return Response(serializer.data)


class AddressViewsSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        request = self.request
        return Address.objects.filter(user=request.user)

    def create(self, request, *args, **kwargs):
        data = dict(request.data)
        data["user"] = request.user.id
        serializer = AddressSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        address = Address.objects.filter(pk=pk).first()
        address.delete()
        return Response({
            "status": 1
        })


class LabTimingListView(mixins.ListModelMixin,
                        viewsets.GenericViewSet):

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        params = request.query_params

        flag = True if int(params.get('pickup', 0)) else False
        queryset = LabTiming.objects.filter(lab=params.get('lab'), pickup_flag=flag)
        if not queryset:
            return Response([])

        obj = LabSlotExtraction(queryset)

        # resp_dict = obj.get_timing()
        resp_list = obj.get_timing_list()

        return Response(resp_list)


class AvailableTestViewSet(mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    queryset = AvailableLabTest.objects.all()
    serializer_class = AvailableLabTestSerializer

    def retrive(self, request, lab_id):
        params = request.query_params
        queryset = AvailableLabTest.objects.select_related().filter(lab=lab_id)

        if not queryset:
            raise Http404("No data available")

        if params.get('test_name'):
            queryset = queryset.filter(test__name__contains=params['test_name'])

        queryset = queryset[:20]

        serializer = AvailableLabTestSerializer(queryset, many=True)
        return Response(serializer.data)


class LabSlotExtraction(object):
    MORNING = 0
    AFTERNOON = 1
    EVENING = 2
    TIME_SPAN = 15
    timing = dict()

    def __init__(self, queryset):
        for i in range(7):
            self.timing[i] = dict()
        self.extract_time_slot(queryset)

    def extract_time_slot(self, queryset):
        for obj in queryset:
            self.fetch_time_slot(obj)

    def fetch_time_slot(self, obj):
        start = obj.start
        end = obj.end
        time_span = self.TIME_SPAN
        day = obj.day
        # timing = self.context['timing']

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
        for h in range(start, end):
            for i in range(0, num_slots):
                temp_h = h + i * int_span
                day_slot, am_pm = self.get_day_slot(temp_h)
                time_str = self.form_time_string(temp_h, am_pm)
                self.timing[day]['timing'][day_slot][temp_h] = time_str

    def get_day_slot(self, hour):
        am = 'AM'
        pm = 'PM'
        if hour < 12:
            return self.MORNING, am
        elif hour < 16:
            return self.AFTERNOON, pm
        else:
            return self.EVENING, pm

    def form_time_string(self, time, am_pm):

        day_time_hour = int(time)
        day_time_min = (time - day_time_hour) * 60

        if time >= 12:
            day_time_hour -= 12

        day_time_hour_str = str(int(day_time_hour))
        if int(day_time_hour) / 10 < 1:
            day_time_hour_str = '0' + str(int(day_time_hour))

        day_time_min_str = str(int(day_time_min))
        if int(day_time_min) / 10 < 1:
            day_time_min_str = '0' + str(int(day_time_min))

        time_str = day_time_hour_str + ":" + day_time_min_str + " " + am_pm

        return time_str

    def get_timing_list(self):
        for i in range(7):
            if self.timing[i].get('timing'):
                temp_list = list()
                temp_list = [[k, v] for k, v in self.timing[i]['timing'][0].items()]
                self.timing[i]['timing'][0] = temp_list
                temp_list = [[k, v] for k, v in self.timing[i]['timing'][1].items()]
                self.timing[i]['timing'][1] = temp_list
                temp_list = [[k, v] for k, v in self.timing[i]['timing'][2].items()]
                self.timing[i]['timing'][2] = temp_list
        return self.timing
