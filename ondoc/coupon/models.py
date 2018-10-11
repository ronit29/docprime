from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment


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
    description = models.CharField(max_length=500, default="")

    def used_coupon_count(self, user):
        count = 0
        if str(self.type) == str(self.DOCTOR) or str(self.type) == str(self.ALL):
            count += OpdAppointment.objects.filter(user=user,
                                                   status__in=[OpdAppointment.CREATED, OpdAppointment.BOOKED,
                                                               OpdAppointment.RESCHEDULED_DOCTOR,
                                                               OpdAppointment.RESCHEDULED_PATIENT,
                                                               OpdAppointment.ACCEPTED,
                                                               OpdAppointment.COMPLETED],
                                                   coupon__code=self).count()
        if str(self.type) == str(self.LAB) or str(self.type) == str(self.ALL):
            count += LabAppointment.objects.filter(user=user,
                                                   status__in=[LabAppointment.CREATED, LabAppointment.BOOKED,
                                                               LabAppointment.RESCHEDULED_LAB,
                                                               LabAppointment.RESCHEDULED_PATIENT,
                                                               LabAppointment.ACCEPTED,
                                                               LabAppointment.COMPLETED],
                                                   coupon__code=self).count()

    def __str__(self):
        return self.code

    class Meta:
        db_table = "coupon"
