import dateutil
from rest_framework import serializers
from rest_framework.fields import CharField

from ondoc.cart.models import Cart
from ondoc.common.models import SearchCriteria, UserConfig
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage, LabReportFile, CommonPackage,
                                     LabTestCategory, LabAppointmentTestMapping, LabTestGroup, LabTestGroupMapping)
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.authentication.models import UserProfile, Address
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer, CommaSepratedToListField
from ondoc.api.v1.auth.serializers import AddressSerializer, UserProfileSerializer
from ondoc.api.v1.utils import form_time_slot, GenericAdminEntity, util_absolute_url
from ondoc.doctor.models import OpdAppointment, CancellationReason
from ondoc.account.models import Order, Invoice
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon, CouponRecommender
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
from ondoc.plus.models import PlusUser, PlusAppointmentMapping, PlusPlans
from ondoc.plus.usage_criteria import get_class_reference, get_price_reference
from ondoc.prescription.models import AppointmentPrescription
from ondoc.ratings_review.models import RatingsReview
from django.db.models import Avg
from django.db.models import Q
from ondoc.api.v1.ratings import serializers as rating_serializer
from ondoc.location.models import EntityUrls, EntityAddress
from ondoc.seo.models import NewDynamic
from ondoc.subscription_plan.models import Plan, UserPlanMapping
from packaging.version import parse
from ondoc.plus.enums import UtilizationCriteria

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
            rate_count = obj.rating.filter(is_live=True).count()
        avg = 0
        if rate_count:
            all_rating = []
            for rate in obj.rating.filter(is_live=True):
                all_rating.append(rate.ratings)
            if all_rating:
                avg = sum(all_rating) / len(all_rating)
        if rate_count > 5 or (rate_count <= 5 and avg > 4):
            return True
        return False

    def get_center_visit_enabled(self, obj):
        if obj and obj.center_visit and ((obj.network and obj.network.center_visit) or not obj.network):
            return True
        return False
        # if obj and obj.network and settings.THYROCARE_NETWORK_ID:
        #     if obj.network.id == settings.THYROCARE_NETWORK_ID:
        #         return False
        # return True

    def get_rating(self, obj):
        if self.parent:
            return None
        app = obj.labappointment.all().select_related('profile')

        query = self.context.get('rating_queryset')
        if query:
            rating_queryset = query.exclude(Q(review='') | Q(review=None)).order_by('-ratings', '-updated_at')
            reviews = rating_serializer.RatingsModelSerializer(rating_queryset, many=True, context={'app': app})
            return reviews.data[:5]

        return []

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
            if entity and entity.additional_info:
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
                  'center_visit_enabled', 'display_rating_widget', 'is_thyrocare', 'network_id')


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
    vip = serializers.SerializerMethodField()
    hide_price = serializers.ReadOnlyField(source='test.hide_price')
    included_in_user_plan = serializers.SerializerMethodField()
    is_price_zero = serializers.SerializerMethodField()
    # is_prescription_needed = serializers.SerializerMethodField()
    lensfit_offer = serializers.SerializerMethodField()
    is_radiology = serializers.SerializerMethodField()
    is_pathology = serializers.SerializerMethodField()

    def get_is_price_zero(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        if agreed_price is not None and agreed_price==0:
            return True
        else:
            return False

    def get_included_in_user_plan(self, obj):
        package_free_or_not_dict = self.context.get('package_free_or_not_dict', {})
        return package_free_or_not_dict.get(obj.test.id, False)

    # def get_is_prescription_needed(self, obj):
    #     request = self.context.get("request")
    #     if not request:
    #         return False
    #
    #     data = None
    #     logged_in_user = request.user
    #     agreed_price = self.get_agreed_price(obj)
    #     if logged_in_user.is_authenticated and not logged_in_user.is_anonymous and agreed_price:
    #         user_insurance = request.user.active_insurance
    #         data = user_insurance.validate_limit_usages(agreed_price) if user_insurance else None
    #
    #     if not data:
    #         return False
    #
    #   return data.get('prescription_needed', False)

    def get_vip(self, obj):
        request = self.context.get("request")
        lab_obj = self.context.get("lab")
        resp = Lab.get_vip_details(request.user)
        user = request.user
        plus_obj = None
        if user and user.is_authenticated and not user.is_anonymous:
            plus_obj = user.active_plus_user if user.active_plus_user and user.active_plus_user.status == PlusUser.ACTIVE else None
        plan = plus_obj.plan if plus_obj else None
        deal_price = obj.custom_deal_price if obj.custom_deal_price else obj.computed_deal_price
        agreed_price = obj.custom_agreed_price if obj.custom_agreed_price else obj.computed_agreed_price
        price_data = {"mrp": obj.mrp, "deal_price": deal_price, "cod_deal_price": deal_price, "fees": agreed_price}
        resp['vip_gold_price'] = agreed_price
        resp['vip_convenience_amount'] = obj.calculate_convenience_charge(plan)
        resp['is_enable_for_vip'] = True if lab_obj and lab_obj.is_enabled_for_plus_plans() else False
        resp['is_prescription_required'] = False


        if not plus_obj:
            return resp
        resp['is_gold_member'] = True if plus_obj.plan.is_gold else False

        entity = "LABTEST" if not obj.test.is_package else "PACKAGE"

        price_engine = get_price_reference(plus_obj, "LABTEST")
        if not price_engine:
            price = obj.mrp
        else:
            price = price_engine.get_price(price_data)
        engine = get_class_reference(plus_obj, entity)
        if not engine:
            return resp
        if engine and obj and obj.mrp and lab_obj and lab_obj.is_enabled_for_plus_plans():
            # engine_response = engine.validate_booking_entity(cost=obj.mrp, id=obj.test.id)
            # resp['vip_convenience_amount'] = user.active_plus_user.plan.get_convenience_charge(price, "LABTEST")
            # resp['vip_convenience_amount'] = PlusPlans.get_default_convenience_amount(price_data, "LABTEST", default_plan_query=user.active_plus_user.plan)
            resp['vip_convenience_amount'] = obj.calculate_convenience_charge(plan)
            engine_response = engine.validate_booking_entity(cost=price, id=obj.test.id, mrp=obj.mrp, deal_price=deal_price, price_engine_price=price)
            resp['covered_under_vip'] = engine_response['is_covered']
            resp['vip_amount'] = engine_response['amount_to_be_paid']
        if plus_obj and plus_obj.plan and plus_obj.plan.is_prescription_required and resp['covered_under_vip']:
            resp['is_prescription_required'] = True
        else:
            resp['is_prescription_required'] = False
        return resp



    def get_insurance(self, obj):
        request = self.context.get("request")
        lab_obj = self.context.get("lab")
        resp = Lab.get_insurance_details(request.user)

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

    def get_lensfit_offer(self, obj):
        from ondoc.api.v1.coupon.serializers import CouponSerializer
        is_insurance_covered = False
        offer = {
            'applicable': False,
            'coupon': {}
        }
        # Commented as not being used
        if False:
            insurance_applicable = False
            request = self.context.get("request")
            lab = self.context.get("lab")
            profile = self.context.get("profile")
            user = request.user
            resp = Lab.get_insurance_details(user)

            if lab.is_enabled_for_insurance and obj.mrp is not None and resp['insurance_threshold_amount'] is not None \
                    and obj.mrp <= resp['insurance_threshold_amount']:
                is_insurance_covered = True

            if is_insurance_covered and user and user.is_authenticated and profile:
                insurance_applicable = user.active_insurance and profile.is_insured_profile

            if not insurance_applicable:
                deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
                coupon_code = Coupon.objects.filter(is_lensfit=True).order_by('-created_at').first()
                product_id = Order.LAB_PRODUCT_ID

                filters = dict()
                filters['lab'] = dict()
                lab_obj = filters['lab']
                lab_obj['id'] = lab.id
                lab_obj['network_id'] = lab.network_id
                lab_obj['city'] = lab.city
                filters['tests'] = [obj.test]
                filters['deal_price'] = deal_price
                coupon_recommender = CouponRecommender(request.user, profile, 'lab', product_id, coupon_code, None)
                applicable_coupons = coupon_recommender.applicable_coupons(**filters)

                lensfit_coupons = list(filter(lambda x: x.is_lensfit is True, applicable_coupons))
                if lensfit_coupons:
                    offer['applicable'] = True
                    coupon_properties = coupon_recommender.get_coupon_properties(str(lensfit_coupons[0]))
                    serializer = CouponSerializer(lensfit_coupons[0], context={'coupon_properties': coupon_properties})
                    offer['coupon'] = serializer.data

        return offer

    def get_is_radiology(self, obj):
        return obj.test.test_type == LabTest.RADIOLOGY

    def get_is_pathology(self, obj):
        return obj.test.test_type == LabTest.PATHOLOGY


    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled',
                  'package', 'parameters', 'is_package', 'number_of_tests', 'why', 'pre_test_info', 'expected_tat',
                  'hide_price', 'included_in_user_plan', 'insurance', 'is_price_zero', 'insurance_agreed_price',
                  'lensfit_offer', 'vip', 'is_radiology', 'is_pathology')

