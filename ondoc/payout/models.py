from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.api.v1.utils import get_previous_month_year

from django.utils import timezone


class Outstanding(auth_model.TimeStampedModel):
    HOSPITAL_NETWORK_LEVEL = 0
    HOSPITAL_LEVEL = 1
    DOCTOR_LEVEL = 2
    LAB_NETWORK_LEVEL = 3
    LAB_LEVEL = 4
    # LEVEL_CHOICES = list(enumerate(level_list))
    LEVEL_CHOICES = [(HOSPITAL_NETWORK_LEVEL, "Hospital Network Level"), (HOSPITAL_LEVEL, "Hospital Level"),
                     (DOCTOR_LEVEL, "Doctor Level"), (LAB_NETWORK_LEVEL, "Lab Network Level"), (LAB_LEVEL, "Lab Level")]
    net_hos_doc_id = models.IntegerField()
    outstanding_level = models.IntegerField(choices=LEVEL_CHOICES)
    current_month_outstanding = models.DecimalField(max_digits=10, decimal_places=2)
    previous_month_outstanding = models.DecimalField(max_digits=10, decimal_places=2)
    paid_by_pb = models.DecimalField(max_digits=10, decimal_places=2)
    paid_to_pb = models.DecimalField(max_digits=10, decimal_places=2)
    outstanding_month = models.PositiveSmallIntegerField()
    outstanding_year = models.IntegerField()

    class Meta:
        db_table = "outstanding"
        unique_together = ("net_hos_doc_id", "outstanding_level", "outstanding_month", "outstanding_year")

    @classmethod
    def create_outstanding(cls, billing_level_obj, out_level, app_outstanding_fees):
        # obj, out_level = auth_model.UserPermission.doc_hospital_admin(app_obj)
        now = timezone.now()
        present_month, present_year = now.month, now.year
        out_obj = None
        try:
            out_obj = Outstanding.objects.get(net_hos_doc_id=billing_level_obj.id, outstanding_level=out_level,
                                              outstanding_month=present_month, outstanding_year=present_year)
        except:
            pass
        # app_outstanding_fees = app_obj.doc_payout_amount()
        if out_obj:
            out_obj.current_month_outstanding += app_outstanding_fees
            out_obj.save()
        else:
            month, year = get_previous_month_year(present_month, present_year)
            prev_out_obj = None
            try:
                prev_out_obj = Outstanding.objects.get(net_hos_doc_id=billing_level_obj.id, outstanding_level=out_level,
                                                       outstanding_month=month, outstanding_year=year)
            except:
                pass
            previous_month_outstanding = 0
            if prev_out_obj:
                previous_month_outstanding = (prev_out_obj.current_month_outstanding +
                                              prev_out_obj.previous_month_outstanding - prev_out_obj.paid_by_pb +
                                              prev_out_obj.paid_to_pb)

            outstanding_data = {
                "net_hos_doc_id": obj.id,
                "outstanding_level": out_level,
                "current_month_outstanding": app_outstanding_fees,
                "previous_month_outstanding": previous_month_outstanding,
                "paid_by_pb": 0,
                "paid_to_pb": 0,
                "outstanding_month": present_month,
                "outstanding_year": present_year
            }
            out_obj = Outstanding.objects.create(**outstanding_data)
            return out_obj

    @classmethod
    def get_month_billing(cls, prev_obj, present_obj):
        prev_out = prev_payed_by_pb = prev_payed_to_pb = 0
        if prev_obj is not None:
            prev_out = prev_obj.current_month_outstanding
            prev_payed_by_pb = prev_obj.paid_by_pb
            prev_payed_to_pb = prev_obj.paid_to_pb
        total_out = (present_obj.current_month_outstanding + present_obj.previous_month_outstanding -
                     present_obj.paid_by_pb + present_obj.paid_to_pb)
        resp_data = {
            "previous_outstanding": prev_out,
            "previous_payed_by_pb": prev_payed_by_pb,
            "previous_payed_to_pb": prev_payed_to_pb,
            "current_outstanding": present_obj.current_month_outstanding,
            "total_outstanding": total_out,
            "current_month": present_obj.outstanding_month,
            "current_year": present_obj.outstanding_year,
            "outstanding_level": present_obj.outstanding_level
        }
        return resp_data


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

