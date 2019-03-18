from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ondoc.api.v1.subscription_plan import serializers
from ondoc.authentication.backends import JWTAuthentication
from ondoc.authentication.models import User
from ondoc.subscription_plan.models import UserPlanMapping, Plan, PlanFeature, PlanFeatureMapping
from rest_framework.response import Response


class SubscriptionPlanUserViewSet(viewsets.GenericViewSet):

    def subscription_plan(self, request):
        serializer = serializers.UserSubscriptionRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        user_plan_mapping = UserPlanMapping.objects.prefetch_related('user__profiles', 'user', 'plan').filter(
            user__phone_number=validated_data.get('phone_number'), user__user_type=User.CONSUMER,
            expire_at__gt=timezone.now(), is_active=True).first()

        return Response(serializers.UserSubscriptionResponseSerializer(user_plan_mapping).data)

    def get_queryset(self):
        return UserPlanMapping.objects.objects.none()


class SubscriptionPlanListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        plan_queryset = list(Plan.objects.prefetch_related(
            Prefetch('feature_mappings', PlanFeatureMapping.objects.filter(enabled=True))).filter(enabled=True))
        plan_feature_queryset = list(PlanFeature.objects.prefetch_related('test__test__parameter').filter(enabled=True))
        plans_data = serializers.PlanWithFeatureSerializer(plan_queryset, many=True,
                                                           context={"plan_feature_queryset": plan_feature_queryset}).data
        feature_data = serializers.PlanFeatureSerializer(plan_feature_queryset, many=True).data
        return Response({'plans': plans_data, 'feature_details': feature_data})


class SubscriptionPlanLoggedInUserViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return UserPlanMapping.objects.objects.none()

    def buy(self, request):
        serializer = serializers.UserSubscriptionBuyRequestSerializer(data=request.data,
                                                                      context={'request': request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        resp = UserPlanMapping.create_order(request, validated_data)
        return Response(resp)

    def retrieve(self, request):
        from copy import deepcopy
        serializer = serializers.UserSubscriptionRetrieveRequestSerializer(data=request.query_params,
                                                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        user_plan_obj = validated_data.get('user_plan')
        result = deepcopy(user_plan_obj.extra_details)
        result.update({"created_at": user_plan_obj.created_at, "expire_at": user_plan_obj.expire_at,
                       "is_active": user_plan_obj.is_active})
        return Response(result)

    def has_plan(self, request):
        user_plan_mapping = UserPlanMapping.objects.filter(user=request.user, is_active=True, expire_at__gt=timezone.now()).first()
        has_active_plan = False
        user_plan_id = None
        if user_plan_mapping:
            has_active_plan = True
            user_plan_id = user_plan_mapping.id
        return Response({"has_active_plan": has_active_plan, "user_plan_id": user_plan_id})
