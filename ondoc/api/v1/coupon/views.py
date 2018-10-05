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
        if request.user.last_login:
            user = request.user
        else:
            return Response({
                'status': 'Failed',
                'message': 'User not Logged In'})
        applicable_coupons = []
        all_coupons_data = coupon_models.Coupon.objects.all()
        for coupon in all_coupons_data:
            if CouponsMixin.validate_coupon(self, user, coupon.code):
                applicable_coupons.append({"id": coupon.id,
                                           "code": coupon.code,
                                           "desc": coupon.description})
        return Response(applicable_coupons)
