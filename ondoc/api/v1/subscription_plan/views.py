from django.utils import timezone
from rest_framework import viewsets
from ondoc.api.v1.subscription_plan import serializers
from ondoc.authentication.models import User
from ondoc.subscription_plan.models import UserPlanMapping
from rest_framework.response import Response


class SubscriptionPlanUserViewSet(viewsets.GenericViewSet):

    def subscription_plan(self, request):
        serializer = serializers.UserSubscriptionRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        user_plan_mapping = UserPlanMapping.objects.prefetch_related('user__profiles', 'user', 'plan').filter(
            user__phone_number=validated_data.get('phone_number'), user__user_type=User.CONSUMER,
            expire_at__gt=timezone.now()).first()

        return Response(serializers.UserSubscriptionResponseSerializer(user_plan_mapping).data)

    def get_queryset(self):
        return UserPlanMapping.objects.objects.none()
