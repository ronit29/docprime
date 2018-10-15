from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator


class Insurer(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100)
    is_disabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurer"


class InsurerFloat(auth_model.TimeStampedModel):

    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    max_float = models.PositiveIntegerField(default=None)
    current_float = models.PositiveIntegerField(default=None)

    def __str__(self):
        return self.insurer


    class Meta:
        db_table = "insurer_float"

class InsurancePlans(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    amount = models.PositiveIntegerField(default=None)
    is_disabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return self.type

    class Meta:
        db_table = "insurance_plans"


class InsuranceThreshold(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.CASCADE)
    opd_count_limit = models.PositiveIntegerField(default=None)
    opd_amount_limit = models.PositiveIntegerField(default=None)
    lab_count_limit = models.PositiveIntegerField(default=None)
    lab_amount_limit = models.PositiveIntegerField(default=None)
    min_age = models.PositiveIntegerField(default=None)
    max_age = models.PositiveIntegerField(default=None)
    child_min_age = models.PositiveIntegerField(default=None)
    tenure = models.PositiveIntegerField(default=None)
    is_disabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return str(self.insurer)

    class Meta:
        db_table = "insurance_threshold"


class InsuredMembers(auth_model.TimeStampedModel):
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE, 'Male'), (FEMALE, 'Female'), (OTHER, 'Other')]
    SELF = 'self'
    HUSBAND = 'husband'
    WIFE = 'wife'
    SON = 'son'
    DAUGHTER = 'daughter'
    RELATION_CHOICES = [(HUSBAND, 'Husband'), (WIFE, 'Wife'), (SON, 'Son'), (DAUGHTER, 'Daughter'), (SELF, 'Self')]
    ADULT = "adult"
    CHILD = "child"
    MEMBER_TYPE_CHOICES = [(ADULT, 'adult'), (CHILD, 'child')]
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=False)
    dob = models.DateTimeField(null=False)
    email = models.EmailField(max_length=100)
    relation = models.CharField(max_length=50, choices=RELATION_CHOICES)
    pincode = models.PositiveIntegerField(default=None)
    address = models.TextField(default=None)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, null=True, blank=True, default=None)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, on_delete=models.SET_NULL, null=True)


    class Meta:
        db_table = "insured_members"


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
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING, null=True)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING, null=True)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)

    class Meta:
        db_table = "user_insurance"


# class ProfileInsurance(auth_model.TimeStampedModel):
#     insurance = models.ForeignKey(Insurance, on_delete=models.DO_NOTHING)
#     user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
#     profile = models.ManyToManyField(auth_model.UserProfile)
#     product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
#     insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)
#
#     class Meta:
#         db_table = "profile_insurance"


class InsuranceTransaction(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
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
        db_table = "insurance_transaction"
