from django.db import models
from ondoc.api.v1.utils import format_iso_date
from ondoc.authentication import models as auth_model
from ondoc.account.models import Order
from django.contrib.postgres.fields import JSONField
from datetime import date, timedelta, datetime

class Cart(auth_model.TimeStampedModel, auth_model.SoftDeleteModel):

    product_id = models.IntegerField(choices=Order.PRODUCT_IDS)
    user = models.ForeignKey(auth_model.User, related_name='cart_item', on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(blank=True, null=True)
    data = JSONField()

    @classmethod
    def remove_all(cls, user):
        try:
            curr_time = datetime.now()
            cls.objects.filter(user=user, deleted_at__isnull=True).update(deleted_at=curr_time)
        except Exception as e:
            pass

    @classmethod
    def get_free_opd_item_count(cls, request, cart_item=None):
        user = request.user
        existing_cart_items = Cart.objects.filter(deleted_at__isnull=True, user=user, product_id=Order.DOCTOR_PRODUCT_ID).exclude(id=cart_item)
        free_count = 0
        for item in existing_cart_items:
            try:
                validated_data = item.validate(request)
                price_data = item.get_price_details(validated_data)
                if price_data["deal_price"] == 0:
                    free_count += 1
            except Exception as e:
                pass
        return free_count

    @classmethod
    def compare_item_data(cls, data, item_data):
        '''
            This method compare two cart item's data and return if they are exactly similar.
            based on provided conditions.
            returns True => if not similar, False => if similar
        '''
        data = dict(data)
        data['start_date'] = format_iso_date(data['start_date'])
        item_data['start_date'] = format_iso_date(item_data['start_date'])

        equal_check = ["lab", "doctor", "hospital", "profile", "start_date", "start_time"]
        subset_check = ["test_ids", "procedure_ids"]

        items_equal = True
        for key in equal_check:
            if key in item_data and key in data and str(item_data[key]) != str(data[key]):
                items_equal = False
                continue
            if key in item_data and key not in data:
                items_equal = False
                continue
            if key in data and key not in item_data:
                items_equal = False
                continue

        if not items_equal:
            return not items_equal

        for key in subset_check:
            if key in item_data and key in data:
                if not set(data[key]).issubset(set(item_data[key])):
                    items_equal = False

        return not items_equal

    @classmethod
    def validate_duplicate(cls, data, user, product_id, cart_item=None):
        '''
        This method will compare a given cart_item data to all items present in cart.
        If any duplicate item is found , it will return the same.
        '''
        existing_cart_items = Cart.objects.filter(deleted_at__isnull=True, user=user, product_id=product_id).values('id', 'data').exclude(id=cart_item)
        if existing_cart_items:
            for item in existing_cart_items:
                if not cls.compare_item_data(data, item.get("data")):
                    # if cart_item is set, we are trying to validate while updating an existing cart_item , in this case do not
                    # send the duplicate appointment back to the caller
                    if cart_item:
                        return False, None
                    else:
                        return False, cls.get_cart_item_by_id(item.get("id"))
        return True, None

    @classmethod
    def get_cart_item_by_id(cls, item_id):
        return cls.objects.filter(id=item_id).first()

    def validate(self, request):
        from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
        from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer

        self.data["cart_item"] = self.id
        if self.product_id == Order.DOCTOR_PRODUCT_ID:
            serializer = CreateAppointmentSerializer(data=self.data, context={'request': request, 'data' : self.data})
            serializer.is_valid(raise_exception=True)
        elif self.product_id == Order.LAB_PRODUCT_ID:
            serializer = LabAppointmentCreateSerializer(data=self.data, context={'request': request, 'data' : self.data})
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

    @classmethod
    def get_pg_if_pgcoupon(cls, user, cart_item=None):
        from ondoc.coupon.models import Coupon

        existing_cart_items = Cart.objects.filter(deleted_at__isnull=True, user=user).exclude(id=cart_item)
        used_coupon = []
        for item in existing_cart_items:
            if "coupon_code" in item.data:
                used_coupon.extend(item.data["coupon_code"])
        used_coupon = list(set(used_coupon))
        pg_specific_coupon = Coupon.objects.filter(code__in=used_coupon).exclude(payment_option__isnull=True).first()
        return pg_specific_coupon.payment_option if pg_specific_coupon else None

    def __str__(self):
        return str(self.id)

    @classmethod
    def check_for_insurance(cls, validated_data, request):
        from ondoc.insurance.models import UserInsurance
        user_insurance = UserInsurance.objects.filter(user=request.user).last()
        is_appointment_insured = False
        insurance_id = None
        insurance_message = ""
        cart_items = Cart.objects.filter(user=request.user, deleted_at__isnull=True)
        if user_insurance:
            is_appointment_insured, insurance_id, insurance_message = user_insurance.validate_insurance_for_cart(validated_data, cart_items)
        return is_appointment_insured, insurance_id, insurance_message
