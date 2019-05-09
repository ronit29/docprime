import operator
from copy import deepcopy
from itertools import groupby
from pyodbc import Date

from ondoc.api.v1.diagnostic.serializers import CustomLabTestPackageSerializer
from ondoc.api.v1.doctor.serializers import CommaSepratedToListField
from ondoc.authentication.backends import JWTAuthentication
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializer
from ondoc.api.v1.auth.serializers import AddressSerializer
from ondoc.integrations.models import IntegratorTestMapping, IntegratorReport
from ondoc.cart.models import Cart
from ondoc.common.models import UserConfig, GlobalNonBookable, AppointmentHistory
from ondoc.ratings_review import models as rating_models
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest, CommonPackage,
                                     FrequentlyAddedTogetherTests, TestParameter, ParameterLabTest, QuestionAnswer,
                                     LabPricingGroup, LabTestCategory, LabTestCategoryMapping, LabTestThresholds)
from ondoc.account import models as account_models
from ondoc.authentication.models import UserProfile, Address
from ondoc.insurance.models import UserInsurance, InsuranceThreshold
from ondoc.notification.models import EmailNotification
from ondoc.coupon.models import Coupon
from ondoc.doctor import models as doctor_model
from ondoc.api.v1 import insurance as insurance_utility
from ondoc.api.v1.utils import form_time_slot, IsConsumer, labappointment_transform, IsDoctor, payment_details, \
    aware_time_zone, get_lab_search_details, TimeSlotExtraction, RawSql, util_absolute_url, get_package_free_or_not_dict
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

from django.db.models import Prefetch
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
from django.db.models.functions import StrIndex, Coalesce

from ondoc.location.models import EntityUrls, EntityAddress, CompareSEOUrls, CompareLabPackagesSeoUrls
from ondoc.seo.models import NewDynamic
from ondoc.subscription_plan.models import UserPlanMapping
from . import serializers
import copy
import re
import datetime
from collections import OrderedDict, defaultdict
import random
from django.contrib.auth import get_user_model
from ondoc.matrix.tasks import push_order_to_matrix
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber
from django.db.models import Avg
from django.db.models.expressions import RawSQL
from ondoc.doctor.v1.serializers import ArticleAuthorSerializer
User = get_user_model()


class SearchPageViewSet(viewsets.ReadOnlyModelViewSet):

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        count = request.query_params.get('count', 10)
        count = int(count)
        if count <= 0:
            count = 10
        test_queryset = CommonTest.get_tests(count)
        conditions_queryset = CommonDiagnosticCondition.objects.prefetch_related('lab_test').all().order_by('-priority')[:count]
        lab_queryset = PromotedLab.objects.select_related('lab').filter(lab__is_live=True, lab__is_test_lab=False)
        package_queryset = CommonPackage.get_packages(count)
        recommended_package_qs = LabTestCategory.objects.prefetch_related('recommended_lab_tests__parameter').filter(is_live=True,
                                                                                                          show_on_recommended_screen=True,
                                                                                                          recommended_lab_tests__searchable=True,
                                                                                                          recommended_lab_tests__enable_for_retail=True).order_by('-priority').distinct()[:count]
        test_serializer = diagnostic_serializer.CommonTestSerializer(test_queryset, many=True, context={'request': request})
        package_serializer = diagnostic_serializer.CommonPackageSerializer(package_queryset, many=True, context={'request': request})
        lab_serializer = diagnostic_serializer.PromotedLabsSerializer(lab_queryset, many=True)
        condition_serializer = diagnostic_serializer.CommonConditionsSerializer(conditions_queryset, many=True)
        recommended_package = diagnostic_serializer.RecommendedPackageCategoryList(recommended_package_qs, many=True, context={'request': request})
        temp_data = dict()
        user_config = UserConfig.objects.filter(key='package_adviser_filters').first()
        advisor_filter = []
        if user_config:
            advisor_filter = user_config.data
        temp_data['common_tests'] = test_serializer.data
        temp_data['recommended_package'] = {'result': recommended_package.data,
                                            'information': {'screening': 'Screening text', 'physical': 'Physical Text'},
                                            'filters': advisor_filter}
        temp_data['common_package'] = package_serializer.data
        temp_data['preferred_labs'] = lab_serializer.data
        temp_data['common_conditions'] = condition_serializer.data

        return Response(temp_data)


