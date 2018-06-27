from django.db import models
from ondoc.authentication import models as auth_model

from django.utils import timezone


class Outstanding(auth_model.TimeStampedModel):
    HOSPITAL_NETWORK_LEVEL = 0
    HOSPITAL_LEVEL = 1
    DOCTOR_LEVEL = 2
    LAB_NETWORK_LEVEL = 3
    LAB_LEVEL = 4
    level_list = ["Hospital Network Level", "Hospital Level", "Doctor Level", "Lab Network Level", "Lab Level"]
    LEVEL_CHOICES = list(enumerate(level_list))
    net_hos_doc_id = models.IntegerField()
    outstanding_level = models.IntegerField(choices=LEVEL_CHOICES)
    current_month_outstanding = models.DecimalField(max_digits=10, decimal_places=2)
    previous_month_outstanding = models.DecimalField(max_digits=10, decimal_places=2)
    paid_by_pb = models.DecimalField(max_digits=10, decimal_places=2)
    paid_to_pb = models.DecimalField(max_digits=10, decimal_places=2)
    outstanding_month = models.PositiveSmallIntegerField(max_length=12)
    outstanding_year = models.IntegerField()

    class Meta:
        db_table = "outstanding"
        unique_together = ("net_hos_doc_id", "outstanding_level", "outstanding_month", "outstanding_year")

    @classmethod
    def create_outstanding(cls, app_obj):
        obj, out_level = auth_model.UserPermission.doc_hospital_admin(app_obj)
        now = timezone.now()
        present_month, present_year = now.month, now.year
        out_obj = Outstanding.objects.get(net_hos_doc_id=obj.id, outstanding_level=out_level,
                                          outstanding_month=present_month, outstanding_year=present_year)
        app_outstanding_fees = app_obj.doc_payout_amount()
        if out_obj.exist():
            out_obj.current_month_outstanding += app_outstanding_fees
            out_obj.save()
        else:

            pass


class Payout(auth_model.TimeStampedModel):
    PG = 0
    CASH = 1
    CHEQUE = 2
    payment_list = ["PG", "Cash", "Cheque"]
    PAYMENT = list(enumerate(payment_list))
    net_hos_doc_id = models.IntegerField()
    payout_level = models.PositiveSmallIntegerField(choices=Outstanding.LEVEL_CHOICES)
    payment_type = models.PositiveSmallIntegerField(choices=PAYMENT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "payout"


class NetworkOutstandingManager(models.Manager):
    def get_queryset(self):
        return super(NetworkOutstandingManager, self).get_queryset().filter(outstanding_level=Outstanding.NETWORK_LEVEL)

    def create(self, **kwargs):
        kwargs.update({'outstanding_level': Outstanding.NETWORK_LEVEL})
        return super(NetworkOutstandingManager, self).create(**kwargs)


class NetworkOutstanding(Outstanding):
    objects = NetworkOutstandingManager()

    class Meta:
        proxy = True


class HospitalOutstandingManager(models.Manager):
    def get_queryset(self):
        return super(HospitalOutstandingManager, self).get_queryset().filter(outstanding_level=Outstanding.HOSPITAL_LEVEL)

    def create(self, **kwargs):
        kwargs.update({'outstanding_level': Outstanding.HOSPITAL_LEVEL})
        return super(HospitalOutstandingManager, self).create(**kwargs)


class HospitalOutstanding(Outstanding):
    objects = HospitalOutstandingManager()

    class Meta:
        proxy = True


class DoctorOutstandingManager(models.Manager):
    def get_queryset(self):
        return super(DoctorOutstandingManager, self).get_queryset().filter(outstanding_level=Outstanding.DOCTOR_LEVEL)

    def create(self, **kwargs):
        kwargs.update({'outstanding_level': Outstanding.DOCTOR_LEVEL})
        return super(DoctorOutstandingManager, self).create(**kwargs)


class DoctorOutstanding(Outstanding):
    objects = DoctorOutstandingManager()

    class Meta:
        proxy = True

