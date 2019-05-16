from ondoc.cart.models import Cart
from ondoc.coupon.models import Coupon, RandomGeneratedCoupon, UserSpecificCoupon, CouponRecommender
from ondoc.account.models import Order
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment, AvailableLabTest, LabTest
from ondoc.authentication import models as auth_models
from ondoc.api.v1.utils import CouponsMixin
from ondoc.api.v1.coupon import serializers as coupon_serializers
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from ondoc.authentication.backends import JWTAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework import status
from django.db import transaction
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DateTimeField
from django.forms.models import model_to_dict
from . import serializers
from django.conf import settings
import requests, re, json
import sys
from django.utils import timezone
from django.db.models import Prefetch
import datetime

User = get_user_model()


class ApplicableCouponsViewSet(viewsets.GenericViewSet):

    queryset=Coupon.objects.all()

#    def list(self, request, *args, **kwargs):
#        serializer = serializers.ProductIDSerializer(data=request.query_params)
#        serializer.is_valid(raise_exception=True)
#        input_data = serializer.validated_data

#        product_id = input_data.get("product_id")
#        lab = input_data.get("lab_id", None)
#        tests = input_data.get("tests", [])
#        procedures = input_data.get("procedures", [])
#        doctor = input_data.get("doctor_id", None)
#        hospital = input_data.get("hospital_id", None)
#        deal_price = input_data.get("deal_price")
#        coupon_code = input_data.get("coupon_code")
#        profile = input_data.get("profile_id", None)
#        cart_item_id = input_data.get('cart_item').id if input_data.get('cart_item') else None
#        show_all = input_data.get('show_all', False)

#        types = []
#        if deal_price==0:
#            deal_price=None

 #       if (product_id and product_id == Order.DOCTOR_PRODUCT_ID) or doctor:
 #           types = [Coupon.ALL, Coupon.DOCTOR]
 #       elif (product_id and product_id == Order.LAB_PRODUCT_ID) or lab:
 #           types = [Coupon.ALL, Coupon.LAB]
 #       else:
 #           types = [Coupon.ALL, Coupon.DOCTOR, Coupon.LAB]


 #       user = request.user
 #       if not user.is_authenticated:
 #           user = None

#        coupons = Coupon.objects.filter(type__in=types)

#        if deal_price:
#            coupons = coupons.filter(Q(min_order_amount__isnull=True) | Q(min_order_amount__lte = deal_price))

        # check if request is made to fetch a specific coupon, if not only return visible coupons
#        if coupon_code:
#            coupons = RandomGeneratedCoupon.get_coupons([coupon_code])
#            # coupons = coupons.filter(code__iexact=coupon_code)
#        else:
#            coupons = coupons.filter(is_visible=True)

#        if user and user.is_authenticated:
#            coupons = coupons.filter(Q(is_user_specific=False) \
#                | (Q(is_user_specific=True) & Q(user_specific_coupon__user=user)))

#            # expression = F('sent_at') + datetime.timedelta(days=1) * F('validity')
#            #
#            # annotate_expression = ExpressionWrapper(expression, DateTimeField())
#            # coupons = coupons.prefetch_related(Prefetch('random_generated_coupon',
#            #                           queryset=RandomGeneratedCoupon.objects.annotate(last_date=annotate_expression)
#            #                           .filter(user=user,
#            #                                   sent_at__isnull=False,
#            #                                   consumed_at__isnull=True,
#            #                                   last_date__gte=datetime.datetime.now())))

#            if profile:
#                if profile.gender:
#                    coupons = coupons.filter(Q(gender__isnull=True) | Q(gender=profile.gender))
#                else:
#                    coupons = coupons.filter(gender__isnull=True)