class LabTestList(viewsets.ReadOnlyModelViewSet):
    queryset = LabTest.objects.filter(searchable=True).all()
    serializer_class = diagnostic_serializer.LabTestListSerializer
    lookup_field = 'id'
    filter_backends = (SearchFilter,)
    # filter_fields = ('name',)
    search_fields = ('name',)

    @transaction.non_atomic_requests
    def autocomplete_packages(self, request, *args, **kwargs):
        name = request.query_params.get('name')
        temp_data = dict()
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            test_queryset = LabTest.objects.filter(
                Q(search_key__icontains=search_key) |
                Q(search_key__icontains=' ' + search_key) |
                Q(search_key__istartswith=search_key),
                is_package=True).filter(searchable=True).annotate(
                search_index=StrIndex('search_key', Value(search_key))).order_by(
                'search_index')
            test_queryset = paginate_queryset(test_queryset, request)
        else:
            test_queryset = self.queryset.filter(is_package=True)[:20]

        test_serializer = diagnostic_serializer.LabTestListSerializer(test_queryset, many=True)
        temp_data['packages'] = test_serializer.data
        return Response(temp_data)

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
                Q(search_key__istartswith=search_key)).filter(searchable=True).annotate(search_index=StrIndex('search_key', Value(search_key))).order_by(
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
    def list_packages(self, request, **kwrgs):
        parameters = request.query_params
        serializer = diagnostic_serializer.LabPackageListSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        long = validated_data.get('long')
        lat = validated_data.get('lat')
        min_distance = validated_data.get('min_distance')
        max_distance = validated_data.get('max_distance')
        min_price = validated_data.get('min_price')
        max_price = validated_data.get('max_price')
        max_age = validated_data.get('max_age')
        min_age = validated_data.get('min_age')
        gender = validated_data.get('gender')
        package_type = validated_data.get('package_type')
        sort_on = validated_data.get('sort_on')
        category_ids = validated_data.get('category_ids', [])
        package_category_ids = validated_data.get('package_category_ids', [])
        test_ids = validated_data.get('test_ids', [])
        package_ids = validated_data.get('package_ids', [])
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)
        max_distance = max_distance*1000 if max_distance is not None else 10000
        min_distance = min_distance*1000 if min_distance is not None else 0
        sort_order = validated_data.get('sort_order', 'asc')
        avg_ratings = validated_data.get('avg_ratings', [])
        home_visit = validated_data.get('home_visit')
        lab_visit = validated_data.get('lab_visit')

        package_free_or_not_dict = get_package_free_or_not_dict(request)
        page_size = 30
        if not request.query_params.get('page') or int(request.query_params.get('page')) < 1:
            page = 1
        else:
            page = int(request.query_params.get('page'))
        offset = (page - 1) * page_size
        valid_package_ids = None

        if test_ids:
            valid_package_ids = list(LabTest.objects.filter(test__id__in=test_ids).annotate(
                included_test_count=Count('test')).filter(
                included_test_count=len(test_ids)).distinct().values_list('id', flat=True))
        if category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(list(
                LabTest.objects.filter(test__recommended_categories__id__in=category_ids).distinct().values_list('id',
                                                                                                                 flat=True)))

        if package_category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(list(
                LabTest.objects.filter(categories__id__in=package_category_ids).distinct().values_list('id',
                                                                                               flat=True)))

        if package_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(package_ids)

        if not valid_package_ids and valid_package_ids is not None:
            valid_package_ids = [-1]


        package_search_query = 'select x.*, CASE WHEN "x"."custom_deal_price" IS not NULL THEN "x"."custom_deal_price"'\
                               ' else computed_deal_price END AS "price", ST_Distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), x.location) as distance from '\
                               ' (SELECT "lab_test"."id", "lab_test"."name","lab_test"."why","lab_test"."pre_test_info",' \
                               ' "lab_test"."test_type", "lab_test"."is_package", "lab_test"."number_of_tests", "lab_test"."category",' \
                               ' "lab_test"."sample_type", "lab_test"."home_collection_possible", "lab_test"."enable_for_ppc", "lab_test"."enable_for_retail", "lab_test"."about_test",' \
                               ' "lab_test"."show_details", "lab_test"."priority", "lab_test"."hide_price",' \
                               ' "lab_test"."searchable", "lab_test"."url", "lab_test"."custom_url", "lab_test"."min_age", "lab_test"."max_age",' \
                               ' "lab_test"."gender_type",' \
                               ' ("lab"."lab_priority" * "lab_test"."priority") AS "priority_score",' \
                               ' "available_lab_test"."mrp" AS "mrp",' \
                               ' "available_lab_test"."custom_deal_price",' \
                               ' "available_lab_test"."computed_deal_price" ,' \
                               ' "lab"."id" AS "lab",' \
                               ' "lab"."location",' \
                               ' ROW_NUMBER() OVER (PARTITION BY (Coalesce(lab.network_id, random())), "lab_test"."id"' \
                               ' ORDER BY ST_Distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), lab.location) ASC)' \
                               ' AS "rnk"' \
                               ' FROM "lab_test" inner JOIN "available_lab_test" ON ("lab_test"."id" = "available_lab_test"."test_id")' \
                               ' inner JOIN "lab_pricing_group" ON ("available_lab_test"."lab_pricing_group_id" = "lab_pricing_group"."id")' \
                               ' inner JOIN "lab" ON ("lab_pricing_group"."id" = "lab"."lab_pricing_group_id") WHERE' \
                               ' ("lab_test"."enable_for_retail" = true AND "lab_test"."is_package" = true AND "lab_test"."searchable" = true' \
                               ' AND "available_lab_test"."enabled" = true AND "lab"."enabled" = true AND "lab"."is_live" = true AND' \
                               ' ST_DWithin("lab"."location", St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), %(max_distance)s))' \
                               ' and not ST_DWithin("lab"."location", St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), %(min_distance)s)' \
                               ' {filter_query}' \
                               ' )x where rnk =1 {sort_query} offset {offset} limit {limit} '

        package_count_query = '''
                                select count(distinct available_lab_test), array_agg( distinct ltc.id ) as category_ids FROM "lab_test"
                                left JOIN labtest_package ltp on ltp.package_id = lab_test.id
                                inner JOIN "available_lab_test" ON ("lab_test"."id" = "available_lab_test"."test_id") 
                                inner JOIN "lab_pricing_group" ON ("available_lab_test"."lab_pricing_group_id" = "lab_pricing_group"."id") 
                                inner JOIN "lab" ON ("lab_pricing_group"."id" = "lab"."lab_pricing_group_id") 
                                left JOIN "lab_test_recommended_category_mapping" ltrc on ltrc.lab_test_id = ltp.lab_test_id
                                left JOIN "lab_test_category" ltc on ltrc.parent_category_id = ltc.id 
                                WHERE "lab_test"."enable_for_retail" = true AND "lab_test"."is_package" = true 
                                AND "lab_test"."searchable" = true AND "available_lab_test"."enabled" = true 
                                AND "lab"."enabled" = true AND "lab"."is_live" = true '''
        # package_count_query = ' SELECT count(distinct available_lab_test)' \
        #                       ' FROM "lab_test" inner JOIN "available_lab_test" ON ("lab_test"."id" = "available_lab_test"."test_id")' \
        #                       ' inner JOIN "lab_pricing_group" ON ("available_lab_test"."lab_pricing_group_id" = "lab_pricing_group"."id")' \
        #                       ' inner JOIN "lab" ON ("lab_pricing_group"."id" = "lab"."lab_pricing_group_id") WHERE' \
        #                       ' "lab_test"."enable_for_retail" = true AND "lab_test"."is_package" = true AND "lab_test"."searchable" = true' \
        #                       ' AND "available_lab_test"."enabled" = true AND "lab"."enabled" = true AND "lab"."is_live" = true AND' \
        #                       ' ST_DWithin("lab"."location", St_setsrid(St_point(%(longitude)s, %(latitude)s), 4326), %(max_distance)s)' \
        #                       ' and not ST_DWithin("lab"."location", St_setsrid(St_point(%(longitude)s, %(latitude)s), 4326), %(min_distance)s)'

        
        params = {}
        params['latitude'] = str(lat)
        params['longitude'] = str(long)
        sort_query = ''
        if not sort_on:
            sort_query = ' order by priority_score desc '
        elif sort_on == 'fees':
            sort_query = ' order by price %s ' %sort_order
        elif sort_on == 'distance':
            sort_query = ' order by distance asc '

        filter_query = ''
        params['min_distance'] = str(min_distance)
        params['max_distance'] = str(max_distance)
        if min_price:
            filter_query += ' and case when custom_deal_price is not null then custom_deal_price>=%(min_price)s else computed_deal_price>=%(min_price)s end '
            params['min_price'] = str(min_price)
        if max_price:
            filter_query += ' and case when custom_deal_price is not null then custom_deal_price<=%(max_price)s else computed_deal_price<=%(max_price)s end '
            params['max_price'] = str(max_price)
        if home_visit and not lab_visit:
            filter_query += ' and is_home_collection_enabled = True and home_collection_possible = True '
        if lab_visit and not home_visit:
            filter_query += ' and is_home_collection_enabled = False and home_collection_possible = False '
        if avg_ratings:
            filter_query += " and (case when rating_data is not null then(rating_data->> 'avg_rating')::float > (%(avg_ratings)s) end) "
            params['avg_ratings'] = max(avg_ratings)

        if valid_package_ids is not None:
            filter_query += ' and lab_test.id IN('
            counter = 1
            for t_id in valid_package_ids:
                if not counter == 1:
                    filter_query += ','
                filter_query += '%(' + 'package_id' + str(counter) + ')s'
                params['package_id' + str(counter)] = t_id
                counter += 1
            filter_query += ')'
        if filter_query:
            package_count_query += filter_query

        package_count = RawSql(package_count_query, params).fetch_all()
        result_count = package_count[0].get('count', 0)
        categories_ids = package_count[0].get('category_ids', [])
        # if filter_query:
        #     filter_query = ' and '+filter_query
        package_search_query = package_search_query.format(filter_query=filter_query, sort_query=sort_query, offset=offset, limit=page_size)
        all_packages = list(LabTest.objects.raw(package_search_query, params))
        from django.db.models import prefetch_related_objects
        prefetch_related_objects(all_packages, 'test', 'test__recommended_categories', 'test__parameter', 'categories')
        lab_ids = [package.lab for package in all_packages]
        entity_url_qs = EntityUrls.objects.filter(entity_id__in=lab_ids, is_valid=True, url__isnull=False,
                                                  sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).values(
            'url', lab_id=F('entity_id'))
        entity_url_dict = {}
        for item in entity_url_qs:
            entity_url_dict.setdefault(item.get('lab_id'), [])
            entity_url_dict[item.get('lab_id')].append(item.get('url'))
        lab_data = Lab.objects.prefetch_related('lab_documents', 'lab_timings', 'network',
                                                'home_collection_charges').in_bulk(lab_ids)
        category_data = {}
        test_package_queryset = []
        cache = {}
        for t_p in all_packages:
            if t_p not in cache:
                cache[t_p.id] = True
                test_package_queryset.append(t_p)

        # category_to_be_shown_in_filter_ids=set()
        for temp_package in test_package_queryset:
            single_test_data = {}
            for temp_test in temp_package.test.all():
                add_test_name = True
                for temp_category in temp_test.recommended_categories.all():
                    if temp_category.is_live:
                        add_test_name = False
                        name = temp_category.name
                        priority = temp_category.priority
                        category_id = temp_category.id
                        # category_to_be_shown_in_filter_ids.add(category_id)
                        test_id = None
                        icon_url = util_absolute_url(temp_category.icon.url) if temp_category.icon else None
                        parameter_count = len(temp_test.parameter.all()) or 1
                        if single_test_data.get((category_id, test_id)):
                            single_test_data[(category_id, test_id)]['parameter_count'] += parameter_count
                        else:
                            single_test_data[(category_id, test_id)] = {'name': name,
                                                                        'category_id': category_id,
                                                                        'test_id': test_id,
                                                                        'parameter_count': parameter_count,
                                                                        'icon': icon_url, 'priority': priority}
                if add_test_name:
                    category_id = None
                    test_id = temp_test.id
                    name = temp_test.name
                    priority = 0
                    parameter_count = len(temp_test.parameter.all()) or 1
                    icon_url = None
                    single_test_data[(category_id, test_id)] = {'name': name,
                                                                'category_id': category_id,
                                                                'test_id': test_id,
                                                                'parameter_count': parameter_count,
                                                                'icon': icon_url, 'priority': priority}
            single_test_data_sorted = sorted(list(single_test_data.values()), key=lambda k: k['priority'], reverse= True)
            category_data[temp_package.id] = single_test_data_sorted

        serializer = CustomLabTestPackageSerializer(all_packages, many=True,
                                                    context={'entity_url_dict': entity_url_dict, 'lab_data': lab_data,
                                                             'request': request, 'category_data': category_data,
                                                             'package_free_or_not_dict': package_free_or_not_dict})

        category_to_be_shown_in_filter_ids = set()
        category_queryset = LabTestCategory.objects.filter(is_package_category=True, is_live=True, id__in=categories_ids).order_by('-priority')
        category_result = []
        for category in category_queryset:
            name = category.name
            category_id = category.id
            is_selected = False
            if category_ids is not None and category_id in category_ids:
                is_selected = True
            category_result.append({'name': name, 'id': category_id, 'is_selected': is_selected})

        result = serializer.data
        if result:
            from ondoc.coupon.models import Coupon
            search_coupon = Coupon.get_search_coupon(request.user)

            for package_result in result:
                if "price" in package_result:
                    price = int(float(package_result["price"]))
                    discounted_price = price if not search_coupon else search_coupon.get_search_coupon_discounted_price(price)
                    package_result["discounted_price"] = discounted_price

        top_content = None
        bottom_content = None
        title = None
        description = None
        dynamic = NewDynamic.objects.filter(url__url='full-body-checkup-health-packages', is_enabled=True)
        for x in dynamic:
            top_content = x.top_content if x.top_content else None
            bottom_content = x.bottom_content if x.bottom_content else None
            title = x.meta_title if x.meta_title else None
            description = x.meta_description if x.meta_description else None
        return Response({'result': result, 'categories': category_result, 'count': result_count,
                         'categories_count': len(category_result), 'bottom_content': bottom_content,
                         'search_content': top_content, 'title': title, 'description': description})

    @transaction.non_atomic_requests
    def list_packages_v2(self, request, **kwrgs):
        parameters = request.query_params
        serializer = diagnostic_serializer.LabPackageListSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        long = validated_data.get('long')
        lat = validated_data.get('lat')
        min_distance = validated_data.get('min_distance')
        max_distance = validated_data.get('max_distance')
        min_price = validated_data.get('min_price')
        max_price = validated_data.get('max_price')
        max_age = validated_data.get('max_age')
        min_age = validated_data.get('min_age')
        gender = validated_data.get('gender')
        package_type = validated_data.get('package_type')
        sort_on = validated_data.get('sort_on')
        category_ids = validated_data.get('category_ids', [])
        package_category_ids = validated_data.get('package_category_ids', [])
        test_ids = validated_data.get('test_ids', [])
        package_ids = validated_data.get('package_ids', [])
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)
        max_distance = max_distance*1000 if max_distance is not None else 10000
        min_distance = min_distance*1000 if min_distance is not None else 0

        package_free_or_not_dict = get_package_free_or_not_dict(request)

        main_queryset = LabTest.objects.prefetch_related('test', 'test__recommended_categories',
                                                         'test__parameter', 'categories').filter(enable_for_retail=True,
                                                                                                 searchable=True,
                                                                                                 is_package=True)

        page_size = 30

        if not request.query_params.get('page') or int(request.query_params.get('page')) < 1:
            page = 1
        else:
            page = int(request.query_params.get('page'))

        offset = (page - 1) * page_size

        if package_ids:
            main_queryset = main_queryset.filter(id__in=package_ids)
        valid_package_ids = None

        if test_ids:
            valid_package_ids = list(LabTest.objects.filter(test__id__in=test_ids).annotate(
                included_test_count=Count('test')).filter(
                included_test_count=len(test_ids)).distinct().values_list('id', flat=True))

        if category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
                lab_categories = None
                lab_categories = LabTest.objects.filter(test__recommended_categories__id__in=category_ids).distinct().values_list('id',
                                                                                                                 flat=True)
            valid_package_ids.extend(list(lab_categories if len(lab_categories) == len(category_ids) else None))

        if package_category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(list(
                LabTest.objects.filter(categories__id__in=package_category_ids).distinct().values_list('id',
                                                                                               flat=True)))

        if valid_package_ids is not None:
            main_queryset = main_queryset.filter(id__in=valid_package_ids)


        # all_packages_in_network_labs = main_queryset.filter(
        #     availablelabs__enabled=True,
        #     availablelabs__lab_pricing_group__labs__is_live=True,
        #     availablelabs__lab_pricing_group__labs__network__isnull=False,
        #     availablelabs__lab_pricing_group__labs__location__dwithin=(
        #         Point(float(long),
        #               float(lat)),
        #         D(m=max_distance))).annotate(
        #     priority_score=F('availablelabs__lab_pricing_group__labs__lab_priority') * F('priority')).annotate(
        #     distance=Distance('availablelabs__lab_pricing_group__labs__location', pnt)).annotate(
        #     lab=F('availablelabs__lab_pricing_group__labs'), mrp=F('availablelabs__mrp'),
        #     price=Case(
        #         When(availablelabs__custom_deal_price__isnull=True,
        #              then=F('availablelabs__computed_deal_price')),
        #         When(availablelabs__custom_deal_price__isnull=False,
        #              then=F('availablelabs__custom_deal_price'))),
        #     rank=Window(expression=RowNumber(), order_by=F('distance').asc(),
        #                 partition_by=[F(
        #                     'availablelabs__lab_pricing_group__labs__network'), F('id')]))
        #
        # all_packages_in_non_network_labs = main_queryset.filter(
        #     availablelabs__enabled=True,
        #     availablelabs__lab_pricing_group__labs__is_live=True,
        #     availablelabs__lab_pricing_group__labs__enabled=True,
        #     availablelabs__lab_pricing_group__labs__network__isnull=True,
        #     availablelabs__lab_pricing_group__labs__location__dwithin=(
        #         Point(float(long),
        #               float(lat)),
        #         D(
        #             m=max_distance))).annotate(
        #     priority_score=F('availablelabs__lab_pricing_group__labs__lab_priority') * F('priority')).annotate(
        #     distance=Distance('availablelabs__lab_pricing_group__labs__location', pnt)).annotate(
        #     lab=F('availablelabs__lab_pricing_group__labs'), mrp=F('availablelabs__mrp'),
        #     price=Case(
        #         When(availablelabs__custom_deal_price__isnull=True,
        #              then=F('availablelabs__computed_deal_price')),
        #         When(availablelabs__custom_deal_price__isnull=False,
        #              then=F('availablelabs__custom_deal_price'))),
        # )
        #
        # all_packages_in_non_network_labs = all_packages_in_non_network_labs.distinct()
        # all_packages_in_network_labs = all_packages_in_network_labs.distinct()
        # all_packages = [package for package in all_packages_in_network_labs if package.rank == 1]
        # all_packages.extend([package for package in all_packages_in_non_network_labs])

        all_packages = main_queryset.filter(
            availablelabs__enabled=True,
            availablelabs__lab_pricing_group__labs__is_live=True,
            availablelabs__lab_pricing_group__labs__enabled=True,
            availablelabs__lab_pricing_group__labs__location__dwithin=(
                Point(float(long),
                      float(lat)),
                D(m=max_distance))).annotate(
            priority_score=F('availablelabs__lab_pricing_group__labs__lab_priority') * F(
                'priority')).annotate(
            distance=Distance('availablelabs__lab_pricing_group__labs__location',
                              pnt)).annotate(
            lab=F('availablelabs__lab_pricing_group__labs'), mrp=F('availablelabs__mrp'),
            price=Case(
                When(availablelabs__custom_deal_price__isnull=True,
                     then=F('availablelabs__computed_deal_price')),
                When(availablelabs__custom_deal_price__isnull=False,
                     then=F('availablelabs__custom_deal_price'))),
            rank=Window(expression=RowNumber(), order_by=F('distance').asc(),
                        partition_by=[RawSQL('Coalesce(lab.network_id, random())', []), F('id')])
        )

        all_packages = [package for package in all_packages if package.rank == 1]

        if not sort_on:
            all_packages = sorted(all_packages, key=lambda x: x.priority_score if hasattr(x,
                                                                                          'priority_score') and x.priority_score is not None else -float(
                'inf'), reverse=True)
        elif sort_on == 'fees':
            all_packages = sorted(all_packages,
                                  key=lambda x: x.price if hasattr(x, 'price') and x.price is not None else -float(
                                      'inf'))
        elif sort_on == 'distance':
            all_packages = sorted(all_packages, key=lambda x: x.distance if hasattr(x,
                                                                                    'distance') and x.distance is not None else -float(
                'inf'))

        all_packages = filter(lambda x: x, all_packages)
        if min_distance:
            all_packages = filter(lambda
                                      x: x.distance.m >= min_distance if x.distance is not None and x.distance.m is not None else False,
                                  all_packages)
        if min_price:
            all_packages = filter(lambda x: x.price >= min_price if x.price is not None else False, all_packages)
        if max_price:
            all_packages = filter(lambda x: x.price <= max_price if x.price is not None else False, all_packages)
        if min_age and max_age:
            all_packages = filter(lambda x: (x.min_age <= max_age if x.min_age is not None else False) and (
                x.max_age >= min_age if x.max_age is not None else False), all_packages)
        elif max_age:
            all_packages = filter(lambda x: x.min_age <= max_age if x.min_age is not None else False, all_packages)
        elif min_age:
            all_packages = filter(lambda x: x.max_age >= min_age if x.max_age is not None else False, all_packages)
        if gender:
            all_packages = filter(
                lambda x: x.gender_type in [gender, LabTest.ALL] if x.gender_type is not None else False, all_packages)
        if package_type == 1:
            all_packages = filter(lambda x: x.home_collection_possible, all_packages)
        if package_type == 2:
            all_packages = filter(lambda x: not x.home_collection_possible, all_packages)

        all_packages = list(all_packages)
        result_count = len(all_packages)
        lab_ids = [package.lab for package in all_packages]
        entity_url_qs = EntityUrls.objects.filter(entity_id__in=lab_ids, is_valid=True, url__isnull=False,
                                                  sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).values(
            'url', lab_id=F('entity_id'))
        entity_url_dict = {}
        for item in entity_url_qs:
            entity_url_dict.setdefault(item.get('lab_id'), [])
            entity_url_dict[item.get('lab_id')].append(item.get('url'))
        lab_data = Lab.objects.prefetch_related('rating', 'lab_documents', 'lab_timings', 'network',
                                                'home_collection_charges').in_bulk(lab_ids)
        category_data = {}
        test_package_ids = set([package.id for package in all_packages])
        test_package_queryset = LabTest.objects.prefetch_related('test__recommended_categories', 'test__parameter').filter(id__in=test_package_ids)
        category_to_be_shown_in_filter_ids=set()
        for temp_package in test_package_queryset:
            single_test_data = {}
            for temp_test in temp_package.test.all():
                add_test_name = True
                for temp_category in temp_test.recommended_categories.all():
                    if temp_category.is_live:
                        add_test_name = False
                        name = temp_category.name
                        priority = temp_category.priority
                        category_id = temp_category.id
                        category_to_be_shown_in_filter_ids.add(category_id)
                        test_id = None
                        icon_url = util_absolute_url(temp_category.icon.url) if temp_category.icon else None
                        parameter_count = len(temp_test.parameter.all()) or 1
                        if single_test_data.get((category_id, test_id)):
                            single_test_data[(category_id, test_id)]['parameter_count'] += parameter_count
                        else:
                            single_test_data[(category_id, test_id)] = {'name': name,
                                                                        'category_id': category_id,
                                                                        'test_id': test_id,
                                                                        'parameter_count': parameter_count,
                                                                        'icon': icon_url, 'priority': priority}
                if add_test_name:
                    category_id = None
                    test_id = temp_test.id
                    name = temp_test.name
                    priority = 0
                    parameter_count = len(temp_test.parameter.all()) or 1
                    icon_url = None
                    single_test_data[(category_id, test_id)] = {'name': name,
                                                                'category_id': category_id,
                                                                'test_id': test_id,
                                                                'parameter_count': parameter_count,
                                                                'icon': icon_url, 'priority': priority}
            single_test_data_sorted = sorted(list(single_test_data.values()), key=lambda k: k['priority'], reverse= True)
            category_data[temp_package.id] = single_test_data_sorted

        if not parameters.get('from_app'):
            all_packages = all_packages[offset:page * page_size]

        serializer = CustomLabTestPackageSerializer(all_packages, many=True,
                                                    context={'entity_url_dict': entity_url_dict, 'lab_data': lab_data,
                                                             'request': request, 'category_data': category_data,
                                                             'package_free_or_not_dict': package_free_or_not_dict})
        category_queryset = LabTestCategory.objects.filter(id__in=category_to_be_shown_in_filter_ids).order_by('-priority')
        category_result = []
        for category in category_queryset:
            name = category.name
            category_id = category.id
            is_selected = False
            if category_ids is not None and category_id in category_ids:
                is_selected = True
            category_result.append({'name': name, 'id': category_id, 'is_selected': is_selected})

        result = serializer.data
        if result:
            from ondoc.coupon.models import Coupon
            search_coupon = Coupon.get_search_coupon(request.user)

            for package_result in result:
                if "price" in package_result:
                    price = int(float(package_result["price"]))
                    discounted_price = price if not search_coupon else search_coupon.get_search_coupon_discounted_price(price)
                    package_result["discounted_price"] = discounted_price

        top_content = None
        bottom_content = None
        title = None
        description = None
        dynamic = NewDynamic.objects.filter(url__url='full-body-checkup-health-packages', is_enabled=True)
        for x in dynamic:
            top_content = x.top_content if x.top_content else None
            bottom_content = x.bottom_content if x.bottom_content else None
            title = x.meta_title if x.meta_title else None
            description = x.meta_description if x.meta_description else None
        return Response({'result': result, 'categories': category_result, 'count': result_count,
                         'categories_count': len(category_result), 'bottom_content': bottom_content,
                         'search_content': top_content, 'title': title, 'description': description})

    @transaction.non_atomic_requests
    def package_list(self, request, **kwrgs):
        parameters = request.query_params
        serializer = diagnostic_serializer.LabPackageListSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        long = validated_data.get('long')
        lat = validated_data.get('lat')
        min_distance = validated_data.get('min_distance')
        max_distance = validated_data.get('max_distance')
        min_price = validated_data.get('min_price')
        max_price = validated_data.get('max_price')
        max_age = validated_data.get('max_age')
        min_age = validated_data.get('min_age')
        gender = validated_data.get('gender')
        package_type = validated_data.get('package_type')
        sort_on = validated_data.get('sort_on')
        category_ids = validated_data.get('category_ids', [])
        package_category_ids = validated_data.get('package_category_ids', [])
        test_ids = validated_data.get('test_ids', [])
        package_ids = validated_data.get('package_ids', [])
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)
        max_distance = max_distance*1000 if max_distance is not None else 10000
        min_distance = min_distance*1000 if min_distance is not None else 0

        package_free_or_not_dict = get_package_free_or_not_dict(request)

        main_queryset = LabTest.objects.prefetch_related('test', 'test__recommended_categories',
                                                         'test__parameter', 'categories').filter(enable_for_retail=True,
                                                                                                 searchable=True,
                                                                                                 is_package=True)

        page_size = 30

        if not request.query_params.get('page') or int(request.query_params.get('page')) <1:
            page = 1
        else:
            page = int(request.query_params.get('page'))

        offset = (page - 1) * page_size

        if package_ids:
            main_queryset = main_queryset.filter(id__in=package_ids)
        valid_package_ids = None

        if test_ids:
            valid_package_ids = list(LabTest.objects.filter(test__id__in=test_ids).annotate(
                included_test_count=Count('test')).filter(
                included_test_count=len(test_ids)).distinct().values_list('id', flat=True))

        if category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(list(
                LabTest.objects.filter(test__recommended_categories__id__in=category_ids).distinct().values_list('id',
                                                                                                                 flat=True)))

        if package_category_ids:
            if valid_package_ids is None:
                valid_package_ids = []
            valid_package_ids.extend(list(
                LabTest.objects.filter(categories__id__in=package_category_ids).distinct().values_list('id',
                                                                                               flat=True)))

        if valid_package_ids is not None:
            main_queryset = main_queryset.filter(id__in=valid_package_ids)

        all_packages_in_labs = main_queryset.filter(
            availablelabs__enabled=True,
            availablelabs__lab_pricing_group__labs__is_live=True,
            availablelabs__lab_pricing_group__labs__enabled=True,
            availablelabs__lab_pricing_group__labs__location__dwithin=(
                Point(float(long),
                      float(lat)),
                D(m=max_distance))).annotate(
            priority_score=F('availablelabs__lab_pricing_group__labs__lab_priority') * F(
                'priority')).annotate(
            distance=Distance('availablelabs__lab_pricing_group__labs__location',
                              pnt)).annotate(
            lab=F('availablelabs__lab_pricing_group__labs'), mrp=F('availablelabs__mrp'),
            price=Case(
                When(availablelabs__custom_deal_price__isnull=True,
                     then=F('availablelabs__computed_deal_price')),
                When(availablelabs__custom_deal_price__isnull=False,
                     then=F('availablelabs__custom_deal_price'))),
            rank=Window(expression=RowNumber(), order_by=F('distance').asc(),
                        partition_by=[RawSQL('Coalesce(lab.network_id, random())', []), F('id')])
        )

        all_packages_in_labs = all_packages_in_labs.distinct()
        if not sort_on:
            all_packages_in_labs = all_packages_in_labs.order_by('-priority_score')

        if sort_on == 'fees':
            all_packages_in_labs = all_packages_in_labs.order_by('price')

        elif sort_on == 'distance':
            all_packages_in_labs = all_packages_in_labs.order_by('distance')

        # all_packages_in_labs = list(all_packages_in_labs)
        # all_packages = filter(lambda x: x.rank == 1, all_packages_in_labs)
        all_packages = [package for package in all_packages_in_labs if package.rank == 1]
        # all_packages = filter(lambda x: x, all_packages)
        if min_distance:
            all_packages = filter(lambda
                                      x: x.distance.m >= min_distance if x.distance is not None and x.distance.m is not None else False,
                                  all_packages)
        if min_price:
            all_packages = filter(lambda x: x.price >= min_price if x.price is not None else False, all_packages)
        if max_price:
            all_packages = filter(lambda x: x.price <= max_price if x.price is not None else False, all_packages)
        if min_age and max_age:
            all_packages = filter(lambda x: (x.min_age <= max_age if x.min_age is not None else False) and (
                x.max_age >= min_age if x.max_age is not None else False), all_packages)
        elif max_age:
            all_packages = filter(lambda x: x.min_age <= max_age if x.min_age is not None else False, all_packages)
        elif min_age:
            all_packages = filter(lambda x: x.max_age >= min_age if x.max_age is not None else False, all_packages)
        if gender:
            all_packages = filter(
                lambda x: x.gender_type in [gender, LabTest.ALL] if x.gender_type is not None else False, all_packages)
        if package_type == 1:
            all_packages = filter(lambda x: x.home_collection_possible, all_packages)
        if package_type == 2:
            all_packages = filter(lambda x: not x.home_collection_possible, all_packages)

        all_packages = [package for package in all_packages]
        lab_ids = [package.lab for package in all_packages]
        entity_url_qs = EntityUrls.objects.filter(entity_id__in=lab_ids, is_valid=True, url__isnull=False,
                                                  sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).values(
            'url', lab_id=F('entity_id'))
        entity_url_dict = {}
        for item in entity_url_qs:
            entity_url_dict.setdefault(item.get('lab_id'), [])
            entity_url_dict[item.get('lab_id')].append(item.get('url'))
        lab_data = Lab.objects.prefetch_related('rating', 'lab_documents', 'lab_timings', 'network',
                                                'home_collection_charges').in_bulk(lab_ids)
        category_data = {}
        test_package_ids = set([package.id for package in all_packages])
        test_package_queryset = LabTest.objects.prefetch_related('test__recommended_categories',
                                                                 'test__parameter').filter(id__in=test_package_ids)
        for temp_package in test_package_queryset:
            single_test_data = {}
            for temp_test in temp_package.test.all():
                add_test_name = True
                for temp_category in temp_test.recommended_categories.all():
                    add_test_name = False
                    name = temp_category.name
                    category_id = temp_category.id
                    test_id = None
                    icon_url = util_absolute_url(temp_category.icon.url) if temp_category.icon else None
                    parameter_count = len(temp_test.parameter.all()) or 1
                    if single_test_data.get((category_id, test_id)):
                        single_test_data[(category_id, test_id)]['parameter_count'] += parameter_count
                    else:
                        single_test_data[(category_id, test_id)] = {'name': name,
                                                                    'category_id': category_id,
                                                                    'test_id': test_id,
                                                                    'parameter_count': parameter_count,
                                                                    'icon': icon_url}
                if add_test_name:
                    category_id = None
                    test_id = temp_test.id
                    name = temp_test.name
                    parameter_count = len(temp_test.parameter.all()) or 1
                    icon_url = None
                    single_test_data[(category_id, test_id)] = {'name': name,
                                                                'category_id': category_id,
                                                                'test_id': test_id,
                                                                'parameter_count': parameter_count,
                                                                'icon': icon_url}
            category_data[temp_package.id] = list(single_test_data.values())

        all_packages_data = None
        if not parameters.get('from_app'):
            all_packages_data = all_packages[offset:page * page_size]
        else:
            all_packages_data = all_packages
        serializer = CustomLabTestPackageSerializer(all_packages_data, many=True,
                                                    context={'entity_url_dict': entity_url_dict, 'lab_data': lab_data,
                                                             'request': request, 'category_data': category_data})
        category_queryset = LabTestCategory.objects.filter(is_package_category=True, is_live=True)
        category_result = []
        for category in category_queryset:
            name = category.name
            category_id = category.id
            is_selected = False
            if category_ids is not None and category_id in category_ids:
                is_selected = True
            category_result.append({'name': name, 'id': category_id, 'is_selected': is_selected})

        result = serializer.data
        if result:
            from ondoc.coupon.models import Coupon
            search_coupon = Coupon.get_search_coupon(request.user)

            for package_result in result:
                if "price" in package_result:
                    price = int(float(package_result["price"]))
                    discounted_price = price if not search_coupon else search_coupon.get_search_coupon_discounted_price(
                        price)
                    package_result["discounted_price"] = discounted_price

        top_content = None
        bottom_content = None
        title = None
        description = None
        dynamic = NewDynamic.objects.filter(url__url='full-body-checkup-health-packages', is_enabled=True)
        for x in dynamic:
            top_content = x.top_content if x.top_content else None
            bottom_content = x.bottom_content if x.bottom_content else None
            title = x.meta_title if x.meta_title else None
            description = x.meta_description if x.meta_description else None
        return Response({'result': result, 'categories': category_result, 'count': len(all_packages),
                         'categories_count': len(category_result), 'bottom_content': bottom_content,
                         'search_content': top_content, 'title': title, 'description': description})


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
                    return Response(status=status.HTTP_404_NOT_FOUND)

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
            response = self.retrieve(request, entity.entity_id, entity)
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

        # Insurance check for logged in user
        logged_in_user = request.user
        insurance_threshold = InsuranceThreshold.objects.all().order_by('-lab_amount_limit').first()
        insurance_data_dict = {
            'is_user_insured': False,
            'insurance_threshold_amount': insurance_threshold.lab_amount_limit if insurance_threshold else 5000
        }

        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
            user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
            if user_insurance and user_insurance.is_valid():
                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                if insurance_threshold:
                    insurance_data_dict['insurance_threshold_amount'] = 0 if insurance_threshold.lab_amount_limit is None else \
                        insurance_threshold.lab_amount_limit
                    insurance_data_dict['is_user_insured'] = True

        parameters = serializer.validated_data

        parameters['insurance_threshold_amount'] = insurance_data_dict['insurance_threshold_amount']

        queryset = self.get_lab_list(parameters)
        count = queryset.count()
        paginated_queryset = paginate_queryset(queryset, request)
        response_queryset = self.form_lab_whole_data(paginated_queryset, parameters.get("ids"))

        serializer = diagnostic_serializer.LabCustomSerializer(response_queryset,  many=True,
                                         context={"request": request, "insurance_data_dict": insurance_data_dict})

        entity_ids = [lab_data['id'] for lab_data in response_queryset]

        id_url_dict = dict()
        entity = EntityUrls.objects.filter(entity_id__in=entity_ids, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Lab').values('entity_id', 'url')
        for data in entity:
            id_url_dict[data['entity_id']] = data['url']

        for resp in serializer.data:

            resp_tests = resp['tests']
            bool_array = list()
            for resp_test in resp_tests:
                insurance_coverage = resp_test.get('mrp') <= insurance_data_dict['insurance_threshold_amount']
                bool_array.append(insurance_coverage)

            if False not in bool_array and len(bool_array) > 0:
                resp['insurance']['is_insurance_covered'] = True

            if id_url_dict.get(resp['lab']['id']):
                resp['lab']['url'] = id_url_dict[resp['lab']['id']]
            else:
                resp['lab']['url'] = None

        test_ids = parameters.get('ids',[])

        tests = list(LabTest.objects.filter(id__in=test_ids, enable_for_retail=True).values('id', 'name', 'hide_price', 'show_details', 'url'))
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
    def search_by_url(self, request, *args, **kwargs):
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
                    return Response(status=status.HTTP_404_NOT_FOUND)

            extras = entity.additional_info
            if extras.get('location_json'):
                kwargs['location_json'] = extras.get('location_json')
                kwargs['url'] = url
                kwargs['parameters'] = get_lab_search_details(extras, request.query_params)
                response = self.search(request, **kwargs)
                return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.non_atomic_requests
    def search(self, request, **kwargs):
        tests = []
        parameters = request.query_params
        if kwargs.get('parameters'):
            parameters = kwargs.get('parameters')

        # Insurance check for logged in user
        logged_in_user = request.user
        insurance_threshold = InsuranceThreshold.objects.all().order_by('-lab_amount_limit').first()
        insurance_data_dict = {
            'is_user_insured': False,
            'insurance_threshold_amount': insurance_threshold.lab_amount_limit if insurance_threshold else 5000,
            'is_insurance_covered' : False
        }

        is_insurance_covered = False

        if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
            user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
            if user_insurance and user_insurance.is_valid():
                insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
                if insurance_threshold:
                    insurance_data_dict['insurance_threshold_amount'] = 0 if insurance_threshold.lab_amount_limit is None else \
                        insurance_threshold.lab_amount_limit
                    insurance_data_dict['is_user_insured'] = True


        test_ids = parameters.get('ids', [])
        if test_ids:
            try:
                if not isinstance(test_ids, list) and isinstance(test_ids, str):
                    test_ids = test_ids.split(",")
                    new_test_ids = [x for x in test_ids if x]
                    tests = list(
                        LabTest.objects.filter(id__in=new_test_ids).values('id', 'name', 'hide_price', 'show_details',
                                                                           'test_type', 'url'))
            except:
                tests = []
            if not tests:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        serializer = diagnostic_serializer.SearchLabListSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        if kwargs.get('location_json'):
            serializer.validated_data['location_json'] = kwargs['location_json']
        if kwargs.get('url'):
            serializer.validated_data['url'] = kwargs['url']
        parameters = serializer.validated_data
        page = int(request.query_params.get('page', 1))

        parameters['insurance_threshold_amount'] = insurance_data_dict['insurance_threshold_amount']
        queryset_result = self.get_lab_search_list(parameters, page)
        count = 0
        if len(queryset_result)>0:
            count = queryset_result[0].get("result_count",0)

        #count = len(queryset_result)
        #paginated_queryset = paginate_queryset(queryset_result, request)
        result = self.form_lab_search_whole_data(queryset_result, parameters.get("ids"), insurance_data_dict=insurance_data_dict)


        if result:
            from ondoc.coupon.models import Coupon
            search_coupon = Coupon.get_search_coupon(request.user)

            for lab_result in result:
                if "price" in lab_result:
                    discounted_price = lab_result["price"] if not search_coupon else search_coupon.get_search_coupon_discounted_price(lab_result["price"])
                    lab_result["discounted_price"] = discounted_price

        # result = list()
        # for data in response_queryset.items():
        # result.append(data[1])

        # serializer = diagnostic_serializer.LabNetworkSerializer(response_queryset, many=True,
        #                                                        context={"request": request})

        # entity_ids = [lab_data.get('id')for lab_data in result]
        #
        # id_url_dict = dict()


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

        if kwargs.get('test_flag') == 1:
            result = list(result)
            return {"result": result[0:3] if len(result)>0 else result,
                             "count": count, 'tests': tests,
                             "seo": seo, 'breadcrumb': breadcrumb}


        return Response({"result": result,
                         "count": count, 'tests': tests,
                         "seo": seo, 'breadcrumb':breadcrumb})

    def get_lab_search_list(self, parameters, page):
        # distance in meters

        DEFAULT_DISTANCE = 20000
        MAX_SEARCHABLE_DISTANCE = 50000

        if not page or page<1:
            page = 1

        default_long = 77.071848
        default_lat = 28.450367
        min_distance = parameters.get('min_distance')
        max_distance = parameters.get('max_distance')*1000 if parameters.get('max_distance') else DEFAULT_DISTANCE
        max_distance = min(max_distance, MAX_SEARCHABLE_DISTANCE)
        long = parameters.get('long', default_long)
        lat = parameters.get('lat', default_lat)
        ids = parameters.get('ids', [])
        min_price = parameters.get('min_price', 0)
        max_price = parameters.get('max_price')
        name = parameters.get('name')
        network_id = parameters.get("network_id")
        is_insurance = parameters.get('is_insurance')
        insurance_threshold_amount = parameters.get('insurance_threshold_amount')
        availability = parameters.get('availability', None)
        avg_ratings = parameters.get('avg_ratings', None)
        home_visit = parameters.get('home_visit', False)
        lab_visit = parameters.get('lab_visit', False)

        #filtering_params = []
        #filtering_params_query1 = []
        filtering_query = []
        filtering_params = {}
        #params = {}
        if not min_distance:
            min_distance = 0

        filtering_params['min_distance'] = min_distance
        filtering_params['max_distance'] = max_distance
        filtering_params['latitude'] = lat
        filtering_params['longitude'] = long

        if network_id:
            filtering_query.append("lb.network_id=(%(network_id)s)")
            filtering_params['network_id'] = str(network_id)

        if name:
            search_key = re.findall(r'[a-z0-9A-Z.:]+',name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            filtering_query.append("lb.name ilike %(name)s")
            filtering_params['name'] = search_key + '%'
            # filtering_params_query1.append(
            #     "name ilike %(name)s")

        #test_params = []

        if ids and len(ids)>0:
            counter = 1
            test_str = 'avlt.test_id IN('
            for id in ids:
                if not counter == 1:
                    test_str += ','
                test_str = test_str + '%(' + 'test' + str(counter) + ')s'
                filtering_params['test' + str(counter)] = id
                counter += 1
            filtering_query.append(
                test_str + ')'
            )

            filtering_params['length'] = len(ids)

        # else:
        #     params['length']=0

        group_filter=[]

        if min_price:
            group_filter.append("price>=(%(min_price)s)")
            filtering_params['min_price'] = min_price
        if max_price:
            group_filter.append("price<=(%(max_price)s)")
            filtering_params['max_price'] = max_price

        if is_insurance and ids:
            filtering_query.append("mrp<=(%(insurance_threshold_amount)s)")
            filtering_params['insurance_threshold_amount'] = insurance_threshold_amount

        if avg_ratings:
            filtering_query.append("(case when rating_data is not null then(rating_data->> 'avg_rating')::float > (%(avg_ratings)s) end)")
            filtering_params['avg_ratings'] = max(avg_ratings)

        if ids:
            if home_visit and not lab_visit:
                filtering_query.append('  is_home_collection_enabled = True and home_collection_possible = True ')
            if lab_visit and not home_visit:
                filtering_query.append('  is_home_collection_enabled = False and home_collection_possible = False ')

        # if ids and availability:
        #     start_day = Date.today().weekday()
        #     avail_days = max(map(int, availability))
        #     days = list()
        #     if avail_days == serializers.SearchLabListSerializer.TODAY:
        #         days.append(start_day)
        #     elif avail_days == serializers.SearchLabListSerializer.TOMORROW:
        #         days.append(start_day)
        #         days.append(0 if start_day == 6 else start_day + 1)
        #     elif avail_days == serializers.SearchLabListSerializer.NEXT_3_DAYS:
        #         for day in range(4):
        #             days.append(0 if start_day == 6 else start_day + 1)
        #
        #     counter = 1
        #     if len(days) > 0:
        #         lab_days_str = 'lbt.day IN ('
        #         for day in days:
        #             if not counter == 1:
        #                 lab_days_str += ','
        #             lab_days_str = lab_days_str + '%(' + 'lab_day' + str(counter) + ')s'
        #             filtering_params['lab_day' + str(counter)] = day
        #             counter += 1
        #         filtering_query.append(lab_days_str + ')')

        filter_query_string = ""
        if len(filtering_query) > 0:
            filter_query_string = " and "+" and ".join(filtering_query)
        
        group_filter_query_string = ""

        if len(group_filter)>0:
            group_filter_query_string = " where "+" and ".join(group_filter)

        filtering_params['page_start'] = (page-1)*20
        filtering_params['page_end'] = page*20

        # filtering_result = {}
        # if filtering_params:
        #     filtering_result['string'] = " and ".join(filtering_params)
        # if filtering_result.get('string'):
        #     filtering_result = 'and ' + filtering_result.get('string')
        # else:
        #     filtering_result = ' '
        # filtering_params_query1_result = {}
        # if filtering_params_query1:
        #     filtering_params_query1_result['string'] = " and ".join(filtering_params_query1)
        # if filtering_params_query1_result.get('string'):
        #     filtering_params_query1_result = 'and ' + filtering_params_query1_result.get('string')
        # else:
        #     filtering_params_query1_result = ' '

        # test_result={}

        # if test_params:
        #     test_result['string'] = " and ".join(test_params)

        # price_result={}
        # if price:
        #     price_result['string'] = " and ".join(price)
        # else:
        #     price_result['string'] = 'where price>=0'

        order_by = self.apply_search_sort(parameters)

        if ids:
            query = ''' select * from (select id,network_id, name ,price, count, mrp, pickup_charges, distance, order_priority, new_network_rank, rank,
            max(new_network_rank) over(partition by 1) result_count
            from ( 
            select id,network_id, name ,price, count, mrp, pickup_charges, distance, order_priority, 
                        dense_rank() over(order by network_rank) as new_network_rank, rank from
                        (
                        select id,network_id, rank() over(partition by coalesce(network_id,random()) order by order_rank) as rank,
                         min (order_rank) OVER (PARTITION BY coalesce(network_id,random())) network_rank,
                         name ,price, count, mrp, pickup_charges, distance, order_priority from
                        (select id,network_id,  
                        name ,price, test_count as count, total_mrp as mrp,pickup_charges, distance, 
                        ROW_NUMBER () OVER (ORDER BY {order} ) order_rank,
                        max_order_priority as order_priority
                        from (
                        select lb.*, sum(mrp) total_mrp, count(*) as test_count,
                        case when bool_and(home_collection_possible)=True and is_home_collection_enabled=True 
                        then max(home_pickup_charges) else 0
                        end as pickup_charges,
                        sum(case when custom_deal_price is null then computed_deal_price else custom_deal_price end)as price,
                        max(ST_Distance(location,St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326))) as distance,
                        max(order_priority) as max_order_priority from lab lb inner join available_lab_test avlt on
                        lb.lab_pricing_group_id = avlt.lab_pricing_group_id  
                        and lb.is_test_lab = False and lb.is_live = True and lb.lab_pricing_group_id is not null 
                        and St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326),lb.location, (%(max_distance)s)) 
                        and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), lb.location,  (%(min_distance)s)) = false 
                        and avlt.enabled = True 
                        inner join lab_test lt on lt.id = avlt.test_id and lt.enable_for_retail=True 
                         where 1=1 {filter_query_string}

                        group by lb.id having count(*)=(%(length)s))a
                        {group_filter_query_string})y )x where rank<=5 )z 
                        )r
                        where new_network_rank<=(%(page_end)s) and new_network_rank>(%(page_start)s) order by new_network_rank, rank
                         '''.format(filter_query_string=filter_query_string, 
                            group_filter_query_string=group_filter_query_string, order=order_by)

            lab_search_result = RawSql(query, filtering_params).fetch_all()
        else:
            query1 = '''select * from (select id,network_id, name , distance, order_priority, new_network_rank, rank,
                    max(new_network_rank) over(partition by 1) result_count from 
                    (select id,network_id, name , distance, order_priority, 
                    dense_rank() over(order by network_rank) as new_network_rank, rank from
                    (
                    select id,network_id,rank() over(partition by coalesce(network_id,random()) order by order_rank) as rank,
                     min (order_rank) OVER (PARTITION BY coalesce(network_id,random())) network_rank,
                     name , distance, order_priority from
                    (select id,network_id,  
                    name , distance, 
                    ROW_NUMBER () OVER (ORDER BY {order} ) order_rank,
                    max_order_priority as order_priority
                    from (
                    select *,
                    max(ST_Distance(location,St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326))) as distance,
                    max(order_priority) as max_order_priority
                    from lab lb where is_test_lab = False and is_live = True and lab_pricing_group_id is not null 
                    and St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326),location, (%(max_distance)s)) 
                    and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), location, (%(min_distance)s)) = false
                    {filter_query_string}
                    group by id)a)y )x where rank<=5)z )r where 
                    new_network_rank<=(%(page_end)s) and new_network_rank>(%(page_start)s) order by new_network_rank, 
                    rank'''.format(
                    filter_query_string=filter_query_string, order=order_by)

            lab_search_result = RawSql(query1, filtering_params).fetch_all()

        return lab_search_result

    def apply_search_sort(self, parameters):
        order_by = parameters.get("sort_on")
        if order_by is not None:
            if order_by == "fees" and parameters.get('ids'):
                if parameters.get('sort_order') == 'desc':
                    queryset_order_by = ' order_priority desc, price + pickup_charges desc, distance asc'
                else:
                    queryset_order_by = ' order_priority desc, price + pickup_charges asc, distance asc'
            elif order_by == 'distance':
                queryset_order_by = ' order_priority desc, distance asc'
            elif order_by == 'name':
                queryset_order_by = ' order_priority desc, name asc'
            else:
                queryset_order_by = ' order_priority desc, distance asc'
        else:
            queryset_order_by =' order_priority desc, distance asc'
        return queryset_order_by

    def form_lab_search_whole_data(self, queryset, test_ids=None, insurance_data_dict={}):
        ids = [value.get('id') for value in queryset]
        # ids, id_details = self.extract_lab_ids(queryset)
        labs = Lab.objects.select_related('network').prefetch_related('lab_documents', 'lab_image', 'lab_timings','home_collection_charges')

        entity = EntityUrls.objects.filter(entity_id__in=ids, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Lab').values('entity_id', 'url')
        id_url_dict = dict()
        for data in entity:
            id_url_dict[data['entity_id']] = data['url']

        if test_ids:
            group_queryset = LabPricingGroup.objects.prefetch_related(Prefetch(
                    "available_lab_tests",
                    queryset=AvailableLabTest.objects.filter(test_id__in=test_ids).prefetch_related('test__categories'),
                    to_attr="selected_tests"
                )).all()

            labs = labs.prefetch_related(
                Prefetch(
                    "lab_pricing_group",
                    queryset=group_queryset,
                    to_attr="selected_group"
                )
            )
        labs = labs.filter(id__in=ids)
        # resp_queryset = list()
        temp_var = dict()
        tests = dict()
        lab = dict()

        for obj in labs:
            temp_var[obj.id] = obj
            tests[obj.id] = list()
            if test_ids and obj.selected_group and obj.selected_group.selected_tests:
                for test in obj.selected_group.selected_tests:
                    if test.custom_deal_price:
                        deal_price=test.custom_deal_price
                    else:
                        deal_price=test.computed_deal_price
                    tests[obj.id].append({"id": test.test_id, "name": test.test.name, "deal_price": deal_price, "mrp": test.mrp, "number_of_tests": test.test.number_of_tests, 'categories': test.test.get_all_categories_detail(), "url": test.test.url})

        # day_now = timezone.now().weekday()
        # days_array = [i for i in range(7)]
        # rotated_days_array = days_array[day_now:] + days_array[:day_now]
        #lab_network = dict()
        for row in queryset:

            # lab_timing = list()
            # lab_timing_data = list()
            # next_lab_timing_dict = {}
            # next_lab_timing_data_dict = {}
            # data_array = [list() for i in range(7)]
            lab_obj = temp_var[row["id"]]
            if lab_obj.sublocality and lab_obj.city:
                row['address'] = lab_obj.sublocality + ' ' + lab_obj.city
            elif lab_obj.city:
                row['address'] = lab_obj.city
            else:
                row['address'] = ""
            row['lab_thumbnail'] = util_absolute_url(lab_obj.get_thumbnail()) if lab_obj.get_thumbnail() else None

            # row['lab_thumbnail'] = self.request.build_absolute_uri(lab_obj.get_thumbnail()) if lab_obj.get_thumbnail() else None

            row['home_pickup_charges'] = lab_obj.home_pickup_charges
            row['is_home_collection_enabled'] = lab_obj.is_home_collection_enabled
            row['is_insurance_enabled'] = lab_obj.is_insurance_enabled
            row['avg_rating'] = lab_obj.rating_data.get('avg_rating') if lab_obj.display_rating_on_list() else None
            row['rating_count'] = lab_obj.rating_data.get('rating_count') if lab_obj.display_rating_on_list() else None

            row['avg_rating'] = lab_obj.rating_data.get('avg_rating') if lab_obj.display_rating_on_list() else None
            row['rating_count'] = lab_obj.rating_data.get('rating_count') if lab_obj.display_rating_on_list() else None
            # if lab_obj.always_open:
            #     lab_timing = "12:00 AM - 11:45 PM"
            #     next_lab_timing_dict = {rotated_days_array[1]: "12:00 AM - 11:45 PM"}
            #     lab_timing_data = [{
            #         "start": 0.0,
            #         "end": 23.75
            #     }]
            #     next_lab_timing_data_dict = {rotated_days_array[1]: {
            #         "start": 0.0,
            #         "end": 23.75
            #     }}
            # else:
            #     timing_queryset =lab_obj.lab_timings.all()
            #
            #     for data in timing_queryset:
            #         data_array[data.day].append(data)
            #
            #     rotated_data_array = data_array[day_now:] + data_array[:day_now]
            #
            #     for count, timing_data in enumerate(rotated_data_array):
            #         day = rotated_days_array[count]
            #         if count == 0:
            #             if timing_data:
            #                 lab_timing, lab_timing_data = self.get_lab_timing(timing_data)
            #                 lab_timing_data = sorted(lab_timing_data, key=lambda k: k["start"])
            #         elif timing_data:
            #             next_lab_timing, next_lab_timing_data = self.get_lab_timing(timing_data)
            #             next_lab_timing_data = sorted(next_lab_timing_data, key=lambda k: k["start"])
            #             next_lab_timing_dict[day] = next_lab_timing
            #             next_lab_timing_data_dict[day] = next_lab_timing_data
            #             break

            # {'lab_timing': lab_timing, 'lab_timing_data': lab_timing_data}, {
            #     'next_lab_timing_dict': next_lab_timing_dict, 'next_lab_timing_data_dict': next_lab_timing_data_dict}
            # lab_timing, lab_timing_data, next_lab_timing_dict, next_lab_timing_data_dict = lab_obj.lab_timings_today_and_next()[0:4]
            lab_timing_temp_dict = lab_obj.lab_timings_today_and_next()
            lab_timing, lab_timing_data = lab_timing_temp_dict['lab_timing'], lab_timing_temp_dict['lab_timing_data']
            next_lab_timing_dict, next_lab_timing_data_dict = lab_timing_temp_dict['next_lab_timing_dict'], \
                                                              lab_timing_temp_dict['next_lab_timing_data_dict']

            if lab_obj.home_collection_charges.exists():
                row["distance_related_charges"] = 1
            else:
                row["distance_related_charges"] = 0

            row["lab_timing"] = lab_timing
            row["lab_timing_data"] = lab_timing_data
            row["next_lab_timing"] = next_lab_timing_dict
            row["next_lab_timing_data"] = next_lab_timing_data_dict
            row["tests"] = tests.get(row["id"])

            if lab_obj.id in id_url_dict.keys():
                row['url'] = id_url_dict[lab_obj.id]
            else:
                row['url'] = ''


        lab_network = OrderedDict()
        for res in queryset:
            network_id = res.get('network_id')
            existing = None
            if network_id:
                existing = lab_network.get(network_id)

            if not existing:
                res['other_labs'] = []

                # Insurance logic. Add Insurance dictionary for all labs and for [0] index for
                # lab network case as lab network have more than 1 labs under it.

                res['insurance'] = deepcopy(insurance_data_dict)
                all_tests_under_lab = res.get('tests', [])
                bool_array = list()
                if all_tests_under_lab and res['is_insurance_enabled']:
                    for paticular_test_in_lab in all_tests_under_lab:
                        insurance_coverage = paticular_test_in_lab.get('mrp', 0) <= insurance_data_dict['insurance_threshold_amount']
                        bool_array.append(insurance_coverage)

                    if False not in bool_array and len(bool_array) > 0:
                        res['insurance']['is_insurance_covered'] = True
                elif res['is_insurance_enabled'] and not all_tests_under_lab:
                    res['insurance']['is_insurance_covered'] = True

                #existing = res
                key = network_id
                if not key:
                    key = random.randint(10, 1000000000)
                lab_network[key] = res
            else:
                existing['other_labs'].append(res)

        return lab_network.values()


        # res = dict()
        # for r in

            # if row.get('network_id'):
            #     if lab_network.get('network_id' + str(row.get('network_id'))):
            #
            #         lab_network['network_id' + str(row.get('network_id'))]['other_labs'].append(row)
            #
            #     else:
            #         lab_network['network_id' + str(row.get('network_id'))] = row
            #         if not lab_network.get('network_id' + str(row.get('network_id'))).get('other_labs'):
            #             lab_network.get('network_id' + str(row.get('network_id')))['other_labs'] = list()
            #
            # else:
            #     lab_network['lab_id: '+str(row.get('id'))] = row
            #     if not lab_network.get('lab_id: '+str(row.get('id'))).get('other_labs'):
            #         lab_network.get('lab_id: '+str(row.get('id')))['other_labs'] = list()
            # resp_queryset.append(row)

        return lab_network


    @transaction.non_atomic_requests
    def retrieve(self, request, lab_id, entity=None):

        lab_obj = Lab.objects.select_related('network')\
                             .prefetch_related('rating', 'lab_documents')\
                             .filter(id=lab_id, is_live=True).first()

        if not lab_obj:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not entity:
            entity = EntityUrls.objects.filter(entity_id=lab_id,
                                               sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).order_by('-is_valid')
            if len(entity) > 0:
                entity = entity[0]

        test_ids = (request.query_params.get("test_ids").split(",") if request.query_params.get('test_ids') else [])
        package_free_or_not_dict = get_package_free_or_not_dict(request)
        queryset = AvailableLabTest.objects.prefetch_related('test__labtests__parameter',
                                                             'test__packages__lab_test__recommended_categories',
                                                             'test__packages__lab_test__labtests__parameter').filter(
            lab_pricing_group__labs__id=lab_id,
            lab_pricing_group__labs__is_test_lab=False,
            lab_pricing_group__labs__is_live=True,
            enabled=True,
            test__enable_for_retail=True,
            test__in=test_ids)

        test_serializer = diagnostic_serializer.AvailableLabTestPackageSerializer(queryset, many=True,
                                                                           context={"lab": lab_obj, "request": request, "package_free_or_not_dict": package_free_or_not_dict})
        # for Demo
        demo_lab_test = AvailableLabTest.objects.filter(test__enable_for_retail=True, lab_pricing_group=lab_obj.lab_pricing_group, enabled=True, test__searchable=True).order_by("-test__priority").prefetch_related('test')[:2]
        lab_test_serializer = diagnostic_serializer.AvailableLabTestSerializer(demo_lab_test, many=True, context={"lab": lab_obj, "request": request, "package_free_or_not_dict": package_free_or_not_dict})
        # day_now = timezone.now().weekday()

        timing_queryset = list()
        lab_serializable_data = list()
        lab_timing = None
        lab_timing_data = list()
        distance_related_charges = None

        distance_related_charges = 1 if lab_obj.home_collection_charges.all().exists() else 0
        if lab_obj.always_open:
            lab_timing = "12:00 AM - 11:45 PM"
            lab_timing_data = [{
                "start": 0.0,
                "end": 23.75
            }]
        else:
            # timing_queryset = lab_obj.lab_timings.filter(day=day_now)
            lab_timing_temp_result = lab_obj.lab_timings_today_and_next()
            lab_timing, lab_timing_data = lab_timing_temp_result['lab_timing'], lab_timing_temp_result['lab_timing_data']

            # entity = EntityUrls.objects.filter(entity_id=lab_id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Lab')
        # if entity.exists():
        #     entity = entity.first()
        rating_queryset = lab_obj.rating.filter(is_live=True)
        if lab_obj.network:
            rating_queryset = rating_models.RatingsReview.objects.prefetch_related('compliment')\
                                                                 .filter(is_live=True,
                                                                         lab_ratings__network=lab_obj.network)
        lab_serializer = diagnostic_serializer.LabModelSerializer(lab_obj, context={"request": request,
                                                                                    "entity": entity,
                                                                                    "rating_queryset": rating_queryset})
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

    # def get_lab_timing(self, queryset):
    #     lab_timing = ''
    #     lab_timing_data = list()
    #     temp_list = list()
    #
    #     for qdata in queryset:
    #         temp_list.append({"start": qdata.start, "end": qdata.end})
    #
    #     temp_list = sorted(temp_list, key=lambda k: k["start"])
    #
    #     index = 0
    #     while index < len(temp_list):
    #         temp_dict = dict()
    #         x = index
    #         if not lab_timing:
    #             lab_timing += self.convert_time(temp_list[index]["start"]) + " - "
    #         else:
    #             lab_timing += " | " + self.convert_time(temp_list[index]["start"]) + " - "
    #         temp_dict["start"] = temp_list[index]["start"]
    #         while x + 1 < len(temp_list) and temp_list[x]["end"] >= temp_list[x+1]["start"]:
    #             x += 1
    #         index = x
    #         lab_timing += self.convert_time(temp_list[index]["end"])
    #         temp_dict["end"] = temp_list[index]["end"]
    #         lab_timing_data.append(temp_dict)
    #         index += 1
    #
    #     return lab_timing, lab_timing_data

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
        is_insurance = parameters.get('is_insurance')
        insurance_threshold_amount = parameters.get('insurance_threshold_amount')

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

            if is_insurance:
                queryset = queryset.filter(mrp__lte=insurance_threshold_amount)

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

    def form_lab_whole_data(self, queryset, test_ids=None):
        ids = [value.get('id') for value in queryset]
        # ids, id_details = self.extract_lab_ids(queryset)
        labs = Lab.objects.select_related('network').prefetch_related('lab_documents', 'lab_image', 'lab_timings','home_collection_charges')

        if test_ids:
            group_queryset = LabPricingGroup.objects.prefetch_related(Prefetch(
                    "available_lab_tests",
                    queryset=AvailableLabTest.objects.filter(test_id__in=test_ids).prefetch_related('test'),
                    to_attr="selected_tests"
                )).all()

            labs = labs.prefetch_related(
                Prefetch(
                    "lab_pricing_group",
                    queryset=group_queryset,
                    to_attr="selected_group"
                )
            )
        labs = labs.filter(id__in=ids)
        resp_queryset = list()
        temp_var = dict()
        tests = dict()

        for obj in labs:
            temp_var[obj.id] = obj
            tests[obj.id] = list()
            if test_ids and obj.selected_group and obj.selected_group.selected_tests:
                for test in obj.selected_group.selected_tests:
                    if test.custom_deal_price:
                        deal_price=test.custom_deal_price
                    else:
                        deal_price=test.computed_deal_price
                    tests[obj.id].append({"id": test.test_id, "name": test.test.name, "deal_price": deal_price, "mrp": test.mrp,
                                          "url":test.test.url, "show_details": test.test.show_details})
        # day_now = timezone.now().weekday()
        # days_array = [i for i in range(7)]
        # rotated_days_array = days_array[day_now:] + days_array[:day_now]
        for row in queryset:
        #     lab_timing = list()
        #     lab_timing_data = list()
        #     next_lab_timing_dict = {}
        #     next_lab_timing_data_dict = {}
        #     data_array = [list() for i in range(7)]
            row["lab"] = temp_var[row["id"]]
        #
        #     if row["lab"].always_open:
        #         lab_timing = "12:00 AM - 11:45 PM"
        #         next_lab_timing_dict = {rotated_days_array[1]: "12:00 AM - 11:45 PM"}
        #         lab_timing_data = [{
        #             "start": 0.0,
        #             "end": 23.75
        #         }]
        #         next_lab_timing_data_dict = {rotated_days_array[1]: {
        #             "start": 0.0,
        #             "end": 23.75
        #         }}
        #     else:
        #         timing_queryset = row["lab"].lab_timings.all()
        #
        #         for data in timing_queryset:
        #             data_array[data.day].append(data)
        #
        #         rotated_data_array = data_array[day_now:] + data_array[:day_now]
        #
        #         for count, timing_data in enumerate(rotated_data_array):
        #             day = rotated_days_array[count]
        #             if count == 0:
        #                 if timing_data:
        #                     lab_timing, lab_timing_data = self.get_lab_timing(timing_data)
        #                     lab_timing_data = sorted(lab_timing_data, key=lambda k: k["start"])
        #             elif timing_data:
        #                 next_lab_timing, next_lab_timing_data = self.get_lab_timing(timing_data)
        #                 next_lab_timing_data = sorted(next_lab_timing_data, key=lambda k: k["start"])
        #                 next_lab_timing_dict[day] = next_lab_timing
        #                 next_lab_timing_data_dict[day] = next_lab_timing_data
        #                 break

            lab_timing_temp_dict = row["lab"].lab_timings_today_and_next()
            lab_timing, lab_timing_data = lab_timing_temp_dict['lab_timing'], lab_timing_temp_dict['lab_timing_data']
            next_lab_timing_dict, next_lab_timing_data_dict = lab_timing_temp_dict['next_lab_timing_dict'], \
                                                              lab_timing_temp_dict['next_lab_timing_data_dict']

            if row["lab"].home_collection_charges.exists():
                row["distance_related_charges"] = 1
            else:
                row["distance_related_charges"] = 0

            row["lab_timing"] = lab_timing
            row["lab_timing_data"] = lab_timing_data
            row["next_lab_timing"] = next_lab_timing_dict
            row["next_lab_timing_data"] = next_lab_timing_data_dict
            row["tests"] = tests.get(row["id"])
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
                Q(status__in=[models.LabAppointment.COMPLETED, models.LabAppointment.CANCELLED]) | Q(time_slot_start__date__lt=timezone.now()))\
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


    @staticmethod
    def update_plan_details(request, data):
        from ondoc.doctor.models import OpdAppointment
        user = request.user
        active_plan_mapping = UserPlanMapping.get_active_plans(user).first()
        user_plan_id = None
        included_in_user_plan = False
        test_included_in_user_plan = UserPlanMapping.get_free_tests(request)
        selected_test_id = [x for x in data.get('test_ids', [])]
        if sorted(selected_test_id) == sorted(test_included_in_user_plan):
            if active_plan_mapping:
                user_plan_id = active_plan_mapping.id
                included_in_user_plan = True
                data.update(
                    {'included_in_user_plan': included_in_user_plan, 'user_plan': user_plan_id})
                data['payment_type'] = OpdAppointment.PLAN

        if not included_in_user_plan:
            data.update(
                {'included_in_user_plan': included_in_user_plan, 'user_plan': user_plan_id})

        # TODO: SHASHANK_SINGH not sure ask shubham
        if data.get('cart_item'):
            old_cart_obj = Cart.objects.filter(id=data.get('cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type')
            if payment_type == OpdAppointment.PLAN and data.get('data')['included_in_user_plan'] == False:
                data.get('data')['payment_type'] = OpdAppointment.PREPAID

    @transaction.atomic
    def create(self, request, **kwargs):
        from ondoc.doctor.models import OpdAppointment
        data = dict(request.data)
        if not data.get("is_home_pickup"):
            data.pop("address", None)

        self.update_plan_details(request, data)
        serializer = diagnostic_serializer.LabAppointmentCreateSerializer(data=data, context={'request': request, 'data' : request.data, 'use_duplicate' : True})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user_insurance = UserInsurance.get_user_insurance(request.user)
        if user_insurance:
            insurance_validate_dict = user_insurance.validate_insurance(validated_data)
            data['is_appointment_insured'] = insurance_validate_dict['is_insured']
            data['insurance_id'] = insurance_validate_dict['insurance_id']
            data['insurance_message'] = insurance_validate_dict['insurance_message']

            if data['is_appointment_insured']:
                data['payment_type'] = OpdAppointment.INSURANCE
        else:
            data['is_appointment_insured'], data['insurance_id'], data[
                'insurance_message'] = False, None, ""
        # data['is_appointment_insured'], data['insurance_id'], data['insurance_message'] = Cart.check_for_insurance(validated_data, request)

        cart_item_id = validated_data.get('cart_item').id if validated_data.get('cart_item') else None

        if validated_data.get("existing_cart_item"):
            cart_item = validated_data.get("existing_cart_item")
            old_cart_obj = Cart.objects.filter(id=validated_data.get('existing_cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type')
            if payment_type == OpdAppointment.INSURANCE and data['is_appointment_insured'] == False:
                data['payment_type'] = OpdAppointment.PREPAID
            # cart_item.data = request.data
            cart_item.data = data
            cart_item.save()
        else:
            cart_item, is_new = Cart.objects.update_or_create(id=cart_item_id, deleted_at__isnull=True, product_id=account_models.Order.LAB_PRODUCT_ID,
                                                  user=request.user, defaults={"data": data})

        if hasattr(request, 'agent') and request.agent:
            resp = { 'is_agent': True , "status" : 1 }
        else:
            resp = account_models.Order.create_order(request, [cart_item], validated_data.get("use_wallet"))

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

        coupon_discount, coupon_cashback, coupon_list = Coupon.get_total_deduction(data, effective_price)

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
            "discount": int(coupon_discount),
            "cashback": int(coupon_cashback)
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

    def create_order(self, request, appointment_details, product_id, use_wallet=True):

        user = request.user
        balance = 0
        cashback_balance = 0

        if use_wallet:
            consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance
            cashback_balance = consumer_account.cashback

        total_balance = balance + cashback_balance
        resp = {}

        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            balance = 0
            resp['is_agent'] = True

        can_use_insurance, insurance_id, insurance_fail_message = self.can_use_insurance(user, appointment_details)
        if can_use_insurance:
            appointment_details['insurance'] = insurance_id
            appointment_details['effective_price'] = appointment_details['agreed_price']
            appointment_details["effective_price"] += appointment_details["home_pickup_charges"]
            appointment_details['payment_type'] = doctor_model.OpdAppointment.INSURANCE
        elif appointment_details['payment_type'] == doctor_model.OpdAppointment.INSURANCE:
            resp['status'] = 0
            resp['message'] = insurance_fail_message
            return resp
        else:
            appointment_details['insurance'] = None


        appointment_action_data = copy.deepcopy(appointment_details)
        appointment_action_data = labappointment_transform(appointment_action_data)

        account_models.Order.disable_pending_orders(appointment_action_data, product_id,
                                                    account_models.Order.LAB_APPOINTMENT_CREATE)


        if ( (appointment_details['payment_type'] == doctor_model.OpdAppointment.PREPAID and
              total_balance < appointment_details.get("effective_price")) or resp['is_agent'] ):

            payable_amount = max(0, appointment_details.get("effective_price") - total_balance)
            required_amount = appointment_details.get("effective_price")
            cashback_amount = min(required_amount, cashback_balance)
            wallet_amount = 0
            if cashback_amount < required_amount:
                wallet_amount = min(balance, required_amount - cashback_amount)

            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.LAB_APPOINTMENT_CREATE,
                action_data=appointment_action_data,
                amount=payable_amount,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )

            appointment_details["payable_amount"] = payable_amount
            resp["status"] = 1
            resp['data'], resp['payment_required'] = payment_details(request, order)
            try:
                ops_email_data = dict()
                ops_email_data.update(order.appointment_details())
                ops_email_data["transaction_time"] = aware_time_zone(timezone.now())
                # EmailNotification.ops_notification_alert(ops_email_data, settings.OPS_EMAIL_ID,
                #                                          order.product_id,
                #                                          EmailNotification.OPS_PAYMENT_NOTIFICATION)

                # push_order_to_matrix.apply_async(
                #     ({'order_id': order.id, 'created_at': int(order.created_at.timestamp()),
                #       'timeslot': int(appointment_details['time_slot_start'].timestamp())},), countdown=5)
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
                action=account_models.Order.LAB_APPOINTMENT_CREATE,
                action_data=appointment_action_data,
                amount=0,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )

            appointment_object = order.process_order()

            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {"id": appointment_object.id,
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

    def can_use_insurance(self, user, appointment_details):
        user_insurance_obj = UserInsurance.get_user_insurance(user)
        if not user_insurance_obj:
            return False, None, ''
        insurance_validate_dict = user_insurance_obj.validate_insurance(appointment_details)
        insurance_check = insurance_validate_dict['is_insured']
        insurance_id = insurance_validate_dict['insurance_id']
        fail_message = insurance_validate_dict['insurance_message']

        return insurance_check, insurance_id, fail_message
        # Check if appointment can be covered under insurance
        # also return a valid message
        # return False, 'Not covered under insurance'

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

    @transaction.non_atomic_requests
    def list_new(self, request, *args, **kwargs):
        params = request.query_params

        for_home_pickup = True if int(params.get('pickup', 0)) else False
        lab = params.get('lab')

        # Added for Thyrocare integration
        from ondoc.integrations import service
        pincode = params.get('pincode')
        date = params.get('date')
        integration_dict = None
        if lab:
            lab_obj = Lab.objects.filter(id=int(lab), is_live=True).first()
            if lab_obj and lab_obj.network and lab_obj.network.id:
                integration_dict = IntegratorTestMapping.get_if_third_party_integration(network_id=lab_obj.network.id)

                if lab_obj.network.id == settings.THYROCARE_NETWORK_ID and settings.THYROCARE_INTEGRATION_ENABLED:
                    pass
                else:
                    integration_dict = None

        if not integration_dict:
            lab_slots = lab_obj.get_timing(for_home_pickup)
            resp_data = {"time_slots": lab_slots}
        else:
            class_name = integration_dict['class_name']
            integrator_obj = service.create_integrator_obj(class_name)
            data = integrator_obj.get_appointment_slots(pincode, date, is_home_pickup=for_home_pickup)
            resp_data = {"time_slots": data}

        # resp_data = LabTiming.timing_manager.lab_booking_slots(lab__id=lab, lab__is_live=True, for_home_pickup=for_home_pickup)
        # global_leave_serializer = v2_serializers.GlobalNonBookableSerializer(
        #     GlobalNonBookable.objects.filter(deleted_at__isnull=True, booking_type=GlobalNonBookable.LAB), many=True)
        # for agent do not set any time limitations
        if hasattr(request, "agent") and request.agent:
            resp_data = {
                "time_slots" : resp_data["time_slots"],
                "today_min": None,
                "tomorrow_min": None,
                "today_max": None
            }
        # resp_data['global_leaves'] = global_leave_serializer.data
        return Response(resp_data)


class AvailableTestViewSet(mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    queryset = AvailableLabTest.objects.filter(test__searchable=True, lab_pricing_group__labs__is_live=True).all()
    serializer_class = diagnostic_serializer.AvailableLabTestSerializer

    @transaction.non_atomic_requests
    def retrieve(self, request, lab_id):
        params = request.query_params
        queryset = AvailableLabTest.objects.select_related().filter(test__searchable=True,
                                                                    test__enable_for_retail=True,
                                                                    lab_pricing_group__labs=lab_id,
                                                                    lab_pricing_group__labs__is_live=True, enabled=True)
        if not queryset:
            return Response([])
        lab_obj = Lab.objects.filter(pk=lab_id).first()
        if params.get('test_name'):
            search_key = re.findall(r'[a-z0-9A-Z.]+', params.get('test_name'))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            queryset = queryset.filter(
                Q(test__search_key__istartswith=search_key) | Q(test__search_key__icontains=" "+search_key))
        else:
            queryset = queryset.order_by('-test__priority')

        # queryset = queryset[:20]
        paginated_queryset = paginate_queryset(queryset, request)
        package_free_or_not_dict = get_package_free_or_not_dict(request)
        serializer = diagnostic_serializer.AvailableLabTestSerializer(paginated_queryset, many=True,
                                                                      context={"lab": lab_obj, 'request': request, "package_free_or_not_dict": package_free_or_not_dict})
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
        source = request.query_params.get('source', '')
        responsible_user = request.user if request.user.is_authenticated else None
        lab_appointment._source = source if source in [x[0] for x in AppointmentHistory.SOURCE_CHOICES] else ''
        lab_appointment._responsible_user = responsible_user
        if lab_appointment:
            lab_appointment.action_completed()
            # lab_appointment_serializer = diagnostic_serializer.LabAppointmentRetrieveSerializer(lab_appointment,
            #                                                                                         context={
            #                                                                                             'request': request})
            resp = {'success':'LabAppointment Updated Successfully!'}
        return Response(resp)


class TestDetailsViewset(viewsets.GenericViewSet):

    def get_queryset(self):
        return None

    def retrieve_test_by_url(self, request):

        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        entity = EntityUrls.objects.filter(url=url, sitemap_identifier=LabTest.LAB_TEST_SITEMAP_IDENTIFIER).order_by(
            '-is_valid')
        if len(entity) > 0:
            entity = entity[0]
            if not entity.is_valid:
                valid_entity_url_qs = EntityUrls.objects.filter(
                    sitemap_identifier=LabTest.LAB_TEST_SITEMAP_IDENTIFIER, entity_id=entity.entity_id,
                    is_valid='t')
                if valid_entity_url_qs.exists():
                    corrected_url = valid_entity_url_qs[0].url
                    return Response(status=status.HTTP_301_MOVED_PERMANENTLY, data={'url': corrected_url})
                else:
                    return Response(status=status.HTTP_404_NOT_FOUND)

            # entity_id = entity.entity_id
            response = self.retrieve(request, entity)
            return response
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def retrieve(self, request, entity=None, *args, **kwargs):
        params = request.query_params
        parameters = dict()
        if params.get('url'):
            test_ids = [entity.entity_id]
            lab_id = None

        else:
            try:
                test_ids = params.get('test_ids', None)
                if test_ids:
                    test_ids = [int(x) for x in test_ids.split(',')]
                    test_ids = set(test_ids)
                lab_id = params.get('lab_id', None)
                if lab_id:
                    try:
                        lab_id = int(lab_id)
                    except:
                        return Response([], status=status.HTTP_400_BAD_REQUEST)

            except:
                return Response([], status=status.HTTP_400_BAD_REQUEST)


        queryset = LabTest.objects.prefetch_related('labtests__parameter', 'faq',
                                                    'base_test__booked_together_test', 'availablelabs',
                                                    'availablelabs__lab_pricing_group',
                                                    'availablelabs__lab_pricing_group__labs', 'test__parameter').filter(id__in=test_ids,
                                                                                                     show_details=True)


        if not queryset:
            return Response([])
        final_result = []
        test_queryset = queryset[0]
        for data in queryset:
            result = {}
            result['name'] = data.name
            result['id'] = data.id
            result['about_test'] = {'title': 'About the test', 'value': data.about_test}
            result['preparations'] = {'title': 'Preparations', 'value': data.preparations}
            result['why_get_tested'] = {'title': 'Why get tested?', 'value': data.why}
            result['url'] = data.url
            info=[]
            for lab_test in data.labtests.all():
                name = lab_test.parameter.name
                info.append(name)
            result['test_may_include'] = {'title': 'This test includes', 'value': info}
            pack_list = []
            if data.is_package == True:
                for ptest in data.test.all():
                    if ptest.searchable == True and ptest.enable_for_retail == True:
                        resp = {}
                        resp['name'] = ptest.name
                        resp['id'] = ptest.id
                        resp['parameters'] = [test_parameter.name for test_parameter in ptest.parameter.all()]
                        resp['parameters_details'] = [{'name': t_param.name, 'details': t_param.details} for t_param in ptest.parameter.all()]
                        pack_list.append(resp)
            result['this_package_will_include'] = {'title': 'This package includes', 'tests': pack_list}

            queryset1 = data.faq.all()
            result['faqs'] = []
            for qa in queryset1:
                result['faqs'].append({'title': 'Frequently asked questions',
                                       'value': {'test_question': qa.test_question, 'test_answer': qa.test_answer}})

            booked_together=[]
            if lab_id:
                fbts = data.frequently_booked_together.filter(availablelabs__enabled=True,
                                                          availablelabs__lab_pricing_group__labs__id=lab_id).distinct()
            if lab_id:
               for fbt in fbts:
                    name = fbt.name
                    id = fbt.id
                    show_details = fbt.show_details
                    booked_together.append({'id': id, 'lab_test': name, 'show_details': show_details})

            else:
                for fbt in data.base_test.all():
                    name = fbt.booked_together_test.name
                    id = fbt.booked_together_test.id
                    show_details = fbt.booked_together_test.show_details
                    booked_together.append({'id': id, 'lab_test': name, 'show_details': show_details})

            result['frequently_booked_together'] = {'title': 'Frequently booked together', 'value': booked_together}
            result['show_details'] = data.show_details

        lab = LabList()
        test_ids = list(test_ids)

        for i in range(len(test_ids)):
            test_ids[i] = str(test_ids[i])

        if params.get('lat') and params.get('long'):
            parameters['lat'] = params.get('lat')
            parameters['long'] = params.get('long')

        parameters['ids'] = ",".join(test_ids)
        parameters['max_distance'] = 15
        parameters['min_distance'] = 0

        kwargs['parameters'] = parameters
        kwargs['test_flag'] = 1

        result['labs'] = lab.search(request, **kwargs)

        seo = dict()
        author = None

        if test_queryset.name and test_queryset.url:
            seo['title'] = test_queryset.name + '  - Cost & Normal Range of Results'
            seo['description'] = 'Book ' + test_queryset.name + ' @50% off. Free Sample Collection. Know what is ' \
                                 + test_queryset.name + ', Price, Normal Range, ' + test_queryset.name + ' Results, Procedure & Preparation.'
        else:
            seo = None
        result['seo'] = seo
        result['breadcrumb'] = list()
        result['breadcrumb'].append({"title": "Home", "url": "/"})
        result['breadcrumb'].append({"title": "Tests", "url": "/tests"})

        if test_queryset.name and test_queryset.url:
            result['breadcrumb'].append({"title": test_queryset.name, "url": test_queryset.url})

        result['canonical_url'] = test_queryset.url if test_queryset.url else None

        if test_queryset.author:
            serializer = ArticleAuthorSerializer(test_queryset.author, context={'request': request})
            author = serializer.data
        result['author'] = author
        result['published_date'] = '{:%d-%m-%Y}'.format(test_queryset.created_at.date()) if test_queryset.created_at else None
        result['last_updated_date'] = '{:%d-%m-%Y}'.format(test_queryset.created_at.date()) if test_queryset.updated_at else None
        final_result.append(result)

        return Response(final_result)

    def list_by_alphabet(self, request):
        alphabet = request.GET.get('alphabet')
        if not alphabet:
            return Response(status=status.HTTP_404_NOT_FOUND)
        response = {}
        tests_count = 0

        tests = list(LabTest.objects.filter(enable_for_retail=True, name__istartswith=alphabet, show_details=True).exclude(url__exact='').order_by('name').values('id', 'name', 'url'))

        if tests:
            tests_count = len(tests)
        response['count'] = tests_count
        response['tests'] = tests
        response['key'] = alphabet

        return Response(response)


class LabTestCategoryListViewSet(viewsets.GenericViewSet):
    # queryset = None
    def get_queryset(self):
        return None

    def list(self, request):
        parameters = request.query_params
        try:
            lab_tests = parameters.get('lab_tests', None)
            if lab_tests:
                lab_tests = [int(x) for x in lab_tests.split(',')]
                lab_tests = set(lab_tests)
        except:
            return Response([], status= status.HTTP_400_BAD_REQUEST)
        if lab_tests:
            categories = LabTestCategory.objects.prefetch_related('lab_tests').filter(lab_tests__id__in=lab_tests,
                                                                                      lab_test_mappings__is_primary=True,
                                                                                      is_live=True).distinct()
        else:
            categories = LabTestCategory.objects.prefetch_related('lab_tests').filter(is_live=True).distinct()
        empty = []
        not_in_others = set()
        for lab_test_category in categories:
            resp = dict()
            resp['category_name'] = lab_test_category.name
            resp['category_id'] = lab_test_category.id
            temp_tests = []
            for lab_test in lab_test_category.lab_tests.all():
                name = lab_test.name
                id = lab_test.id
                if lab_tests and id in lab_tests:
                    is_selected = True
                    not_in_others.add(id)
                else:
                    is_selected = False
                if not is_selected:
                    temp_tests.append({'name': name, 'id': id, 'is_selected': is_selected})
                else:
                    temp_tests.insert(0, {'name': name, 'id': id, 'is_selected': is_selected})
            resp['tests'] = temp_tests
            empty.append(resp)

        if lab_tests:
            others = lab_tests.difference(not_in_others)
            if others:
                resp = dict()
                resp['category_name'] = 'Others'
                resp['category_id'] = -1
                temp_tests = []
                for lab_test in LabTest.objects.filter(id__in=others):
                    name = lab_test.name
                    id = lab_test.id
                    is_selected = True
                    temp_tests.append({'name': name, 'id': id, 'is_selected': is_selected})
                resp['tests'] = temp_tests
                empty.append(resp)
        return Response(empty)


class DigitalReports(viewsets.GenericViewSet):

    def retrieve(self, request, booking_id=None):
        response = dict()
        appointment_obj = LabAppointment.objects.filter(id=booking_id).first()
        if not appointment_obj:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Invalid booking_id.'})

        integrator_response = appointment_obj.integrator_response.all().first()
        if not integrator_response:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'No response found from integrator for this appointment.'})

        booked_tests_or_packages = appointment_obj.test_mappings.all()
        booked_tests_or_packages = list(map(lambda tp: tp.test, booked_tests_or_packages))
        booked_tests = list()

        for lt in booked_tests_or_packages:
            if lt.is_package:
                booked_tests.extend(lt.test.all())
            else:
                booked_tests.append(lt)

        response['profiles_count'] = len(booked_tests)
        profiles = list()

        response['colour_count_dict'] = {
            LabTestThresholds.Colour.RED.lower(): 0,
            LabTestThresholds.Colour.ORANGE.lower(): 0,
            LabTestThresholds.Colour.GREEN.lower(): 0
        }

        user_age = appointment_obj.profile.get_age()

        integrator_report = IntegratorReport.objects.filter(integrator_response_id=integrator_response.id).first()
        if not integrator_report:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'No report found from integrator for this appointment.'})

        report_json = integrator_report.json_data
        report_parameter_array = list()

        # booked_tests = [LabTest.objects.get(id=11361)]

        for booked_test in booked_tests:
            profile_dict = dict()
            profile_dict['name'] = booked_test.name
            profile_dict['icon'] = ""
            profile_dict['parameter_list'] = list()

            test_parameters = booked_test.parameter.all()
            for parameter in test_parameters:
                parameter_dict = dict()
                parameter_dict['name'] = parameter.name
                parameter_dict['details'] = parameter.details
                integrator_parameter_obj = parameter.integrator_mapped_parameters.filter().first()

                #TODO: get value from report json and remove below line.
                value = 16

                threshold_qs = parameter.parameter_thresholds.all()
                if user_age:
                    valid_threshold = threshold_qs.filter(min_value__lte=value, max_value__gte=value,
                                                          min_age__lte=appointment_obj.profile.get_age(),
                                                          max_age__gte=appointment_obj.profile.get_age(),
                                                          gender=appointment_obj.profile.gender).first()
                else:
                    valid_threshold = threshold_qs.filter(min_value__lte=value,
                                                          max_value__gte=value,
                                                          gender=appointment_obj.profile.gender).first()

                if not valid_threshold:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

                parameter_dict['color'] = valid_threshold.color
                parameter_dict['value'] = value
                parameter_dict['what_to_do'] = valid_threshold.what_to_do
                parameter_dict['details'] = valid_threshold.details
                parameter_dict['ideal_range'] = '%.2f - %.2f' % (valid_threshold.min_value, valid_threshold.max_value)

                response['colour_count_dict'][valid_threshold.color.lower()] += 1

                profile_dict['parameter_list'].append(parameter_dict)

            profiles.append(profile_dict)

        response['profiles'] = profiles

        return Response(data=response)


