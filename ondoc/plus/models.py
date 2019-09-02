from django.db import models
from ondoc.authentication import models as auth_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from ondoc.account import models as account_model
from ondoc.authentication.models import UserProfile
from ondoc.common.helper import Choices
import json
from django.db import transaction


class LiveMixin(models.Model):
    def save(self, *args, **kwargs):
        if self.enabled:
            self.is_live = True
        else:
            self.is_live = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class PlusProposer(auth_model.TimeStampedModel):
    name = models.CharField(max_length=250)
    min_float = models.PositiveIntegerField(default=None)
    logo = models.ImageField('Plus Logo', upload_to='plus/images', null=True, blank=False)
    website = models.CharField(max_length=100, null=True, blank=False)
    phone_number = models.BigIntegerField(blank=False, null=True)
    email = models.EmailField(max_length=100, null=True, blank=False)
    address = models.CharField(max_length=500, null=True, blank=False, default='')
    company_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_code = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_contact_number = models.BigIntegerField(blank=False, null=True)
    gstin_number = models.CharField(max_length=50, null=True, blank=False, default='')
    signature = models.ImageField('Plus Signature', upload_to='plus/images', null=True, blank=False)
    is_live = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    plus_document = models.FileField(null=True, blank=False, upload_to='plus/documents',
                                        validators=[FileExtensionValidator(allowed_extensions=['pdf'])])

    def __str__(self):
        return "{}".format(self.name)


    @property
    def get_active_plans(self):
        return self.plus_plans.filter(is_live=True).order_by('total_allowed_members')

    @property
    def get_all_plans(self):
        return self.plus_plans.all().order_by('total_allowed_members')

    class Meta:
        db_table = 'plus_proposer'


class PlusPlans(auth_model.TimeStampedModel, LiveMixin):
    plan_name = models.CharField(max_length=300)
    proposer = models.ForeignKey(PlusProposer, related_name='plus_plans', on_delete=models.DO_NOTHING)
    internal_name = models.CharField(max_length=200, null=True)
    mrp = models.PositiveIntegerField(default=0)
    deal_price = models.PositiveIntegerField(default=0)
    tax_rebate = models.PositiveIntegerField(default=0)
    tenure = models.PositiveIntegerField(default=1)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    total_allowed_members = models.PositiveSmallIntegerField(default=0)
    is_selected = models.BooleanField(default=False)
    features = JSONField(blank=False, null=False, default=dict)

    @classmethod
    def all_active_plans(cls):
        return cls.objects.filter(is_live=True, enabled=True)

    def __str__(self):
        return "{}".format(self.plan_name)

    class Meta:
        db_table = 'plus_plans'


class PlusPlanParameters(auth_model.TimeStampedModel):
    key = models.CharField(max_length=100, null=False, blank=False)
    details = models.CharField(max_length=500, null=False, blank=False)

    def __str__(self):
        return "{}".format(self.key)

    class Meta:
        db_table = 'plus_plan_parameters'


class PlusPlanParametersMapping(auth_model.TimeStampedModel):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plan_parameters", null=False, blank=False, on_delete=models.CASCADE)
    parameter = models.ForeignKey(PlusPlanParameters, null=False, blank=False, on_delete=models.CASCADE)
    value = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return "{} - ({} : {})".format(self.plus_plan, self.parameter, self.value )

    class Meta:
        db_table = 'plus_plan_parameters_mapping'


class PlusPlanContent(auth_model.TimeStampedModel):

    class PossibleTitles(Choices):
        SALIENT_FEATURES = 'SALIENT_FEATURES'
        WHATS_NOT_COVERED = 'WHATS_NOT_COVERED'

    plan = models.ForeignKey(PlusPlans, related_name="plan_content", on_delete=models.CASCADE)
    title = models.CharField(max_length=500, blank=False, choices=PossibleTitles.as_choices())
    content = models.TextField(blank=False)

    class Meta:
        db_table = 'plus_plan_content'


class PlusThreshold(auth_model.TimeStampedModel, LiveMixin):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plus_threshold", on_delete=models.DO_NOTHING)
    opd_amount_limit = models.PositiveIntegerField(default=0)
    opd_total_free_count = models.PositiveIntegerField(default=0)
    opd_discount_count = models.PositiveIntegerField(default=0)
    opd_applicable_discount = models.PositiveIntegerField(default=0)
    lab_amount_limit = models.PositiveIntegerField(default=0)
    lab_total_free_count = models.PositiveIntegerField(default=0)
    lab_discount_count = models.PositiveIntegerField(default=0)
    lab_applicable_discount = models.PositiveIntegerField(default=0)
    package_amount_limit = models.PositiveIntegerField(default=0)
    package_count_limit = models.PositiveIntegerField(default=0)
    custom_validation = JSONField(blank=False, null=False)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    class Meta:
        db_table = 'plus_threshold'

    def __str__(self):
        return str(self.plus_plan)


