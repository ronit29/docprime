from ondoc.coupon.models import Coupon
from ondoc.account.models import Order
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
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

User = get_user_model()


class ApplicableCouponsViewSet(viewsets.GenericViewSet):

    def list(self, request, *args, **kwargs):

        serializer = serializers.ProductIDSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data
        product_id = input_data.get("product_id")

        lab_id = input_data.get("lab_id", None)
        test_ids = input_data.get("test_ids", [])

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
                .annotate(opd_used_count=Count('opd_appointment_coupon', filter=(Q(opd_appointment_coupon__user=user) & ~Q(opd_appointment_coupon__status__in=[OpdAppointment.CANCELLED]))),
                          lab_used_count=Count('lab_appointment_coupon', filter=(Q(lab_appointment_coupon__user=user) & ~Q(lab_appointment_coupon__status__in=[LabAppointment.CANCELLED]))))\
                .filter(coupon_qs).prefetch_related('lab_appointment_coupon', 'opd_appointment_coupon')

            if product_id and product_id == Order.LAB_PRODUCT_ID:
                lab_qs = Q(lab_id=lab_id)
                if test_ids:
                    lab_qs = lab_qs & Q(test__in=test_ids)
                lab_qs = lab_qs | ( Q(lab_network= F("lab__network_id")) )
                coupons_data = coupons_data.filter(lab_qs)
        else:
            coupons_data = Coupon.objects.filter(coupon_qs)

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
                                           "tnc": coupon.tnc})

        return Response(applicable_coupons)


class CouponDiscountViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def coupon_discount(self, request, *args, **kwargs):

        serializer = serializers.UserSpecificCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data

        coupon_code = set(input_data.get("coupon_code"))
        deal_price = input_data.get("deal_price")
        product_id = input_data.get("product_id")
        lab = input_data.get("lab")
        test = input_data.get("test")

        if str(product_id) == str(Order.DOCTOR_PRODUCT_ID):
            obj = OpdAppointment()
        elif str(product_id) == str(Order.LAB_PRODUCT_ID):
            obj = LabAppointment()

        coupon_obj = Coupon.objects.filter(code__in=coupon_code)

        discount = 0
        if coupon_obj.count() == len(coupon_code):
            for coupon in coupon_obj:
                if obj.validate_user_coupon(user=request.user, coupon_obj=coupon).get("is_valid"):
                    if coupon.is_user_specific:
                        if not obj.validate_product_coupon(coupon_obj=coupon, lab=lab, test=test, product_id=product_id):
                            return Response({"status": 0, "message": "Invalid coupon code for the user"},
                                            status.HTTP_404_NOT_FOUND)
                    discount += obj.get_discount(coupon, deal_price)
                else:
                    return Response({"status": 0, "message": "Invalid coupon code for the user"},
                                    status.HTTP_404_NOT_FOUND)
        else:
            return Response({"status": 0, "message": "Invalid coupon code for the user"},
                            status.HTTP_404_NOT_FOUND)
        return Response({"discount": discount, "status": 1}, status.HTTP_200_OK)