class CompareLabPackagesViewSet(viewsets.ReadOnlyModelViewSet):

    def retrieve_by_url(self, request, *args, **kwargs):
        url = request.data.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = url.lower()
        compare_seo_url = CompareSEOUrls.objects.filter(url=url)
        if len(compare_seo_url) > 0:
            compare_seo_url = compare_seo_url[0]

        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        package_lab_ids = list()
        compare_package_details = dict()
        compare_lab_packages = CompareLabPackagesSeoUrls.objects.filter(url=compare_seo_url)

        if compare_lab_packages and len(compare_lab_packages)>1 and len(compare_lab_packages) <=5:
            for data in compare_lab_packages:
                package_lab_ids.append({'package_id': data.package_id, 'lab_id': data.lab_id})

        compare_package_details['package_lab_ids'] = package_lab_ids
        compare_package_details['lat'] = request.GET.get('lat') if request.GET.get('lat') else None
        compare_package_details['long'] = request.GET.get('long') if request.GET.get('long') else None
        compare_package_details['title'] = compare_seo_url.title if compare_seo_url.title else None
        kwargs['compare_package_details'] = compare_package_details
        kwargs['compare_seo_url'] = compare_seo_url

        response = self.retrieve(request, **kwargs)
        return response

    def retrieve(self, request, *args, **kwargs):
        from django.db.models import Min
        if kwargs and kwargs['compare_package_details']:
            request_parameters = kwargs['compare_package_details']
        else:
            request_parameters = request.data
        serializer = serializers.CompareLabPackagesSerializer(data=request_parameters, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response = {}
        # latitude = None
        # longitude = None
        # longitude = validated_data.get('longitude')
        # latitude = validated_data.get('latitude')
        # point_string = 'POINT(' + str(longitude) + ' ' + str(latitude) + ')'
        # pnt = GEOSGeometry(point_string, srid=4326)
        # tests = None
        # total_test_ids = set()
        # max_distance = 10000
        # min_distance = 0
        title = None
        if validated_data.get('title'):
            title = validated_data.get('title').replace('_', ' ').title()
        response['title'] = title
        requested_package_ids = set([x.get('package_id').id for x in validated_data.get('package_lab_ids', [])])
        requested_lab_ids = set([x.get('lab_id').id for x in validated_data.get('package_lab_ids', [])])

        packages = LabTest.objects.prefetch_related('test', 'test__recommended_categories', 'test__parameter',
                                                    'categories', Prefetch('availablelabs',
                                                                           AvailableLabTest.objects.filter(
                                                                               enabled=True)),
                                                    Prefetch('availablelabs__lab_pricing_group__labs',
                                                             Lab.objects.filter(is_live=True))).filter(
            is_package=True, id__in=requested_package_ids).distinct()

        # packages_price = packages.values('id').annotate(
        #     min_price=Min(Coalesce('availablelabs__custom_deal_price', 'availablelabs__computed_deal_price')))

        avts = AvailableLabTest.objects.filter(enabled=True, lab_pricing_group__labs__id__in=requested_lab_ids,
                                               test_id__in=requested_package_ids).annotate(
            requested_lab=F('lab_pricing_group__labs__id'), price=Case(
                When(custom_deal_price__isnull=True,
                     then=F('computed_deal_price')),
                When(custom_deal_price__isnull=False,
                     then=F('custom_deal_price'))), )
        price_master = {}
        for avt in avts:
            price_master[(avt.test.id, avt.requested_lab)] = (avt.mrp, avt.price)

        package_test_master = {p: [x for x in p.test.all()] for p in packages}
        category_data_master = {}
        test_data_master = {}
        test_without_cat = set()
        category_parameter_count_master = defaultdict(int)
        all_category_ids = set()

        for package_temp in packages:
            for test_temp in package_temp.test.all():
                temp_test_id = test_temp.id
                temp_test_name = test_temp.name
                if temp_test_id not in test_data_master:
                    parameters = [x.name for x in test_temp.parameter.all()]
                    test_data_master[temp_test_id] = {"id": temp_test_id, "name": temp_test_name,
                                                      "parameter_count": len(parameters) or 1,
                                                      "parameters": parameters}

        for temp_package in packages:
            pack_id = temp_package.id
            for temp_p_test in temp_package.test.all():
                add_test = True
                test_id = temp_p_test.id
                test_name = temp_p_test.name
                if len(temp_p_test.recommended_categories.all()) == 1:
                    for temp_category in temp_p_test.recommended_categories.all():
                        if temp_category.is_live:
                            add_test = False
                            cat_id = temp_category.id
                            all_category_ids.add(cat_id)
                            cat_name = temp_category.name
                            cat_icon_url = util_absolute_url(temp_category.icon.url) if temp_category.icon else None
                            if cat_id in category_data_master:
                                if test_id not in category_data_master[cat_id]["test_ids"]:
                                    category_data_master[cat_id]["test_ids"].append(test_id)
                            else:
                                category_data_master[cat_id] = {"id": cat_id,
                                                  "icon": cat_icon_url,
                                                  "name": cat_name,
                                                  "test_ids": [test_id]}
                            category_parameter_count_master[(pack_id, cat_id)] += test_data_master[test_id]["parameter_count"]
                if add_test:
                    test_without_cat.add(test_id)
                    category_parameter_count_master[(pack_id, 0)] += test_data_master[test_id]["parameter_count"]
                    all_category_ids.add(0)

        category_data = list(category_data_master.values())
        if test_without_cat:
            category_data.append({"id": 0, "icon": None, "name": "Others", "test_ids": list(test_without_cat)})

        total_test_ids = set(test_data_master.keys())
        lab_packages_all_details = {}
        for data in packages:
            if data.id and data.name:
                package_detail = {}
                labs_count = 0
                tests_included = list()
                available_labs = None
                tests = data.test.all()
                temp_test_id = set()
                parameter_count = sum([len(x.parameter.all()) or 1 for x in data.test.all()])
                package_detail['id'] = data.id
                package_detail['name'] = data.name
                package_detail['total_parameters_count'] = parameter_count

                if data.availablelabs.all():
                    available_labs = data.availablelabs.all()
                    for avl_labs in available_labs:
                        if avl_labs.lab_pricing_group and avl_labs.lab_pricing_group.labs.all():
                            labs_count = labs_count + avl_labs.lab_pricing_group.labs.count()
                package_detail['total_labs_available'] = labs_count

                if tests:
                    for test in tests:
                        temp_test_id.add(test.id)
                        tests_included.append({'test_id': test.id, 'available': True})

                if len(total_test_ids-temp_test_id) > 0:
                    for test_id in list(total_test_ids-temp_test_id):
                        tests_included.append({'test_id': test_id, 'available': False})

                package_detail['tests_included'] = tests_included
                # package_min_price = None
                # for price in packages_price:
                #     if price.get('id') == data.id:
                #         package_min_price = price.get('min_price')
                # package_detail['minimum_price'] = package_min_price
                category_parameter_result = []
                for category_id_temp in all_category_ids:
                    category_parameter_result.append({"id": category_id_temp,
                                                      "count": category_parameter_count_master.get(
                                                          (data.id, category_id_temp), 0)})
                package_detail['category_parameter_count'] = category_parameter_result
                lab_packages_all_details[data.id] = package_detail

        final_result = []
        for pack_lab in validated_data.get('package_lab_ids', []):
            temp_data = {}
            t_pack = pack_lab.get('package')
            t_lab = pack_lab.get('lab')
            temp_data.update(deepcopy(lab_packages_all_details.get(t_pack.id, {})))
            temp_data['lab'] = {'id': t_lab.id, 'name': t_lab.name, 'thumbnail': t_lab.get_thumbnail()}
            temp_data['mrp'], temp_data['price'] = price_master.get((t_pack.id, t_lab.id), (None, None))
            final_result.append(temp_data)
        # response['packages'] = list(lab_packages_all_details.values())
        response['packages'] = final_result
        response['category_info'] = category_data
        response['test_info'] = list(test_data_master.values())
        response['search_content'] = None
        response['bottom_content'] = None
        response['description'] = None
        if kwargs and kwargs['compare_seo_url']:
            new_dynamic = NewDynamic.objects.filter(url_value=kwargs['compare_seo_url'].url)
            if new_dynamic:
                response['search_content'] = new_dynamic.first().top_content
                response['bottom_content'] = new_dynamic.first().bottom_content
                response['description'] = new_dynamic.first().meta_description
                if response['title'] is None:
                    response['title'] = new_dynamic.first().meta_title
        return Response(response)
