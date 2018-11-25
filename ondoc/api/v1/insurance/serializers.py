from rest_framework import serializers
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer
from ondoc.insurance.models import (Insurer, InsurancePlans, InsuranceThreshold, InsurerAccount, InsuredMembers,
                                    InsuranceTransaction, UserInsurance)
from ondoc.authentication.models import (User, UserProfile)
from ondoc.account import models as account_models
from ondoc.account.models import (Order)
from django.contrib.postgres.fields import JSONField


class InsuranceThresholdSerializer(serializers.ModelSerializer):

    # id = serializers.PrimaryKeyRelatedField(queryset=InsuranceThreshold.objects.all(), required=True)
    # lab_amount_limit = serializers.IntegerField()
    # lab_count_limit = serializers.IntegerField()
    # opd_count_limit = serializers.IntegerField()
    # opd_amount_limit = serializers.IntegerField()
    # max_age = serializers.IntegerField()
    # min_age = serializers.IntegerField()
    # child_min_age = serializers.IntegerField()

    class Meta:
        model = InsuranceThreshold

        # fields = '__all__'
        exclude = ('created_at', 'updated_at', 'enabled', 'is_live')


class InsurancePlansSerializer(serializers.ModelSerializer):

    #id = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all(), required=True)
    #type = serializers.CharField(max_length=100)
    #amount = serializers.IntegerField()
    #threshold = serializers.SerializerMethodField()
    threshold = InsuranceThresholdSerializer(source='get_active_threshold', many=True)

    # def get_threshold(self, obj):
    #     threshold = InsuranceThreshold.objects.filter(insurance_plan=obj).first()
    #     if threshold:
    #         insurance_threshold = InsuranceThresholdSerializer(threshold)
    #         return insurance_threshold.data

    class Meta:
        model = InsurancePlans
        fields = ('id', 'name', 'amount', 'threshold')
        #fields = '__all__'

class InsurerSerializer(serializers.ModelSerializer):
    #id = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all(), required=True)
    #plans = serializers.SerializerMethodField()

    # def get_plans(self, obj):
    #     plans = InsurancePlans.objects.filter(insurer=obj)
    #     if plans:
    #         insurance_plans = InsurancePlansSerializer(plans, many=True)
    #         return insurance_plans.data
    plans = InsurancePlansSerializer(source='get_active_plans', many=True)


    class Meta:
        model = Insurer
        #fields = '__all__'
        fields = ('id', 'name', 'min_float', 'logo', 'website', 'phone_number', 'email', 'plans')


class MemberListSerializer(serializers.Serializer):

    title = serializers.ChoiceField(choices=InsuredMembers.TITLE_TYPE_CHOICES)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(max_length=50, allow_blank=True)
    last_name = serializers.CharField(max_length=50)
    dob = serializers.DateField()
    email = serializers.EmailField()
    relation = serializers.ChoiceField(choices=InsuredMembers.RELATION_CHOICES)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    member_type = serializers.ChoiceField(choices=InsuredMembers.MEMBER_TYPE_CHOICES)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    gender = serializers.ChoiceField(choices=InsuredMembers.GENDER_CHOICES)
    town = serializers.CharField(max_length=100)
    district = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)


class InsuredMemberSerializer(serializers.Serializer):

    members = serializers.ListSerializer(child=MemberListSerializer())
    # insurer = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all())
    # insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())


# class InsuredMemberSerializer(serializers.ListSerializer):
#
#     class Meta:
#         model = InsuredMembers
#         exclude = ('created_at', 'updated_at')


class InsuranceTransactionSerializer(serializers.Serializer):

    insurer = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all())
    insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())
    amount = serializers.IntegerField()
    #status_type = serializers.ChoiceField(choices=InsuranceTransaction.STATUS_CHOICES)
    # insured_members = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=InsuredMembers.objects.all))
    insured_members = serializers.ListSerializer(child=MemberListSerializer())
    transaction_date = serializers.DateTimeField()


class InsuredTransactionIdsSerializer(serializers.Serializer):
    # ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=InsuranceTransaction.objects.all()))
    id = serializers.PrimaryKeyRelatedField(queryset=InsuranceTransaction.objects.all())


class InsuredMemberIdsSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=InsuredMembers.objects.all())
    hypertension = serializers.NullBooleanField(required=False)
    liver_disease = serializers.NullBooleanField(required=False)
    heart_disease = serializers.NullBooleanField(required=False)
    diabetes = serializers.NullBooleanField(required=False)


class UserInsuranceSerializer(serializers.Serializer):

    insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    premium_amount = serializers.IntegerField()
    insured_members = serializers.ListSerializer(child=MemberListSerializer())
    purchase_date = serializers.DateTimeField()
    expiry_date = serializers.DateTimeField()
