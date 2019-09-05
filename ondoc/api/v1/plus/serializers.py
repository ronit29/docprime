from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer

from ondoc.api.v1.doctor.serializers import CommonConditionsSerializer
from ondoc.authentication.models import UserProfile
from ondoc.authentication.models import User
from ondoc.doctor.models import Hospital
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser, PlusUserUtilization)
from ondoc.plus.enums import PlanParametersEnum
from ondoc.account import models as account_models


class PlusThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlusThreshold
        exclude = ('created_at', 'updated_at', 'enabled', 'is_live')


class PlusPlansSerializer(serializers.ModelSerializer):
    # threshold = PlusThresholdSerializer(source='get_active_threshold', many=True)
    content = serializers.SerializerMethodField()
    enabled_hospital_networks = serializers.SerializerMethodField()
    worth = serializers.SerializerMethodField()
    you_pay = serializers.SerializerMethodField()
    you_get = serializers.SerializerMethodField()
    utilize = serializers.SerializerMethodField()

    def get_content(self, obj):
        resp = defaultdict(list)
        qs = obj.plan_content.all().order_by('id').values('title', 'content')
        for e in qs:
            resp[e['title'].lower()].append(e['content'])
        return resp

    def get_enabled_hospital_networks(self, obj):
        request = self.context.get('request')
        if not request:
            return None

        serializer = CommonConditionsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        top_hospitals_data = Hospital.get_top_hospitals_data(request, validated_data.get('lat'), validated_data.get('long'))
        return top_hospitals_data

    def get_worth(self, obj):
        data = {}
        plan_parameters = obj.plan_parameters.filter(parameter__key__in=[PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                       PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                       PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT,
                                                       PlanParametersEnum.MEMBERS_COVERED_IN_PACKAGE,
                                                       PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE])

        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value

        data['tax_rebate'] = obj.tax_rebate
        return data

    def get_you_pay(self, obj):
        data = {}
        data['mrp'] = obj.mrp
        data['deal_price'] = obj.deal_price
        data['tax_rebate'] = obj.tax_rebate

        data['effective_price'] = obj.deal_price - obj.tax_rebate
        return data

    def get_you_get(self, obj):
        data = {}
        plan_parameters = obj.plan_parameters.filter(parameter__key__in=[PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                                         PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                                         PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT])

        effective_price = 0
        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value
            effective_price += int(pp.value)

        data['effective_price'] = effective_price
        return data

    def utilize(self, obj):
        request = self.context.get('request')
        user = request.user
        plus_user = PlusUser.objects.filter(user_id=user.id).first()
        utilization = plus_user.get_utilization()
        return utilization

    class Meta:
        model = PlusPlans
        fields = ('id', 'plan_name', 'worth', 'mrp', 'tax_rebate', 'you_pay', 'you_get', 'deal_price', 'is_selected', 'tenure', 'total_allowed_members', 'content', 'enabled_hospital_networks')


class PlusProposerSerializer(serializers.ModelSerializer):
    plans = PlusPlansSerializer(source='get_active_plans', many=True)

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans')


class PlusMemberListSerializer(serializers.Serializer):
    title = serializers.ChoiceField(choices=PlusMembers.TITLE_TYPE_CHOICES)
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50, allow_blank=True, allow_null=True)
    dob = serializers.DateField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    city = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    city_code = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    relation = serializers.ChoiceField(choices=PlusMembers.Relations.as_choices())
    # is_primary_user = serializers.BooleanField()
    # plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.all_active_plans(), allow_null=False, allow_empty=False)


class PlusMembersSerializer(serializers.Serializer):
    members = serializers.ListSerializer(child=PlusMemberListSerializer())


class PlusUserSerializer(serializers.Serializer):

    plus_plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.IntegerField()
    plus_members = serializers.ListSerializer(child=PlusMemberListSerializer())
    purchase_date = serializers.DateTimeField()
    expire_date = serializers.DateTimeField()
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())
