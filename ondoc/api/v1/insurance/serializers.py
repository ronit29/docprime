from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from ondoc.insurance.models import (Insurer, InsurancePlans, InsuranceThreshold, InsurerFloat, InsuredMembers)


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

    class Meta:
        model = InsuranceThreshold
        field = {'id', 'lab_amount_limit', 'lab_count_limit', 'opd_count_limit', 'opd_amount_limit',
                 'max_age', 'min_age', 'tenure'}


class MemberListSerializer(serializers.Serializer):

    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    dob = serializers.DateField()
    email = serializers.EmailField()
    relation = serializers.CharField(max_length=50)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    # gender = serializers.SerializerMethodField()

    # def get_gender(self, obj):
    #     if obj.relation == InsuredMembers.HUSBAND or InsuredMembers.SON:
    #         gender = InsuredMembers.MALE
    #     else:
    #         gender = InsuredMembers.FEMALE
    #
    #     return gender


class InsuredMemberSerializer(serializers.Serializer):
    # member_list = MemberListSerializer(many=True)
    members = serializers.ListSerializer(child=MemberListSerializer())
    insurer = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all())
    insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())

    # class Meta:
    #     model = InsuredMembers
    #     fields={'insurer', 'insurance_plan', 'insured_member'}


