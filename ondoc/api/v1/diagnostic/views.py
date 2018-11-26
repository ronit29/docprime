from ondoc.authentication.backends import JWTAuthentication
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.api.v1.auth.serializers import AddressSerializer

from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest, CommonPackage, QuestionAnswer,
                                     FrequentlyAddedTogetherTests, TestParameter, ParameterLabTest)
from ondoc.account import models as account_models
from ondoc.authentication.models import UserProfile, Address
from ondoc.notification.models import EmailNotification
from ondoc.coupon.models import Coupon
from ondoc.doctor import models as doctor_model
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.utils import form_time_slot, IsConsumer, labappointment_transform, IsDoctor, payment_details, aware_time_zone, get_lab_search_details, TimeSlotExtraction
from ondoc.api.pagination import paginate_queryset

from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from ondoc.authentication.backends import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Distance
from django.shortcuts import get_object_or_404

from django.db import transaction
from django.db.models import Count, Sum, Max, When, Case, F, Q, Value, DecimalField, IntegerField
from django.http import Http404
from django.conf import settings
import hashlib
from rest_framework import status
from django.utils import timezone
from ondoc.diagnostic import models
from ondoc.authentication import models as auth_models
from django.db.models import Q, Value
from django.db.models.functions import StrIndex

from ondoc.location.models import EntityUrls, EntityAddress
from . import serializers
import copy
import re
import datetime
from django.contrib.auth import get_user_model
from ondoc.matrix.tasks import push_order_to_matrix
User = get_user_model()


