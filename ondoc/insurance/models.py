import datetime
from django.core.validators import FileExtensionValidator
from ondoc.notification.tasks import send_insurance_notifications
import json

from django.db import models, transaction
from django.db.models import Q

from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator
from ondoc.authentication.models import UserProfile, User
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from ondoc.common.helper import Choices
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from ondoc.api.v1.utils import RawSql


def generate_insurance_policy_number():
    query = '''select nextval('userinsurance_policy_num_seq') as inc'''
    seq = RawSql(query, []).fetch_all()
    sequence = None
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else None

    if sequence:
        return str('120100/12001/2018/A012708/DP%.9d' % sequence)
    else:
        raise ValueError('Sequence Produced is not valid.')


class LiveMixin(models.Model):
    def save(self, *args, **kwargs):
        if self.enabled:
            self.is_live = True
        else:
            self.is_live = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class Insurer(auth_model.TimeStampedModel, LiveMixin):
    name = models.CharField(max_length=100)
    #max_float = models.PositiveIntegerField(default=None)
    min_float = models.PositiveIntegerField(default=None)
    enabled = models.BooleanField(default=True)
    logo = models.ImageField('Insurer Logo', upload_to='insurer/images', null=True, blank=True)
    website = models.CharField(max_length=100, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True)
    email = models.EmailField(max_length=100, null=True)
    is_live = models.BooleanField(default=False)

    @property
    def get_active_plans(self):
        return self.plans.filter(is_live=True).order_by('total_allowed_members')

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurer"


class InsurerAccount(auth_model.TimeStampedModel):

    insurer = models.ForeignKey(Insurer,related_name="float", on_delete=models.CASCADE)
    current_float = models.PositiveIntegerField(default=None)

    def __str__(self):
        return str(self.insurer)

    class Meta:
        db_table = "insurer_account"

    # @classmethod
    # def debit_float_schedule(self, insurer, amount):
    #     insurer_float = InsurerAccount.objects.get(insurer=insurer)
    #     if insurer_float:
    #         current_float = insurer_float.current_float
    #         if amount <= current_float:
    #             updated_current_float = current_float - amount
    #             insurer_float.current_float = updated_current_float
    #             insurer_float.save()
    #         else:
    #             return False
    #     else:
    #         return False