class PlusUser(auth_model.TimeStampedModel):
    from ondoc.account.models import MoneyPool
    ACTIVE = 1
    CANCELLED = 2
    EXPIRED = 3
    ONHOLD = 4
    CANCEL_INITIATE = 5
    CANCELLATION_APPROVED = 6

    STATUS_CHOICES = [(ACTIVE, "Active"), (CANCELLED, "Cancelled"), (EXPIRED, "Expired"), (ONHOLD, "Onhold"),
                      (CANCEL_INITIATE, 'Cancel Initiate'), (CANCELLATION_APPROVED, "Cancellation Approved")]

    id = models.BigAutoField(primary_key=True)  # TODO Alter the sequence in the production.
    user = models.ForeignKey(auth_model.User, related_name='active_plus_users', on_delete=models.DO_NOTHING)
    plan = models.ForeignKey(PlusPlans, related_name='purchased_plus', on_delete=models.DO_NOTHING)
    purchase_date = models.DateTimeField(null=False, blank=False, default=timezone.now)
    expire_date = models.DateTimeField(null=False, blank=False)
    status = models.PositiveIntegerField(choices=STATUS_CHOICES, default=ACTIVE)
    cancel_reason = models.CharField(max_length=300, null=True, blank=True)
    order = models.ForeignKey(account_model.Order, on_delete=models.DO_NOTHING)
    amount = models.PositiveIntegerField(default=0)
    invoice = models.FileField(default=None, null=True, upload_to='plus/invoice',
                           validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    price_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True)
    matrix_lead_id = models.IntegerField(null=True)
    raw_plus_member = JSONField(blank=False, null=False, default=list)

    def is_valid(self):
        if self.expire_date >= timezone.now() and (self.status == self.ACTIVE):
            return True
        else:
            return False

    def is_appointment_valid(self, appointment_time):
        if self.expire_date >= appointment_time:
            return True
        else:
            return False

    def get_primary_member_profile(self):
        insured_members = self.plus_members.filter().order_by('id')
        proposers = list(filter(lambda member: member.is_primary_user, insured_members))
        if proposers:
            return proposers[0]

        return None

    @classmethod
    def profile_create_or_update(cls, member, user):
        profile = {}
        l_name = member.get('last_name') if member.get('last_name') else ''
        name = "{fname} {lname}".format(fname=member['first_name'], lname=l_name)
        if member['profile'] or UserProfile.objects.filter(name__iexact=name, user=user.id).exists():
            # Check whether Profile exist with same name
            existing_profile = UserProfile.objects.filter(name__iexact=name, user=user.id).first()
            if member['profile']:
                profile = member['profile']
            elif existing_profile:
                profile = existing_profile
            if profile:
                if profile.user_id == user.id:
                    profile.name = name
                    profile.email = member['email']
                    profile.gender = member['gender']
                    profile.dob = member['dob']
                    if member['relation'] == "self":
                        profile.is_default_user = True
                    else:
                        profile.is_default_user = False
                    profile.save()

                profile = profile.id
        # Create Profile if not exist with name or not exist in profile id from request
        else:
            data = {'name': name, 'email': member['email'], 'gender': member['gender'], 'user_id': user.id,
                    'dob': member['dob'], 'is_default_user': False, 'is_otp_verified': False,
                    'phone_number': user.phone_number}
            if member['is_primary_user']:
                data['is_default_user'] = True

            member_profile = UserProfile.objects.create(**data)
            profile = member_profile.id

        return profile

    @classmethod
    def get_enabled_hospitals(cls, *args, **kwargs):
        from ondoc.doctor.models import HospitalNetwork, HospitalNetworkDocument
        networks = list()
        request = kwargs.get('request')
        hospital_networks = HospitalNetwork.get_plus_enabled()
        for hospital_network in hospital_networks:
            data = {}

            hospital_network_logo = hospital_network.hospital_network_documents.filter(document_type=HospitalNetworkDocument.LOGO).first()
            data['name'] = hospital_network.name
            data['id'] = hospital_network.id
            data['logo'] = request.build_absolute_uri(hospital_network_logo.name.url) if hospital_network_logo and hospital_network_logo.name else None
            networks.append(data)

        return networks

    @classmethod
    def create_plus_user(cls, plus_data, user):
        members = plus_data['plus_members']

        for member in members:
            member['profile'] = cls.profile_create_or_update(member, user)
            member['dob'] = str(member['dob'])
            # member['profile'] = member['profile'].id if member.get('profile') else None
        plus_data['insured_members'] = members

        plus_membership_obj = cls.objects.create(plan=plus_data['insurance_plan'],
                                                          user=plus_data['user'],
                                                          raw_plus_member=json.dumps(plus_data['insured_members']),
                                                          purchase_date=plus_data['purchase_date'],
                                                          expire_date=plus_data['expiry_date'],
                                                          amount=plus_data['premium_amount'],
                                                          order=plus_data['order'])

        PlusMembers.create_plus_members(plus_membership_obj)
        return plus_membership_obj

    class Meta:
        db_table = 'plus_users'
        unique_together = (('user', 'plan'),)


