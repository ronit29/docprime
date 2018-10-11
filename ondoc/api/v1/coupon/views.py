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

        product_id = request.query_params.get("product_id")
        product_id = int(product_id) if product_id else None

        if not product_id:
            coupons_data = Coupon.objects.all()
        elif product_id in [Order.LAB_PRODUCT_ID, Order.DOCTOR_PRODUCT_ID]:
            if product_id == Order.DOCTOR_PRODUCT_ID:
                coupons_data = Coupon.objects.filter(type__in=[Coupon.DOCTOR, Coupon.ALL])
            elif product_id == Order.LAB_PRODUCT_ID:
                coupons_data = Coupon.objects.filter(type__in=[Coupon.LAB, Coupon.ALL])
        else:
            return Response({"status": 0, "message": "Invalid Product ID"}, status.HTTP_404_NOT_FOUND)

        if request.user.is_authenticated:
            user = request.user
            is_user = True
        else:
            is_user = False

        applicable_coupons = []
        obj = CouponsMixin()
        for coupon in coupons_data:
            if (is_user and obj.validate_coupon(user, coupon.code)) or not is_user:
                applicable_coupons.append({"product_id": product_id,
                                           "coupon_id": coupon.id,
                                           "code": coupon.code,
                                           "desc": coupon.description,
                                           "count": coupon.count - coupon.used_coupon_count(user)})
        return Response(applicable_coupons)


class CouponDiscountViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def coupon_discount(self, request, *args, **kwargs):
        input_data = request.data
        coupon_code = input_data.get("coupon_code")
        deal_price = input_data.get("deal_price")
        product_id = input_data.get("product_id")

        obj = None
        if str(product_id) == str(Order.DOCTOR_PRODUCT_ID):
            obj = OpdAppointment()
        elif str(product_id) == str(Order.LAB_PRODUCT_ID):
            obj = LabAppointment()
        if obj:
            discount = 0
            if coupon_code:
                for coupon in coupon_code:
                    if not obj.validate_coupon(request.user, coupon):
                        return Response({"status": 0, "message": "Invalid coupon code for the user"},
                                        status.HTTP_404_NOT_FOUND)
                    else:
                        discount += obj.get_discount(coupon, deal_price)

            return Response({"discount": discount, "status": 1}, status.HTTP_200_OK)
        else:
            return Response({"status": 0, "message": "Invalid Product ID"}, status.HTTP_404_NOT_FOUND)