class InsurancePlans(auth_model.TimeStampedModel, LiveMixin):
    insurer = models.ForeignKey(Insurer,related_name="plans", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    amount = models.PositiveIntegerField(default=0)
    policy_tenure = models.PositiveIntegerField(default=1)
    adult_count = models.SmallIntegerField(default=0)
    child_count = models.SmallIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    total_allowed_members = models.PositiveSmallIntegerField(default=0)

    @property
    def get_active_threshold(self):
        return self.threshold.filter(is_live=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurance_plans"


class InsurancePlanContent(auth_model.TimeStampedModel):

    class PossibleTitles(Choices):
        WHATS_COVERED = 'WHATS_COVERED'
        WHATS_NOT_COVERED = 'WHATS_NOT_COVERED'

    plan = models.ForeignKey(InsurancePlans,related_name="content", on_delete=models.CASCADE)
    title = models.CharField(max_length=500, blank=False, choices=PossibleTitles.as_choices())
    content = models.TextField(blank=False)

    class Meta:
        db_table = 'insurance_plan_content'
        # unique_together = (("plan", "title"),)


class InsuranceThreshold(auth_model.TimeStampedModel, LiveMixin):
    #insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)
    insurance_plan = models.ForeignKey(InsurancePlans, related_name="threshold", on_delete=models.CASCADE)
    opd_count_limit = models.PositiveIntegerField(default=0)
    opd_amount_limit = models.PositiveIntegerField(default=0)
    lab_count_limit = models.PositiveIntegerField(default=0)
    lab_amount_limit = models.PositiveIntegerField(default=0)
    min_age = models.PositiveIntegerField(default=0)
    max_age = models.PositiveIntegerField(default=0)
    child_min_age = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return str(self.insurance_plan)

    class Meta:
        db_table = "insurance_threshold"


class UserInsurance(auth_model.TimeStampedModel):
    insurance_plan = models.ForeignKey(InsurancePlans, related_name='active_users', on_delete=models.DO_NOTHING)
    user = models.ForeignKey(auth_model.User, related_name='purchased_insurance', on_delete=models.DO_NOTHING)
    purchase_date = models.DateTimeField(blank=False, null=False)
    expiry_date = models.DateTimeField(blank=False, null=False, default=timezone.now)
    policy_number = models.CharField(max_length=100, blank=False, null=False, unique=True, default=generate_insurance_policy_number)
    insured_members = JSONField(blank=False, null=False)
    premium_amount = models.PositiveIntegerField(default=0)
    order = models.ForeignKey(account_model.Order, on_delete=models.DO_NOTHING)
    coi = models.FileField(default=None, null=True, upload_to='insurance/coi', validators=[FileExtensionValidator(allowed_extensions=['pdf'])])

    def __str__(self):
        return str(self.user)

    class Meta:
        db_table = "user_insurance"

    def is_valid(self):
        if self.expiry_date >= timezone.now():
            return True
        else:
            return False


    @classmethod
    def create_user_insurance(cls, insurance_data):
        import json
        members = insurance_data['insured_members']
        for member in members:
            member['dob'] = str(member['dob'])
            member['profile'] = member['profile'].id
        insurance_data['insured_members'] = members
        user_insurance_obj = UserInsurance.objects.create(insurance_plan=insurance_data['insurance_plan'],
                                                            user=insurance_data['user'],
                                                            insured_members=json.dumps(insurance_data['insured_members']),
                                                            purchase_date=insurance_data['purchase_date'],
                                                            expiry_date=insurance_data['expiry_date'],
                                                            premium_amount=insurance_data['premium_amount'],
                                                            order=insurance_data['order'])

        insured_members = InsuredMembers.create_insured_members(user_insurance_obj)
        return user_insurance_obj

    @classmethod
    def validate_insurance(self, appointment_data):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        profile = appointment_data['profile']
        user = appointment_data['user']
        user_insurance = UserInsurance.objects.filter(user=user).first()
        if 'lab' in appointment_data:
            if user_insurance:
                if timezone.now() < user_insurance.expiry_date:
                    insured_members = user_insurance.members.all().filter(profile=profile)
                    if insured_members.exists():
                        return True, user_insurance.id, 'Covered Under Insurance'
                    else:
                        return False, user_insurance.id, 'Profile Not covered under insurance'
                else:
                    return False, user_insurance.id, 'Insurance Expired'
            else:
                return False, "", 'Not covered under insurance'
        elif 'doctor' in appointment_data:
            if user_insurance:
                if timezone.now() < user_insurance.expiry_date:
                    insured_members = user_insurance.members.all().filter(profile=profile)
                    if insured_members:
                        doctor = DoctorPracticeSpecialization.objects.get(doctor_id=appointment_data['doctor'])
                        gynecologist_list = json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS)
                        oncologist_list = json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS)
                        if doctor.specialization_id in oncologist_list or \
                                        doctor.specialization_id in gynecologist_list:
                            if doctor.specialization_id in gynecologist_list:
                                doctor_with_same_specialization = DoctorPracticeSpecialization.objects.filter(
                                    specialization_id__in=gynecologist_list).values_list(
                                    'doctor_id', flat=True)
                                opd_appointment_count = OpdAppointment.objects.filter(~Q(status=6),
                                    doctor_id__in=doctor_with_same_specialization, payment_type=3,
                                    insurance_id__isnull=False).count()
                                if opd_appointment_count >= 5:
                                    return False, user_insurance.id, 'Gynecologist Limit of 5 exceeded'
                                else:
                                    return True, user_insurance.id, 'Covered Under Insurance'
                            elif doctor.specialization_id in oncologist_list:
                                doctor_with_same_specialization = DoctorPracticeSpecialization.objects.filter(
                                    specialization_id__in=oncologist_list).values_list(
                                    'doctor_id', flat=True)
                                opd_appointment_count = OpdAppointment.objects.filter(~Q(status=6),
                                    doctor_id__in=doctor_with_same_specialization, payment_type=3,
                                    insurance_id__isnull=False).count()
                                if opd_appointment_count >= 5:
                                    return False, user_insurance.id, 'Oncologist Limit of 5 exceeded'
                                else:
                                    return True, user_insurance.id, 'Covered Under Insurance'
                        else:
                            return True, user_insurance.id, 'Covered Under Insurance'
                    else:
                        return False, user_insurance.id, 'Profile Not covered under insurance'
                else:
                    return False, user_insurance.id, 'Insurance Expired'
            else:
                return False, "", 'Not covered under insurance'


