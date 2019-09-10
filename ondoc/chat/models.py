import decimal

from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from ondoc.account.models import Order, ConsumerAccount, MoneyPool
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, User, RefundMixin


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


class ChatConsultation(TimeStampedModel, RefundMixin):
    PRODUCT_ID = Order.CHAT_PRODUCT_ID
    BOOKED = 1
    CANCELLED = 2
    STATUS_CHOICES = [(BOOKED, 'Booked'), (CANCELLED, 'Cancelled')]

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )

    PREPAID = 1
    PAY_CHOICES = [(PREPAID, 'Prepaid')]

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
    payment_type = models.PositiveSmallIntegerField(choices=PAY_CHOICES, default=PREPAID)

    class Meta:
        db_table = "chat_consultation"

    @property
    def promotional_amount(self):
        promotional_amount = decimal.Decimal(0)
        if self.extra_details and self.extra_details.get('promotional_amount'):
            return decimal.Decimal(self.extra_details.get('promotional_amount'))

        return promotional_amount

    @transaction.atomic
    def action_cancelled(self, refund_flag=1):
        old_instance = ChatConsultation.objects.get(pk=self.id)
        if old_instance.status != self.CANCELLED:
            self.status = self.CANCELLED
            self.save()
            initiate_refund = True
            self.action_refund(refund_flag, initiate_refund)

    def get_cancellation_breakup(self):
        wallet_refund = cashback_refund = 0
        if self.money_pool:
            wallet_refund, cashback_refund = self.money_pool.get_refund_breakup(self.amount)
        elif self.price_data:
            wallet_refund = self.price_data["wallet_amount"]
            cashback_refund = self.price_data["cashback_amount"]
        else:
            wallet_refund = self.effective_price

        return wallet_refund, cashback_refund