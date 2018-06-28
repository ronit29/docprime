from rest_framework import serializers
from ondoc.payout import models as payout_models


class OutstandingModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = payout_models.Outstanding
        fields = "__all__"
