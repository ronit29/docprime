from rest_framework import serializers
from ondoc.diagnostic.models import AvailableLabTest
from rest_framework.validators import UniqueTogetherValidator


class AjaxAvailableLabTestSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2)
    custom_agreed_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)    
    custom_deal_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = AvailableLabTest
        fields = ('id', 'lab_pricing_group', 'enabled', 'test', 'mrp', 'custom_agreed_price', 'custom_deal_price')
        validators = [
            UniqueTogetherValidator(
                queryset=AvailableLabTest.objects.all(),
                fields=('test', 'lab_pricing_group')
            )
        ]