class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()
    insurance = serializers.SerializerMethodField()
    vip = serializers.SerializerMethodField()
    is_package = serializers.SerializerMethodField()
    included_in_user_plan = serializers.SerializerMethodField()
    is_price_zero = serializers.SerializerMethodField()
    is_pathology = serializers.SerializerMethodField()
    is_radiology = serializers.SerializerMethodField()

    def get_is_price_zero(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        if agreed_price is not None and agreed_price == 0:
            return True
        else:
            return False

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

    def get_vip(self, obj):
        request = self.context.get("request")
        lab_obj = self.context.get("lab")
        resp = Lab.get_vip_details(request.user)
        user = request.user
        deal_price = obj.custom_deal_price if obj.custom_deal_price else obj.computed_deal_price
        agreed_price = obj.custom_agreed_price if obj.custom_agreed_price else obj.computed_agreed_price
        price_data = {"mrp": obj.mrp, "deal_price": deal_price, "cod_deal_price": deal_price, "fees": agreed_price}

        resp['is_enable_for_vip'] = True if lab_obj and lab_obj.is_enabled_for_plus_plans() else False
        plus_obj = None
        if user and user.is_authenticated and not user.is_anonymous:
            plus_obj = user.active_plus_user if user.active_plus_user and user.active_plus_user.status == PlusUser.ACTIVE else None
        plan = plus_obj.plan if plus_obj else None
        resp['vip_gold_price'] = agreed_price
        resp['vip_convenience_amount'] = obj.calculate_convenience_charge(plan)

        if not plus_obj:
            return resp
        resp['is_gold_member'] = True if plus_obj.plan.is_gold else False
        entity = "LABTEST" if not obj.test.is_package else "PACKAGE"
        price_engine = get_price_reference(plus_obj, "LABTEST")
        if not price_engine:
            price = obj.mrp
        else:
            price = price_engine.get_price(price_data)
        engine = get_class_reference(plus_obj, entity)

        if not engine:
            return resp

        if engine and obj and obj.mrp and lab_obj and lab_obj.is_enabled_for_plus_plans():
            # engine_response = engine.validate_booking_entity(cost=obj.mrp, id=obj.test.id)
            # resp['vip_convenience_amount'] = user.active_plus_user.plan.get_convenience_charge(price, "LABTEST")
            resp['vip_convenience_amount'] = obj.calculate_convenience_charge(plan)
            engine_response = engine.validate_booking_entity(cost=price, id=obj.test.id, mrp=obj.mrp, deal_price=deal_price, price_engine_price=price)
            resp['covered_under_vip'] = engine_response['is_covered']
            resp['vip_amount'] = engine_response['amount_to_be_paid']

        return resp

        # plus_obj = user.active_plus_user if not user.is_anonymous and user.is_authenticated else None
        # utilization = plus_obj.get_utilization if plus_obj else {}
        # package_amount_balance = utilization.get('available_package_amount', 0)
        #
        # if plus_obj and lab_obj and obj and lab_obj.enabled_for_plus_plans and obj.mrp:
        #     utilization_criteria, can_be_utilized = plus_obj.can_package_be_covered_in_vip(obj)
        #     if can_be_utilized:
        #         resp['covered_under_vip'] = True
        #     else:
        #         return resp
        #
        #     if utilization_criteria == UtilizationCriteria.COUNT:
        #         resp['vip_amount'] = 0
        #     else:
        #         if obj.mrp <= package_amount_balance:
        #             resp['vip_amount'] = 0
        #         else:
        #             resp['vip_amount'] = obj.mrp - package_amount_balance
        #
        # return resp

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

    def get_is_package(self, obj):
        return obj.test.is_package

    def get_is_radiology(self, obj):
        return obj.test.test_type == LabTest.RADIOLOGY

    def get_is_pathology(self, obj):
        return obj.test.test_type == LabTest.PATHOLOGY

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled',
                  'insurance', 'is_package', 'included_in_user_plan', 'is_price_zero', 'insurance_agreed_price',
		  'is_pathology', 'is_radiology', 'vip')



class LabAppointmentTestMappingSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()
    test_type = serializers.ReadOnlyField(source='test.test_type')

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
                  'test_type', 'is_home_collection_enabled')


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
    svg_icon = serializers.SerializerMethodField

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    def get_svg_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['svg_icon']) if obj['svg_icon'] else None

    class Meta:
        model = CommonTest
        fields = ('id', 'name', 'icon', 'show_details', 'test_type', 'url', 'svg_icon')


class CommonPackageSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='package.id')
    name = serializers.ReadOnlyField(source='package.name')
    show_details = serializers.ReadOnlyField(source='package.show_details')
    icon = serializers.SerializerMethodField()
    url = serializers.ReadOnlyField(source='package.url')
    no_of_tests = serializers.ReadOnlyField(source='package.number_of_tests')
    agreed_price = serializers.SerializerMethodField()
    mrp = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    discounted_price = serializers.SerializerMethodField()
    vip = serializers.SerializerMethodField()
    svg_icon = serializers.SerializerMethodField()

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)
        queryset = AvailableLabTest.objects
        filters = Q()  # Create an empty Q object to start with

        for ins in instance:
            if ins.lab and ins.lab.lab_pricing_group_id and ins.package_id:
                q = Q(lab_pricing_group_id=ins.lab.lab_pricing_group_id,test_id = ins.package_id)
                filters |= q

        if filters:
            queryset = queryset.select_related('test').prefetch_related('test__categories').filter(filters)
        else:
            queryset = queryset.none()
        for ins in instance:
            ins._selected_test = None
            for x in queryset:
                if ins.lab and ins.lab.lab_pricing_group_id == x.lab_pricing_group_id and ins.package_id == x.test_id:
                    ins._selected_test = x
                    break

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if obj.icon else None

    def get_svg_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.svg_icon.url) if obj.svg_icon else None

    def get_agreed_price(self, obj):
        if obj._selected_test:
            return obj._selected_test.get_deal_price()
        return None

    def get_mrp(self, obj):
        if obj._selected_test:
            return obj._selected_test.mrp
        return None

    def get_discounted_price(self, obj):
        discounted_price = None
        coupon_recommender = self.context.get('coupon_recommender')
        filters = dict()

        if obj._selected_test:
            deal_price = obj._selected_test.get_deal_price()
            if coupon_recommender:
                filters['deal_price'] = deal_price
                filters['tests'] = [obj._selected_test.test]

                package_result_lab = getattr(obj, 'lab') if hasattr(obj, 'lab') else None
                if package_result_lab and isinstance(package_result_lab, Lab):
                    filters['lab'] = dict()
                    lab_obj = filters['lab']
                    lab_obj['id'] = package_result_lab.id
                    lab_obj['network_id'] = package_result_lab.network_id
                    lab_obj['city'] = package_result_lab.city
            search_coupon = coupon_recommender.best_coupon(**filters) if coupon_recommender else None

            discounted_price = deal_price if not search_coupon else search_coupon.get_search_coupon_discounted_price(deal_price)

        return discounted_price

    def get_vip(self, obj):
        request = self.context.get("request")
        resp = Lab.get_vip_details(request.user, search_criteria_query=self.context.get('is_gold_search_criteria'))
        user = request.user

        deal_price = None
        mrp = None
        agreed_price = None
        if obj._selected_test:
            mrp = obj._selected_test.mrp
            deal_price = obj._selected_test.custom_deal_price if obj._selected_test.custom_deal_price else obj._selected_test.computed_deal_price
            agreed_price = obj._selected_test.custom_agreed_price if obj._selected_test.custom_agreed_price else obj._selected_test.computed_agreed_price

        lab_obj = obj.lab
        price_data = {"mrp": mrp, "deal_price": deal_price,
                      "cod_deal_price": deal_price,
                      "fees": agreed_price}
        resp['vip_gold_price'] = agreed_price
        plus_obj = None
        if user and user.is_authenticated and not user.is_anonymous:
            plus_obj = user.active_plus_user if user.active_plus_user and user.active_plus_user.status == PlusUser.ACTIVE else None
        plan = plus_obj.plan if plus_obj else None
        resp['vip_gold_price'] = agreed_price
        resp['vip_convenience_amount'] = obj._selected_test.calculate_convenience_charge(plan=plan if plan else self.context.get('plan'))

        # resp['vip_convenience_amount'] = PlusPlans.get_default_convenience_amount(agreed_price, "LABTEST")
        resp['is_enable_for_vip'] = True if lab_obj and lab_obj.is_enabled_for_plus_plans() else False

        if not plus_obj:
            return resp
        resp['is_gold_member'] = True if plus_obj.plan.is_gold else False
        entity = "PACKAGE"

        price_engine = get_price_reference(plus_obj, "LABTEST")
        if not price_engine:
            price = mrp
        else:
            price = price_engine.get_price(price_data)

        engine = get_class_reference(plus_obj, entity)
        if not engine:
            return resp

        if engine and obj and obj._selected_test and lab_obj and lab_obj.is_enabled_for_plus_plans() and obj._selected_test.mrp:
            # engine_response = engine.validate_booking_entity(cost=obj._selected_test.mrp, id=obj.package.id)
            # resp['vip_convenience_amount'] = user.active_plus_user.plan.get_convenience_charge(price, "LABTEST")
            resp['vip_convenience_amount'] = obj._selected_test.calculate_convenience_charge(plan)
            engine_response = engine.validate_booking_entity(cost=price, id=obj.package.id, mrp=obj._selected_test.mrp, deal_price=deal_price, price_engine_price=price)
            resp['covered_under_vip'] = engine_response['is_covered']
            resp['vip_amount'] = engine_response['amount_to_be_paid']

        return resp

        # if plus_obj and obj and obj._selected_test and lab_obj.enabled_for_plus_plans and obj._selected_test.mrp:
        #     utilization_criteria, can_be_utilized = plus_obj.can_package_be_covered_in_vip(None, mrp=obj._selected_test.mrp, id=obj.package.id)
        #     if can_be_utilized:
        #         resp['covered_under_vip'] = True
        #     else:
        #         return resp
        #
        #     if utilization_criteria == UtilizationCriteria.COUNT:
        #         resp['vip_amount'] = 0
        #     else:
        #         if obj.mrp <= package_amount_balance:
        #             resp['vip_amount'] = 0
        #         else:
        #             resp['vip_amount'] = obj._selected_test.mrp - package_amount_balance
        #
        # return resp

    class Meta:
        model = CommonPackage
        fields = ('id', 'name', 'icon', 'show_details', 'url', 'no_of_tests', 'mrp', 'agreed_price', 'discounted_price', 'lab', 'vip', 'svg_icon',)


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

