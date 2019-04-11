from rest_framework import serializers
from rest_framework.fields import CharField

from ondoc.cart.models import Cart
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage, LabReportFile, CommonPackage,
                                     LabTestCategory, LabAppointmentTestMapping)
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.authentication.models import UserProfile, Address
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer, CommaSepratedToListField
from ondoc.api.v1.auth.serializers import AddressSerializer, UserProfileSerializer
from ondoc.api.v1.utils import form_time_slot, GenericAdminEntity, util_absolute_url
from ondoc.doctor.models import OpdAppointment, CancellationReason
from ondoc.account.models import Order, Invoice
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon
from django.db.models import Count, Sum, When, Case, Q, F, ExpressionWrapper, DateTimeField
from django.contrib.auth import get_user_model
from collections import OrderedDict
from django.utils import timezone
from ondoc.api.v1 import utils
from django.conf import settings
import datetime
import pytz
import random
import logging
import json

from ondoc.insurance.models import UserInsurance, InsuranceThreshold
from ondoc.ratings_review.models import RatingsReview
from django.db.models import Avg
from django.db.models import Q
from ondoc.api.v1.ratings import serializers as rating_serializer
from ondoc.location.models import EntityUrls, EntityAddress
from ondoc.seo.models import NewDynamic
from ondoc.subscription_plan.models import Plan, UserPlanMapping

logger = logging.getLogger(__name__)
utc = pytz.UTC
User = get_user_model()


class LabTestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id', 'name', 'is_package', 'show_details')


class LabListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = ('id', 'name')


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id', 'name', 'pre_test_info', 'why', 'show_details', 'url')
        # fields = ('id', 'account_name', 'users', 'created')


class LabImageModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabImage
        fields = ('name', )
        # exclude = ('created_at', 'updated_at',)


class LabModelSerializer(serializers.ModelSerializer):

    lat = serializers.SerializerMethodField()
    long = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    #lab_image = LabImageModelSerializer(many=True)
    lab_thumbnail = serializers.SerializerMethodField()
    home_pickup_charges = serializers.ReadOnlyField()
    seo = serializers.SerializerMethodField()
    # rating = rating_serializer.RatingsModelSerializer(read_only=True, many=True, source='get_ratings')
    rating_graph = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    unrated_appointment = serializers.SerializerMethodField()
    center_visit_enabled = serializers.SerializerMethodField()
    display_rating_widget = serializers.SerializerMethodField()
    is_thyrocare = serializers.SerializerMethodField()

    def get_is_thyrocare(self, obj):
        if obj and obj.network and settings.THYROCARE_NETWORK_ID:
            if obj.network.id == settings.THYROCARE_NETWORK_ID:
                return True
        return False

    def get_display_rating_widget(self, obj):
        if self.parent:
            return None
        if obj.network and self.context.get('rating_queryset'):
            network_queryset = self.context.get('rating_queryset')
            rate_count = network_queryset.count()
        else:
            rate_count = obj.rating.count()
        avg = 0
        if rate_count:
            all_rating = []
            for rate in obj.rating.all():
                all_rating.append(rate.ratings)
            if all_rating:
                avg = sum(all_rating) / len(all_rating)
        if rate_count > 5 or (rate_count <= 5 and avg > 4):
            return True
        return False

    def get_center_visit_enabled(self, obj):
        if obj and obj.network and settings.THYROCARE_NETWORK_ID:
            if obj.network.id == settings.THYROCARE_NETWORK_ID:
                return False
        return True

    def get_rating(self, obj):
        if self.parent:
            return None
        app = LabAppointment.objects.select_related('profile').filter(lab_id=obj.id).all()
        if obj.network:
            app = LabAppointment.objects.select_related('profile').filter(lab__network=obj.network).all()
        query = self.context.get('rating_queryset')
        rating_queryset = query.exclude(Q(review='') | Q(review=None)).order_by('-ratings', '-updated_at')
        reviews = rating_serializer.RatingsModelSerializer(rating_queryset, many=True, context={'app': app})
        return reviews.data[:5]

    def get_unrated_appointment(self, obj):
        if self.parent:
            return None

        request = self.context.get('request')
        if request:
            if request.user.is_authenticated:
                user = request.user
                lab_app = None
                lab = user.lab_appointments.filter(lab=obj, status=LabAppointment.COMPLETED).order_by('-updated_at').first()
                if lab and lab.is_rated == False:
                    lab_app = lab
                if lab_app:
                    data = LabAppointmentModelSerializer(lab_app, many=False, context={'request': request})
                    return data.data
            return None

    def get_rating_graph(self, obj):
        if self.parent:
            return None
        query = self.context.get('rating_queryset')

        if query:
            data = rating_serializer.RatingsGraphSerializer(query, context={'request': self.context.get('request')}).data
            return data
        return None

    def get_seo(self, obj):
        if self.parent:
            return None
        # entity = EntityUrls.objects.filter(entity_id=obj.id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Lab')

        locality = None
        sublocality = None
        entity = None
        # if entity.exists():
            #entity = entity[0]
        if self.context.get('entity'):
            entity = self.context.get('entity')
            if entity.additional_info:
                locality = entity.additional_info.get('locality_value')
                sublocality = entity.additional_info.get('sublocality_value')

        if sublocality and locality:
            title = obj.name + ' - Diagnostic Centre in '+ sublocality + " " + locality + ' | DocPrime'
        elif locality:
            title = obj.name + ' - Diagnostic Centre in ' + locality + ' | DocPrime'
        else:
            title = obj.name + ' - Diagnostic Centre | DocPrime'

        description = obj.name + ': Book test at ' + obj.name + ' online, check fees, packages prices and more at DocPrime. '

        if entity:
            new_object = NewDynamic.objects.filter(url__url=entity.url, is_enabled=True).first()
            if new_object:
                if new_object.meta_title:
                    title = new_object.meta_title
                if new_object.meta_description:
                    description = new_object.meta_description
        return {'title': title, "description": description}

    def get_breadcrumb(self, obj):

        if self.parent:
            return None
        # entity = EntityUrls.objects.filter(entity_id=obj.id, url_type='PAGEURL', is_valid='t',
        #                                    entity_type__iexact='Lab')
        breadcrums = None
        if self.context.get('entity'):
            entity = self.context.get('entity')
        # if entity.exists():
            breadcrums = entity.additional_info.get('breadcrums')
            if breadcrums:
                return breadcrums
        return breadcrums

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            raise ValueError("request is not passed in serializer.")
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    def get_address(self, obj):
        return obj.get_lab_address() if obj.get_lab_address() else None

    def get_lat(self,obj):
        if obj.location:
            return obj.location.y

    def get_long(self,obj):
        if obj.location:
            return obj.location.x


    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'lab_thumbnail', 'name', 'operational_since', 'locality', 'address',
                  'sublocality', 'city', 'state', 'country', 'always_open', 'about', 'home_pickup_charges',
                  'is_home_collection_enabled', 'seo', 'breadcrumb', 'rating', 'rating_graph', 'unrated_appointment',
                  'center_visit_enabled', 'display_rating_widget', 'is_thyrocare')