#                #TODO age defaults
#                user_age = profile.get_age()
#                if user_age:
#                    coupons = coupons.filter(Q(age_start__isnull=True, age_end__isnull=True)
#                                             | Q(age_start__lte=user_age, age_end__gte=user_age))
#                else:
#                    coupons = coupons.filter(age_start__isnull=True, age_end__isnull=True)
#            else:
#                coupons = coupons.filter(gender__isnull=True)
#                coupons = coupons.filter(age_start__isnull=True, age_end__isnull=True)
#        else:
#            coupons = coupons.filter(is_user_specific=False)

#        if product_id:
#            if tests:
#                coupons = coupons.filter(Q(test__isnull=True) | Q(test__in=tests))
#                test_categories = set(tests.values_list('categories', flat=True))
#                coupons = coupons.filter(Q(test_categories__isnull=True) | Q(test_categories__in=test_categories))
#            else:
#                coupons = coupons.filter(test__isnull=True)
#                coupons = coupons.filter(test_categories__isnull=True)

#            if lab:
#                coupons = coupons.filter(Q(cities__isnull=True) | Q(cities__icontains=lab.city))
#            else:
#                coupons = coupons.filter(cities__isnull=True)

#            if hospital:
#                coupons = coupons.filter(Q(hospitals__isnull=True) | Q(hospitals=hospital))
#                coupons = coupons.filter(Q(cities__isnull=True) | Q(cities__icontains=hospital.city))
#            else:
#                coupons = coupons.filter(hospitals__isnull=True)
#                coupons = coupons.filter(cities__isnull=True)

#            if doctor:
#                coupons = coupons.filter(Q(doctors__isnull=True) | Q(doctors=doctor))
#                coupons = coupons.filter(Q(specializations__isnull=True)
#                                         | Q(specializations__in=
#                                           doctor.doctorpracticespecializations.values_list('specialization', flat=True))
#                                         )
#            else:
#                coupons = coupons.filter(doctors__isnull=True)
#                coupons = coupons.filter(specializations__isnull=True)

#            if procedures:
#                coupons = coupons.filter(Q(procedures__isnull=True) | Q(procedures__in=procedures))
#                procedure_categories = set(procedures.values_list('categories', flat=True))
#                coupons = coupons.filter(Q(procedure_categories__isnull=True) | Q(procedure_categories__in=procedure_categories))
#            else:
#                coupons = coupons.filter(procedures__isnull=True)
#                coupons = coupons.filter(procedure_categories__isnull=True)

#        if product_id:
#            coupons = coupons.filter(is_corporate=False)
#        else:
#            coupons = coupons.order_by("is_corporate")


#        total_opd_booked = Prefetch('opd_appointment_coupon', \
#                                  queryset=OpdAppointment.objects.exclude(status__in=[OpdAppointment.CANCELLED]), \
#                                  to_attr='total_opd_booked')

#        user_opd_booked = Prefetch('opd_appointment_coupon', \
#                                  queryset=OpdAppointment.objects.filter(user=user).exclude(status__in=[OpdAppointment.CANCELLED]), \
#                                  to_attr='user_opd_booked')


#        total_lab_booked = Prefetch('lab_appointment_coupon', \
#                                  queryset=LabAppointment.objects.exclude(status__in=[LabAppointment.CANCELLED]), \
#                                  to_attr='total_lab_booked')

#        user_lab_booked = Prefetch('lab_appointment_coupon', \
#                                  queryset=LabAppointment.objects.filter(user=user).exclude(status__in=[LabAppointment.CANCELLED]), \
#                                  to_attr='user_lab_booked')

#        # TODO
#        # user_opd_completed = OpdAppointment.objects.filter(user=user, status__in=[OpdAppointment.COMPLETED]).count()
#        #
#        # user_lab_completed = LabAppointment.objects.filter(user=user, status__in=[LabAppointment.COMPLETED]).count()

#        coupons = coupons.prefetch_related('user_specific_coupon', 'lab', 'test', total_opd_booked, user_opd_booked, total_lab_booked, user_lab_booked)
#        # coupons = coupons.prefetch_related('lab_network', 'lab', 'test', 'test_categories',
#        #                                    'specializations', 'procedures', 'procedure_categories',
#        #                                    total_opd_booked, user_opd_booked, total_lab_booked, user_lab_booked)
#        coupons = coupons.distinct()

