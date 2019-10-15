from django.db.models import Q
from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer

from ondoc.api.v1.doctor.serializers import CommonConditionsSerializer
from ondoc.authentication.models import UserProfile
from ondoc.authentication.models import User
from ondoc.common.models import DocumentsProofs
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

    def get_utilize(self, obj):
        request = self.context.get('request')
        user = request.user
        utilization = {}
        if user and not user.is_anonymous and user.is_authenticated and user.active_plus_user:
            plus_user = user.active_plus_user
        elif user and not user.is_anonymous and user.is_authenticated and user.inactive_plus_user:
            plus_user = user.inactive_plus_user
        else:
            plus_user = None
        # plus_user = user.active_plus_user if not user.is_anonymous and user.is_authenticated else None
        if plus_user:
            utilization = plus_user.get_utilization
        return utilization

    class Meta:
        model = PlusPlans
        fields = ('id', 'plan_name', 'worth', 'mrp', 'tax_rebate', 'you_pay', 'you_get', 'deal_price', 'is_selected',
                  'tenure', 'total_allowed_members', 'content', 'enabled_hospital_networks', 'utilize')


class PlusProposerSerializer(serializers.ModelSerializer):
    # plans = PlusPlansSerializer(source='get_active_plans', many=True)
    plans = serializers.SerializerMethodField()

    def get_plans(self, obj):
        request = self.context.get('request')
        is_gold = request.query_params.get('is_gold', False)
        all_plans = request.query_params.get('all', False)

        plus_plans_qs = obj.get_active_plans.filter(~Q(is_gold=True))

        if is_gold:
            plus_plans_qs = obj.get_active_plans.filter(is_gold=True)

        if all_plans:
            plus_plans_qs = obj.get_active_plans

        serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)
        return serializer_obj.data

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans')


class PlusProposerUTMSerializer(serializers.ModelSerializer):
    plans = serializers.SerializerMethodField()

    def get_plans(self, obj):
        request = self.context.get('request')
        utm = self.context.get('utm')
        if utm:
            plus_plans_qs = PlusPlans.get_active_plans_via_utm(utm)
            serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)
            return serializer_obj.data
        return []

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans')


class PlusMembersDocumentSerializer(serializers.Serializer):
    proof_file = serializers.PrimaryKeyRelatedField(queryset=DocumentsProofs.objects.all())


class PlusMemberListSerializer(serializers.Serializer):
    title = serializers.ChoiceField(choices=PlusMembers.TITLE_TYPE_CHOICES)
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50, allow_blank=True, allow_null=True)
    dob = serializers.DateField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    city = serializers.CharField(required=True)
    city_code = serializers.CharField(required=True)
    relation = serializers.ChoiceField(choices=PlusMembers.Relations.as_choices())
    document_ids = serializers.ListField(required=False, allow_null=True, child=PlusMembersDocumentSerializer())
    # is_primary_user = serializers.BooleanField()
    # plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.all_active_plans(), allow_null=False, allow_empty=False)


class PlusMembersSerializer(serializers.Serializer):
    members = serializers.ListSerializer(child=PlusMemberListSerializer())

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        active_plus_user_obj = user.active_plus_user
        if active_plus_user_obj:
            plus_members = active_plus_user_obj.plus_members.all()
            if len(plus_members) > 1:
                raise serializers.ValidationError({'members': 'Members can be added only once.'})

            total_allowed_members = active_plus_user_obj.plan.total_allowed_members

            if len(plus_members) + len(attrs.get('members'))-1 > total_allowed_members:
                raise serializers.ValidationError({'members': 'Cannot add members more than total allowed memebers.'})

            # existing_members_name_set = set(map(lambda m: m.get_full_name(), plus_members))

            # check if there is name duplicacy or not.
            to_be_added_member_list = attrs.get('members', [])
            to_be_added_member_set = set(map(lambda member: "%s %s" % (member['first_name'], member['last_name']), to_be_added_member_list))
            to_be_added_member_relation_set = set(map(lambda member: "%s" % (member['relation']), to_be_added_member_list))

            # if PlusMembers.Relations.SELF in to_be_added_member_relation_set:
            #     raise serializers.ValidationError({'name': 'Proposer has already be added. Cannot be added and changed.'})

            if len(to_be_added_member_set) != len(to_be_added_member_list):
                raise serializers.ValidationError({'name': 'Multiple members cannot have same name'})

            # if to_be_added_member_set & existing_members_name_set:
            #     raise serializers.ValidationError({'name': 'Member already exist. Members name need to be unique.'})

        return attrs


class PlusUserSerializer(serializers.Serializer):

    plus_plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.IntegerField()
    plus_members = serializers.ListSerializer(child=PlusMemberListSerializer())
    purchase_date = serializers.DateTimeField()
    expire_date = serializers.DateTimeField()
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())


class PlusUserModelSerializer(serializers.ModelSerializer):

    plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.IntegerField()
    plus_members = serializers.ListSerializer(child=PlusMemberListSerializer())
    purchase_date = serializers.DateTimeField()
    expire_date = serializers.DateTimeField()
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())

    class Meta:
        model = PlusUser
        fields = '__all__'
