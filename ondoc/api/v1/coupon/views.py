from ondoc.coupon import models as coupon_models
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
        applicable_coupons = []
        all_coupons_data = coupon_models.Coupon.objects.all()
        obj = CouponsMixin()

        if request.user.is_authenticated:
            user = request.user
            is_user = True
        else:
            is_user = False

        for coupon in all_coupons_data:
            if (is_user and obj.validate_coupon(user, coupon.code)) or not is_user:
                applicable_coupons.append({"id": coupon.id,
                                           "code": coupon.code,
                                           "desc": coupon.description})

        return Response(applicable_coupons)


class CouponDiscountViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def coupon_discount(self, request, *args, **kwargs):
        input_data = request.data
        coupon_code = input_data.get("coupon_code")
        deal_price = input_data.get("deal_price")
        product_id = input_data.get("product_id")
        if product_id == str(Order.DOCTOR_PRODUCT_ID):
            obj = OpdAppointment()
        elif product_id == str(Order.LAB_PRODUCT_ID):
            obj = LabAppointment()
        if coupon_code:
            if not obj.validate_coupon(request.user, coupon_code):
                return Response({"status":0, "message": "Invalid coupon code for the user"}, status.HTTP_404_NOT_FOUND)
            else:
                discount = obj.get_discount(coupon_code, deal_price)

        return Response({"discount": discount, "status": 1})
