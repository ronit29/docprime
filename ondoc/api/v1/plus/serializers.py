from operator import itemgetter

from django.db.models import Q
from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer

from ondoc.api.v1.doctor.serializers import CommonConditionsSerializer
from ondoc.authentication.models import UserProfile
from ondoc.authentication.models import User
from ondoc.common.models import DocumentsProofs
from ondoc.coupon.models import RandomGeneratedCoupon, CouponRecommender
from ondoc.doctor.models import Hospital
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser, PlusUserUtilization,
                               PlusPlanParameters, PlusPlanParametersMapping)
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
    show_consultation_text = serializers.SerializerMethodField()

    def get_show_consultation_text(self, obj):
        # online_chat_param = PlusPlanParameters.objects.filter(key='ONLINE_CHAT_AMOUNT').first()
        # if not online_chat_param:
        #     return False

        # parameter_mapping = PlusPlanParametersMapping.objects.filter(plus_plan_id=obj.id, parameter_id=online_chat_param.id).first()
        parameter_mapping = list(
                filter(lambda x: x.parameter and x.parameter.key == PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                       obj.plan_parameters.all()))
        if parameter_mapping:
            parameter_mapping = parameter_mapping[0]
            if parameter_mapping.value:
                return True

        return False

    def get_content(self, obj):
        resp = defaultdict(list)
        qs = obj.plan_content.all().order_by('id').values('title', 'content')
        for e in qs:
            resp[e['title'].lower()].append(e['content'])
        return resp

    def get_enabled_hospital_networks(self, obj):
        return []
        # request = self.context.get('request')
        # if not request:
        #     return None
        #
        # serializer = CommonConditionsSerializer(data=request.query_params)
        # serializer.is_valid(raise_exception=True)
        # validated_data = serializer.validated_data
        # top_hospitals_data = Hospital.get_top_hospitals_data(request, validated_data.get('lat'), validated_data.get('long'))
        # return top_hospitals_data

    def get_worth(self, obj):
        data = {}
        # plan_parameters = obj.plan_parameters.filter(parameter__key__in=[PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
        #                                                PlanParametersEnum.ONLINE_CHAT_AMOUNT,
        #                                                PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT,
        #                                                PlanParametersEnum.MEMBERS_COVERED_IN_PACKAGE,
        #                                                PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE])

        plan_parameters = list(
            filter(lambda x: x.parameter and x.parameter.key in [PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                                 PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                                 PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT,
                                                                 PlanParametersEnum.MEMBERS_COVERED_IN_PACKAGE,
                                                                 PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE],
                   obj.plan_parameters.all()))

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

        plan_parameters = list(
            filter(lambda x: x.parameter and x.parameter.key in [PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                                         PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                                         PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT],
                   obj.plan_parameters.all()))

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
                  'tenure', 'total_allowed_members', 'default_single_booking', 'content', 'enabled_hospital_networks',
                  'utilize', 'is_gold', 'show_consultation_text', 'is_corporate')


class PlusProposerSerializer(serializers.ModelSerializer):
    # plans = PlusPlansSerializer(source='get_active_plans', many=True)
    plans = serializers.SerializerMethodField()
    gold_plans = serializers.SerializerMethodField()

    def get_plans(self, obj):
        request = self.context.get('request')
        resp = []

        if request.query_params.get('is_gold'):
            return resp

        plus_plans_qs = obj.get_active_plans.filter(~Q(is_gold=True)).order_by('priority')
        serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)

        resp = serializer_obj.data

        return resp

    def get_gold_plans(self, obj):
        request = self.context.get('request')
        resp = []

        if request.query_params.get('is_gold') or request.query_params.get('all'):

            plus_plans_qs = obj.get_active_plans.filter(is_gold=True).order_by('priority')

            serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)

            resp = serializer_obj.data

        return resp

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans', 'gold_plans')


class PlusProposerUTMSerializer(serializers.ModelSerializer):
    plans = serializers.SerializerMethodField()
    gold_plans = serializers.SerializerMethodField()

    def get_plans(self, obj):
        request = self.context.get('request')
        utm = self.context.get('utm')
        if utm:
            plus_plans_qs = PlusPlans.get_active_plans_via_utm(utm)
            plus_plans_qs = list(filter(lambda p: not p.is_gold, plus_plans_qs))
            serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)
            return serializer_obj.data
        return []

    def get_gold_plans(self, obj):
        request = self.context.get('request')
        utm = self.context.get('utm')
        resp = []

        if request.query_params.get('is_gold') or request.query_params.get('all'):
            plus_plans_qs = PlusPlans.get_active_plans_via_utm(utm)
            plus_plans_qs = list(filter(lambda p: p.is_gold, plus_plans_qs))
            serializer_obj = PlusPlansSerializer(plus_plans_qs, context=self.context, many=True)

            resp = serializer_obj.data

        return resp

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans', 'gold_plans')


