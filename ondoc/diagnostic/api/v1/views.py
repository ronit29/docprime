from .serializers import LabListSerializer, LabTestListSerializer, LabCustomSerializer, AvailableLabTestSerializer, \
    LabAppointmentModelSerializer, LabAppointmentCreateSerializer, LabAppointmentUpdateSerializer
from ondoc.diagnostic.models import LabTest, AvailableLabTest, Lab, LabAppointment
from ondoc.authentication.models import UserProfile

from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.authentication import TokenAuthentication

from django_filters.rest_framework import DjangoFilterBackend
from django_filters import filters

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Distance
from django.shortcuts import get_object_or_404

from django.db.models import Count, Sum, Max


class LabTestList(viewsets.ReadOnlyModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class = LabTestListSerializer
    lookup_field = 'id'
    filter_backends = (SearchFilter,)
    # filter_fields = ('name',)
    search_fields = ('name',)


class LabList(viewsets.ReadOnlyModelViewSet):
    # queryset = self.form_queryset()
    authentication_classes = (TokenAuthentication,)
    queryset = AvailableLabTest.objects.all()
    serializer_class = LabListSerializer
    lookup_field = 'id'
    # filter_backends = (DjangoFilterBackend, )
    # filter_fields = ('name', 'deal_price', )

    def list(self, request, **kwargs):
        parameters = request.query_params
        queryset = self.get_lab_list(parameters)

        serializer = LabCustomSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, lab_id):
        queryset = AvailableLabTest.objects.filter(lab=lab_id)
        # obj = get_object_or_404(queryset)
        serializer = AvailableLabTestSerializer(queryset, many=True)
        return Response(serializer.data)

    def get_lab_list(self, parameters):
        # allowed_ordering = ['price','distance',]
        ids = list(map(int, parameters.get("ids").split(",")))
        distance = 13514700

        default_long = -96.876369
        default_lat = 29.905320
        long = parameters.get('long', default_long)
        lat = parameters.get('lat', default_lat)
        point_string = 'POINT('+str(long)+' '+str(lat)+')'

        pnt = GEOSGeometry(point_string, srid=4326)

        queryset = (
            AvailableLabTest.objects.filter(lab__location__distance_lte=(pnt, distance)).filter(test__in=ids).values(
                'lab').annotate(price=Sum('mrp'),
                                count=Count('id'), distance=Max(
                    Distance('lab__location', pnt)), name=Max('lab__name')).filter(count__gte=len(ids)))

        queryset = self.apply_custom_filters(queryset, parameters)

        list_of_labs = list()
        lab_price_map = dict()
        for q in queryset:
            list_of_labs.append(int(q.get("lab")))
            lab_price_map[int(q.get("lab"))] = int(q.get("price"))

        return self.get_labs(list_of_labs, lab_price_map)

    @staticmethod
    def apply_custom_filters(queryset, parameters):
        price = parameters.get('price')
        order_by = parameters.get("order_by")
        if price:
            queryset = queryset.filter(price__lte=price)

        if order_by is not None:
            if order_by == "price":
                queryset = queryset.order_by("price")
            elif order_by == 'distance':
                queryset = queryset.order_by("distance")
            elif order_by == 'name':
                queryset = queryset.order_by("name")
        return queryset

    @staticmethod
    def get_labs(list_of_labs, lab_price_map):
        lab_queryset = Lab.objects.filter(id__in=list_of_labs)
        for q in lab_queryset:
            index = list_of_labs.index(q.id)
            list_of_labs[index] = {"lab": q, "price": lab_price_map[q.id]}
        return list_of_labs


class LabAppointmentView(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    queryset = LabAppointment.objects.all()
    serializer_class = LabAppointmentModelSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('profile', 'lab',)

    def list(self, request, *args, **kwargs):
        queryset = LabAppointment.objects.filter(profile=request.user)
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
        lab_appointment_obj = LabAppointment.objects.get(pk=pk)
        serializer = LabAppointmentUpdateSerializer(lab_appointment_obj, data=request.data,
                                                    context={'lab_id': lab_appointment_obj.lab})
        serializer.is_valid(raise_exception=True)

        lab_appointment_queryset = serializer.save()
        serializer = LabAppointmentModelSerializer(lab_appointment_queryset)
        return Response(serializer.data)


