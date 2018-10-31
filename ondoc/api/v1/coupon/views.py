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

        obj = CouponsMixin()
        if not product_id:
            coupons_data = Coupon.objects.all()
        elif product_id in [Order.LAB_PRODUCT_ID, Order.DOCTOR_PRODUCT_ID]:
            if product_id == Order.DOCTOR_PRODUCT_ID:
                coupons_data = Coupon.objects.filter(type__in=[Coupon.DOCTOR, Coupon.ALL])
                obj = OpdAppointment()
            elif product_id == Order.LAB_PRODUCT_ID:
                coupons_data = Coupon.objects.filter(type__in=[Coupon.LAB, Coupon.ALL])
                obj = LabAppointment()
        else:
            return Response({"status": 0, "message": "Invalid Product ID"}, status.HTTP_404_NOT_FOUND)

        if request.user.is_authenticated:
            user = request.user
            is_user = True
        else:
            is_user = False

        applicable_coupons = []

        for coupon in coupons_data:

            if is_user:
                is_valid_user_coupon = obj.validate_user_coupon(user=user, coupon_obj=coupon)
            elif not is_user and coupon.is_user_specific:
                continue
            else:
                is_valid_user_coupon = {"is_valid": None, "used_count": 0}

            if (is_user and is_valid_user_coupon.get("is_valid")) or not is_user:
                applicable_coupons.append({"coupon_type": coupon.type,
                                           "coupon_id": coupon.id,
                                           "code": coupon.code,
                                           "desc": coupon.description,
                                           "coupon_count": coupon.count,
                                           "used_count": is_valid_user_coupon.get("used_count"),
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
