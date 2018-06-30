from rest_framework import serializers
from ondoc.payout import models as payout_models
from ondoc.account.models import Order
from ondoc.doctor.models import OpdAppointment


class OutstandingModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = payout_models.Outstanding
        fields = "__all__"


class BillingSummarySerializer(serializers.Serializer):
    month = serializers.IntegerField(max_value=12,min_value=1)
    year = serializers.IntegerField()
    doc_lab = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    payment_type = serializers.ChoiceField(choices=OpdAppointment.PAY_CHOICES)