#        payment_option_filter = None
#        if user and user.is_authenticated:
#            payment_option_filter = Cart.get_pg_if_pgcoupon(user, cart_item_id)

#        obj = OpdAppointment()
#        is_first_time_user = True
#        if user:
#            is_first_time_user = obj.is_user_first_time(user)

#        applicable_coupons = []
#        for coupon in coupons:
#            allowed = True
#            valid = True
#            invalidating_message = ""

#            if coupon.total_count and len(coupon.total_opd_booked) \
#                + len(coupon.total_lab_booked) >= coupon.total_count:
#                allowed = False
#                valid = False


#            cart_count = Cart.objects.filter(user=user, deleted_at__isnull=True, data__coupon_code__contains=coupon.code).exclude(id=cart_item_id).count()
#            coupon.cart_count = cart_count
#            if coupon.count and (len(coupon.user_opd_booked) + len(coupon.user_lab_booked) + coupon.cart_count) \
#                    >= coupon.count:
#                allowed = True and show_all
#                valid = False
#                invalidating_message = "Coupon can only be used " + str(coupon.count) + " times per user."

#            if payment_option_filter and coupon.payment_option and coupon.payment_option.id != payment_option_filter.id:
#                allowed = True and show_all
#                valid = False
#                invalidating_message = "2 payment gateway coupons cannot be used in the same transaction."

#            # TODO
#            # if ((user_opd_completed + user_lab_completed + 1) % coupon.step_count != 0 ):
#            #     allowed = False

#            if coupon.start_date and coupon.start_date>timezone.now() \
#                or (coupon.start_date + datetime.timedelta(days=coupon.validity))<timezone.now():
#                allowed = False
#                valid = False

#            if coupon.new_user_constraint and not is_first_time_user:
#                allowed = False
#                valid = False

#            if coupon.is_user_specific and user:
#                if coupon.user_specific_coupon.exists():
#                    user_specefic = coupon.user_specific_coupon.filter(user=user).first()
#                    if user_specefic and (len(coupon.user_opd_booked)+len(coupon.user_lab_booked)) >= user_specefic.count:
#                        allowed = False
#                        valid = False

#            # is coupon lab specific
#            if coupon.lab and lab and coupon.lab != lab:
#                allowed = False
#                valid = False

#            # is coupon specific to a network
#            if coupon.lab_network and lab and coupon.lab_network != lab.network:
#                allowed = False
#                valid = False

#            is_random_generated = False
#            random_coupon_code = None
#            if hasattr(coupon, 'is_random') and coupon.is_random:
#                is_random_generated = True
#                random_coupon_code = coupon.random_coupon_code
#                random_count = coupon.random_coupon_used_count(user, coupon.random_coupon_code, cart_item_id)
#                if random_count > 0:
#                    allowed = False
#                    valid = False

#            if allowed:
#                applicable_coupons.append({
#                            "is_random_generated": is_random_generated,
#                            "random_coupon_code": random_coupon_code,
#                            "valid": valid,
#                            "invalidating_message": invalidating_message,
#                            "coupon_type": coupon.type,
#                            "coupon_id": coupon.id,
#                            "code": random_coupon_code or coupon.code,
#                            "desc": coupon.description,
#                            "coupon_count": coupon.count,
#                            "used_count": len(coupon.user_opd_booked)+len(coupon.user_lab_booked)+coupon.cart_count,
#                            "coupon": coupon,
#                            "heading": coupon.heading,
#                            "is_corporate" : coupon.is_corporate,
#                            "tests": [ test.id for test in coupon.test.all() ],
#                            "network_id": coupon.lab_network.id if coupon.lab_network else None,
#                            "is_cashback": coupon.coupon_type == Coupon.CASHBACK,
#                            "tnc": coupon.tnc})
#                if user:
#                    pass
#                    # for random_coupon in coupon.random_generated_coupon.all():
#                    #     applicable_coupons.append({"is_random_generated": True,
#                    #            "valid": valid,
#                    #            "invalidating_message": invalidating_message,
#                    #             "coupon_type": coupon.type,
#                    #             "random_coupon_id": random_coupon.id,
#                    #             "coupon_id": coupon.id,
#                    #             "random_code": random_coupon.random_coupon,
#                    #             "code": coupon.code,
#                    #             "desc": coupon.description,
#                    #             "coupon_count": 1,
#                    #             "used_count": 0,
#                    #             "coupon": coupon,
#                    #             "heading": coupon.heading,
#                    #             "is_corporate": coupon.is_corporate,
#                    #             "tests": [test.id for test in coupon.test.all()],
#                    #             "network_id": coupon.lab_network.id if coupon.lab_network else None,
#                    #             "tnc": coupon.tnc})


