from rest_framework import serializers
from ondoc.authentication import models as auth_models
from ondoc.account.models import Order


class CartCreateSerializer(serializers.Serializer):

    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    data = serializers.JSONField(required=True)
