from rest_framework import serializers
from ondoc.diagnostic.models import PathologyTest

class PathologyTestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PathologyTest
        fields = ('id','name')


class PathologyTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PathologyTest
        fields = ('id','name','pre_test_info','why')
        # fields = ('id', 'account_name', 'users', 'created')