class LabTestNameSerializer(serializers.ModelSerializer):
    test_name = serializers.ReadOnlyField(source='test.name')

    class Meta:
        model = LabAppointmentTestMapping
        fields = ('test_name', )

class LabAppointmentTestMappingModelSerializer(serializers.ModelSerializer):
    test_id = serializers.ReadOnlyField(source="test.id")
    test_name = serializers.ReadOnlyField(source="test.name")
    test_type = serializers.ReadOnlyField(source="test.test_type")

    class Meta:
        model = LabAppointmentTestMapping
        fields = ('id', 'test_id', 'test_name', 'test_type', 'time_slot_start', 'is_home_pickup')


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
    report_files = serializers.SerializerMethodField()
    prescription = serializers.SerializerMethodField()
    lab_test_name = serializers.SerializerMethodField()
    vip = serializers.SerializerMethodField()
    selected_timings_type = serializers.SerializerMethodField()
    payment_mode = serializers.SerializerMethodField()

    def get_vip(self, obj):
        search_criteria = SearchCriteria.objects.filter(search_key='is_gold').first()
        hosp_is_gold = False
        if search_criteria:
            hosp_is_gold = search_criteria.search_value

        plus_appointment_mapping = None
        if obj:
            plus_appointment_mapping = PlusAppointmentMapping.objects.filter(object_id=obj.id).first()

        return {
            'is_vip_member': True if obj and obj.plus_plan and obj.plus_plan.plan and not obj.plus_plan.plan.is_gold else False,
            'vip_amount': plus_appointment_mapping.amount if plus_appointment_mapping else 0,
            'is_gold_member': True if plus_appointment_mapping and plus_appointment_mapping.plus_user and plus_appointment_mapping.plus_user.plan and plus_appointment_mapping.plus_user.plan.is_gold else False,
            'vip_amount_deducted': plus_appointment_mapping.amount if plus_appointment_mapping else 0,
            'covered_under_vip': True if obj and obj.plus_plan else False,
            'extra_charge': plus_appointment_mapping.extra_charge if plus_appointment_mapping else 0,
            'is_gold': hosp_is_gold
        }

    def get_prescription(self, obj):
        return []

    def get_report_files(self, obj):
        if obj:
            return obj.get_report_type()

    def get_lab_test(self, obj):
        return list(obj.test_mappings.values_list('test_id', flat=True))

    def get_lab_test_name(self, obj):
        return LabTestNameSerializer(obj.test_mappings.all(), many=True).data

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.lab.get_thumbnail()) if obj.lab and obj.lab.get_thumbnail() else None

    def get_patient_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile.get_thumbnail()) if obj.profile and obj.profile.get_thumbnail() else None

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

    def get_selected_timings_type(self, obj):
        selected_timings_type = None
        if obj.action_data:
            selected_timings_type = obj.action_data.get('selected_timings_type')

        return selected_timings_type

    def get_payment_mode(self, obj):
        payment_modes = dict(OpdAppointment.PAY_CHOICES)
        if payment_modes:
            effective_price = obj.effective_price
            payment_type = obj.payment_type
            if effective_price > 0 and payment_type == 5:
                return 'Online'
            else:
                return payment_modes.get(obj.payment_type, '')
        return ''

    class Meta:
        model = LabAppointment
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'patient_thumbnail', 'patient_name', 'allowed_action', 'address', 'invoices', 'reports', 'report_files',
                  'prescription', 'lab_test_name', 'vip', 'selected_timings_type', 'payment_mode')


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
    coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])
    coupon_data = serializers.JSONField(required=False)


class PrescriptionDocumentSerializer(serializers.Serializer):
    prescription = serializers.PrimaryKeyRelatedField(queryset=AppointmentPrescription.objects.all())


class LabAppointmentTestTransactionSerializer(serializers.Serializer):
    TEST_TYPE = [(LabTest.RADIOLOGY, "Radiology"), (LabTest.PATHOLOGY, "Pathology")]
    test_id = serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all())
    is_home_pickup = serializers.BooleanField(default=False)
    time_slot_start = serializers.DateTimeField()

class LabAppTransactionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    agreed_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    time_slot_start = serializers.DateTimeField(required=True, allow_null=True)
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
    plus_plan = serializers.PrimaryKeyRelatedField(queryset=PlusUser.objects.all(), allow_null=True)
    plus_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    extra_details = serializers.JSONField(required=False)
    user_plan = serializers.PrimaryKeyRelatedField(queryset=UserPlanMapping.objects.all(), allow_null=True)
    coupon_data = serializers.JSONField(required=False)
    prescription_list = serializers.ListSerializer(child=PrescriptionDocumentSerializer(), required=False)
    spo_data = serializers.JSONField(required=False, default={})
    _source = serializers.CharField(required=False, allow_null=True)
    _responsible_user = serializers.IntegerField(required=False, allow_null=True)
    # test_time_slots = serializers.ListSerializer(child=LabAppointmentTestTransactionSerializer(), required=False, allow_empty=False)
    selected_timings_type = serializers.ChoiceField(required=False, choices=(('common', 'common'), ('separate', 'separate')))
    vip_convenience_amount = serializers.DecimalField(allow_null=True, max_digits=10, decimal_places=2)

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)
        if data.get('multi_timings_enabled'):
            # data.pop('time_slot_start', None)
            # data.pop('is_home_pickup', None)
            # self.fields.fields['time_slot_start'].required = False
            # self.fields.fields['is_home_pickup'].required = False
            # self.fields.fields['test_time_slots'].required = True
            self.fields.fields['selected_timings_type'].required = True
        else:
            data.pop('selected_timings_type', None)
            # data.pop('test_time_slots', None)
            # self.fields.fields['test_time_slots'].required = False
            # self.fields.fields['selected_timings_type'].required = False
            # self.fields.fields['time_slot_start'].required = True



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


