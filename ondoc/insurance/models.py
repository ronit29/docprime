import datetime
from django.core.validators import FileExtensionValidator
from ondoc.notification.tasks import send_insurance_notifications
import json

from django.db import models, transaction
from django.db.models import Q
import logging
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator
from ondoc.authentication.models import UserProfile, User
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from ondoc.common.helper import Choices
from django.core.files.uploadedfile import TemporaryUploadedFile
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from ondoc.api.v1.utils import RawSql
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.template.loader import render_to_string
from num2words import num2words
from hardcopy import bytestring_to_pdf

logger = logging.getLogger(__name__)


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
    logo = models.ImageField('Insurer Logo', upload_to='insurer/images', null=True, blank=False)
    website = models.CharField(max_length=100, null=True, blank=False)
    phone_number = models.BigIntegerField(blank=False, null=True)
    email = models.EmailField(max_length=100, null=True, blank=False)
    address = models.CharField(max_length=500, null=True, blank=False, default='')
    company_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_code = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_contact_number = models.BigIntegerField(blank=False, null=True)
    gstin_number = models.CharField(max_length=50, null=True, blank=False, default='')
    signature = models.ImageField('Insurer Signature', upload_to='insurer/images', null=True, blank=False)
    is_live = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)

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

    def generate_pdf(self):
        insured_members = self.members.filter().order_by('id')
        proposer = list(filter(lambda member: member.relation.lower() == 'self', insured_members))
        proposer = proposer[0]

        proposer_fname = proposer.first_name if proposer.first_name else ""
        proposer_mname = proposer.middle_name if proposer.middle_name else ""
        proposer_lname = proposer.last_name if proposer.last_name else ""

        proposer_name = '%s %s %s %s' % (proposer.title, proposer_fname, proposer_mname, proposer_lname)

        member_list = list()
        count = 1
        for member in insured_members:
            fname = member.first_name if member.first_name else ""
            mname = member.middle_name if member.middle_name else ""
            lname = member.last_name if member.last_name else ""

            name = '%s %s %s' % (fname, mname, lname)
            data = {
                'name': name.title(),
                'member_number': count,
                'dob': member.dob.strftime('%d-%m-%Y'),
                'relation': member.relation.title(),
                'id': member.id,
                'gender': member.gender.title(),
                'age': int((datetime.datetime.now().date() - member.dob).days/365),
            }
            member_list.append(data)
            count = count + 1

        context = {
            'purchase_data': str(self.purchase_date.date().strftime('%d-%m-%Y')),
            'expiry_date': str(self.expiry_date.date().strftime('%d-%m-%Y')),
            'premium': self.premium_amount,
            'premium_in_words': ('%s rupees only.' % num2words(self.premium_amount)).title(),
            'proposer_name': proposer_name.title(),
            'proposer_address': '%s, %s, %s, %s, %d' % (proposer.address, proposer.town, proposer.district, proposer.state, proposer.pincode),
            'proposer_mobile': proposer.phone_number,
            'proposer_email': proposer.email,
            'intermediary_name': self.insurance_plan.insurer.intermediary_name,
            'intermediary_code': self.insurance_plan.insurer.intermediary_code,
            'intermediary_contact_number': self.insurance_plan.insurer.intermediary_contact_number,
            'issuing_office_address': self.insurance_plan.insurer.address,
            'issuing_office_gstin': self.insurance_plan.insurer.gstin_number,
            'group_policy_name': 'Docprime Technologies Pvt. Ltd.',
            'group_policy_address': 'Plot No. 119, Sector 44, Gurugram, Haryana 122001',
            'group_policy_email': 'customercare@docprime.com',
            'nominee_name': '',
            'nominee_relation': '',
            'nominee_address': '',
            'policy_related_email': '%s and customercare@docprime.com' % self.insurance_plan.insurer.email,
            'policy_related_tollno': '%d and 18001239419' % self.insurance_plan.insurer.intermediary_contact_number,
            'policy_related_website': '%s and https://docprime.com' % self.insurance_plan.insurer.website,
            'current_date': datetime.datetime.now().date().strftime('%d-%m-%Y'),
            'policy_number': self.policy_number,
            'application_number': self.id,
            'total_member_covered': len(member_list),
            'plan': self.insurance_plan.name,
            'insured_members': member_list,
            'insurer_logo': self.insurance_plan.insurer.logo.url,
            'insurer_signature': self.insurance_plan.insurer.signature.url
        }
        html_body = render_to_string("pdfbody.html", context=context)
        filename = "COI_{}.pdf".format(str(timezone.now().timestamp()))
        try:
            extra_args = {
                'virtual-time-budget': 6000
            }
            file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
            f = open(file.temporary_file_path())
            bytestring_to_pdf(html_body.encode(), f, **extra_args)
            f.seek(0)
            f.flush()
            f.content_type = 'application/pdf'

            self.coi = InMemoryUploadedFile(file, None, filename, 'application/pdf', file.tell(), None)
            self.save()
        except Exception as e:
            logger.error("Got error while creating pdf for opd invoice {}".format(e))

    class Meta:
        db_table = "user_insurance"

    def is_valid(self):
        if self.expiry_date >= timezone.now():
            return True
        else:
            return False

    @classmethod
    def profile_create_or_update(cls, member, user):
        profile = {}
        name = "{fname} {lname}".format(fname=member['first_name'], lname=member['last_name'])
        if member['profile'] or UserProfile.objects.filter(name__iexact=name, user=user.id).exists():
            # Check whether Profile exist with same name
            existing_profile = UserProfile.objects.filter(name__iexact=name, user=user.id).first()
            if member['profile']:
                profile = member['profile']
            elif existing_profile:
                profile = existing_profile.id
            if profile:
                if profile.get('user_id') == user.id:
                    member_profile = profile.update(name=name, email=member['email'], gender=member['gender'],
                                                    dob=member['dob'])
        # Create Profile if not exist with name or not exist in profile id from request
        else:
            member_profile = UserProfile.objects.create(name=name,
                                                        email=member['email'], gender=member['gender'],
                                                        user_id=user.id, dob=member['dob'],
                                                        is_default_user=False, is_otp_verified=False,
                                                        phone_number=user.phone_number)
            profile = member_profile.id

        return profile

    @classmethod
    def create_user_insurance(cls, insurance_data, user):
        members = insurance_data['insured_members']
        for member in members:
            member['profile'] = UserInsurance.profile_create_or_update(member, user)
            member['dob'] = str(member['dob'])
            # member['profile'] = member['profile'].id if member.get('profile') else None
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
        user_insurance = UserInsurance.objects.filter(user=user).last()
        if 'lab' in appointment_data:
            if user_insurance:
                if user_insurance.is_valid():
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
                if user_insurance.is_valid():
                    insured_members = user_insurance.members.all().filter(profile=profile)
                    if insured_members:
                        doctor = DoctorPracticeSpecialization.objects.filter(doctor_id=appointment_data['doctor']).values('specialization_id')
                        specilization_ids = doctor
                        specilization_ids_set = set(map(lambda specialization: specialization['specialization_id'], specilization_ids))
                        gynecologist_list = json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS)
                        gynecologist_set = set(gynecologist_list)
                        oncologist_list = json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS)
                        oncologist_set = set(oncologist_list)
                        if (specilization_ids_set & oncologist_set) or (specilization_ids_set & gynecologist_set):
                            if specilization_ids_set & gynecologist_set :
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
                            elif specilization_ids_set & oncologist_set:
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
            self.user_insurance.generate_pdf()
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
