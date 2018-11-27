from ondoc.coupon.models import Coupon
from ondoc.account.models import Order
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment, AvailableLabTest
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
from django.db.models import Q, Sum, Count, F
from . import serializers
from django.conf import settings
import requests, re, json
import sys

User = get_user_model()


class ApplicableCouponsViewSet(viewsets.GenericViewSet):

    def list(self, request, *args, **kwargs):

        serializer = serializers.ProductIDSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data
        product_id = input_data.get("product_id")

        lab = input_data.get("lab_id", None)
        test_ids = input_data.get("test_ids", [])

        # types - gives types of coupon to pick in queryset
        if product_id and product_id == Order.DOCTOR_PRODUCT_ID:
            types = [Coupon.ALL, Coupon.DOCTOR]
        elif product_id and product_id == Order.LAB_PRODUCT_ID:
            types = [Coupon.ALL, Coupon.LAB]
        else:
            types = [Coupon.ALL, Coupon.DOCTOR, Coupon.LAB]
        coupon_qs = (Q(is_user_specific=False) & Q(type__in=types))

        if request.user.is_authenticated:
            user = request.user
            coupon_qs = coupon_qs | (Q(is_user_specific=True) & Q(user_specific_coupon__user=user) & Q(type__in=types))

            coupons_data = Coupon.objects\
                .select_related('lab_network')\
                .annotate(opd_used_count=Count('opd_appointment_coupon', filter=(Q(opd_appointment_coupon__user=user) & ~Q(opd_appointment_coupon__status__in=[OpdAppointment.CANCELLED])), distinct=True),
                          lab_used_count=Count('lab_appointment_coupon', filter=(Q(lab_appointment_coupon__user=user) & ~Q(lab_appointment_coupon__status__in=[LabAppointment.CANCELLED])), distinct=True))\
                .filter(coupon_qs).prefetch_related('lab_appointment_coupon', 'opd_appointment_coupon', 'test')
        else:
            coupons_data = Coupon.objects.filter(coupon_qs)

        if product_id and product_id == Order.LAB_PRODUCT_ID and lab:
            lab_qs = Q(lab=lab)
            if test_ids:
                lab_qs = lab_qs & (Q(test__in=test_ids, lab=lab) | Q(test__isnull=True, lab=lab)) | (Q(lab_network=lab.network, lab__isnull=True, test__in=test_ids))

            lab_qs = lab_qs |   Q(lab_network=lab.network, lab=lab) | \
                                Q(lab_network=lab.network, lab__isnull=True, test__isnull=True) | \
                                Q(lab__isnull=True, lab_network__isnull=True)
            coupons_data = coupons_data.filter(lab_qs)

        if product_id:
            coupons_data = coupons_data.filter(is_corporate=False)
        else:
            coupons_data = coupons_data.order_by("is_corporate")


        applicable_coupons = []
        for coupon in coupons_data:
            used_count = 0
            if hasattr(coupon, "opd_used_count") and hasattr(coupon, "lab_used_count"):
                used_count = coupon.opd_used_count + coupon.lab_used_count

            if used_count < coupon.count:
                applicable_coupons.append({"coupon_type": coupon.type,
                                           "coupon_id": coupon.id,
                                           "code": coupon.code,
                                           "desc": coupon.description,
                                           "coupon_count": coupon.count,
                                           "used_count": used_count,
                                           "coupon": coupon,
                                           "heading": coupon.heading,
                                           "is_corporate" : coupon.is_corporate,
                                           "tests": [ test.id for test in coupon.test.all() ],
                                           "network_id": coupon.lab_network.id if coupon.lab_network else None,
                                           "tnc": coupon.tnc})


        # sort coupons on discount granted
        if applicable_coupons:
            def compare_coupon(coupon):
                obj = CouponsMixin()
                deal_price = input_data.get("deal_price", None)
                deal_price = deal_price if deal_price is not None else sys.maxsize
                discount = obj.get_discount(coupon["coupon"], deal_price)
                return ( 1 if coupon["is_corporate"] else 0 , discount )
            applicable_coupons = sorted(applicable_coupons, key=compare_coupon, reverse=True)

        def remove_coupon_data(c):
            c.pop('coupon')
            return c
        applicable_coupons = list(map(remove_coupon_data ,applicable_coupons))

        return Response(applicable_coupons)


class CouponDiscountViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

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

        if str(product_id) == str(Order.DOCTOR_PRODUCT_ID):
            obj = OpdAppointment()
        elif str(product_id) == str(Order.LAB_PRODUCT_ID):
            obj = LabAppointment()

        discount = 0

        for coupon in coupons_data:
            if obj.validate_user_coupon(user=request.user, coupon_obj=coupon).get("is_valid"):
                if lab and tests:
                    tests = AvailableLabTest.objects.filter(lab_pricing_group__labs=lab, test__in=tests)
                    total_price = obj.get_applicable_tests_with_total_price(coupon_obj=coupon,
                                                                            lab_test_queryset=tests).get("total_price")
                    discount += obj.get_discount(coupon, total_price)
                    continue
                if doctor:
                    pass
                discount += obj.get_discount(coupon, deal_price)
            else:
                return Response({"status": 0, "message": "Invalid coupon code for the user"},
                                status.HTTP_404_NOT_FOUND)

        return Response({"discount": discount, "status": 1}, status.HTTP_200_OK)
