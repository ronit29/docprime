from rest_framework import serializers

from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.subscription_plan.models import Plan


class UserSubscriptionRequestSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class UserSubscriptionResponseSerializer(serializers.Serializer):
    profile = serializers.SerializerMethodField(default=None)
    plan_details = serializers.SerializerMethodField(default=None)
    priority_queue = serializers.BooleanField(source='plan.priority_queue', default=False)
    plan_id = serializers.IntegerField(source='plan.id', default=None)
    # user = serializers.SerializerMethodField()

    def get_profile(self, obj):
        if obj.user:
            for profile in obj.user.profiles.all():
                if profile.is_default_user:
                    return UserProfileSerializer(profile).data
        return None

    def get_plan_details(self, obj):
        if obj.plan:
            return PlanSerializer(obj.plan).data
        return None

    # def get_user(self,obj):
    #     return None
