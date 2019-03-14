from rest_framework import serializers

from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.diagnostic.serializers import LabTestSerializer, PackageSerializer
from ondoc.subscription_plan.models import Plan, PlanFeature


class UserSubscriptionRequestSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class PlanSerializerList(PlanSerializer):

    features = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ('id', 'name', 'mrp', 'deal_price', 'unlimited_online_consultation', 'priority_queue', 'features')

    def get_features(self, obj):
        plan_feature_dict = {}
        for plan_feature_mapping in obj.feature_mappings.all():
            plan_feature_dict[plan_feature_mapping.feature.id] = plan_feature_mapping
        result = []
        plan_feature_list = self.context.get('plan_feature_queryset', [])
        for plan_feature in plan_feature_list:
            temp_plan_feature_mapping = plan_feature_dict.get(plan_feature.id, None)
            result.append({'id': plan_feature.id,
                           'count': temp_plan_feature_mapping.count if temp_plan_feature_mapping else None})
        return result


class PlanFeatureSerializer(serializers.ModelSerializer):
    test = PackageSerializer()

    class Meta:
        model = PlanFeature
        fields = ('id', 'test',
                  # 'lab', 'hospital'  # TODO: if subscription plan contains anything except test
                  )


class UserSubscriptionResponseSerializer(serializers.Serializer):
    profile = serializers.SerializerMethodField(default=None)
    plan_details = serializers.SerializerMethodField(default=None)
    priority_queue = serializers.BooleanField(source='plan.priority_queue', default=False)
    plan_id = serializers.IntegerField(source='plan.id', default=None)

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
