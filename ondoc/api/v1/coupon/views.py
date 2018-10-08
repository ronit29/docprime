from ondoc.coupon import models as coupon_models
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
