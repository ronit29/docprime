from django.db import models
from ondoc.authentication import models as auth_model


class Coupon(auth_model.TimeStampedModel):
    DOCTOR = 1
    LAB = 2
    ALL = 3
    TYPE_CHOICES = (("", "Select"), (DOCTOR, "Doctor"), (LAB, "Lab"), (ALL, "All"),)
    code = models.CharField(max_length=50)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percentage_discount = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    flat_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    validity = models.PositiveIntegerField(blank=True, null=True)
    type = models.IntegerField(choices=TYPE_CHOICES)
    count = models.PositiveIntegerField()

    def __str__(self):
        return self.coupon_code.name + " (" + self.name + ")"

    class Meta:
        db_table = "coupon"
