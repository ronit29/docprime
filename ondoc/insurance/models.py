from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from ondoc.account.models import Order


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

    def debit_float_schedule(self, insurer, amount):
        insurer_float = InsurerFloat.objects.filter(insurer=insurer).first()
        current_float = insurer_float.current_float
        if amount >= current_float:
            updated_current_float = current_float - amount
        insurer_float.update(current_float=updated_current_float)

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
    hypertension = models.NullBooleanField(blank=True, null=True)
    diabetes = models.NullBooleanField(blank=True, null=True)
    liver_disease = models.NullBooleanField(blank=True, null=True)
    heart_disease = models.NullBooleanField(blank=True, null=True)

    class Meta:
        db_table = "insured_members"

    def create_insured_members(self, insurance_data):
        insured_members = insurance_data.get("members")
        list_members = []
        for member in insured_members:
            insured_members_obj = InsuredMembers.create(insurer=insurance_data.get('insurer'), **member)
            insured_members_obj.save()
            list_members.append(model_to_dict(insured_members_obj))
        members_data = {"members": list_members}
        return members_data


class Insurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.SET_NULL, null=True)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    name = models.CharField(max_length=100)
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_profile = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "insurance"


class InsuranceTransaction(auth_model.TimeStampedModel):
    CREATED = 1
    COMPLETED = 2
    FAILED = 3
    STATUS_CHOICES = [(CREATED, 'Created'), (COMPLETED, 'Completed'),
                      (FAILED, 'Failed')]
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
    order_id = models.ForeignKey(Order, on_delete=models.DO_NOTHING)
    amount = models.PositiveIntegerField(null=True)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    status_type = models.CharField(max_length=50)
    insured_members = JSONField(blank=True, null=True)

    class Meta:
        db_table = "insurance_transaction"

    def create_insurance_transaction(self, order, insured_members):
        insurance_data = order.action_data
        insurance_transaction_obj = InsuranceTransaction.create(insurer=insurance_data.get('insurer'),
                                                                insurance_plan=insurance_data.get('insurance_plan'),
                                                                user=insurance_data.get('user'),
                                                                order_id=order.id, amount=order.amount,
                                                                status_type=InsuranceTransaction.CREATED,
                                                                insured_members=insured_members)
        insurance_transaction_obj.save()
        return insurance_transaction_obj


class UserInsurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING, null=True)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING, null=True)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    insurance_transaction = models.ForeignKey(InsuranceTransaction, on_delete=models.DO_NOTHING, null=True)
    insured_members = JSONField(blank=True, null=True)

    class Meta:
        db_table = "user_insurance"

    def create_user_insurance(self, insurance_data, insured_members, insurance_transaction):
        user_insurance = UserInsurance.create(insurer=insurance_data.get('insurer'),
                                              insurance_plan=insurance_data.get('insurance_plan'),
                                              user=insurance_data.get('user'),
                                              insurance_transaction=insurance_transaction,
                                              insured_members=insured_members)
        user_insurance.save()
        return user_insurance

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



