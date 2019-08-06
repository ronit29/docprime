from django.db import models, transaction
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.common import models as common_models
from ondoc.account import models as acct_mdoels
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField

# Create your models here.


class EConsultation(auth_models.TimeStampedModel, auth_models.CreatedByModel):

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )

    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7
    EXPIRED = 8
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_DOCTOR, 'Rescheduled by Doctor'),
                      (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed'), (EXPIRED, 'Expired')]

    doctor = models.ForeignKey(doc_models.Doctor, on_delete=models.SET_NULL, null=True)
    offline_patient = models.ForeignKey(doc_models.OfflinePatients, on_delete=models.SET_NULL, null=True)
    online_patient = models.ForeignKey(auth_models.UserProfile, on_delete=models.SET_NULL, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2)
    validity = models.PositiveIntegerField(null=True, blank=True)
    link = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)

    #payment Fields
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    refund_details = GenericRelation(common_models.RefundDetails, related_query_name="reconsult_refund_details")
    coupon_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(acct_mdoels.MoneyPool, on_delete=models.SET_NULL, null=True, related_name='econsult_pool')
    price_data = JSONField(blank=True, null=True)
    merchant_payout = models.ForeignKey(acct_mdoels.MerchantPayout, related_name="econsultations", on_delete=models.SET_NULL, null=True)

    @classmethod
    def update_consultation(self, data):
        self.payment_status = self.PAYMENT_ACCEPTED

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "e_consultation"
