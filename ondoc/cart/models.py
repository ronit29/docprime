from django.db import models
from ondoc.api.v1.utils import format_iso_date
from ondoc.authentication import models as auth_model
from ondoc.account.models import Order
from django.contrib.postgres.fields import JSONField


class Cart(auth_model.TimeStampedModel, auth_model.SoftDeleteModel):

    product_id = models.IntegerField(choices=Order.PRODUCT_IDS)
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(blank=True, null=True)
    data = JSONField()

    @classmethod
    def compare_item_data(cls, data, item_data):
        # compare data after cleanup
        data = dict(data)
        data.pop('coupon_code', None)
        item_data.pop('coupon_code', None)
        data.pop('use_wallet', None)
        item_data.pop('use_wallet', None)
        data.pop('cart_item', None)
        item_data.pop('cart_item', None)
        data['start_date'] = format_iso_date(data['start_date'])
        item_data['start_date'] = format_iso_date(item_data['start_date'])
        return data != item_data

    @classmethod
    def validate_duplicate(cls, data, user, product_id, cart_item=None):
        existing_cart_items = Cart.objects.filter(deleted_at__isnull=True, user=user, product_id=product_id).values('id', 'data').exclude(id=cart_item)
        if existing_cart_items:
            for item in existing_cart_items:
                if not cls.compare_item_data(data, item.get("data")):
                    return False
        return True

    def validate(self, request):
        from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
        from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer

        self.data["cart_item"] = self.id
        if self.product_id == Order.DOCTOR_PRODUCT_ID:
            serializer = CreateAppointmentSerializer(data=self.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
        elif self.product_id == Order.LAB_PRODUCT_ID:
            serializer = LabAppointmentCreateSerializer(data=self.data, context={'request': request})
            serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        return validated_data

    def get_price_details(self, validated_data):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        if self.product_id == Order.DOCTOR_PRODUCT_ID:
            price_data = OpdAppointment.get_price_details(validated_data)
        elif self.product_id == Order.LAB_PRODUCT_ID:
            price_data = LabAppointment.get_price_details(validated_data)

        return price_data

    def get_fulfillment_data(self, validated_data):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        if self.product_id == Order.DOCTOR_PRODUCT_ID:
            price_data = self.get_price_details(validated_data)
        elif self.product_id == Order.LAB_PRODUCT_ID:
            price_data = self.get_price_details(validated_data)

        if self.product_id == Order.DOCTOR_PRODUCT_ID:
            fulfillment_data = OpdAppointment.create_fulfillment_data(self.user, validated_data, price_data)
        elif self.product_id == Order.LAB_PRODUCT_ID:
            fulfillment_data = LabAppointment.create_fulfillment_data(self.user, validated_data, price_data)

        return fulfillment_data

    def __str__(self):
        return str(self.id)
