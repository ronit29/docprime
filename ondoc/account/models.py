from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel
# Create your models here.


class Order(TimeStampedModel):
    RESCHEDULE = 1
    CREATE = 2
    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, "Payment Accepted"),
        (PAYMENT_PENDING, "Payment Pending"),
    )
    ACTION_CHOICES = (("", "Select"), (RESCHEDULE, 'Reschedule'), (CREATE, "Create"))
    DOCTOR_APPOINTMENT = 1
    LAB_APPOINTMENT = 2
    product_list = ["Doctor Appointment", "Lab Appointment"]
    PRODUCT_IDS = list(enumerate(product_list, 1))
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS)
    appointment_id = models.PositiveSmallIntegerField(blank=True, null=True)
    action = models.PositiveSmallIntegerField(blank=True, null=True, choices=ACTION_CHOICES)
    action_data = JSONField(blank=True, null=True)
    amount = models.SmallIntegerField(blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    error_status = models.CharField(max_length=250, verbose_name="Error")
    is_viewable = models.BooleanField(verbose_name='Is Viewable', default=False)


    def __str__(self):
        return self.appointment_id

    class Meta:
        db_table = "order"