#        if applicable_coupons:
#            def compare_coupon(coupon):
#                obj = CouponsMixin()
#                deal_price = input_data.get("deal_price", None)
#                deal_price = deal_price if deal_price is not None else sys.maxsize
#                discount = obj.get_discount(coupon["coupon"], deal_price)
#                return ( 1 if coupon["is_corporate"] else 0 , discount )

#            def filter_coupon(coupon):
#                obj = CouponsMixin()
#                deal_price = input_data.get("deal_price", None)
#                if deal_price:
#                    discount = obj.get_discount(coupon["coupon"], deal_price)
#                    return discount > 0
#                return True

#            # sort coupons on discount granted
#            applicable_coupons = sorted(applicable_coupons, key=compare_coupon, reverse=True)
#            # filter if no discount is offered
#            applicable_coupons = list(filter(filter_coupon, applicable_coupons))

#            def remove_coupon_data(c):
#                c.pop('coupon')
#                if c.get("payment_option"):
#                    c["payment_option"]["image"] = request.build_absolute_uri(c["payment_option"]["image"].url)
#                return c
#            applicable_coupons = list(map(remove_coupon_data, applicable_coupons))

#        return Response(applicable_coupons)

    def list_v2(self, request, *args, **kwargs):
        serializer = serializers.ProductIDSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data

        product_id = input_data.get("product_id")
        lab = input_data.get("lab_id", None)
        tests = input_data.get("tests", [])
        procedures = input_data.get("procedures", [])
        doctor = input_data.get("doctor_id", None)
        hospital = input_data.get("hospital_id", None)
        deal_price = input_data.get("deal_price")
        coupon_code = input_data.get("coupon_code")
        profile = input_data.get("profile_id", None)
        cart_item_id = input_data.get('cart_item').id if input_data.get('cart_item') else None
        show_all = input_data.get('show_all', False)

        coupon_type = 'both'

        if (product_id and product_id == Order.DOCTOR_PRODUCT_ID) or doctor:
            coupon_type = 'doctor'
        elif (product_id and product_id == Order.LAB_PRODUCT_ID) or lab:
            coupon_type = 'lab'

        if deal_price==0:
            deal_price=None

        coupon_recommender = CouponRecommender(request.user, profile, coupon_type, product_id, coupon_code, cart_item_id)
        filters = dict()

        if lab:
            filters['lab'] = dict()
            lab_obj = filters['lab']
            lab_obj['id'] = lab.id
            lab_obj['network_id'] = lab.network_id
            lab_obj['city'] = lab.city
        if doctor:
            doctor_specializations = []
            for dps in doctor.doctorpracticespecializations.all():
                doctor_specializations.append(dps.specialization_id)
            filters['doctor_id'] = doctor.id
            filters['doctor_specializations_ids'] = doctor_specializations
        filters['tests'] = tests
        filters['hospital'] = hospital
        filters['deal_price'] = deal_price
        filters['procedures_ids'] = procedures
        filters['show_all'] = show_all

        coupons = coupon_recommender.applicable_coupons(**filters)
        applicable_coupons = []

        for coupon in coupons:
            coupon_property = coupon_recommender.get_coupon_properties(coupon.code)
            applicable_coupons.append({"is_random_generated": coupon_property.get('is_random_generated', False),
                                       "random_coupon_code": coupon_property.get('random_coupon_code', ""),
                                       "valid": coupon_property.get('valid', True),
                                       "invalidating_message": coupon_property.get('invalidating_message', ''),
                                       "coupon_type": coupon.type,
                                       "coupon_id": coupon.id,
                                       "code": coupon_property.get('random_coupon_code', False) or coupon.code,
                                       "desc": coupon.description,
                                       "coupon_count": coupon.count,
                                       "used_count": coupon_property.get('used_count', 0),
                                       "heading": coupon.heading,
                                       "is_corporate" : coupon.is_corporate,
                                       "tests": [test.id for test in coupon.test.all()],
                                       "network_id": coupon.lab_network.id if coupon.lab_network else None,
                                       "is_cashback": coupon.coupon_type == Coupon.CASHBACK,
                                       "tnc": coupon.tnc
                                       })

            # if request.user:
            #     for random_coupon in coupon.random_generated_coupon.all():
            #         applicable_coupons.append({"is_random_generated": True,
            #                "valid": coupon_property.get('valid', True),
            #                "invalidating_message": coupon_property.get('invalidating_message', ''),
            #                 "coupon_type": coupon.type,
            #                 "random_coupon_id": random_coupon.id,
            #                 "coupon_id": coupon.id,
            #                 "random_code": random_coupon.random_coupon,
            #                 "code": coupon.code,
            #                 "desc": coupon.description,
            #                 "coupon_count": 1,
            #                 "used_count": 0,
            #                 "coupon": coupon,
            #                 "heading": coupon.heading,
            #                 "is_corporate": coupon.is_corporate,
            #                 "tests": [test.id for test in coupon.test.all()],
            #                 "network_id": coupon.lab_network.id if coupon.lab_network else None,
            #                 "tnc": coupon.tnc})
        return Response(applicable_coupons)


class CouponDiscountViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    #permission_classes = (IsAuthenticated,)

    def coupon_discount(self, request, *args, **kwargs):

        serializer = serializers.UserSpecificCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data

        coupons_data = input_data.get("coupons_data")
        deal_price = input_data.get("deal_price")
        product_id = input_data.get("product_id")
        lab = input_data.get("lab")
        tests = input_data.get("tests", [])
        doctor = input_data.get("doctor")
        hospital = input_data.get("hospital")
        procedures = input_data.get("procedures", [])
        profile = input_data.get("profile")
        cart_item_id = input_data.get('cart_item').id if input_data.get('cart_item') else None

        if str(product_id) == str(Order.DOCTOR_PRODUCT_ID):
            obj = OpdAppointment()
        elif str(product_id) == str(Order.LAB_PRODUCT_ID):
            obj = LabAppointment()

        discount = 0

        for coupon in coupons_data:
            if obj.validate_user_coupon(cart_item=cart_item_id, user=request.user, coupon_obj=coupon,
                                        profile=profile).get("is_valid"):
                if lab and tests:
                    total_price = obj.get_applicable_tests_with_total_price(coupon_obj=coupon,
                                                                            test_ids=tests, lab=lab).get("total_price")
                    discount += obj.get_discount(coupon, total_price)
                    continue
                if doctor and hospital and procedures:
                    total_price = obj.get_applicable_procedures_with_total_price(coupon_obj=coupon, doctor=doctor,
                                                                                 hospital=hospital, procedures=procedures).get("total_price")
                    discount += obj.get_discount(coupon, total_price)
                    continue
                discount += obj.get_discount(coupon, deal_price)
            else:
                return Response({"status": 0, "message": "Invalid coupon code for the user"},
                                status.HTTP_404_NOT_FOUND)

        return Response({"discount": discount, "status": 1}, status.HTTP_200_OK)
