from rest_framework import serializers
from ondoc.authentication import models as auth_models
from ondoc.account.models import Order
from ondoc.cart.models import Cart
from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer


class CartCreateSerializer(serializers.Serializer):

    product_id = serializers.ChoiceField(choices=Order.PRODUCT_IDS)
    user = serializers.PrimaryKeyRelatedField(queryset=auth_models.User.objects.all())
    data = serializers.JSONField()

    def validate(self, attrs):
        request = self.context.get("request")
        product_id = attrs.get("product_id")
        user = attrs.get("user")
        data = attrs.get("data")

        if data.get("doctor"):
            opd_app_serializer = CreateAppointmentSerializer(data=data, context={'request': request})
            opd_app_serializer.is_valid(raise_exception=True)
        elif data.get("lab"):
            lab_app_serializer = LabAppointmentCreateSerializer(data=data, context={'request': request})
            lab_app_serializer.is_valid(raise_exception=True)

        return attrs

    # class meta:
    #     model = Cart
