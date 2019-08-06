from django.db import models
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
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
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    link = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "e_consultation"
