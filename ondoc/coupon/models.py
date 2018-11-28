from django.db import models
from ondoc.authentication import models as auth_model
from django.core.validators import MaxValueValidator, MinValueValidator

class Coupon(auth_model.TimeStampedModel):
    DOCTOR = 1
    LAB = 2
    ALL = 3
    TYPE_CHOICES = (("", "Select"), (DOCTOR, "Doctor"), (LAB, "Lab"), (ALL, "All"),)
    code = models.CharField(max_length=50)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percentage_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MaxValueValidator(100), MinValueValidator(0)])
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    flat_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    validity = models.PositiveIntegerField(blank=False, null=False)
    type = models.IntegerField(choices=TYPE_CHOICES)
    count = models.PositiveIntegerField()
    total_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.CharField(max_length=500, default="")
    heading = models.CharField(max_length=500, default="")
    tnc = models.CharField(max_length=2000, default="")
    lab_network = models.ForeignKey("diagnostic.LabNetwork", on_delete=models.CASCADE, blank=True, null=True)
    lab = models.ForeignKey("diagnostic.Lab", on_delete=models.CASCADE, blank=True, null=True)
    # test = models.ManyToManyField("diagnostic.LabTest", blank=True, null=True, )
    test = models.ManyToManyField("diagnostic.LabTest", blank=True, null=True)
    show_price = models.BooleanField(default=True)
    is_user_specific = models.BooleanField(default=False)
    is_corporate = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.percentage_discount == 100:
            self.show_price = False
        return super().save(*args, **kwargs)

    def used_coupon_count(self, user):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

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
        return count

    def total_used_coupon_count(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        count = 0
        if str(self.type) == str(self.DOCTOR) or str(self.type) == str(self.ALL):
            count += OpdAppointment.objects.filter(status__in=[OpdAppointment.CREATED, OpdAppointment.BOOKED,
                                                               OpdAppointment.RESCHEDULED_DOCTOR,
                                                               OpdAppointment.RESCHEDULED_PATIENT,
                                                               OpdAppointment.ACCEPTED,
                                                               OpdAppointment.COMPLETED],
                                                   coupon__code=self).count()
        if str(self.type) == str(self.LAB) or str(self.type) == str(self.ALL):
            count += LabAppointment.objects.filter(status__in=[LabAppointment.CREATED, LabAppointment.BOOKED,
                                                               LabAppointment.RESCHEDULED_LAB,
                                                               LabAppointment.RESCHEDULED_PATIENT,
                                                               LabAppointment.ACCEPTED,
                                                               LabAppointment.COMPLETED],
                                                   coupon__code=self).count()
        return count

    def __str__(self):
        return self.code

    class Meta:
        db_table = "coupon"


class UserSpecificCoupon(auth_model.TimeStampedModel):

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, null=False, related_name="user_specific_coupon")
    phone_number = models.CharField(max_length=10, blank=False, null=False)
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.coupon.code

    class Meta:
        db_table = "user_specific_coupon"
