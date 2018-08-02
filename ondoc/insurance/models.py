from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model


class Insurer(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "insurer"


class Insurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.SET_NULL, null=True)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    name = models.CharField(max_length=100)
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_profile = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "insurance"


class UserInsurance(auth_model.TimeStampedModel):
    insurance = models.ForeignKey(Insurance, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)

    class Meta:
        db_table = "user_insurance"


class ProfileInsurance(auth_model.TimeStampedModel):
    insurance = models.ForeignKey(Insurance, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    profile = models.ManyToManyField(auth_model.UserProfile)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "profile_insurance"


class PgInsurance(auth_model.TimeStampedModel):
    insurance = models.ForeignKey(Insurance, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)

    product_id = models.SmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
    order_id = models.PositiveIntegerField()
    type = models.SmallIntegerField(choices=account_model.PgTransaction.TYPE_CHOICES)

    payment_mode = models.CharField(max_length=50)
    response_code = models.IntegerField()
    bank_id = models.CharField(max_length=50)
    transaction_date = models.CharField(max_length=80)
    bank_name = models.CharField(max_length=100)
    currency = models.CharField(max_length=15)
    status_code = models.IntegerField()
    pg_name = models.CharField(max_length=100)
    status_type = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, unique=True)
    pb_gateway_name = models.CharField(max_length=100)

    class Meta:
        db_table = "pg_insurance"


# class InsuranceTransaction(auth_model.TimeStampedModel):
#
#     pass