class InsuranceTransaction(auth_model.TimeStampedModel):
    CREDIT = 1
    DEBIT = 2
    TRANSACTION_TYPE_CHOICES = ((CREDIT, 'CREDIT'), (DEBIT, "DEBIT"),)

    user_insurance = models.ForeignKey(UserInsurance,related_name='transactions', on_delete=models.DO_NOTHING)
    account = models.ForeignKey(InsurerAccount,related_name='transactions', on_delete=models.DO_NOTHING)
    transaction_type = models.PositiveSmallIntegerField(choices=TRANSACTION_TYPE_CHOICES)
    amount = models.PositiveSmallIntegerField(default=0)

    def after_commit_tasks(self):
        if self.transaction_type == InsuranceTransaction.DEBIT:
            send_insurance_notifications(self.user_insurance.user.id)

    def save(self, *args, **kwargs):
        if self.pk:
            return

        super().save(*args, **kwargs)
        transaction_amount = self.amount
        if self.transaction_type == self.DEBIT:
            self.amount = -1*transaction_amount

        self.account.current_float += self.amount
        self.account.save()

        transaction.on_commit(lambda: self.after_commit_tasks())

    class Meta:
        db_table = "insurance_transaction"
        unique_together = (("user_insurance", "account", "transaction_type"),)


class InsuredMembers(auth_model.TimeStampedModel):
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE, 'Male'), (FEMALE, 'Female'), (OTHER, 'Other')]
    SELF = 'self'
    SPOUSE = 'spouse'
    SON = 'son'
    DAUGHTER = 'daughter'
    RELATION_CHOICES = [(SPOUSE, 'Spouse'), (SON, 'Son'), (DAUGHTER, 'Daughter'), (SELF, 'Self')]
    ADULT = "adult"
    CHILD = "child"
    MEMBER_TYPE_CHOICES = [(ADULT, 'adult'), (CHILD, 'child')]
    MR = 'mr.'
    MISS = 'miss'
    MRS = 'mrs.'
    TITLE_TYPE_CHOICES = [(MR, 'mr.'), (MRS, 'mrs.'), (MISS, 'miss')]
    # insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    # insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=True)
    dob = models.DateField(blank=False, null=False)
    email = models.EmailField(max_length=100, null=True)
    relation = models.CharField(max_length=50, choices=RELATION_CHOICES, default=None)
    pincode = models.PositiveIntegerField(default=None)
    address = models.TextField(default=None)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, default=None)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, related_name="insurance", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=20, choices=TITLE_TYPE_CHOICES, default=None)
    middle_name = models.CharField(max_length=50, null=True)
    town = models.CharField(max_length=100, null=False)
    district = models.CharField(max_length=100, null=False)
    state = models.CharField(max_length=100, null=False)
    user_insurance = models.ForeignKey(UserInsurance, related_name="members", on_delete=models.DO_NOTHING, null=False)

    class Meta:
        db_table = "insured_members"

    @classmethod
    def create_insured_members(cls, user_insurance):
        import json
        members = user_insurance.insured_members
        members = json.loads(members)
        for member in members:
            user_profile = UserProfile.objects.get(id=member.get('profile'))
            insured_members_obj = InsuredMembers.objects.create(first_name=member.get('first_name'),
                                                                        title=member.get('title'),
                                                                        middle_name=member.get('middle_name'),
                                                                        last_name=member.get('last_name'),
                                                                        dob=member.get('dob'), email=member.get('email'),
                                                                        relation=member.get('relation'),
                                                                        address=member.get('address'),
                                                                        pincode=member.get('pincode'),
                                                                        phone_number=user_profile.phone_number,
                                                                        gender=member.get('gender'),
                                                                        profile=user_profile,
                                                                        town=member.get('town'),
                                                                        district=member.get('district'),
                                                                        state=member.get('state'),
                                                                        user_insurance=user_insurance
                                                                        )


class Insurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.SET_NULL, null=True)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    name = models.CharField(max_length=100)
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_profile = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "insurance"


class InsuranceDisease(auth_model.TimeStampedModel):
    disease = models.CharField(max_length=100)
    enabled = models.BooleanField()
    is_live = models.BooleanField()

    class Meta:
        db_table = "insurance_disease"


class InsuranceDiseaseResponse(auth_model.TimeStampedModel):
    disease = models.ForeignKey(InsuranceDisease,related_name="affected_members", on_delete=models.SET_NULL, null=True)
    member = models.ForeignKey(InsuredMembers, related_name="diseases", on_delete=models.SET_NULL, null=True)
    response = models.BooleanField(default=False)

    class Meta:
        db_table = "insurance_disease_response"