class PlusTransaction(auth_model.TimeStampedModel):
    CREDIT = 1
    DEBIT = 2
    TRANSACTION_TYPE_CHOICES = ((CREDIT, 'CREDIT'), (DEBIT, "DEBIT"),)

    PLUS_PLAN_PURCHASE = 1
    PREMIUM_PAYOUT = 2

    REASON_CHOICES = ((PLUS_PLAN_PURCHASE, 'Plus Plan purchase'), (PREMIUM_PAYOUT, 'Premium payout'))

    # user_insurance = models.ForeignKey(UserInsurance,related_name='transactions', on_delete=models.DO_NOTHING)
    plus_user = models.ForeignKey(PlusUser,related_name='plus_transactions', on_delete=models.DO_NOTHING, default=None)
    # account = models.ForeignKey(InsurerAccount,related_name='transactions', on_delete=models.DO_NOTHING)
    transaction_type = models.PositiveSmallIntegerField(choices=TRANSACTION_TYPE_CHOICES)
    amount = models.PositiveSmallIntegerField(default=0)
    reason = models.PositiveSmallIntegerField(null=True, choices=REASON_CHOICES)

    def after_commit_tasks(self):
        pass

    def save(self, *args, **kwargs):
        #should never be saved again
        if self.pk:
            return

        super().save(*args, **kwargs)

        transaction_amount = int(self.amount)
        if self.transaction_type == self.DEBIT:
            transaction_amount = -1*transaction_amount

        master_policy_obj = self.user_insurance.master_policy
        account_id = master_policy_obj.insurer_account.id
        # insurer_account = InsurerAccount.objects.select_for_update().get(id=account_id)
        # insurer_account.current_float += transaction_amount
        # insurer_account.save()

        transaction.on_commit(lambda: self.after_commit_tasks())

    class Meta:
        db_table = "plus_transaction"


class PlusMembers(auth_model.TimeStampedModel):
    class Relations(Choices):
        SELF = 'SELF'
        SPOUSE = "SPOUSE"
        FATHER = "FATHER"
        MOTHER = "MOTHER"
        SON = "SON"
        DAUGHTER = "DAUGHTER"
        SPOUSE_FATHER = "SPOUSE_FATHER"
        SPOUSE_MOTHER = "SPOUSE_MOTHER"
        BROTHER = "BROTHER"
        SISTER = "SISTER"
        OTHERS = "OTHERS"

    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE, 'Male'), (FEMALE, 'Female'), (OTHER, 'Other')]
    # SELF = 'self'
    # SPOUSE = 'spouse'
    # SON = 'son'
    # DAUGHTER = 'daughter'
    # RELATION_CHOICES = [(SPOUSE, 'Spouse'), (SON, 'Son'), (DAUGHTER, 'Daughter'), (SELF, 'Self')]
    ADULT = "adult"
    CHILD = "child"
    MEMBER_TYPE_CHOICES = [(ADULT, 'adult'), (CHILD, 'child')]
    MR = 'mr.'
    MISS = 'miss'
    MRS = 'mrs.'
    MAST = 'mast.'
    TITLE_TYPE_CHOICES = [(MR, 'mr.'), (MRS, 'mrs.'), (MISS, 'miss'), (MAST, 'mast.')]
    # insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    # insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=True)
    dob = models.DateField(blank=False, null=False)
    email = models.EmailField(max_length=100, null=True)
    relation = models.CharField(max_length=50, choices=Relations.as_choices(), default=None)
    pincode = models.PositiveIntegerField(default=None)
    address = models.TextField(default=None)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, default=None)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, related_name="plus_member", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=20, choices=TITLE_TYPE_CHOICES, default=None)
    middle_name = models.CharField(max_length=50, null=True)
    town = models.CharField(max_length=100, null=False)
    district = models.CharField(max_length=100, null=False)
    state = models.CharField(max_length=100, null=False)
    state_code = models.CharField(max_length=10, default='')
    plus_user = models.ForeignKey(PlusUser, related_name="plus_members", on_delete=models.DO_NOTHING, null=False, default=None)
    city_code = models.CharField(max_length=10, blank=True, null=True, default='')
    district_code = models.CharField(max_length=10, blank=True, null=True, default='')
    is_primary_user = models.NullBooleanField()

    @classmethod
    def create_plus_members(cls, plus_user_obj):
        import json
        members = plus_user_obj.raw_plus_member
        members = json.loads(members)
        for member in members:
            user_profile = UserProfile.objects.get(id=member.get('profile'))
            insured_members_obj = cls.objects.create(first_name=member.get('first_name'), title=member.get('title'),
                                                     last_name=member.get('last_name'), dob=member.get('dob'),
                                                     email=member.get('email'), address=member.get('address'),
                                                     pincode=member.get('pincode'), phone_number=user_profile.phone_number,
                                                     gender=member.get('gender'), profile=user_profile, town=member.get('town'),
                                                     district=member.get('district'), state=member.get('state'),
                                                     state_code = member.get('state_code'), plus_user=plus_user_obj,
                                                     city_code=member.get('city_code'), district_code=member.get('district_code'))

    class Meta:
        db_table = "plus_members"