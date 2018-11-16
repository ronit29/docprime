import datetime
from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator
from ondoc.authentication.models import UserProfile, User
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from datetime import timedelta


class Insurer(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100)
    max_float = models.PositiveIntegerField(default=None)
    min_float = models.PositiveIntegerField(default=None)
    is_disabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurer"


class InsurerFloat(auth_model.TimeStampedModel):

    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    current_float = models.PositiveIntegerField(default=None)

    def __str__(self):
        return self.insurer


    class Meta:
        db_table = "insurer_float"

    @classmethod
    def debit_float_schedule(self, insurer, amount):
        insurer_float = InsurerFloat.objects.get(insurer=insurer)
        if insurer_float:
            current_float = insurer_float.current_float
            if amount <= current_float:
                updated_current_float = current_float - amount
                insurer_float.current_float = updated_current_float
                insurer_float.save()
            else:
                return False
        else:
            return False


class InsurancePlans(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    amount = models.PositiveIntegerField(default=None)
    policy_tenure = models.PositiveIntegerField(default=None)
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
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=False)
    dob = models.DateField(blank=True, null=True)
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

    @classmethod
    def create_insured_members(self, insurance_data):
        insured_members = insurance_data.get("members")
        insurer = Insurer.objects.get(id=insurance_data.get('insurer').get('id'))
        insurance_plan_id = InsurancePlans.objects.get(id=insurance_data.get('insurance_plan').get('id'))

        list_members = []
        for member in insured_members:
            user_profile = UserProfile.objects.get(id=member.get('member_profile').get('id'))
            insured_members_obj = InsuredMembers.objects.create( first_name=member.get('first_name'),
                                                                    last_name=member.get('last_name'),
                                                                    dob=member.get('dob'), email=member.get('email'),
                                                                    relation=member.get('relation'),
                                                                    address=member.get('address'),
                                                                    pincode=member.get('pincode'),
                                                                    phone_number=member.get('member_profile').get('phone_number'),
                                                                    gender=member.get('member_profile').get('gender'),
                                                                    profile=user_profile,
                                                                    insurer=insurer,
                                                                 insurance_plan=insurance_plan_id
                                                                    )
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
    order = models.ForeignKey(account_model.Order, on_delete=models.DO_NOTHING, null=True)
    amount = models.PositiveIntegerField(default=None)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    transaction_date = models.DateTimeField(blank=True, null=True)
    status_type = models.CharField(max_length=50)
    insured_members = JSONField(blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=False, null=True, default=None)

    class Meta:
        db_table = "insurance_transaction"

    @classmethod
    def create_insurance_transaction(self, data, insured_members, order):

        insurer = Insurer.objects.get(id=data.get('insurer').id)
        insurance_plan = InsurancePlans.objects.get(id=data.get('insurance_plan').id)
        insurance_transaction_obj = InsuranceTransaction.objects.create(insurer=insurer,
                                                                insurance_plan=insurance_plan,
                                                                user=data.get('user'),
                                                                status_type=InsuranceTransaction.CREATED,
                                                                insured_members=insured_members,
                                                                amount=data.get('amount'),
                                                                order=order,
                                                                transaction_date=datetime.datetime.now(),
                                                                )

        return insurance_transaction_obj


class UserInsurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING, null=True)
    insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING, null=True)
    user = models.ForeignKey(auth_model.User, on_delete=models.DO_NOTHING)
    purchase_date = models.DateTimeField(blank=True, null=True)
    expiry_date = models.DateTimeField(blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    insurance_transaction = models.ForeignKey(InsuranceTransaction, on_delete=models.DO_NOTHING, null=True)
    insured_members = JSONField(blank=True, null=True)

    def __str__(self):
        return str(self.user)

    class Meta:
        db_table = "user_insurance"

    @classmethod
    def create_user_insurance(self, insurance_data, insured_members, insurance_transaction):
        insurer = Insurer.objects.get(id=insurance_data.get('insurer').get('id'))
        insurance_plan = InsurancePlans.objects.get(id=insurance_data.get('insurance_plan').get('id'))
        insurance_transaction_obj = InsuranceTransaction.objects.get(id=insurance_transaction.id)
        tenure = insurance_plan.policy_tenure
        expiry_date = insurance_transaction_obj.transaction_date + timedelta(days=tenure*365)
        user = User.objects.get(id=insurance_data.get('user'))
        user_insurance = UserInsurance.objects.create(insurer=insurer,
                                                      insurance_plan=insurance_plan,
                                                      user=user,
                                                      insurance_transaction=insurance_transaction_obj,
                                                      insured_members=insured_members,
                                                      policy_number=insurance_transaction.policy_number,
                                                      purchase_date=insurance_transaction.transaction_date.date(),
                                                      expiry_date=expiry_date.date()
                                                      )
        return user_insurance