class LabProfileSerializer(LabModelSerializer):

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'address', 'lab_image', 'lab_thumbnail', 'name', 'operational_since', 'locality',
                  'sublocality', 'city', 'state', 'country', 'about', 'always_open', 'building', )


class AvailableLabTestPackageSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    is_package = serializers.ReadOnlyField(source='test.is_package')
    number_of_tests = serializers.ReadOnlyField(source='test.number_of_tests')
    expected_tat = serializers.ReadOnlyField(source='test.expected_tat')
    pre_test_info = serializers.ReadOnlyField(source='test.pre_test_info')
    why = serializers.ReadOnlyField(source='test.why')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()
    package = serializers.SerializerMethodField()
    parameters = serializers.SerializerMethodField()
    insurance = serializers.SerializerMethodField()
    hide_price = serializers.ReadOnlyField(source='test.hide_price')
    included_in_user_plan = serializers.SerializerMethodField()

    def get_included_in_user_plan(self, obj):
        package_free_or_not_dict = self.context.get('package_free_or_not_dict', {})
        return package_free_or_not_dict.get(obj.test.id, False)

    def get_insurance(self, obj):
        request = self.context.get("request")
        lab_obj = self.context.get("lab")
        resp = Lab.get_insurance_details(request.user)
        # insurance_threshold = InsuranceThreshold.objects.all().order_by('-lab_amount_limit').first()
        # resp = {
        #     'is_insurance_covered': False,
        #     'insurance_threshold_amount': insurance_threshold.lab_amount_limit if insurance_threshold else 5000,
        #     'is_user_insured': False
        # }
        # if request:
        #     logged_in_user = request.user
        #     if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
        #         user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
        #         if user_insurance and user_insurance.is_valid():
        #             insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
        #             if insurance_threshold:
        #                 resp['insurance_threshold_amount'] = 0 if insurance_threshold.lab_amount_limit is None else \
        #                     insurance_threshold.lab_amount_limit
        #                 resp['is_user_insured'] = True

        if lab_obj.is_enabled_for_insurance and obj.mrp is not None and resp['insurance_threshold_amount'] is not None \
                and obj.mrp <= resp['insurance_threshold_amount']:
            resp['is_insurance_covered'] = True

        return resp

    def get_is_home_collection_enabled(self, obj):
        if self.context.get("lab") is not None:
            if self.context["lab"].is_home_collection_enabled and obj.test.home_collection_possible:
                return True
            return False
        return obj.test.home_collection_possible
        # return None

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    def get_package(self, obj):
        ret_data = list()
        if obj.test.is_package:
            packages_test = obj.test.packages.all()
            for t_obj in packages_test:
                rec_dict = dict()
                # param_list = t_obj.lab_test.labtests.all().values_list("parameter__name", flat=True)
                param_objs = t_obj.lab_test.labtests.all()
                rec_dict['category'] = []
                rec_obj = t_obj.lab_test.recommended_categories.all()
                # category = [cat.name for cat in rec_obj]
                for cat in rec_obj:
                    rec_dict['category'].append(
                        {'name': cat.name, 'icon': util_absolute_url(cat.icon.url) if cat.icon else None})
                param_list = list()
                param_details = list()
                for p_obj in param_objs:
                    param_list.append(p_obj.parameter.name)
                    name = p_obj.parameter.name
                    details = p_obj.parameter.details
                    param_details.append({'name': name, 'details': details})
                # param_details = [{'name': data.parameter.name, 'details': data.parameter.details} for data in param_objs]
                ret_data.append({
                    "name": t_obj.lab_test.name,
                    "why": t_obj.lab_test.why,
                    "pre_test_info": t_obj.lab_test.pre_test_info,
                    "expected_tat": t_obj.lab_test.expected_tat,
                    "parameters": param_list,
                    "parameter_details": param_details,
                    "category": rec_dict.get('category')
                })
        return ret_data

    def get_parameters(self, obj):
        # parameters = obj.test.labtests.all().values_list("parameter__name", flat=True)

        parameters = list()
        param_objs = obj.test.labtests.all()
        for obj in param_objs:
            parameters.append(obj.parameter.name)

        return parameters

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled',
                  'package', 'parameters', 'is_package', 'number_of_tests', 'why', 'pre_test_info', 'expected_tat',
                  'hide_price', 'included_in_user_plan', 'insurance')

class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()
    insurance = serializers.SerializerMethodField()
    is_package = serializers.SerializerMethodField()
    included_in_user_plan = serializers.SerializerMethodField()

    def get_included_in_user_plan(self, obj):
        package_free_or_not_dict = self.context.get('package_free_or_not_dict', {})
        return package_free_or_not_dict.get(obj.test.id, False)

    def get_is_home_collection_enabled(self, obj):
        if self.context.get("lab") is not None:
            if self.context["lab"].is_home_collection_enabled and obj.test.home_collection_possible:
                return True
            return False
        return obj.test.home_collection_possible
        # return None

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    def get_insurance(self, obj):
        request = self.context.get("request")
        lab_obj = self.context.get("lab")
        resp = Lab.get_insurance_details(request.user)
        # insurance_threshold = InsuranceThreshold.objects.all().order_by('-lab_amount_limit').first()
        # resp = {
        #     'is_insurance_covered': False,
        #     'insurance_threshold_amount': insurance_threshold.lab_amount_limit if insurance_threshold else 5000,
        #     'is_user_insured': False
        # }
        # if request:
        #     logged_in_user = request.user
        #     if logged_in_user.is_authenticated and not logged_in_user.is_anonymous:
        #         user_insurance = logged_in_user.purchased_insurance.filter().order_by('id').last()
        #         if user_insurance and user_insurance.is_valid():
        #             insurance_threshold = user_insurance.insurance_plan.threshold.filter().first()
        #             if insurance_threshold:
        #                 resp['insurance_threshold_amount'] = 0 if insurance_threshold.lab_amount_limit is None else \
        #                     insurance_threshold.lab_amount_limit
        #                 resp['is_user_insured'] = True

        if lab_obj and lab_obj.is_enabled_for_insurance and obj.mrp is not None and resp['insurance_threshold_amount'] is not None \
                and obj.mrp <= resp['insurance_threshold_amount']:
            resp['is_insurance_covered'] = True

        return resp

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled',
                  'insurance', 'is_package', 'included_in_user_plan')

    def get_is_package(self, obj):
        return obj.test.is_package


class LabAppointmentTestMappingSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()

    def get_is_home_collection_enabled(self, obj):
        if self.context.get("lab") is not None:
            if self.context["lab"].is_home_collection_enabled and obj.test.home_collection_possible:
                return True
            return False
        return obj.test.home_collection_possible
        # return None

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    class Meta:
        model = LabAppointmentTestMapping
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price',
                  # 'enabled',
                  'is_home_collection_enabled')


class LabCustomSerializer(serializers.Serializer):
    # lab = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    price = serializers.IntegerField(default=None)
    mrp = serializers.IntegerField(default=None)
    distance = serializers.IntegerField(source='distance.m')
    pickup_available = serializers.IntegerField(default=0)
    lab_timing = serializers.CharField(max_length=1000)
    lab_timing_data = serializers.ListField()
    next_lab_timing = serializers.DictField()
    next_lab_timing_data = serializers.DictField()
    pickup_charges = serializers.IntegerField(default=None)
    insurance = serializers.SerializerMethodField()
    distance_related_charges = serializers.IntegerField()
    tests = serializers.ListField(child=serializers.DictField())

    def get_insurance(self, obj):
        insurance_data_dict = self.context.get("insurance_data_dict")
        is_insurance_covered = False

        return {
            "is_insurance_covered": is_insurance_covered,
            "insurance_threshold_amount": insurance_data_dict['insurance_threshold_amount'],
            "is_user_insured": insurance_data_dict['is_user_insured'],
        }

# class LabNetworkSerializer(serializers.Serializer):
#     # lab = serializers.SerializerMethodField()
#     lab = LabModelSerializer()
#     network_id = serializers.IntegerField(default=None)
#     price = serializers.IntegerField(default=None)
#     mrp = serializers.IntegerField(default=None)
#     distance = serializers.IntegerField()
#     pickup_available = serializers.IntegerField(default=0)
#     lab_timing = serializers.CharField(max_length=1000)
#     lab_timing_data = serializers.ListField()
#     next_lab_timing = serializers.DictField()
#     next_lab_timing_data = serializers.DictField()
#     pickup_charges = serializers.IntegerField(default=None)
#     distance_related_charges = serializers.IntegerField()
#     tests = serializers.ListField(child=serializers.DictField())

    # def get_lab(self, obj):
    #     queryset = Lab.objects.get(pk=obj['lab'])
    #     serializer = LabModelSerializer(queryset)
    #     return serializer.data


class CommonTestSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='test.id')
    name = serializers.ReadOnlyField(source='test.name')
    show_details = serializers.ReadOnlyField(source='test.show_details')
    icon = serializers.SerializerMethodField
    test_type = serializers.ReadOnlyField(source='test.test_type')
    url = serializers.ReadOnlyField(source='test.url')

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = CommonTest
        fields = ('id', 'name', 'icon', 'show_details', 'test_type', 'url')


class CommonPackageSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='package.id')
    name = serializers.ReadOnlyField(source='package.name')
    show_details = serializers.ReadOnlyField(source='package.show_details')
    icon = serializers.SerializerMethodField()
    url = serializers.ReadOnlyField(source='package.url')

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if obj.icon else None

    class Meta:
        model = CommonPackage
        fields = ('id', 'name', 'icon', 'show_details', 'url')


class CommonConditionsSerializer(serializers.ModelSerializer):

    test = serializers.SerializerMethodField()

    def get_test(self, obj):
        test_id = []
        if obj:
            for tst in obj.lab_test.all():
                test_id.append({"id": tst.id, "name": tst.name})
        return test_id

    class Meta:
        model = CommonDiagnosticCondition
        fields = ('id', 'name', 'test')


class PromotedLabsSerializer(serializers.ModelSerializer):
    # lab = LabModelSerializer()
    id = serializers.ReadOnlyField(source='lab.id')
    name = serializers.ReadOnlyField(source='lab.name')

    class Meta:
        model = PromotedLab
        fields = ('id', 'name', )


class LabAppointmentModelSerializer(serializers.ModelSerializer):
    LAB_TYPE = 'lab'
    type = serializers.ReadOnlyField(default="lab")
    lab_name = serializers.ReadOnlyField(source="lab.name")
    lab_image = LabImageModelSerializer(many=True, source='lab.lab_image', read_only=True)
    lab_thumbnail = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    allowed_action = serializers.SerializerMethodField()
    lab_test = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()

    def get_lab_test(self, obj):
        return list(obj.test_mappings.values_list('test_id', flat=True))

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.lab.get_thumbnail()) if obj.lab.get_thumbnail() else None

    def get_patient_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile.get_thumbnail()) if obj.profile.get_thumbnail() else None

    def get_patient_name(self, obj):
        if obj.profile_detail:
            return obj.profile_detail.get("name")

    def get_invoices(self, obj):
        return obj.get_invoice_urls()

    def get_reports(self, obj):
        return obj.get_report_urls()

    def get_allowed_action(self, obj):
        user_type = ''
        if self.context.get('request'):
            user_type = self.context['request'].user.user_type
            return obj.allowed_action(user_type, self.context.get('request'))
        else:
            return []

    class Meta:
        model = LabAppointment
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'patient_thumbnail', 'patient_name', 'allowed_action', 'address', 'invoices', 'reports')


class LabAppointmentBillingSerializer(serializers.ModelSerializer):
    LAB_TYPE = 'lab'
    type = serializers.ReadOnlyField(default="lab")
    lab_name = serializers.ReadOnlyField(source="lab.name")
    lab_image = LabImageModelSerializer(many=True, source='lab.lab_image', read_only=True)
    lab_thumbnail = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.lab.get_thumbnail()) if obj.lab.get_thumbnail() else None

    def get_patient_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile.get_thumbnail()) if obj.profile.get_thumbnail() else None

    def get_patient_name(self, obj):
        if obj.profile_detail:
            return obj.profile_detail.get("name")

    class Meta:
        model = LabAppointment
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'agreed_price', 'price',
                  'effective_price', 'time_slot_start', 'time_slot_end', 'is_home_pickup', 'lab_thumbnail', 'lab_image',
                  'patient_thumbnail', 'patient_name', 'payment_type')


class PlanTransactionModelSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    extra_details = serializers.JSONField(required=False)


class LabAppTransactionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    agreed_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    time_slot_start = serializers.DateTimeField()
    profile_detail = serializers.JSONField()
    status = serializers.IntegerField()
    payment_type = serializers.IntegerField()
    lab_test = serializers.ListField(child=serializers.IntegerField())
    home_pickup_charges = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_home_pickup = serializers.BooleanField(default=False)
    address = serializers.JSONField(required=False)
    coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default = [])
    discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    insurance = serializers.PrimaryKeyRelatedField(queryset=UserInsurance.objects.all(), allow_null=True)

    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    extra_details = serializers.JSONField(required=False)
    user_plan = serializers.PrimaryKeyRelatedField(queryset=UserPlanMapping.objects.all(), allow_null=True)


class LabAppRescheduleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabAppointment
        fields = '__all__'


class LabAppointmentUpdateSerializer(serializers.Serializer):
    appointment_status = [LabAppointment.CREATED, LabAppointment.ACCEPTED, LabAppointment.RESCHEDULED_LAB,
                          LabAppointment.CANCELLED, LabAppointment.RESCHEDULED_PATIENT, LabAppointment.COMPLETED,
                          LabAppointment.BOOKED]
    status = serializers.ChoiceField(choices=appointment_status)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)

    def validate(self, data):
        request = self.context.get("request")
        temp_data = data
        temp_data["lab_id"] = self.context["lab_id"]
        LabAppointmentCreateSerializer.time_slot_validator(temp_data, request)

        return data

    def create(self, data):
        pass

    def update(self, instance, data):
        # if data['status'] == LabAppointment.RESCHEDULED_PATIENT:
        #     self.reschedule_validation(instance, data)
        # elif data['status'] == LabAppointment.CANCELLED:
        #     self.cancel_validation(instance, data)
        # else:
        #     raise serializers.ValidationError("Invalid Status")
        instance.time_slot_start = data.get("start_time", instance.time_slot_start)
        instance.time_slot_end = data.get("end_time", instance.time_slot_end)
        instance.status = data.get("status", instance.status)
        instance.save()
        return instance

    @staticmethod
    def reschedule_validation(instance, data):
        d = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < d and data['start_time'] < d:
            raise serializers.ValidationError("Cannot Reschedule")

    def cancel_validation(self, instance, data):
        now = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < now:
            raise serializers.ValidationError("Cannot Cancel")