class PlusMembersDocumentSerializer(serializers.Serializer):
    proof_file = serializers.PrimaryKeyRelatedField(queryset=DocumentsProofs.objects.all())


class PlusMemberListSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    title = serializers.ChoiceField(choices=PlusMembers.TITLE_TYPE_CHOICES, required=False, allow_blank=True, allow_null=True)
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50, allow_blank=True, allow_null=True)
    dob = serializers.DateField()
    email = serializers.EmailField(allow_blank=True, allow_null=True, required=False)
    address = serializers.CharField(max_length=250, required=False, allow_null=True)
    pincode = serializers.IntegerField(required=False, allow_null=True)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    city = serializers.CharField(required=False, allow_null=True)
    city_code = serializers.CharField(required=False, allow_null=True)
    relation = serializers.ChoiceField(choices=PlusMembers.Relations.as_choices(), required=False, allow_null=True, allow_blank=True)
    document_ids = serializers.ListField(required=False, allow_null=True, child=PlusMembersDocumentSerializer())
    is_primary_user = serializers.BooleanField(required=False, default=False)
    gender = serializers.ChoiceField(choices=UserProfile.GENDER_CHOICES, required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

class PlusMembersSerializer(serializers.Serializer):
    members = serializers.ListSerializer(child=PlusMemberListSerializer())
    coupon_code = serializers.ListField(child=serializers.CharField(), required=False, default=[])

    def validate(self, attrs):
        from ondoc.account.models import Order

        request = self.context.get('request')
        user = request.user
        plus_user_obj = PlusUser.get_by_user(user)
        if plus_user_obj:
            plus_members = plus_user_obj.plus_members.all()

            total_allowed_members = plus_user_obj.plan.total_allowed_members

            if len(attrs.get('members')) > total_allowed_members:
                raise serializers.ValidationError({'members': 'Cannot add members more than total allowed memebers.'})

            existing_members_name_set = set(map(lambda m: m.get_full_name(), plus_members))

            # check if there is name duplicacy or not.
            member_list = attrs.get('members', [])
            to_be_added_member_list = []
            proposer_name = None
            for each_member in member_list:
                if not each_member.get('id') or each_member['is_primary_user']:
                    to_be_added_member_list.append(each_member)
                if each_member['is_primary_user']:
                    proposer_name = "%s %s" % (each_member['first_name'], each_member['last_name'])

            to_be_added_member_set = set(
                    map(lambda member: "%s %s" % (member['first_name'], member['last_name']), to_be_added_member_list))

            if proposer_name in to_be_added_member_set:
                to_be_added_member_set.remove(proposer_name)

            if to_be_added_member_set & existing_members_name_set:
                raise serializers.ValidationError({'name': 'Member already exist. Members name need to be unique.'})

            attrs['members'] = to_be_added_member_list

        else:
            if attrs.get("coupon_code"):
                coupon_codes = attrs.get("coupon_code", [])
                coupon_obj = RandomGeneratedCoupon.get_coupons(coupon_codes)
                plus_plan_id = request.data.get('plan_id')
                if not plus_plan_id:
                    raise serializers.ValidationError({"Plans": "Plus Plan is not Valid"})

                if coupon_codes and not coupon_obj:
                    raise serializers.ValidationError({"Coupon": "Applied coupon not found"})

                if coupon_obj:
                    for coupon in coupon_obj:
                        profile = attrs.get("profile")
                        obj = PlusUser()
                        if obj.validate_user_coupon(user=user, coupon_obj=coupon, profile=profile).get("is_valid"):
                            if not obj.validate_product_coupon(coupon_obj=coupon, gold_vip_plan_id=plus_plan_id,
                                                               product_id=Order.VIP_PRODUCT_ID):
                                raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                        else:
                            raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                    attrs["coupon_obj"] = list(coupon_obj)

        return attrs


class PlusUserSerializer(serializers.Serializer):

    plus_plan = serializers.PrimaryKeyRelatedField(queryset=PlusPlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.IntegerField()
    effective_price = serializers.IntegerField()
    plus_members = serializers.ListSerializer(child=PlusMemberListSerializer())
    purchase_date = serializers.DateTimeField()
    expire_date = serializers.DateTimeField()
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())
    coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])
    random_coupon_list = serializers.ListField(child=serializers.CharField(), required=False, default=[])


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
