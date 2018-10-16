from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from ondoc.insurance.models import (Insurer, InsurancePlans, InsuranceThreshold, InsurerFloat, InsuredMembers)
from ondoc.authentication.models import UserProfile


class InsurerSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all(), required=True)
    name = serializers.CharField(max_length=50)
    plans = serializers.SerializerMethodField()

    def get_plans(self, obj):
        plans = InsurancePlans.objects.filter(insurer=obj)
        if plans:
            insurance_plans = InsurancePlansSerializer(plans, many=True)
            return insurance_plans.data


    class Meta:
        model = Insurer
        field = ('id', 'name', 'plans', )


class InsurancePlansSerializer(serializers.Serializer):

    id = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all(), required=True)
    type = serializers.CharField(max_length=100)
    amount = serializers.IntegerField()
    threshold = serializers.SerializerMethodField()

    def get_threshold(self, obj):
        threshold = InsuranceThreshold.objects.filter(insurance_plan=obj)
        if threshold:
            insurance_threshold = InsuranceThresholdSerializer(threshold, many=True)
            return insurance_threshold.data

    class Meta:
        model = InsurancePlans
        field = ('id', 'type', 'amount', 'threshold')


class InsuranceThresholdSerializer(serializers.Serializer):

    id = serializers.PrimaryKeyRelatedField(queryset=InsuranceThreshold.objects.all(), required=True)
    lab_amount_limit = serializers.IntegerField()
    lab_count_limit = serializers.IntegerField()
    opd_count_limit = serializers.IntegerField()
    opd_amount_limit = serializers.IntegerField()
    max_age = serializers.IntegerField()
    min_age = serializers.IntegerField()
    tenure = serializers.IntegerField()
    child_min_age = serializers.IntegerField()

    class Meta:
        model = InsuranceThreshold
        field = {'id', 'lab_amount_limit', 'lab_count_limit', 'opd_count_limit', 'opd_amount_limit',
                 'max_age', 'min_age', 'tenure', 'child_min_age'}


class MemberListSerializer(serializers.Serializer):

    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    dob = serializers.DateField()
    email = serializers.EmailField()
    relation = serializers.CharField(max_length=50)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    member_type = serializers.ChoiceField(choices=InsuredMembers.MEMBER_TYPE_CHOICES)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    gender = serializers.ChoiceField(choices=InsuredMembers.GENDER_CHOICES)


class InsuredMemberSerializer(serializers.Serializer):

    members = serializers.ListSerializer(child=MemberListSerializer())
    insurer = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all())
    insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())