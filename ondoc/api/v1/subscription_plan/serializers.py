from django.utils import timezone
from rest_framework import serializers

from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.diagnostic.serializers import LabTestSerializer, PackageSerializer
from ondoc.subscription_plan.models import Plan, PlanFeature, UserPlanMapping


class UserSubscriptionRequestSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class PlanWithFeatureSerializer(PlanSerializer):

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
                           'count': temp_plan_feature_mapping.count if temp_plan_feature_mapping and temp_plan_feature_mapping.enabled else None})
        return result


class PlanFeatureSerializer(serializers.ModelSerializer):
    test = PackageSerializer()

    class Meta:
        model = PlanFeature
        fields = ('id', 'test', 'name',
                  # 'lab', 'hospital'  # if_subscription_plan_contains_anything_except_test
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


class UserSubscriptionBuyRequestSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(enabled=True))
    coupon_code = serializers.ListField(child=serializers.CharField(), required=False, default=[])

    def validate(self, data):
        from ondoc.coupon.models import RandomGeneratedCoupon
        from ondoc.doctor.models import OpdAppointment
        from ondoc.account.models import Order
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Invalid request.')
        if UserPlanMapping.objects.filter(user=request.user, is_active=True, expire_at__gte=timezone.now()).exists():
            raise serializers.ValidationError('User already has a subscription plan.')
        if data.get("coupon_code"):
            coupon_codes = data.get("coupon_code", [])
            coupon_obj = RandomGeneratedCoupon.get_coupons(coupon_codes)

            if coupon_obj:
                for coupon in coupon_obj:
                    obj = UserPlanMapping()
                    if obj.validate_user_coupon(user=request.user, coupon_obj=coupon).get("is_valid"):
                        if not obj.validate_product_coupon(coupon_obj=coupon,
                                                           plan=data.get('plan'),
                                                           product_id=Order.SUBSCRIPTION_PLAN_PRODUCT_ID):
                            raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                    else:
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                data["coupon_obj"] = list(coupon_obj)
        return data


class UserSubscriptionRetrieveRequestSerializer(serializers.Serializer):
    user_plan = serializers.PrimaryKeyRelatedField(queryset=UserPlanMapping.objects.all())

    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Invalid request.')
        if not UserPlanMapping.objects.filter(user=request.user, is_active=True, expire_at__gt=timezone.now()).exists():
            raise serializers.ValidationError('User has no active subscription plan.')
        return attrs