class LabAppointmentCreateSerializer(serializers.Serializer):
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))
    test_ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all()))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    time_slot_start = serializers.DateTimeField(required=False)
    start_date = serializers.DateTimeField()
    start_time = serializers.FloatField()
    end_date = serializers.DateTimeField(required=False)
    end_time = serializers.FloatField(required=False)
    is_home_pickup = serializers.BooleanField(default=False)
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), required=False, allow_null=True)
    # address = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.IntegerField(default=OpdAppointment.PREPAID)
    coupon_code = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    use_wallet = serializers.BooleanField(required=False)
    cart_item = serializers.PrimaryKeyRelatedField(queryset=Cart.objects.all(), required=False, allow_null=True)
    pincode = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_thyrocare = serializers.BooleanField(required=False, default=False)
    from_app = serializers.BooleanField(required=False, default=False)
    user_plan = serializers.PrimaryKeyRelatedField(queryset=UserPlanMapping.objects.all(), required=False, allow_null=True, default=None)
    included_in_user_plan = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        MAX_APPOINTMENTS_ALLOWED = 10
        ACTIVE_APPOINTMENT_STATUS = [LabAppointment.BOOKED, LabAppointment.ACCEPTED,
                                     LabAppointment.RESCHEDULED_PATIENT, LabAppointment.RESCHEDULED_LAB]

        request = self.context.get("request")
        unserialized_data = self.context.get("data")
        cart_item_id = data.get('cart_item').id if data.get('cart_item') else None
        use_duplicate = self.context.get("use_duplicate", False)

        if not utils.is_valid_testing_lab_data(request.user, data["lab"]):
            raise serializers.ValidationError("Both User and Lab should be for testing")

        if data.get("is_home_pickup"):
            if data.get("address") is None:
                raise serializers.ValidationError("Address required for home pickup")
            elif not Address.objects.filter(id=data.get("address").id, user=request.user).exists():
                raise serializers.ValidationError("Invalid address for given user")

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")

        # if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"], lab=data[
        #     "lab"]).exists():
        #     raise serializers.ValidationError("A previous appointment with this lab already exists. Cancel it before booking new Appointment.")

        if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"]).count() >= MAX_APPOINTMENTS_ALLOWED:
            raise serializers.ValidationError('Max '+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        if data.get("coupon_code"):
            profile = data.get("profile")
            # coupon_code = data.get("coupon_code")
            coupon_codes = data.get("coupon_code", [])
            coupon_obj = None
            if RandomGeneratedCoupon.objects.filter(random_coupon__in=coupon_codes).exists():
                expression = F('sent_at') + datetime.timedelta(days=1) * F('validity')
                annotate_expression = ExpressionWrapper(expression, DateTimeField())
                random_coupons = RandomGeneratedCoupon.objects.annotate(last_date=annotate_expression
                                                                       ).filter(random_coupon__in=coupon_codes,
                                                                                sent_at__isnull=False,
                                                                                consumed_at__isnull=True,
                                                                                last_date__gte=datetime.datetime.now()
                                                                                ).all()
                if random_coupons:
                    coupon_obj = Coupon.objects.filter(id__in=random_coupons.values_list('coupon', flat=True))
                else:
                    raise serializers.ValidationError('Invalid coupon codes')

            if coupon_obj:
                coupon_obj = Coupon.objects.filter(code__in=coupon_codes) | coupon_obj
            else:
                coupon_obj = Coupon.objects.filter(code__in=coupon_codes)

            # if len(coupon_code) == len(coupon_obj):
            if coupon_obj:
                for coupon in coupon_obj:
                    obj = LabAppointment()
                    if obj.validate_user_coupon(cart_item=cart_item_id, user=request.user, coupon_obj=coupon, profile=profile).get("is_valid"):
                        if not obj.validate_product_coupon(coupon_obj=coupon,
                                                           lab=data.get("lab"), test=data.get("test_ids"),
                                                           product_id=Order.LAB_PRODUCT_ID):
                            raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                    else:
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                data["coupon_obj"] = list(coupon_obj)

        data["existing_cart_item"] = None
        if unserialized_data:
            is_valid, duplicate_cart_item = Cart.validate_duplicate(unserialized_data, request.user, Order.LAB_PRODUCT_ID, cart_item_id)
            if not is_valid:
                if use_duplicate and duplicate_cart_item:
                    data["existing_cart_item"] = duplicate_cart_item
                else:
                    raise serializers.ValidationError("Item already exists in cart.")

        time_slot_start = (form_time_slot(data.get('start_date'), data.get('start_time'))
                           if not data.get("time_slot_start") else data.get("time_slot_start"))

        # validations for same day and next day timeslot bookings
        selected_date = time_slot_start.strftime("%Y-%m-%d")
        lab = data.get("lab")
        pincode = data.get('pincode', None)
        address = data.get("address", None)

        if bool(data.get("is_thyrocare")):
            if not pincode:
                raise serializers.ValidationError("Pincode required for thyrocare.")
            if not int(pincode) == int(address.pincode):
                raise serializers.ValidationError("Entered pincode should be same as pickup address pincode.")

        now = datetime.datetime.now()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        is_today = now.weekday() == time_slot_start.weekday()
        is_tomorrow = tomorrow.weekday() == time_slot_start.weekday()
        curr_time = time_slot_start.hour
        curr_minute = round(round(float(time_slot_start.minute) / 60, 2) * 2) / 2
        curr_time += curr_minute

        if bool(data.get('from_app')):
            available_slots = LabTiming.timing_manager.lab_booking_slots(lab__id=data.get("lab").id, lab__is_live=True, for_home_pickup=data.get("is_home_pickup"))
            is_integrated = False
            if is_today and available_slots.get("today_min") and available_slots.get("today_min") > curr_time:
                raise serializers.ValidationError("Invalid Time slot")
            if is_tomorrow and available_slots.get("tomorrow_min") and available_slots.get("tomorrow_min") > curr_time:
                raise serializers.ValidationError("Invalid Time slot")
            if is_today and available_slots.get("today_max") and available_slots.get("today_max") < curr_time:
                raise serializers.ValidationError("Invalid Time slot")
        else:
            available_slots = lab.get_available_slots(data.get("is_home_pickup"), pincode, selected_date)
            is_integrated = lab.is_integrated()
            selected_day_slots = available_slots['time_slots'][selected_date]
            if not selected_day_slots:
                raise serializers.ValidationError("No time slots available")

            current_day_slots = self.get_slots_list(selected_day_slots)

            if not curr_time in current_day_slots:
                raise serializers.ValidationError("Invalid Time slot")

            if lab.network and lab.network.id == settings.THYROCARE_NETWORK_ID:
                self.thyrocare_test_validator(data)

        if LabAppointment.objects.filter(profile=data.get("profile"), lab=data.get("lab"),
                                         tests__in=data.get("test_ids"), time_slot_start=time_slot_start) \
                .exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED]).exists():
            raise serializers.ValidationError("One active appointment for the selected date & time already exists. Please change the date & time of the appointment.")

        if 'use_wallet' in data and data['use_wallet'] is False:
            data['use_wallet'] = False
        else:
            data['use_wallet'] = True

        self.test_lab_id_validator(data, request)
        self.time_slot_validator(data, request, is_integrated)
        self.user_plan_validator(data, request, cart_item_id)
        return data

    @staticmethod
    def user_plan_validator(data, request, cart_item_id=None):
        if data.get('included_in_user_plan', False):
            raise_exception = False
            lab_tests = data.get('test_ids', [])
            test_included_in_user_plan = UserPlanMapping.get_free_tests(request, cart_item_id)
            for temp_test in lab_tests:
                if temp_test.id not in test_included_in_user_plan:
                    raise_exception = True
                    break
            if raise_exception:
                raise serializers.ValidationError("LabTest not in free user plans")

    def create(self, data):
        deal_price_calculation= Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                     When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
        agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                      When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))

        self.num_appointment_validator(data)
        lab_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"),
                                                                 total_deal_price=Sum(deal_price_calculation),
                                                                 total_agreed_price=Sum(agreed_price_calculation))
        total_deal_price = total_mrp = effective_price = 0
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
        otp = random.randint(1000, 9999)
        appointment_data = {
            "lab": data["lab"],
            "user": self.context["request"].user,
            "profile": data["profile"],
            "price": total_mrp,
            "agreed_price": total_agreed,
            "deal_price": total_deal_price,
            "effective_price": effective_price,
            "time_slot_start": start_dt,
            "profile_detail": profile_detail,
            "payment_status": OpdAppointment.PAYMENT_ACCEPTED,
            "status": LabAppointment.BOOKED,
            "payment_type": data["payment_type"],
            "otp": otp
        }
        if data.get("is_home_pickup") is True:
            address = Address.objects.filter(pk=data.get("address")).first()
            address_serialzer = AddressSerializer(address)
            appointment_data.update({
                "address": address_serialzer.data,
                "is_home_pickup": True
            })
        queryset = LabAppointment.objects.create(**appointment_data)
        queryset.lab_test.add(*lab_test_queryset)
        return queryset

    def update(self, instance, data):
        pass

    @staticmethod
    def num_appointment_validator(data):
        ACTIVE_APPOINTMENT_STATUS = [LabAppointment.CREATED, LabAppointment.ACCEPTED,
                                     LabAppointment.RESCHEDULED_PATIENT, LabAppointment.RESCHEDULED_LAB]
        count = (LabAppointment.objects.filter(lab=data['lab'],
                                               profile=data['profile'],
                                               status__in=ACTIVE_APPOINTMENT_STATUS).count())
        if count >= 2:
            raise serializers.ValidationError("More than 2 appointment with the lab")

    @staticmethod
    def test_lab_id_validator(data, request):
        if not data['test_ids']:
            logger.error(
                "Error 'No Test Ids given' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError(" No Test Ids given")

        avail_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids']).values(
            'id').distinct('test')

        if len(avail_test_queryset) != len(data['test_ids']):
            logger.error("Error 'Test Ids or lab Id is incorrect' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Test Ids or lab Id is incorrect")

    @staticmethod
    def time_slot_validator(data, request, is_integrated):
        start_dt = (form_time_slot(data.get('start_date'), data.get('start_time')) if not data.get("time_slot_start") else data.get("time_slot_start"))

        if start_dt < timezone.now():
            logger.error("Error 'Cannot book in past' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Cannot book in past")

        day_of_week = start_dt.weekday()

        lab_queryset = data['lab']

        lab_timing_queryset = lab_queryset.lab_timings.filter(day=day_of_week, start__lte=data.get('start_time'),
                                                              end__gte=data.get('start_time'),
                                                              for_home_pickup=data["is_home_pickup"]).exists()
        if is_integrated:
            pass
        else:
            if data["is_home_pickup"]:
                if not lab_queryset.is_home_collection_enabled:
                    logger.error(
                        "Error 'Home Pickup is disabled for the lab' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("Home Pickup is disabled for the lab")
                if data.get("start_time") < 7.0 or data.get("start_time") > 19.0:
                    logger.error(
                        "Error 'No time slot available' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("No time slot available")
            else:
                if not lab_queryset.always_open and not lab_timing_queryset:
                    logger.error(
                        "Error 'No time slot available' for lab appointment with data - " + json.dumps(request.data))
                    raise serializers.ValidationError("No time slot available")

    def get_slots_list(self, data):
        slots = list()
        am_timings = data[0]['timing']
        pm_timings = data[1]['timing']
        for timing in am_timings:
            slots.append(timing['value'])

        for timing in pm_timings:
            slots.append(timing['value'])

        return slots

    def thyrocare_test_validator(self, data):
        from ondoc.integrations.models import IntegratorTestMapping

        test_ids = data.get("test_ids", None)
        if test_ids:
            for test in test_ids:
                integrator_test = IntegratorTestMapping.objects.filter(test_id=test).first()
                if integrator_test and integrator_test.integrator_product_data['code'] == 'FBS':
                    self.fbs_valid(test_ids, test)
                elif integrator_test and integrator_test.integrator_product_data['code'] in ['PPBS', 'RBS']:
                    self.ppbs_valid(test_ids, test)
                elif integrator_test and integrator_test.integrator_product_data['code'] == 'INSPP':
                    self.inspp_valid(test_ids, test)

    def fbs_valid(self, test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(test_ids) < 2:
            raise serializers.ValidationError("FBS can be added with any fasting test or package.")

        is_profile_or_fasting_added = False
        test_ids.remove(test)
        if not test_ids:
            pass

        for test in test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST').first()
            if integrator_test and integrator_test.integrator_product_data['fasting'] == 'CF':
                is_profile_or_fasting_added = True
            else:
                integrator_profile = IntegratorTestMapping.objects.filter(Q(test_id=test) & ~Q(test_type='TEST')).first()
                if integrator_profile:
                    is_profile_or_fasting_added = True

        if is_profile_or_fasting_added:
            pass
        else:
            raise serializers.ValidationError("FBS can be added with any fasting test or package.")

    def ppbs_valid(self, test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(test_ids) < 3:
            raise serializers.ValidationError("PPBS or RBS can be added with FBS and one fasting test or package.")

        is_fbs_present = False
        is_profile_or_fasting_added = False
        test_ids.remove(test)
        if not test_ids:
            pass

        for test in test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST').first()
            if integrator_test and integrator_test.integrator_product_data['code'] == 'FBS':
                is_fbs_present = True
            elif integrator_test and integrator_test.integrator_product_data['fasting'] == 'CF':
                is_profile_or_fasting_added = True
            else:
                integrator_profile = IntegratorTestMapping.objects.filter(Q(test_id=test) & ~Q(test_type='TEST')).first()
                if integrator_profile:
                    is_profile_or_fasting_added = True

        if is_fbs_present and is_profile_or_fasting_added:
            pass
        else:
            raise serializers.ValidationError("PPBS or RBS can be added with FBS and one fasting test or package.")

    def inspp_valid(self, test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(test_ids) < 2:
            raise serializers.ValidationError("INSFA test is mandatory to book INSPP.")

        insfa_test_present = False
        test_ids.remove(test)
        if not test_ids:
            pass

        for test in test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST').first()
            if integrator_test and integrator_test.integrator_product_data['code'] == 'INSFA':
                insfa_test_present = True

        if insfa_test_present:
            pass
        else:
            raise serializers.ValidationError("INSFA test is mandatory to book INSPP.")


class TimeSlotSerializer(serializers.Serializer):
    MORNING = 0
    AFTERNOON = 1
    EVENING = 2
    TIME_SPAN = 15
    # INT_SPAN = (TIME_SPAN/60)
    # TIME_INTERVAL = [":"+str(i) for i in range()]
    timing = serializers.SerializerMethodField()

    def get_timing(self, obj):
        start = float(obj.start)
        end = float(obj.end)
        time_span = self.TIME_SPAN
        day = obj.day
        timing = self.context['timing']

        int_span = (time_span / 60)
        # timing = dict()
        if not timing[day].get('timing'):
            timing[day]['timing'] = dict()
            timing[day]['timing'][self.MORNING] = OrderedDict()
            timing[day]['timing'][self.AFTERNOON] = OrderedDict()
            timing[day]['timing'][self.EVENING] = OrderedDict()
        num_slots = int(60 / time_span)
        if 60 % time_span != 0:
            num_slots += 1
        h = start
        while h < end:
        # for h in range(start, end):
            for i in range(0, num_slots):
                temp_h = h + i * int_span
                day_slot, am_pm = self.get_day_slot(temp_h)
                day_time_hour = int(temp_h)
                day_time_min = (temp_h - day_time_hour) * 60
                if temp_h >= 12:
                    day_time_hour -= 12
                day_time_min_str = str(int(day_time_min))
                day_time_hour_str = str(int(day_time_hour))

                if int(day_time_hour) < 10:
                    day_time_hour_str = '0' + str(int(day_time_hour))

                if int(day_time_min) < 10:
                    day_time_min_str = '0' + str(int(day_time_min))
                time_str = day_time_hour_str + ":" + day_time_min_str + " " + am_pm
                # temp_dict[temp_h] = time_str
                timing[day]['timing'][day_slot][temp_h] = time_str
            h += 1
        return timing

    def get_day_slot(self, time):
        am = 'AM'
        pm = 'PM'
        if time < 12:
            return self.MORNING, am
        elif time < 16:
            return self.AFTERNOON, pm
        else:
            return self.EVENING, pm


class IdListField(serializers.Field):
    def to_internal_value(self, data):
        try:
            id_str = data.strip(',')
            ids = set(map(int, id_str.split(",")))
        except:
            raise serializers.ValidationError("Wrong Ids")
        return ids


class SearchLabListSerializer(serializers.Serializer):
    min_distance = serializers.IntegerField(required=False)
    max_distance = serializers.IntegerField(required=False)
    min_price = serializers.IntegerField(required=False)
    max_price = serializers.IntegerField(required=False)
    long = serializers.FloatField(required=False)
    lat = serializers.FloatField(required=False)
    ids = IdListField(required=False)
    sort_on = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    network_id = serializers.IntegerField(required=False)
    is_insurance = serializers.BooleanField(required=False)


class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    time_slot_start = serializers.DateTimeField(required=False)
    time_slot_end = serializers.DateTimeField(required=False)
    start_date = serializers.CharField(required=False)
    start_time = serializers.FloatField(required=False)


class LabAppointmentRetrieveSerializer(LabAppointmentModelSerializer):
    profile = UserProfileSerializer()
    lab = LabModelSerializer()
    # lab_test = AvailableLabTestSerializer(many=True)
    lab_test = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    type = serializers.ReadOnlyField(default='lab')
    reports = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()
    mask_data = serializers.SerializerMethodField()

    def get_mask_data(self, obj):
        mask_number = obj.mask_number.first()
        if mask_number:
            return mask_number.build_data()
        return None

    def get_lab_test(self, obj):
        return LabAppointmentTestMappingSerializer(obj.test_mappings.all(), many=True).data

    def get_cancellation_reason(self, obj):
        return obj.get_serialized_cancellation_reason()

    def get_reports(self, obj):
        reports = []
        for rep in obj.get_reports():
            reports.append({"details": rep.report_details, "files":[file.name.url for file in rep.files.all()]})
        return reports

    def get_invoices(self, obj):
        return obj.get_invoice_urls()

    def get_address(self, obj):
        resp_address = ""
        if obj.address:
            if obj.address.get("address"):
                resp_address += str(obj.address.get("address")).strip().replace(',','')
            if obj.address.get("land_mark"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("land_mark"))
            if obj.address.get("locality"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("locality"))
            if obj.address.get("pincode"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("pincode"))
        return resp_address

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end','is_rated', 'rating_declined',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab', 'otp', 'address', 'type', 'reports', 'invoices', 'cancellation_reason', 'mask_data', 'payment_type', 'price')


class DoctorLabAppointmentRetrieveSerializer(LabAppointmentModelSerializer):
    profile = UserProfileSerializer()
    lab = LabModelSerializer()
    lab_test = AvailableLabTestSerializer(many=True)

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab')


class AppointmentCompleteBodySerializer(serializers.Serializer):
    lab_appointment = serializers.PrimaryKeyRelatedField(queryset=LabAppointment.objects.all())
    otp = serializers.IntegerField(max_value=9999)

    def validate(self, attrs):
        appointment = attrs.get('lab_appointment')
        if appointment.status == LabAppointment.COMPLETED:
            raise serializers.ValidationError("Appointment Already Completed.")
        elif appointment.status == LabAppointment.CANCELLED:
            raise serializers.ValidationError("Cannot Complete a Cancelled Appointment.")
        if not appointment.otp == attrs['otp']:
            raise serializers.ValidationError("Invalid OTP.")
        return attrs


class LabAppointmentFilterSerializer(serializers.Serializer):
    RANGE_CHOICES = ['all', 'previous', 'upcoming', 'pending']
    range = serializers.ChoiceField(choices=RANGE_CHOICES, required=False, default='all')
    lab_id = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all(), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    date = serializers.DateField(required=False)


class LabReportFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = LabReportFile
        fields = ('report', 'name')


class LabReportSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(queryset=LabAppointment.objects.all())
    report_details = serializers.CharField(allow_blank=True, allow_null=True, required=False, max_length=300)
    name = serializers.FileField()

    def validate_appointment(self, value):
        request = self.context.get('request')

        if not LabAppointment.objects.filter(Q(id=value.id), (
                Q(lab__network__isnull=True, lab__manageable_lab_admins__user=request.user,
                  lab__manageable_lab_admins__is_disabled=False) |
                Q(lab__network__isnull=False,
                  lab__network__manageable_lab_network_admins__user=request.user,
                  lab__network__manageable_lab_network_admins__is_disabled=False))).exists():
            raise serializers.ValidationError("User is not authorized to upload report.")
        return value


class LabEntitySerializer(serializers.ModelSerializer):

    address = serializers.SerializerMethodField()
    entity_type = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()


    def get_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            raise ValueError("request is not passed in serializer.")
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    def get_entity_type(self, obj):
        return GenericAdminEntity.LAB

    def get_address(self, obj):
        return obj.get_lab_address() if obj.get_lab_address() else None

    class Meta:
        model = Lab
        fields = ('id',  'thumbnail', 'name', 'address', 'entity_type')


class CustomPackageLabSerializer(LabModelSerializer):
    # avg_rating = serializers.ReadOnlyField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'lab_thumbnail', 'name', 'operational_since', 'locality', 'address',
                  'sublocality', 'city', 'state', 'country', 'always_open', 'about', 'home_pickup_charges',
                  'is_home_collection_enabled', 'seo', 'breadcrumb', 'center_visit_enabled', 'avg_rating', 'url')

    def get_url(self, obj):
        entity_url_dict = self.context.get('entity_url_dict', {})
        return entity_url_dict.get(obj.id, [''])[0] if obj.id else ''

    # def get_avg_rating(self, obj):
    #     return obj.avg_rating


class CustomLabTestPackageSerializer(serializers.ModelSerializer):
    lab = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    mrp = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    lab_timing = serializers.SerializerMethodField()
    lab_timing_data = serializers.SerializerMethodField()
    next_lab_timing = serializers.SerializerMethodField()
    next_lab_timing_data = serializers.SerializerMethodField()
    pickup_charges = serializers.SerializerMethodField()
    pickup_available = serializers.SerializerMethodField()
    distance_related_charges = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    priority_score = serializers.SerializerMethodField()
    category_details = serializers.SerializerMethodField()
    tests = serializers.SerializerMethodField()
    included_in_user_plan = serializers.SerializerMethodField()
    insurance = serializers.SerializerMethodField()


    class Meta:
        model = LabTest
        fields = ('id', 'name', 'lab', 'mrp', 'distance', 'price', 'lab_timing', 'lab_timing_data', 'next_lab_timing',
                  'next_lab_timing_data', 'test_type', 'is_package', 'number_of_tests', 'why', 'pre_test_info',
                  'is_package', 'pickup_charges', 'pickup_available', 'distance_related_charges', 'priority',
                  'show_details', 'categories', 'url', 'priority_score', 'category_details', 'tests', 'included_in_user_plan', 'insurance')

    def get_insurance(self, obj):
        request = self.context.get("request")
        resp = Lab.get_insurance_details(request.user)
        lab_data = self.context.get('lab_data', {})
        lab = lab_data.get(obj.lab, None)

        if obj and lab and lab.is_enabled_for_insurance and obj.mrp is not None and resp['insurance_threshold_amount'] is not None and obj.mrp <= resp['insurance_threshold_amount']:
            resp['is_insurance_covered'] = True

        return resp

    def get_included_in_user_plan(self, obj):
        package_free_or_not_dict = self.context.get('package_free_or_not_dict', {})
        return package_free_or_not_dict.get(obj.id, False)

    def get_priority_score(self, obj):
        return int(obj.priority_score)

    def get_tests(self, obj):
        return_data = list()
        for temp_test in obj.test.all():
            parameter_count = len(temp_test.parameter.all()) or 1
            name = temp_test.name
            test_id = temp_test.id
            return_data.append({'id': test_id, 'name': name, 'parameter_count': parameter_count})
        return return_data

    def get_categories(self, obj):
        return obj.get_all_categories_detail()

    def get_category_details(self, obj):
        category_data = self.context.get('category_data', {})
        return category_data.get(obj.id, [])

    def get_lab(self, obj):
        lab_data = self.context.get('lab_data', {})
        request = self.context.get('request')
        entity_url_dict = self.context.get('entity_url_dict', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return CustomPackageLabSerializer(data,
                                              context={'entity_url_dict': entity_url_dict, 'request': request}).data
        return None

    def get_distance(self, obj):
        return int(obj.distance.m)

    def get_mrp(self, obj):
        return str(obj.mrp)

    def get_price(self, obj):
        return str(obj.price)

    def get_lab_timing(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return data.lab_timings_today_and_next().get('lab_timing', '')
        return ''

    def get_lab_timing_data(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return data.lab_timings_today_and_next().get('lab_timing_data', [])
        return []

    def get_next_lab_timing(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return data.lab_timings_today_and_next().get('next_lab_timing_dict', {})
        return {}

    def get_next_lab_timing_data(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return data.lab_timings_today_and_next().get('next_lab_timing_data_dict', {})
        return {}

    def get_rating(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None and data.rating_data:
            return data.rating_data.get('avg_rating')
        return None

    def get_pickup_charges(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None and data.id == obj.lab and data.is_home_collection_enabled:
            return data.home_pickup_charges
        else:
            return 0

    def get_pickup_available(self, obj):
        for temp_test in obj.test.all():
            if not temp_test.home_collection_possible:
                return 0
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return 1 if data.is_home_collection_enabled else 0
        return 0

    def get_distance_related_charges(self, obj):
        lab_data = self.context.get('lab_data', {})
        data = lab_data.get(obj.lab, None)
        if data is not None:
            return 1 if bool(data.home_collection_charges.all()) else 0
        return 0


class LabPackageListSerializer(serializers.Serializer):
    long = serializers.FloatField(default=77.071848)
    lat = serializers.FloatField(default=28.450367)
    min_distance = serializers.IntegerField(required=False)
    max_distance = serializers.IntegerField(required=False)
    min_price = serializers.IntegerField(required=False)
    max_price = serializers.IntegerField(required=False)
    sort_on = serializers.CharField(required=False)
    category_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)
    package_category_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)
    test_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)
    min_age = serializers.IntegerField(required=False)
    max_age = serializers.IntegerField(required=False)
    gender = serializers.ChoiceField(choices=LabTest.GENDER_TYPE_CHOICES, required=False)
    package_type = serializers.IntegerField(required=False)
    package_ids = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)

    def validate_package_ids(self, attrs):
        try:
            attrs = list(set(attrs))
            if LabTest.objects.filter(searchable=True, enable_for_retail=True, id__in=attrs).count() == len(attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Package IDs')
        raise serializers.ValidationError('Invalid Package IDs')

    def validate_category_ids(self, attrs):
        try:
            attrs = set(attrs)
            if LabTestCategory.objects.filter(is_live=True, is_package_category=True, id__in=attrs).count() == len(attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Category IDs')
        raise serializers.ValidationError('Invalid Category IDs')

    def validate_package_category_ids(self, attrs):
        try:
            attrs = set(attrs)
            if LabTestCategory.objects.filter(is_live=True, is_package_category=True, id__in=attrs).count() == len(attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Package Category IDs')
        raise serializers.ValidationError('Invalid Package Category IDs')

    def validate_test_ids(self, attrs):
        try:
            attrs = set(attrs)
            if LabTest.objects.filter(enable_for_retail=True, searchable=True, id__in=attrs).count() == len(attrs):
                return attrs
        except:
            raise serializers.ValidationError('Invalid Test IDs')
        raise serializers.ValidationError('Invalid Test IDs')


class RecommendedPackageCategoryList(serializers.ModelSerializer):

    tests = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()

    def get_tests(self, obj):
        test_id = []
        if obj:
            for tst in obj.recommended_lab_tests.all():
                temp_parameters = list(tst.parameter.all())
                num_of_parameters = len(temp_parameters)
                temp_parameters_names = [param.name for param in temp_parameters]
                test_id.append({"id": tst.id, "name": tst.name, "num_of_parameters": num_of_parameters,
                                "parameters": temp_parameters_names})
        return test_id

    def get_icon(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(obj.icon.url) if obj.icon and obj.icon.url else None

    class Meta:
        model = LabTestCategory
        fields = ('id', 'name', 'tests', 'icon')


class LabAppointmentUpcoming(LabAppointmentModelSerializer):
    address = serializers.SerializerMethodField()
    provider_id = serializers.IntegerField(source='lab.id')
    name = serializers.ReadOnlyField(source='lab.name')
    hospital_name = serializers.SerializerMethodField()

    class Meta:
        model = LabAppointment
        fields = ('id', 'provider_id', 'name', 'hospital_name', 'patient_name', 'type',
                  'status', 'time_slot_start', 'time_slot_end', 'address')

    def get_address(self, obj):
        return obj.lab.get_lab_address()

    def get_hospital_name(self, obj):
        return None


class PackageSerializer(LabTestSerializer):
    included_tests = serializers.SerializerMethodField()
    show_detail_in_plan = serializers.SerializerMethodField()
    total_parameter_count = serializers.SerializerMethodField()

    class Meta:
        model = LabTest
        fields = ('id', 'name', 'is_package',
                  # 'pre_test_info', 'why',
                  'show_details', 'url',  # They exist but are not needed yet
                  'included_tests', 'show_detail_in_plan', 'total_parameter_count')

    def get_included_tests(self, obj):
        return_data = list()
        for temp_test in obj.test.all():
            parameter_count = len(temp_test.parameter.all()) or 1
            name = temp_test.name
            test_id = temp_test.id
            return_data.append({'id': test_id, 'name': name, 'parameter_count': parameter_count})
        return return_data

    def get_show_detail_in_plan(self, obj):
        for temp_test in obj.test.all():
            return True
        return False

    def get_total_parameter_count(self, obj):
        return_data = 0
        for temp_test in obj.test.all():
            parameter_count = len(temp_test.parameter.all()) or 1
            return_data += parameter_count
        return return_data


class CompareLabPackagesSerializer(serializers.Serializer):

    package_ids = CommaSepratedToListField(required=True, max_length=5, typecast_to=str)
    longitude = serializers.FloatField(default=77.071848)
    latitude = serializers.FloatField(default=28.450367)
    title = serializers.CharField(required=False, max_length=500)

    def validate_package_ids(self, attrs):
        try:
            package_ids = list(set([int(attr) for attr in attrs]))
            if LabTest.objects.filter(id__in=package_ids, is_package=True, enable_for_retail=True).count() == len(package_ids):
                return package_ids
        except:
            raise serializers.ValidationError('Invalid Lab Package IDs')
        raise serializers.ValidationError('Invalid Lab Package IDs')
