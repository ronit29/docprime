from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.account.models import Order
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor, Hospital, OpdAppointment
from ondoc.coupon.models import Coupon
from django.contrib.postgres.fields import JSONField


class Cart(auth_model.TimeStampedModel):

    product_id = models.IntegerField(choices=Order.PRODUCT_IDS)
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE)
    data = JSONField()

    def __str__(self):
        return str(self.id)
