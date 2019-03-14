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
        plan_feature_queryset = list(PlanFeature.objects.filter(enabled=True))
        plans_data = serializers.PlanSerializerList(plan_queryset, many=True,
                                               context={"plan_feature_queryset": plan_feature_queryset}).data
        feature_data = serializers.PlanFeatureSerializer(plan_feature_queryset, many=True).data
        return Response({'plans': plans_data, 'feature_details': feature_data})


class SubscriptionPlanLoggedInUserViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def buy(self, request):
        serializer = serializers.UserSubscriptionBuyRequestSerializer(data=request.query_params,
                                                                      context={'request': request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        resp = Plan.create_order(request, validated_data)
        return Response(resp)

    def get_queryset(self):
        return UserPlanMapping.objects.objects.none()