class LabAppointmentTestSerializer(serializers.Serializer):
    TEST_TYPE = [(LabTest.RADIOLOGY, "Radiology"), (LabTest.PATHOLOGY, "Pathology")]
    test = serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all())
    start_date = serializers.DateTimeField(required=True)
    start_time = serializers.FloatField()
    type = serializers.ChoiceField(choices=TEST_TYPE)
    is_home_pickup = serializers.BooleanField(default=False)


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
    utm_spo_tags = serializers.JSONField(required=False, default={})
    app_version = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    prescription_list = serializers.ListSerializer(child=PrescriptionDocumentSerializer(), required=False)
    _source = serializers.CharField(required=False, allow_null=True)
    _responsible_user = serializers.IntegerField(required=False, allow_null=True)
    test_timings = serializers.ListSerializer(child=LabAppointmentTestSerializer(), required=False, allow_empty=False)
    multi_timings_enabled = serializers.BooleanField(required=False, default=False)
    selected_timings_type = serializers.ChoiceField(required=False, choices=(('common', 'common'), ('separate', 'separate')))
    utm_sbi_tags = serializers.JSONField(required=False, default={})
    plus_plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.objects.filter(is_live=True, is_gold=True), required=False)

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)
        if kwargs.get('context') and kwargs.get('context').get('data') and kwargs.get('context').get('data').get(
                'multi_timings_enabled'):
            self.fields.fields['start_date'].required = False
            self.fields.fields['start_time'].required = False
            self.fields.fields['is_home_pickup'].required = False
            self.fields.fields['test_timings'].required = True
            self.fields.fields['selected_timings_type'].required = True

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

        if data.get('multi_timings_enabled') and data.get('selected_timings_type') == 'common':
            if not data.get('test_timings'):
                raise serializers.ValidationError("Start date and start time not found")
            else:
                datetime_ist = dateutil.parser.parse(str(data.get('test_timings')[0].get('start_date')))
                data['start_date'] = datetime_ist.astimezone(tz=timezone.utc)#.isoformat()
                data['start_time'] = data.get('test_timings')[0].get('start_time')
                data['is_home_pickup'] = data.get('test_timings')[0].get('is_home_pickup')

        address_required = False
        if data.get('multi_timings_enabled'):
            for test_timing in data.get('test_timings'):
                if test_timing.get("is_home_pickup"):
                    address_required = True
                    break
        else:
            if data.get("is_home_pickup"):
                address_required = True

        if address_required:
            if data.get("address") is None:
                raise serializers.ValidationError("Address required for home pickup")
            elif not Address.objects.filter(id=data.get("address").id, user=request.user).exists():
                raise serializers.ValidationError("Invalid address for given user")
        else:
            data.pop("address", None)

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")

        # if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"], lab=data[
        #     "lab"]).exists():
        #     raise serializers.ValidationError("A previous appointment with this lab already exists. Cancel it before booking new Appointment.")

        if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"]).count() >= MAX_APPOINTMENTS_ALLOWED:
            raise serializers.ValidationError('Max '+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        if data.get("coupon_code"):
            profile = data.get("profile")
            coupon_codes = data.get("coupon_code", [])
            coupon_obj = RandomGeneratedCoupon.get_coupons(coupon_codes)

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

        lab = data.get("lab")
        pincode = data.get('pincode', None)
        address = data.get("address", None)
        check_active_appointment = True

        if bool(data.get("is_thyrocare")) :
            if not pincode:
                raise serializers.ValidationError("Pincode required for thyrocare.")
            if address and not (int(pincode) == int(address.pincode)):
                raise serializers.ValidationError("Entered pincode should be same as pickup address pincode.")

        has_pathology_timings = False
        has_radiology_timings = False
        pathology_time_slot_start = None
        pathology_slot_validated = False
        pathology_home_pickup = False
        if data.get('multi_timings_enabled'):
            test_timings = data.get('test_timings')
            for test_timing in test_timings:
                if test_timing.get('type') == LabTest.PATHOLOGY:
                    has_pathology_timings = True
                    if not pathology_time_slot_start:
                        pathology_time_slot_start = form_time_slot(test_timing.get('start_date'), test_timing.get('start_time'))
                        if not pathology_slot_validated:
                            params = dict()
                            params['is_integrated'] = lab.is_integrated()
                            params['is_home_pickup'] = test_timing.get("is_home_pickup")
                            params['start_date'] = test_timing.get('start_date')
                            params['start_time'] = test_timing.get('start_time')
                            params['lab'] = lab
                            self.pathology_time_slot_validator_v2(request, params)
                            pathology_slot_validated = True
                            pathology_home_pickup = test_timing.get('is_home_pickup')
                if test_timing.get('type') == LabTest.RADIOLOGY:
                    has_radiology_timings = True
                    time_slot_start = form_time_slot(test_timing.get('start_date'), test_timing.get('start_time'))
                    selected_date = time_slot_start.strftime("%Y-%m-%d")
                    curr_time = time_slot_start.hour
                    curr_minute = round(round(float(time_slot_start.minute) / 60, 2) * 2) / 2
                    curr_time += curr_minute

                    # radiology for each times
                    available_slots = lab.get_radiology_available_slots(test_timing.get('test'), test_timing.get("is_home_pickup"), pincode, selected_date)
                    # is_integrated = lab.is_integrated()
                    selected_day_slots = available_slots['time_slots'][selected_date]
                    if not selected_day_slots:
                        raise serializers.ValidationError("No time slots available")

                    current_day_slots = self.get_slots_list(selected_day_slots)

                    if not curr_time in current_day_slots:
                        raise serializers.ValidationError("Invalid Time slot")

                    params = dict()
                    params['is_integrated'] = lab.is_integrated()
                    params['is_home_pickup'] = test_timing.get("is_home_pickup")
                    params['start_date'] = test_timing.get('start_date')
                    params['start_time'] = test_timing.get('start_time')
                    params['test'] = test_timing.get('test')
                    params['lab'] = lab
                    self.radiology_time_slot_validator(request, params)
        else:
            has_pathology_timings = True
            pathology_home_pickup = data.get('is_home_pickup')
            pathology_time_slot_start = (form_time_slot(data.get('start_date'), data.get('start_time'))
                               if not data.get("time_slot_start") else data.get("time_slot_start"))

        if has_pathology_timings:
            selected_date = pathology_time_slot_start.strftime("%Y-%m-%d")
            now = datetime.datetime.now()
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            is_today = now.weekday() == pathology_time_slot_start.weekday()
            is_tomorrow = tomorrow.weekday() == pathology_time_slot_start.weekday()
            curr_time = pathology_time_slot_start.hour
            curr_minute = round(round(float(pathology_time_slot_start.minute) / 60, 2) * 2) / 2
            curr_time += curr_minute

            if bool(data.get('from_app')) and data.get('app_version') and parse(data.get('app_version')) < parse('1.2'):
                available_slots = LabTiming.timing_manager.lab_booking_slots(lab__id=data.get("lab").id,
                                                                             lab__is_live=True,
                                                                             for_home_pickup=pathology_home_pickup)
                is_integrated = False
                if is_today and available_slots.get("today_min") and available_slots.get("today_min") > curr_time:
                    raise serializers.ValidationError("Invalid Time slot")
                if is_tomorrow and available_slots.get("tomorrow_min") and available_slots.get(
                        "tomorrow_min") > curr_time:
                    raise serializers.ValidationError("Invalid Time slot")
                if is_today and available_slots.get("today_max") and available_slots.get("today_max") < curr_time:
                    raise serializers.ValidationError("Invalid Time slot")
            else:
                available_slots = lab.get_available_slots(pathology_home_pickup, pincode, selected_date)
                is_integrated = lab.is_integrated()
                selected_day_slots = available_slots.get('time_slots').get(selected_date)
                if not selected_day_slots:
                    raise serializers.ValidationError("No time slots available")

                current_day_slots = self.get_slots_list(selected_day_slots)

                if not curr_time in current_day_slots:
                    raise serializers.ValidationError("Invalid Time slot")

                if lab.network and lab.network.id == settings.THYROCARE_NETWORK_ID:
                    self.thyrocare_test_validator(data)
                    check_active_appointment = False

        if check_active_appointment:
            if data.get('multi_timings_enabled'):
                # user_active_appointments = LabAppointment.objects.prefetch_related('test_mappings').filter(profile=data.get("profile"),
                #                                                                 lab=data.get("lab")) \
                #         .exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED])
                # if user_active_appointments:
                #     # radiology_timings = list(filter(lambda x: x.get('type') == LabTest.RADIOLOGY), test_timings)
                #     for test_timing in test_timings:
                #         test_time_slot_start = form_time_slot(test_timing.get('start_date'), test_timing.get('start_time'))
                #         if user_active_appointments.filter(test_mappings__test_id=test_timing.get('test'),
                #                                            test_mappings__time_slot_start=test_time_slot_start).exists():
                #             raise serializers.ValidationError(
                #                 "One active appointment for the selected date & time already exists. Please change the date & time of the appointment.")

                for test_timing in test_timings:
                    test_time_slot_start = form_time_slot(test_timing.get('start_date'), test_timing.get('start_time'))
                    if LabAppointment.objects.filter(profile=data.get("profile"), lab=data.get("lab"),
                                                     tests__in=data.get("test_ids"),
                                                     time_slot_start=test_time_slot_start) \
                            .exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED]).exists():
                        raise serializers.ValidationError(
                            "One active appointment for the selected date & time already exists. Please change the date & time of the appointment.")
            else:
                if LabAppointment.objects.filter(profile=data.get("profile"), lab=data.get("lab"),
                                                 tests__in=data.get("test_ids"), time_slot_start=pathology_time_slot_start) \
                        .exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED]).exists():
                    raise serializers.ValidationError(
                        "One active appointment for the selected date & time already exists. Please change the date & time of the appointment.")

        if 'use_wallet' in data and data['use_wallet'] is False:
            data['use_wallet'] = False
        else:
            data['use_wallet'] = True

        self.test_lab_id_validator(data, request)
        if not data.get('multi_timings_enabled'):
            self.time_slot_validator(data, request, lab.is_integrated())
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
            # logger.error("Error 'Cannot book in past' for lab appointment with data - " + json.dumps(request.data))
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

    @staticmethod
    def pathology_time_slot_validator_v2(request, params):
        start_dt = (form_time_slot(params.get('start_date'), params.get('start_time')))

        if start_dt < timezone.now():
            # logger.error("Error 'Cannot book in past' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Cannot book in past")

        day_of_week = start_dt.weekday()

        lab_queryset = params.get('lab')

        lab_timing_queryset = lab_queryset.lab_timings.filter(day=day_of_week, start__lte=params.get('start_time'),
                                                              end__gte=params.get('start_time'),
                                                              for_home_pickup=params.get('is_home_pickup')).exists()
        if params.get('is_integrated'):
            pass
        else:
            if params.get('is_home_pickup'):
                if not lab_queryset.is_home_collection_enabled:
                    logger.error(
                        "Error 'Home Pickup is disabled for the lab' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("Home Pickup is disabled for the lab")
                if params.get("start_time") < 7.0 or params.get("start_time") > 19.0:
                    logger.error(
                        "Error 'No time slot available' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("No time slot available")
            else:
                if not lab_queryset.always_open and not lab_timing_queryset:
                    logger.error(
                        "Error 'No time slot available' for lab appointment with data - " + json.dumps(request.data))
                    raise serializers.ValidationError("No time slot available")

    @staticmethod
    def radiology_time_slot_validator(request, params):
        start_dt = (form_time_slot(params.get('start_date'), params.get('start_time')))

        if start_dt < timezone.now():
            # logger.error("Error 'Cannot book in past' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Cannot book in past")

        day_of_week = start_dt.weekday()

        lab_queryset = params.get('lab')
        if params.get('is_integrated'):
            pass
        else:
            if params.get('is_home_pickup'):
                if not lab_queryset.is_home_collection_enabled:
                    logger.error(
                        "Error 'Home Pickup is disabled for the lab' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("Home Pickup is disabled for the lab")
                if params.get("start_time") < 7.0 or params.get("start_time") > 19.0:
                    logger.error(
                        "Error 'No time slot available' for lab appointment with data - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("No time slot available")
            else:
                lab_test_group_mapping = LabTestGroupMapping.objects.filter(test=params.get('test')).first()
                if lab_test_group_mapping:
                    lab_test_group = LabTestGroup.objects.filter(id=lab_test_group_mapping.lab_test_group_id).first()

                    lab_test_group_timing = False
                    if lab_test_group:
                        lab_test_group_timing = lab_queryset.test_group_timings.filter(lab_test_group=lab_test_group.id,
                                                                                       day=day_of_week,
                                                                                       start__lte=params.get('start_time'),
                                                                                       end__gte=params.get('start_time'),
                                                                                       for_home_pickup=params.get('is_home_pickup')).exists()
                    else:
                        logger.error(
                            "Error: Mapping not found - " + json.dumps(
                                request.data))
                        raise serializers.ValidationError("Something went wrong.")

                    if not lab_queryset.always_open and not lab_test_group_timing:
                        logger.error(
                            "Error 'No time slot available' for lab appointment with data - " + json.dumps(request.data))
                        raise serializers.ValidationError("No time slot available")
                else:
                    logger.error(
                        "Error: Mapping not found - " + json.dumps(
                            request.data))
                    raise serializers.ValidationError("Something went wrong.")

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

        booked_test_ids = list(data.get("test_ids", None))
        if booked_test_ids:
            for test in booked_test_ids:
                integrator_test = IntegratorTestMapping.objects.filter(test_id=test, integrator_class_name='Thyrocare').first()
                if integrator_test and integrator_test.integrator_product_data['code'] == 'FBS':
                    self.fbs_valid(booked_test_ids, test)
                elif integrator_test and integrator_test.integrator_product_data['code'] in ['PPBS', 'RBS']:
                    self.ppbs_valid(booked_test_ids, test)
                elif integrator_test and integrator_test.integrator_product_data['code'] == 'INSPP':
                    self.inspp_valid(booked_test_ids, test)

    def fbs_valid(self, booked_test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(booked_test_ids) < 2:
            raise serializers.ValidationError("FBS can be added with any fasting test or package.")

        is_profile_or_fasting_added = False
        booked_test_ids.remove(test)
        if not booked_test_ids:
            pass

        for test in booked_test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST', integrator_class_name='Thyrocare').first()
            if integrator_test and integrator_test.integrator_product_data['fasting'] == 'CF':
                is_profile_or_fasting_added = True
            else:
                integrator_profile = IntegratorTestMapping.objects.filter(Q(test_id=test) & Q(integrator_class_name='Thyrocare') & ~Q(test_type='TEST')).first()
                if integrator_profile:
                    is_profile_or_fasting_added = True

        if is_profile_or_fasting_added:
            pass
        else:
            raise serializers.ValidationError("FBS can be added with any fasting test or package.")

    def ppbs_valid(self, booked_test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(booked_test_ids) < 3:
            raise serializers.ValidationError("PPBS or RBS can be added with FBS and one fasting test or package.")

        is_fbs_present = False
        is_profile_or_fasting_added = False
        booked_test_ids.remove(test)
        if not booked_test_ids:
            pass

        for test in booked_test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST', integrator_class_name='Thyrocare').first()
            if integrator_test and integrator_test.integrator_product_data['code'] == 'FBS':
                is_fbs_present = True
            elif integrator_test and integrator_test.integrator_product_data['fasting'] == 'CF':
                is_profile_or_fasting_added = True
            else:
                integrator_profile = IntegratorTestMapping.objects.filter(Q(test_id=test) & Q(integrator_class_name='Thyrocare') & ~Q(test_type='TEST')).first()
                if integrator_profile:
                    is_profile_or_fasting_added = True

        if is_fbs_present and is_profile_or_fasting_added:
            pass
        else:
            raise serializers.ValidationError("PPBS or RBS can be added with FBS and one fasting test or package.")

    def inspp_valid(self, booked_test_ids, test):
        from ondoc.integrations.models import IntegratorTestMapping
        if len(booked_test_ids) < 2:
            raise serializers.ValidationError("INSFA test is mandatory to book INSPP.")

        insfa_test_present = False
        booked_test_ids.remove(test)
        if not booked_test_ids:
            pass

        for test in booked_test_ids:
            integrator_test = IntegratorTestMapping.objects.filter(test_id=test, test_type='TEST', integrator_class_name='Thyrocare').first()
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
    SORT_ORDER = ('asc', 'desc')
    TODAY = 1
    TOMORROW = 2
    NEXT_3_DAYS = 3
    AVAILABILITY_CHOICES = ((TODAY, 'Today'), (TOMORROW, "Tomorrow"), (NEXT_3_DAYS, "Next 3 days"),)

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
    sort_order = serializers.ChoiceField(choices=SORT_ORDER, required=False)
    availability = CommaSepratedToListField(required=False, max_length=50, typecast_to=str)
    avg_ratings = CommaSepratedToListField(required=False, max_length=50, typecast_to=str)
    lab_visit = serializers.BooleanField(required=False)
    home_visit = serializers.BooleanField(required=False)

    def validate_availability(self, value):
        if not set(value).issubset(set([str(avl_choice[0]) for avl_choice in self.AVAILABILITY_CHOICES])):
            raise serializers.ValidationError("Not a Valid Availability Choice")
        return value


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
    selected_timings_type = serializers.SerializerMethodField()
    appointment_via_sbi = serializers.SerializerMethodField()
    gold = serializers.SerializerMethodField()
    user_referral_amt = serializers.SerializerMethodField()

    def get_user_referral_amt(self, obj):
        return UserConfig.get_referral_amount()

    def get_gold(self, obj):
        from ondoc.api.v1.plus.serializers import PlusUserModelSerializer
        request = self.context.get('request')
        data = {'is_gold': False, 'members': [], 'is_single_flow': False}

        plus_plan = obj.plus_plan
        if plus_plan:
            data['is_gold'] = plus_plan.plan.is_gold
            data['members'] = PlusUserModelSerializer(plus_plan, context={'request': request}).data

            appointment_order = Order.objects.filter(reference_id=obj.id).first()
            if appointment_order and appointment_order.single_booking:
                data['is_single_flow'] = True

        return data


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
            # reports.append({"details": rep.report_details, "files":[file.name.url for file in rep.files.all()]})
            reports.extend([file.name.url for file in rep.files.all()])
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

    def get_selected_timings_type(self, obj):
        selected_timings_type = None
        if obj.action_data:
            selected_timings_type = obj.action_data.get('selected_timings_type')

        return selected_timings_type

    def get_appointment_via_sbi(self, obj):
        sbi_appointment = False
        order = Order.objects.filter(reference_id=obj.id, product_id=2).first()
        if order and order.action_data.get('utm_sbi_tags', None):
            sbi_appointment = True

        return sbi_appointment

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price',
                  'time_slot_start', 'time_slot_end', 'selected_timings_type', 'is_rated', 'rating_declined', 'is_home_pickup', 'lab_thumbnail',
                  'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab', 'otp', 'address', 'type', 'reports',
                  'report_files', 'invoices', 'prescription', 'cancellation_reason', 'mask_data', 'payment_type',
                  'price', 'appointment_via_sbi', 'gold', 'user_referral_amt')


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
    source = serializers.CharField(required=False, allow_blank=True)

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
    is_thyrocare = serializers.SerializerMethodField()

    def get_is_thyrocare(self, obj):
        if obj and obj.network and obj.network.id == settings.THYROCARE_NETWORK_ID:
            return True
        return False

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'lab_thumbnail', 'name', 'operational_since', 'locality', 'address',
                  'sublocality', 'city', 'state', 'country', 'always_open', 'about', 'home_pickup_charges',
                  'is_home_collection_enabled', 'seo', 'breadcrumb', 'center_visit_enabled', 'avg_rating', 'url',
                  'city', 'network_id', 'is_thyrocare')

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
    vip = serializers.SerializerMethodField()


    class Meta:
        model = LabTest
        fields = ('id', 'name', 'lab', 'mrp', 'distance', 'price', 'lab_timing', 'lab_timing_data', 'next_lab_timing',
                  'next_lab_timing_data', 'test_type', 'is_package', 'number_of_tests', 'why', 'pre_test_info',
                  'is_package', 'pickup_charges', 'pickup_available', 'distance_related_charges', 'priority',
                  'show_details', 'categories', 'url', 'priority_score', 'category_details', 'tests', 'included_in_user_plan', 'insurance', 'vip')

    def get_insurance(self, obj):
        request = self.context.get("request")
        ins_threshold_amt = self.context.get("insurance_threshold_amount", None)
        resp = Lab.get_insurance_details(request.user, ins_threshold_amt)
        lab_data = self.context.get('lab_data', {})
        lab = lab_data.get(obj.lab, None)

        if obj and lab and lab.is_enabled_for_insurance and obj.mrp is not None and resp['insurance_threshold_amount'] is not None and obj.mrp <= resp['insurance_threshold_amount']:
            resp['is_insurance_covered'] = True

        return resp

    def get_vip(self, obj):
        request = self.context.get("request")
        search_criteria_query = self.context.get("search_criteria_query")
        resp = Lab.get_vip_details(request.user, search_criteria_query)
        lab_data = self.context.get('lab_data', {})
        lab = lab_data.get(obj.lab, None)

        resp['is_enable_for_vip'] = True if lab and lab.is_enabled_for_plus_plans() else False
        user = request.user
        plus_obj = None
        deal_price = 0
        agreed_price = 0
        mrp = 0
        avl_obj = None
        if lab:
            # avl_obj = None
            # if not self.context.get('avl_objs'):
            #     avl_obj = obj.availablelabs.filter(lab_pricing_group=lab.lab_pricing_group).first()
            # else:
            #     avl_objs = self.context.get('avl_objs')
            #     for av in avl_objs:
            #         if av.lab_pricing_group == lab.lab_pricing_group:
            #             avl_obj = av
            #             break
            avl_obj = obj.availablelabs.filter(lab_pricing_group=lab.lab_pricing_group).first()
            if avl_obj:
                mrp = avl_obj.mrp
                deal_price = avl_obj.custom_deal_price if avl_obj.custom_deal_price else avl_obj.computed_deal_price
                agreed_price = avl_obj.custom_agreed_price if avl_obj.custom_agreed_price else avl_obj.computed_agreed_price
        price_data = {"mrp": mrp, "deal_price": deal_price,
                      "cod_deal_price": deal_price,
                      "fees": agreed_price}

        if user and user.is_authenticated and not user.is_anonymous:
            plus_obj = user.active_plus_user if user.active_plus_user and user.active_plus_user.status == PlusUser.ACTIVE else None
        plan = plus_obj.plan if plus_obj else None
        resp['vip_gold_price'] = agreed_price
        default_plan_query = self.context.get('default_plan_query')
        resp['vip_convenience_amount'] = avl_obj.calculate_convenience_charge(plan) if avl_obj else 0
        # resp['vip_convenience_amount'] = PlusPlans.get_default_convenience_amount(agreed_price, "LABTEST", default_plan_query)
        if not plus_obj:
            return resp
        resp['is_gold_member'] = True if plus_obj.plan.is_gold else False
        entity = "LABTEST" if not obj.is_package else "PACKAGE"

        price_engine = get_price_reference(plus_obj, "LABTEST")
        if not price_engine:
            price = mrp
        else:
            price = price_engine.get_price(price_data)
        engine = get_class_reference(plus_obj, entity)
        if not engine:
            return resp

        if engine and obj and mrp and lab and lab.is_enabled_for_plus_plans():
            # resp['vip_convenience_amount'] = user.active_plus_user.plan.get_convenience_charge(price, "LABTEST")
            resp['vip_convenience_amount'] = avl_obj.calculate_convenience_charge(plan) if avl_obj else 0
            # engine_response = engine.validate_booking_entity(cost=obj.mrp, id=obj.id)
            engine_response = engine.validate_booking_entity(cost=price, id=obj.id, mrp=mrp, deal_price=deal_price, price_engine_price=price)
            resp['covered_under_vip'] = engine_response['is_covered']
            resp['vip_amount'] = engine_response['amount_to_be_paid']

        return resp

        # if plus_obj and lab and obj and lab.enabled_for_plus_plans and obj.mrp:
        #     utilization_criteria, can_be_utilized = plus_obj.can_package_be_covered_in_vip(obj)
        #     if can_be_utilized:
        #         resp['covered_under_vip'] = True
        #     else:
        #         return resp
        #
        #     if utilization_criteria == UtilizationCriteria.COUNT:
        #         resp['vip_amount'] = 0
        #     else:
        #         if obj.mrp <= package_amount_balance:
        #             resp['vip_amount'] = 0
        #         else:
        #             resp['vip_amount'] = obj.mrp - package_amount_balance
        #
        # return resp

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
            categories_count = len(temp_test.categories.all())
            return_data.append({'id': test_id, 'name': name, 'parameter_count': parameter_count, 'categories': categories_count})
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
        return int(obj.distance)

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
    SORT_ORDER = ('asc', 'desc')
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
    sort_order = serializers.ChoiceField(choices=SORT_ORDER, required=False)
    home_visit = serializers.BooleanField(default=False)
    lab_visit = serializers.BooleanField(default=False)
    avg_ratings = CommaSepratedToListField(required=False, max_length=500, typecast_to=int)

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


class PackageLabCompareRequestSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.filter(is_package=True, enable_for_retail=True))
    lab_id = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))

    def validate(self, attrs):
        attrs['package'] = attrs['package_id']
        attrs['lab'] = attrs['lab_id']
        if not AvailableLabTest.objects.filter(lab_pricing_group__labs=attrs.get('lab'), test=attrs.get('package'),
                                               enabled=True).exists():
            raise serializers.ValidationError('Package is not available in the lab.')
        return attrs


class CompareLabPackagesSerializer(serializers.Serializer):
    package_lab_ids = serializers.ListField(child=PackageLabCompareRequestSerializer(), min_length=1, max_length=5)
    long = serializers.FloatField(default=77.071848)
    lat = serializers.FloatField(default=28.450367)
    title = serializers.CharField(required=False, max_length=500)
    category = serializers.PrimaryKeyRelatedField(queryset=LabTestCategory.objects.all(), required=False,
                                                  allow_null=True)


class LabTestPrescriptionSerializer(serializers.Serializer):
    file = serializers.FileField()

