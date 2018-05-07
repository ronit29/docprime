from rest_framework import serializers
from ondoc.diagnostic.models import LabTest

class LabTestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id','name')


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id','name','pre_test_info','why')
        # fields = ('id', 'account_name', 'users', 'created')