class SearchPageViewSet(viewsets.ReadOnlyModelViewSet):

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        count = request.query_params.get('count', 10)
        count = int(count)
        if count <= 0:
            count = 10
        test_queryset = CommonTest.objects.all()[:count]
        conditions_queryset = CommonDiagnosticCondition.objects.prefetch_related('lab_test').all()
        lab_queryset = PromotedLab.objects.select_related('lab').filter(lab__is_live=True, lab__is_test_lab=False)
        package_queryset = CommonPackage.objects.prefetch_related('package').all()[:count]
        test_serializer = diagnostic_serializer.CommonTestSerializer(test_queryset, many=True, context={'request': request})
        package_serializer = diagnostic_serializer.CommonPackageSerializer(package_queryset, many=True, context={'request': request})
        lab_serializer = diagnostic_serializer.PromotedLabsSerializer(lab_queryset, many=True)
        condition_serializer = diagnostic_serializer.CommonConditionsSerializer(conditions_queryset, many=True)
        temp_data = dict()
        temp_data['common_tests'] = test_serializer.data
        temp_data['common_package'] = package_serializer.data
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

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        name = request.query_params.get('name')
        temp_data = dict()
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            test_queryset = LabTest.objects.filter(
                Q(search_key__icontains=search_key) |
                Q(search_key__icontains=' ' + search_key) |
                Q(search_key__istartswith=search_key)).annotate(search_index=StrIndex('search_key', Value(search_key))).order_by(
                'search_index')
            test_queryset = paginate_queryset(test_queryset, request)
            lab_queryset = Lab.objects.filter(is_live=True, is_test_lab=False).filter(
                Q(search_key__icontains=search_key) |
                Q(search_key__icontains=' ' + search_key) |
                Q(search_key__istartswith=search_key)).annotate(search_index=StrIndex('search_key', Value(search_key))).order_by(
                'search_index')
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

    @transaction.non_atomic_requests
    def list_by_url(self, request, *args, **kwargs):
        url = request.GET.get('url', None)
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        entity_url_qs = EntityUrls.objects.filter(url=url, url_type=EntityUrls.UrlType.SEARCHURL,
                                                  entity_type__iexact='Lab').order_by('-sequence')
        if entity_url_qs.exists():
            entity = entity_url_qs.first()
            if not entity.is_valid:
                valid_qs = EntityUrls.objects.filter(url_type=EntityUrls.UrlType.SEARCHURL, is_valid=True,
                                                     entity_type__iexact='Lab', locality_id=entity.locality_id,
                                                     sublocality_id=entity.sublocality_id,
                                                     sitemap_identifier=entity.sitemap_identifier).order_by('-sequence')

                if valid_qs.exists():
                    corrected_url = valid_qs.first().url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

            extras = entity.additional_info
            if extras.get('location_json'):
                kwargs['location_json'] = extras.get('location_json')
                kwargs['url'] = url
                kwargs['parameters'] = get_lab_search_details(extras, request.query_params)
                response = self.list(request, **kwargs)
                return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def retrieve_by_url(self, request):

        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        entity = EntityUrls.objects.filter(url=url, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).order_by('-is_valid')
        if len(entity) > 0:
            entity = entity[0]
            if not entity.is_valid:
                valid_entity_url_qs = EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE, entity_id=entity.entity_id,
                                                                is_valid='t')
                if valid_entity_url_qs.exists():
                    corrected_url = valid_entity_url_qs[0].url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_404_NOT_FOUND)

            #entity_id = entity.entity_id
            response = self.retrieve(request, entity.entity_id, None, entity)
            return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def retrieve_test_by_url(self, request):

        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        entity = EntityUrls.objects.filter(url=url, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_TEST).order_by('-is_valid')
        if len(entity) > 0:
            entity = entity[0]
            if not entity.is_valid:
                valid_entity_url_qs = EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_TEST, entity_id=entity.entity_id,
                                                                is_valid='t')
                if valid_entity_url_qs.exists():
                    corrected_url = valid_entity_url_qs[0].url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_404_NOT_FOUND)

            response = self.retrieve(request, None, entity.entity_id , None)
            return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def list(self, request, **kwargs):
        parameters = request.query_params
        if kwargs.get('parameters'):
            parameters = kwargs.get('parameters')

        serializer = diagnostic_serializer.SearchLabListSerializer(data=parameters)

        serializer.is_valid(raise_exception=True)
        if kwargs.get('location_json'):
            serializer.validated_data['location_json'] = kwargs['location_json']
        if kwargs.get('url'):
            serializer.validated_data['url'] = kwargs['url']

        parameters = serializer.validated_data

        queryset = self.get_lab_list(parameters)
        count = queryset.count()
        paginated_queryset = paginate_queryset(queryset, request)
        response_queryset = self.form_lab_whole_data(paginated_queryset)

        serializer = diagnostic_serializer.LabCustomSerializer(response_queryset,  many=True,
                                         context={"request": request})

        entity_ids = [lab_data['id'] for lab_data in response_queryset]

        id_url_dict = dict()
        entity = EntityUrls.objects.filter(entity_id__in=entity_ids, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Lab').values('entity_id', 'url')
        for data in entity:
            id_url_dict[data['entity_id']] = data['url']

        for resp in serializer.data:
            if id_url_dict.get(resp['lab']['id']):
                resp['lab']['url'] = id_url_dict[resp['lab']['id']]
            else:
                resp['lab']['url'] = None

        test_ids = parameters.get('ids',[])

        tests = list(LabTest.objects.filter(id__in=test_ids).values('id','name'))
        seo = None
        breadcrumb = None
        location = None
        if parameters.get('location_json'):
            locality = ''
            sublocality = ''

            if parameters.get('location_json') and parameters.get('location_json').get('locality_value'):
                locality = parameters.get('location_json').get('locality_value')

            if parameters.get('location_json') and parameters.get('location_json').get('sublocality_value'):
                sublocality = parameters.get('location_json').get('sublocality_value')
                if sublocality:
                    sublocality += ' '

            if parameters.get('location_json') and parameters.get('location_json').get('breadcrum_url'):
                breadcrumb_locality_url = parameters.get('location_json').get('breadcrum_url')

            title = "Diagnostic Centres & Labs "
            if locality:
                title += "in " + sublocality + locality
            title += " | Books Tests"
            description = "Find best Diagnostic Centres and Labs"
            if locality:
                description += " in " + sublocality + locality
                location = sublocality + locality
            elif sublocality:
                location = sublocality
            description += " and book test online, check fees, packages prices and more at DocPrime."
            seo = {'title': title, "description": description, "location": location}
            if sublocality:
                breadcrumb = [{
                    'name': locality,
                     'url': breadcrumb_locality_url
                },
                    {
                        'name': sublocality,
                        'url': parameters.get('url')
                }]

        return Response({"result": serializer.data,
                         "count": count,'tests':tests,
                         "seo": seo, "breadcrumb": breadcrumb})

    @transaction.non_atomic_requests
    def retrieve(self, request, lab_id, test_id=None, entity=None):

        if test_id:
            lab_test = LabTest.objects.filter(id=test_id).values('id', 'name', 'pre_test_info', 'why',
                                                                 'about_test', 'why_get_tested', 'preparations')
            if lab_test:
                return Response(lab_test)
            return Response(status=status.HTTP_404_NOT_FOUND)

        lab_obj = Lab.objects.prefetch_related('rating','lab_documents').filter(id=lab_id, is_live=True).first()

        if not lab_obj:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not entity:
            entity = EntityUrls.objects.filter(entity_id=lab_id,
                                               sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).order_by(
                '-is_valid')
            if len(entity) > 0:
                entity = entity[0]


        test_ids = (request.query_params.get("test_ids").split(",") if request.query_params.get('test_ids') else [])
        queryset = AvailableLabTest.objects.select_related().prefetch_related('test__labtests__parameter', 'test__packages__lab_test', 'test__packages__lab_test__labtests__parameter')\
                                                            .filter(lab_pricing_group__labs__id=lab_id,
                                                                    lab_pricing_group__labs__is_test_lab=False,
                                                                    lab_pricing_group__labs__is_live=True,
                                                                    enabled=True,
                                                                    test__in=test_ids)

        test_serializer = diagnostic_serializer.AvailableLabTestPackageSerializer(queryset, many=True,
                                                                           context={"lab": lab_obj})
        # for Demo
        demo_lab_test = AvailableLabTest.objects.filter(lab_pricing_group=lab_obj.lab_pricing_group, enabled=True).order_by("test__rank").prefetch_related('test')[:2]
        lab_test_serializer = diagnostic_serializer.AvailableLabTestSerializer(demo_lab_test, many=True, context={"lab": lab_obj})
        day_now = timezone.now().weekday()
        timing_queryset = list()
        lab_serializable_data = list()
        lab_timing = None
        lab_timing_data = list()
        distance_related_charges = None

        distance_related_charges = 1 if lab_obj.home_collection_charges.all().exists() else 0
        if lab_obj.always_open:
            lab_timing = "12:00 AM - 23:45 PM"
            lab_timing_data = [{
                "start": 0.0,
                "end": 23.75
            }]
        else:
            timing_queryset = lab_obj.lab_timings.filter(day=day_now)
            lab_timing, lab_timing_data = self.get_lab_timing(timing_queryset)

        # entity = EntityUrls.objects.filter(entity_id=lab_id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Lab')
        # if entity.exists():
        #     entity = entity.first()

        lab_serializer = diagnostic_serializer.LabModelSerializer(lab_obj, context={"request": request, "entity": entity})
        lab_serializable_data = lab_serializer.data
        if entity:
            lab_serializable_data['url'] = entity.url

        # entity = EntityUrls.objects.filter(entity_id=lab_id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Lab').values('url')
        # if entity.exists():
        #     lab_serializable_data['url'] = entity.first()['url'] if len(entity) == 1 else None

        temp_data = dict()
        temp_data['lab'] = lab_serializable_data
        temp_data['distance_related_charges'] = distance_related_charges
        temp_data['tests'] = test_serializer.data
        temp_data['lab_tests'] = lab_test_serializer.data
        temp_data['lab_timing'], temp_data["lab_timing_data"] = lab_timing, lab_timing_data

        # temp_data['url'] = entity.first()['url'] if len(entity) == 1 else None

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
        network_id = parameters.get("network_id")

        # queryset = AvailableLabTest.objects.select_related('lab').exclude(enabled=False).filter(lab_pricing_group__labs__is_live=True,
        #                                                                                         lab_pricing_group__labs__is_test_lab=False)
        queryset = Lab.objects.select_related().filter(is_test_lab=False, is_live=True,
                                                       lab_pricing_group__isnull=False)

        if network_id:
            queryset = queryset.filter(network=network_id)

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
            if LabTest.objects.filter(id__in=ids, home_collection_possible=True).count() == len(ids):
                home_pickup_calculation = Case(
                    When(is_home_collection_enabled=True,
                         then=F('home_pickup_charges')),
                    When(is_home_collection_enabled=False,
                         then=Value(0)),
                    output_field=DecimalField())
                # distance_related_charges = Case(
                #     When(is_home_collection_enabled=False, then=Value(0)),
                #     When(Q(is_home_collection_enabled=True, home_collection_charges__isnull=True),
                #          then=Value(0)),
                #     When(Q(is_home_collection_enabled=True, home_collection_charges__isnull=False),
                #          then=Value(1)),
                #     output_field=IntegerField())
            else:
                home_pickup_calculation = Value(0, DecimalField())
                # distance_related_charges = Value(0, IntegerField())

            deal_price_calculation = Case(
                When(lab_pricing_group__available_lab_tests__custom_deal_price__isnull=True,
                     then=F('lab_pricing_group__available_lab_tests__computed_deal_price')),
                When(lab_pricing_group__available_lab_tests__custom_deal_price__isnull=False,
                     then=F('lab_pricing_group__available_lab_tests__custom_deal_price')))

            queryset = (
                queryset.values('id').annotate(price=Sum(deal_price_calculation),
                                               mrp=Sum(F('lab_pricing_group__available_lab_tests__mrp')),
                                               count=Count('id'),
                                               distance=Max(Distance('location', pnt)),
                                               name=Max('name'),
                                               pickup_charges=Max(home_pickup_calculation),
                                               order_priority=Max('order_priority')).filter(count__gte=len(ids)))

            if min_price is not None:
                queryset = queryset.filter(price__gte=min_price)

            if max_price is not None:
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
        order_by = parameters.get("sort_on")
        if order_by is not None:
            if order_by == "fees" and parameters.get('ids'):
                queryset = queryset.order_by("-order_priority", F("price")+F("pickup_charges"), "distance")
            elif order_by == 'distance':
                queryset = queryset.order_by("-order_priority", "distance")
            elif order_by == 'name':
                queryset = queryset.order_by("-order_priority", "name")
            else:
                queryset = queryset.order_by("-order_priority", "distance")
        else:
            queryset = queryset.order_by("-order_priority", "distance")
        return queryset

    def form_lab_whole_data(self, queryset):
        ids = [value.get('id') for value in queryset]
        # ids, id_details = self.extract_lab_ids(queryset)
        labs = Lab.objects.select_related('network').prefetch_related('lab_documents', 'lab_image', 'lab_timings','home_collection_charges').filter(id__in=ids)
        resp_queryset = list()
        temp_var = dict()

        for obj in labs:
            temp_var[obj.id] = obj
        day_now = timezone.now().weekday()
        days_array = [i for i in range(7)]
        rotated_days_array = days_array[day_now:] + days_array[:day_now]
        for row in queryset:
            lab_timing = list()
            lab_timing_data = list()
            next_lab_timing_dict = {}
            next_lab_timing_data_dict = {}
            data_array = [list() for i in range(7)]
            row["lab"] = temp_var[row["id"]]

            if row["lab"].always_open:
                lab_timing = "12:00 AM - 11:45 PM"
                next_lab_timing_dict = {rotated_days_array[1]: "12:00 AM - 11:45 PM"}
                lab_timing_data = [{
                    "start": 0.0,
                    "end": 23.75
                }]
                next_lab_timing_data_dict = {rotated_days_array[1]: {
                    "start": 0.0,
                    "end": 23.75
                }}
            else:
                timing_queryset = row["lab"].lab_timings.all()

                for data in timing_queryset:
                    data_array[data.day].append(data)

                rotated_data_array = data_array[day_now:] + data_array[:day_now]

                for count, timing_data in enumerate(rotated_data_array):
                    day = rotated_days_array[count]
                    if count == 0:
                        if timing_data:
                            lab_timing, lab_timing_data = self.get_lab_timing(timing_data)
                            lab_timing_data = sorted(lab_timing_data, key=lambda k: k["start"])
                    elif timing_data:
                        next_lab_timing, next_lab_timing_data = self.get_lab_timing(timing_data)
                        next_lab_timing_data = sorted(next_lab_timing_data, key=lambda k: k["start"])
                        next_lab_timing_dict[day] = next_lab_timing
                        next_lab_timing_data_dict[day] = next_lab_timing_data
                        break

            if row["lab"].home_collection_charges.exists():
                row["distance_related_charges"] = 1
            else:
                row["distance_related_charges"] = 0

            row["lab_timing"] = lab_timing
            row["lab_timing_data"] = lab_timing_data
            row["next_lab_timing"] = next_lab_timing_dict
            row["next_lab_timing_data"] = next_lab_timing_data_dict
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

    serializer_class = diagnostic_serializer.LabAppointmentModelSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('profile', 'lab',)

    def get_queryset(self):
        request = self.request
        if request.user.user_type == User.DOCTOR:
            return models.LabAppointment.objects.filter(
                Q(lab__manageable_lab_admins__user=request.user,
                  lab__manageable_lab_admins__is_disabled=False) |
                Q(lab__network__manageable_lab_network_admins__user=request.user,
                  lab__network__manageable_lab_network_admins__is_disabled=False)).distinct()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset:
            return Response([])
        serializer = serializers.LabAppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        range = serializer.validated_data.get('range')
        lab = serializer.validated_data.get('lab_id')
        profile = serializer.validated_data.get('profile_id')
        date = serializer.validated_data.get('date')
        if profile:
            queryset = queryset.filter(profile=profile.id)
        if lab:
            queryset = queryset.filter(lab=lab.id)
        today = datetime.date.today()
        if range == 'previous':
            queryset = queryset.filter(
                status__in=[models.LabAppointment.COMPLETED, models.LabAppointment.CANCELLED])\
                .order_by('-time_slot_start')
        elif range == 'upcoming':
            queryset = queryset.filter(
                status__in=[models.LabAppointment.BOOKED, models.LabAppointment.RESCHEDULED_PATIENT,
                            models.LabAppointment.RESCHEDULED_LAB, models.LabAppointment.ACCEPTED],
                time_slot_start__date__gte=today).order_by('time_slot_start')
        elif range == 'pending':
            queryset = queryset.filter(
                time_slot_start__date__gte=timezone.now(),
                status__in=[models.LabAppointment.BOOKED, models.LabAppointment.RESCHEDULED_PATIENT]
            ).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')
        if date:
            queryset = queryset.filter(time_slot_start__date=date)
        queryset = paginate_queryset(queryset, request)
        serializer = serializers.LabAppointmentRetrieveSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @transaction.non_atomic_requests
    def retrieve(self, request, pk=None):
        user = request.user
        queryset = self.get_queryset().filter(pk=pk).distinct()
        if queryset:
            serializer = serializers.LabAppointmentRetrieveSerializer(queryset, many=True, context={'request':request})
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def create(self, request, **kwargs):
        data = request.data
        if not data.get("is_home_pickup"):
            data.pop("address")
        serializer = diagnostic_serializer.LabAppointmentCreateSerializer(data=data, context={'request': request})
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

        coupon_list = []
        coupon_discount = 0
        if data.get("coupon_code"):
            coupon_list = list(Coupon.objects.filter(code__in=data.get("coupon_code")).values_list('id', flat=True))
            obj = models.LabAppointment()
            for coupon in data.get("coupon_code"):
                coupon_discount += obj.get_discount(coupon, effective_price)

        if data.get("payment_type") in [doctor_model.OpdAppointment.COD, doctor_model.OpdAppointment.PREPAID]:
            if coupon_discount >= effective_price:
                effective_price = 0
            else:
                effective_price = effective_price - coupon_discount

        start_dt = form_time_slot(data["start_date"], data["start_time"])

        test_ids_list = list()
        extra_details = list()
        for obj in lab_test_queryset:
            test_ids_list.append(obj.id)
            extra_details.append({
                "id": str(obj.test.id),
                "name": str(obj.test.name),
                "custom_deal_price": str(obj.custom_deal_price),
                "computed_deal_price": str(obj.computed_deal_price),
                "mrp": str(obj.mrp),
                "computed_agreed_price": str(obj.computed_agreed_price),
                "custom_agreed_price": str(obj.custom_agreed_price)
            })

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
            "lab_test": test_ids_list,
            # "lab_test": [x["id"] for x in lab_test_queryset.values("id")],
            "extra_details": extra_details,
            "coupon": coupon_list,
            "discount": coupon_discount
        }
        if data.get("is_home_pickup") is True:
            address = Address.objects.filter(pk=data.get("address").id).first()
            address_serialzer = AddressSerializer(address)
            appointment_data.update({
                "address": address_serialzer.data,
                "is_home_pickup": True
            })

        return appointment_data

    def update(self, request, pk=None):
        lab_appointment = get_object_or_404(LabAppointment, pk=pk)
        # lab_appointment = self.get_queryset().filter(pk=pk).first()
        # if not lab_appointment:
        #     return Response()
        serializer = serializers.UpdateStatusSerializer(
            data=request.data, context={'request': request, 'lab_appointment': lab_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        allowed_status = lab_appointment.allowed_action(request.user.user_type, request)
        appt_status = validated_data['status']
        if appt_status not in allowed_status:
            resp = {}
            resp['allowed_status'] = allowed_status
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)
        if request.user.user_type == User.DOCTOR:
            req_status = validated_data.get('status')
            if req_status == models.LabAppointment.RESCHEDULED_LAB:
                lab_appointment.action_rescheduled_lab()
            elif req_status == models.LabAppointment.ACCEPTED:
                lab_appointment.action_accepted()

        lab_appointment_serializer = serializers.LabAppointmentRetrieveSerializer(lab_appointment, context={'request':request})
        response = {
            "status": 1,
            "data": lab_appointment_serializer.data
        }
        return Response(response)

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
        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            balance = 0
            resp['is_agent'] = True

        if (appointment_details['payment_type'] == doctor_model.OpdAppointment.PREPAID and
                balance < appointment_details.get("effective_price")):

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
            try:
                ops_email_data = dict()
                ops_email_data.update(order.appointment_details())
                ops_email_data["transaction_time"] = aware_time_zone(timezone.now())
                EmailNotification.ops_notification_alert(ops_email_data, settings.OPS_EMAIL_ID,
                                                         order.product_id,
                                                         EmailNotification.OPS_PAYMENT_NOTIFICATION)

                push_order_to_matrix.apply_async(({'order_id': order.id, 'created_at':int(order.created_at.timestamp()),
                                                   'timeslot':int(appointment_details['time_slot_start'].timestamp())}, ), countdown=5)
            except:
                pass
        else:
            lab_appointment = LabAppointment.create_appointment(appointment_details)
            if appointment_details["payment_type"] == doctor_model.OpdAppointment.PREPAID:
                consumer_account.debit_schedule(lab_appointment, product_id, appointment_details.get("effective_price"))
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
        base_url = "https://{}".format(request.get_host())
        pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
        pgdata['appointmentId'] = ""
        pgdata['orderId'] = order_id
        pgdata['name'] = appointment_details["profile"].name
        pgdata['txAmount'] = str(appointment_details['payable_amount'])

        pgdata['hash'] = account_models.PgTransaction.create_pg_hash(pgdata, settings.PG_SECRET_KEY_P2,
                                                                     settings.PG_CLIENT_KEY_P2)

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


class LabTimingListView(mixins.ListModelMixin,
                        viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated,)

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        params = request.query_params

        for_home_pickup = True if int(params.get('pickup', 0)) else False
        lab = params.get('lab')

        resp_data = LabTiming.timing_manager.lab_booking_slots(lab__id=lab, lab__is_live=True, for_home_pickup=for_home_pickup)

        # for agent do not set any time limitations
        if hasattr(request, "agent") and request.agent:
            resp_data = {
                "time_slots" : resp_data["time_slots"],
                "today_min": None,
                "tomorrow_min": None,
                "today_max": None
            }
        return Response(resp_data)


class AvailableTestViewSet(mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs__is_live=True).all()
    serializer_class = diagnostic_serializer.AvailableLabTestSerializer

    @transaction.non_atomic_requests
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


class LabReportFileViewset(mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin,
                                 mixins.UpdateModelMixin,
                                 mixins.ListModelMixin,
                                 viewsets.GenericViewSet):

    serializer_class = serializers.LabReportFileSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        request = self.request
        if request.user.user_type == User.DOCTOR:
            user = request.user
            return (models.LabReportFile.objects.filter(
                Q(report__appointment__lab__manageable_lab_admins__user=user,
                  report__appointment__lab__manageable_lab_admins__permission_type=auth_models.GenericLabAdmin.APPOINTMENT,
                  report__appointment__lab__manageable_lab_admins__is_disabled=False) |
                Q(report__appointment__lab__network__manageable_lab_network_admins__user=request.user,
                  report__appointment__lab__network__manageable_lab_network_admins__permission_type=auth_models.GenericLabAdmin.APPOINTMENT,
                  report__appointment__lab__network__manageable_lab_network_admins__is_disabled=False)).distinct())

            # return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)
        elif request.user.user_type == User.CONSUMER:
            return models.LabReportFile.objects.filter(report__appointment__user=request.user)
        else:
            return models.LabReportFile.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = serializers.LabReportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if not self.lab_report_permission(request.user, validated_data.get('appointment')):
            return Response([])
        if models.LabReport.objects.filter(appointment=validated_data.get('appointment')).exists():
            report = models.LabReport.objects.filter(
                appointment=validated_data.get('appointment')).first()
        else:
            report = models.LabReport.objects.create(appointment=validated_data.get('appointment'),
                                                     report_details=validated_data.get('report_details'))
        report_file_data = {
            "report": report.id,
            "name": validated_data.get('name')
        }
        report_file_serializer = serializers.LabReportFileSerializer(data=report_file_data,
                                                                     context={"request": request})
        report_file_serializer.is_valid(raise_exception=True)
        report_file_serializer.save()
        return Response(report_file_serializer.data)

    def lab_report_permission(self, user, appointment):
        return auth_models.GenericLabAdmin.objects.filter(user=user, lab=appointment.lab,
                                                          permission_type=auth_models.GenericLabAdmin.APPOINTMENT,
                                                          write_permission=True).exists()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        lab_appointment = request.query_params.get("labappointment")
        if not lab_appointment:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            lab_appointment = int(lab_appointment)
        except TypeError:
            return Response({'msg': "Can't convert labappointment to Integer."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(report__appointment=lab_appointment)
        serializer = serializers.LabReportFileSerializer(
            data=queryset, many=True, context={"request": request})
        serializer.is_valid()
        return Response(serializer.data)


class DoctorLabAppointmentsViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    @transaction.atomic
    def complete(self, request):
        serializer = diagnostic_serializer.AppointmentCompleteBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        lab_appointment = validated_data.get('lab_appointment')

        lab_appointment = LabAppointment.objects.select_for_update().get(id=lab_appointment.id)

        if lab_appointment.lab.manageable_lab_admins.filter(user=request.user,
                                                            is_disabled=False,
                                                            write_permission=True).exists() or \
                (lab_appointment.lab.network is not None and
                 lab_appointment.lab.network.manageable_lab_network_admins.filter(
                     user=request.user,
                     is_disabled=False,
                     write_permission=True).exists()):
            lab_appointment.action_completed()
            lab_appointment_serializer = diagnostic_serializer.LabAppointmentRetrieveSerializer(lab_appointment,
                                                                                                context={
                                                                                                    'request': request})
            return Response(lab_appointment_serializer.data)
        else:
            return Response({'msg': 'User is not allowed to complete this appointment.'},
                            status=status.HTTP_403_FORBIDDEN)


class DoctorLabAppointmentsNoAuthViewSet(viewsets.GenericViewSet):

    @transaction.atomic
    def complete(self, request):
        resp = {}
        serializer = diagnostic_serializer.AppointmentCompleteBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        lab_appointment = validated_data.get('lab_appointment')

        lab_appointment = LabAppointment.objects.select_for_update().get(id=lab_appointment.id)

        if lab_appointment:
            lab_appointment.action_completed()
            # lab_appointment_serializer = diagnostic_serializer.LabAppointmentRetrieveSerializer(lab_appointment,
            #                                                                                         context={
            #                                                                                             'request': request})
            resp = {'success':'LabAppointment Updated Successfully!'}
        return Response(resp)

class TestDetailsViewset(viewsets.GenericViewSet):

    def retrieve(self, request, test_id):
        params = request.query_params
        queryset = LabTest.objects.filter(id=test_id)
        query = ParameterLabTest.objects.filter(lab_test_id=test_id)
        if not queryset:
            return Response([])
        result = {}
        if len(queryset) > 0:
            queryset = queryset[0]
            result['about_test'] = queryset.about_test
            result['why_get_tested'] = [item.strip('\r') for item in queryset.why_get_tested.split('\n')]
            # result['test_may_include'] =
            result['preparations'] = queryset.preparations

        if len(query) > 0:
            info=[]
            for data in query:
                if data.parameter.name:

                    name = data.parameter.name
                    info.append(name)
            result['test_may_include'] = info

        queryset1 = QuestionAnswer.objects.filter(lab_test_id=test_id).values('test_question','test_answer')
        if len(queryset1) > 0:
            result['faqs']= queryset1

        queryset2 = FrequentlyAddedTogetherTests.objects.filter(original_test_id=test_id)
        booked_together=[]
        if len(queryset2) > 0:
            for data in queryset2:
                 if data.booked_together_test.name:

                    name = data.booked_together_test.name
                    id = data.booked_together_test.id
                    booked_together.append({'id':id, 'lab_test': name})

            result['frequently_booked_together'] = booked_together

        return Response(result)




