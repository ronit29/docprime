from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser)


class PlusThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlusThreshold
        exclude = ('created_at', 'updated_at', 'enabled', 'is_live')


class PlusPlansSerializer(serializers.ModelSerializer):
    threshold = PlusThresholdSerializer(source='get_active_threshold', many=True)

    class Meta:
        model = PlusPlans
        fields = ('id', 'name', 'amount', 'threshold', 'is_selected', 'tenure', 'total_allowed_members')


class PlusProposerSerializer(serializers.ModelSerializer):
    plans = PlusPlansSerializer(source='get_active_plans', many=True)

    class Meta:
        model = PlusProposer
        fields = ('id', 'name', 'logo', 'website', 'phone_number', 'email', 'plans')