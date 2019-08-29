from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser)
from ondoc.plus.enums import PlanParametersEnum


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
        return PlusUser.get_enabled_hospitals(request=request)

    def get_worth(self, obj):
        data = {}
        plan_parameters = obj.plan_parameters.filter(parameter__key__in=[PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                       PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                       PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT])

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

        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value

        return data

    class Meta:
        model = PlusPlans
        fields = ('id', 'plan_name', 'worth', 'mrp', 'tax_rebate', 'you_pay', 'you_get', 'deal_price', 'is_selected', 'tenure', 'total_allowed_members', 'content', 'enabled_hospital_networks')


class PlusProposerSerializer(serializers.ModelSerializer):
    plans = PlusPlansSerializer(source='get_active_plans', many=True)

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans')