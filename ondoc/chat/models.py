from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.account.models import Order, ConsumerAccount, MoneyPool
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, User


class ChatMedicalCondition(TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Name")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "chat_medical_condition"


class ChatPrescription(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    file = models.FileField(upload_to='chat/prescription', blank=False, null=False)

    class Meta:
        db_table = "chat_prescription"


class ChatConsultation(TimeStampedModel):
    PRODUCT_ID = Order.CHAT_PRODUCT_ID
    BOOKED = 1
    STATUS_CHOICES = [(BOOKED, 'Booked')]

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )

    id = models.BigAutoField(primary_key=True)
    plan_id = models.PositiveIntegerField(default=1)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="chat_consultation")
    status = models.PositiveSmallIntegerField(default=BOOKED, choices=STATUS_CHOICES)
    extra_details = JSONField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    effective_price = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    price_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "chat_consultation"
