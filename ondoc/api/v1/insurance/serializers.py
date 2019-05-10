from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer

from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor
from ondoc.insurance.models import (Insurer, InsurancePlans, InsuranceThreshold, InsurerAccount, InsuredMembers,
                                    InsuranceTransaction, UserInsurance, InsuranceDisease, InsurancePlanContent,
                                    StateGSTCode, InsuranceCity, InsuranceDistrict)
from ondoc.authentication.models import (User, UserProfile)
from ondoc.account import models as account_models
from ondoc.account.models import (Order)
from django.contrib.postgres.fields import JSONField


class InsuranceThresholdSerializer(serializers.ModelSerializer):

    class Meta:
        model = InsuranceThreshold

        exclude = ('created_at', 'updated_at', 'enabled', 'is_live')


class InsurancePlansSerializer(serializers.ModelSerializer):

    content = serializers.SerializerMethodField()
    threshold = InsuranceThresholdSerializer(source='get_active_threshold', many=True)

    def get_content(self, obj):
        resp = defaultdict(list)
        qs = obj.content.all().order_by('id').values('title', 'content')
        for e in qs:
            resp[e['title'].lower()].append(e['content'])
        return resp

    class Meta:
        model = InsurancePlans
        fields = ('id', 'name', 'amount', 'threshold', 'content', 'adult_count', 'child_count', 'is_selected')
        #fields = '__all__'

class InsurerSerializer(serializers.ModelSerializer):

    plans = InsurancePlansSerializer(source='get_active_plans', many=True)
    insurer_document = serializers.SerializerMethodField()

    def get_insurer_document(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.insurer_document.url) if obj.insurer_document is not None and obj.insurer_document.name else None


    class Meta:
        model = Insurer
        #fields = '__all__'
        fields = ('id', 'name', 'min_float', 'logo', 'website', 'phone_number', 'email', 'plans', 'insurer_document')


class MemberListSerializer(serializers.Serializer):

    title = serializers.ChoiceField(choices=InsuredMembers.TITLE_TYPE_CHOICES)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(max_length=50, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(max_length=50, allow_blank=True, allow_null=True)
    dob = serializers.DateField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    relation = serializers.ChoiceField(choices=InsuredMembers.RELATION_CHOICES)
    address = serializers.CharField(max_length=250)
    pincode = serializers.IntegerField()
    member_type = serializers.ChoiceField(choices=InsuredMembers.MEMBER_TYPE_CHOICES)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    gender = serializers.ChoiceField(choices=InsuredMembers.GENDER_CHOICES)
    town = serializers.CharField(max_length=100)
    district = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    state_code = serializers.CharField(max_length=10)

    def validate(self, attrs):
        request = self.context.get("request")
        insurance_plan = None
        if request:
            insurance_plan = request.data.get('insurance_plan')
        if insurance_plan:
            insurance_threshold = InsuranceThreshold.objects.filter(insurance_plan_id=
                                                                    insurance_plan).first()
            dob_flag, message = insurance_threshold.age_validate(attrs)
            if not dob_flag:
                raise serializers.ValidationError({'dob': message.get('message')})
        return attrs


class InsuredMemberSerializer(serializers.Serializer):

    members = serializers.ListSerializer(child=MemberListSerializer())

    def validate(self, attrs):

        # check if there is name duplicacy or not.
        member_list = attrs.get('members', [])
        name_set = set(map(lambda member: "%s-%s-%s" % (member['first_name'], member['middle_name'], member['last_name']), member_list))

        if len(name_set) != len(member_list):
            raise serializers.ValidationError({'name': 'Multiple members cannot have same name'})

        return attrs

    # insurer = serializers.PrimaryKeyRelatedField(queryset=Insurer.objects.all())
    # insurance_plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlans.objects.all())


class MemberSerializer(serializers.ModelSerializer):

    title = serializers.ReadOnlyField()
    first_name = serializers.ReadOnlyField()
    middle_name = serializers.ReadOnlyField()
    last_name = serializers.ReadOnlyField()
    dob = serializers.ReadOnlyField()
    email = serializers.ReadOnlyField()
    relation = serializers.ReadOnlyField()
    address = serializers.ReadOnlyField()
    pincode = serializers.ReadOnlyField()
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), allow_null=True)
    gender = serializers.ReadOnlyField()
    town = serializers.ReadOnlyField()
    district = serializers.ReadOnlyField()
    state = serializers.ReadOnlyField()
    state_code = serializers.ReadOnlyField()

    class Meta:
        model = InsuredMembers
        fields = '__all__'
        # fields = ('id', 'name', 'min_float', 'logo', 'website', 'phone_number', 'email', 'plans', 'insurer_document')


class InsuredMemberIdSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=InsuredMembers.objects.all())


class InsuranceDiseaseIdSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=InsuranceDisease.objects.all())


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


class UserInsuranceIdsSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=UserInsurance.objects.all())


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
    order = serializers.PrimaryKeyRelatedField(queryset=account_models.Order.objects.all())


class InsuranceValidationSerializer(serializers.Serializer):
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all(), allow_null=True)
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), allow_null=True)
    time_slot_start = serializers.DateTimeField()
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())


class InsuranceCitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceCity
        fields = ('city_code', 'city_name')


class InsuranceDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceDistrict
        fields = ('district_code', 'district_name')


class StateGSTCodeSerializer(serializers.ModelSerializer):
    cities = InsuranceCitySerializer(source='get_active_city', many=True)
    district = InsuranceDistrictSerializer(source='get_active_district', many=True)
    class Meta:
        model = StateGSTCode
        fields = ('id', 'gst_code', 'state_name', 'cities', 'district')


