from django.db import models
from ondoc.authentication import models as auth_model
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
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
from django.db.models import Q
from ondoc.common.models import DocumentsProofs
from ondoc.notification.tasks import push_plus_lead_to_matrix
from .enums import PlanParametersEnum
from datetime import datetime
from django.utils.timezone import utc
import reversion
from django.conf import settings
from django.utils.functional import cached_property


class LiveMixin(models.Model):
    def save(self, *args, **kwargs):
        if self.enabled:
            self.is_live = True
        else:
            self.is_live = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


@reversion.register()
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
    merchant_code = models.CharField(blank=False, null=True, max_length=100)

    def __str__(self):
        return "{}".format(self.name)


    @property
    def get_active_plans(self):
        return self.plus_plans.filter(is_live=True).order_by('id')

    @property
    def get_all_plans(self):
        return self.plus_plans.all().order_by('total_allowed_members')

    class Meta:
        db_table = 'plus_proposer'


@reversion.register()
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
    key = models.CharField(max_length=100, null=False, blank=False, choices=PlanParametersEnum.as_choices())
    details = models.CharField(max_length=500, null=False, blank=False)

    def __str__(self):
        return "{}".format(self.key)

    class Meta:
        db_table = 'plus_plan_parameters'


@reversion.register()
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
        proposers = list(filter(lambda member: member.is_primary_user and member.relation == PlusMembers.Relations.SELF, insured_members))
        if proposers:
            return proposers[0]

        return None

    @cached_property
    def get_utilization(self):
        plan = self.plan
        resp = {}
        data = {}
        plan_parameters = plan.plan_parameters.filter(parameter__key__in=[PlanParametersEnum.DOCTOR_CONSULT_AMOUNT,
                                                                               PlanParametersEnum.ONLINE_CHAT_AMOUNT,
                                                                               PlanParametersEnum.HEALTH_CHECKUPS_AMOUNT,
                                                                               PlanParametersEnum.HEALTH_CHECKUPS_COUNT,
                                                                               PlanParametersEnum.MEMBERS_COVERED_IN_PACKAGE,
                                                                               PlanParametersEnum.PACKAGE_IDS,
                                                                               PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE])

        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value
        
        resp['allowed_package_ids'] = list(map(lambda x: int(x), data['package_ids'].split(','))) if data.get('package_ids') else []
        resp['doctor_consult_amount'] = int(data['DOCTOR_CONSULT_AMOUNT'.lower()])
        resp['doctor_amount_utilized'] = self.get_doctor_plus_appointment_amount()
        resp['doctor_amount_available'] = resp['doctor_consult_amount'] - resp['doctor_amount_utilized']
        resp['members_count_online_consultation'] = data['MEMBERS_COVERED_IN_PACKAGE'.lower()]
        resp['total_package_amount_limit'] = int(data['HEALTH_CHECKUPS_AMOUNT'.lower()])
        resp['total_package_count_limit'] = int(data['HEALTH_CHECKUPS_COUNT'.lower()])

        resp['available_package_amount'] = resp['total_package_amount_limit'] - int(self.get_package_plus_appointment_amount())
        resp['available_package_count'] = resp['total_package_count_limit'] - int(self.get_package_plus_appointment_count())

        return resp

    def update_doctor_utilization(self, appointment_obj):
        pass
        # mrp = appointment_obj.mrp
        # user = self.user
        # plan = self.plan
        # plan_parameters = plan.plan_parameters
        # utilization = self.get_utilization()

    def validate_plus_appointment(self, appointment_data):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        response_dict = {
            'is_vip_member': False,
            'plus_user_id': None,
            'cover_under_vip': "",
            "vip_amount": 0
        }

        OPD = "OPD"
        LAB = "LAB"

        appointment_type = OPD if "doctor" in appointment_data else LAB

        if appointment_data.get('payment_type') == OpdAppointment.COD:
            return response_dict
        profile = appointment_data.get('profile', None)
        user = profile.user
        plus_user = user.active_plus_user
        if not plus_user:
            return response_dict
        plus_members = plus_user.plus_members.all().filter(profile=profile)
        if not plus_members.exists():
            return response_dict

        response_dict['is_vip_member'] = True
        utilization = plus_user.get_utilization
        price_data = OpdAppointment.get_price_details(appointment_data) if appointment_type == OPD else LabAppointment.get_price_details(appointment_data)

        amount_available = int(utilization.get('doctor_amount_available', 0)) if appointment_type == OPD else int(utilization.get('available_package_amount', 0))
        is_cover_after_utilize = True
        amount_paid = 0

        mrp = int(price_data.get('mrp'))
        if amount_available > 0 or mrp <= amount_available:
            is_cover_after_utilize = True
        else:
            is_cover_after_utilize = False

        if is_cover_after_utilize and amount_available >= mrp:
            amount_paid = 0

        elif is_cover_after_utilize and (amount_available > 0) and (amount_available <= mrp):
            amount_paid = mrp - amount_available
        else:
            amount_paid = 0
        response_dict['vip_amount'] = amount_paid

        if appointment_type == OPD:
            doctor = appointment_data['doctor']
            hospital = appointment_data['hospital']
            if doctor.enabled_for_online_booking and hospital.enabled_for_online_booking and \
                                        hospital.enabled_for_prepaid and hospital.enabled_for_plus_plans and \
                                        doctor.enabled_for_plus_plans and is_cover_after_utilize:

                response_dict['cover_under_vip'] = True
                response_dict['plus_user_id'] = plus_user.id

        elif appointment_type == LAB:
            lab = appointment_data['lab']
            if lab and lab.enabled_for_plus_plans and is_cover_after_utilize:

                response_dict['cover_under_vip'] = True
                response_dict['plus_user_id'] = plus_user.id

        return response_dict

    def get_package_plus_appointment_count(self):
        from ondoc.diagnostic.models import LabAppointment
        package_count = 0
        lab_appointments = LabAppointment.objects.filter(plus_plan=self).exclude(status=LabAppointment.CANCELLED)
        if not lab_appointments:
            return 0

        for lab_appointment in lab_appointments:
            package_count = package_count + len(list(filter(lambda lab_test: lab_test.test.is_package, lab_appointment.test_mappings.all())))
        return package_count

    def get_package_plus_appointment_amount(self):
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.doctor.models import OpdAppointment

        import functools
        package_amount = 0
        lab_appointments = LabAppointment.objects.filter(plus_plan=self).exclude(status=OpdAppointment.CANCELLED)
        if not lab_appointments:
            return 0
        for lab_appointment in lab_appointments:
            pacakge_appointments = list(filter(lambda lab_test_mapping: lab_test_mapping.test.is_package, lab_appointment.test_mappings.all()))
            lab_appointments_mrp = list(map(lambda appointment: appointment.mrp, pacakge_appointments))
            package_amount = package_amount + functools.reduce(lambda a, b: a + b, lab_appointments_mrp)

        return package_amount

    def get_doctor_plus_appointment_amount(self):
        import functools
        from ondoc.doctor.models import OpdAppointment
        total_mrp = 0
        opd_appointments = OpdAppointment.objects.filter(plus_plan=self).exclude(status=OpdAppointment.CANCELLED)
        if not opd_appointments:
            return 0

        opd_appointments_mrp = list(map(lambda appointment:appointment.mrp, opd_appointments))
        total_mrp = functools.reduce(lambda a, b: a + b, opd_appointments_mrp)
        return total_mrp

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
                    # profile.gender = member['gender']
                    profile.dob = member['dob']
                    if member['relation'] == PlusMembers.Relations.SELF:
                        profile.is_default_user = True
                    else:
                        profile.is_default_user = False
                    profile.save()

                profile = profile.id
        # Create Profile if not exist with name or not exist in profile id from request
        else:
            data = {'name': name, 'email': member['email'], 'user_id': user.id,
                    'dob': member['dob'], 'is_default_user': False, 'is_otp_verified': False,
                    'phone_number': user.phone_number}
            if member['relation'] == PlusMembers.Relations.SELF:
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

        plus_membership_obj = cls.objects.create(plan=plus_data['plus_plan'],
                                                          user=plus_data['user'],
                                                          raw_plus_member=json.dumps(plus_data['plus_members']),
                                                          purchase_date=plus_data['purchase_date'],
                                                          expire_date=plus_data['expire_date'],
                                                          amount=plus_data['amount'],
                                                          order=plus_data['order'])

        PlusMembers.create_plus_members(plus_membership_obj)
        PlusUserUtilization.create_utilization(plus_membership_obj)
        return plus_membership_obj

    def activate_care_membership(self):
        from ondoc.subscription_plan.models import Plan, UserPlanMapping
        plan = Plan.objects.filter(id=settings.CARE_PLAN_FOR_VIP).first()
        if not plan:
            return

        extra_details = {"id": plan.id,
                         "name": plan.name,
                         "mrp": str(plan.mrp),
                         "deal_price": str(plan.deal_price),
                         "payable_amount": str(0),
                         'via': 'VIP_MEMBERSHIP',
                         "unlimited_online_consultation": plan.unlimited_online_consultation,
                         "priority_queue": plan.priority_queue,
                         "features": [{"id": feature_mapping.feature.id, "name": feature_mapping.feature.name,
                                       "count": feature_mapping.count, "test":
                                           feature_mapping.feature.test.id,
                                       "test_name": feature_mapping.feature.test.name} for feature_mapping in
                                      plan.feature_mappings.filter(enabled=True)]}

        care_membership = UserPlanMapping(plan=plan, user=self.user, is_active=True, extra_details=extra_details,
                                          status=UserPlanMapping.BOOKED, money_pool=None)

        care_membership.save(plus_user_obj=self)

    class Meta:
        db_table = 'plus_users'
        unique_together = (('user', 'plan'),)


class PlusUserUtilization(auth_model.TimeStampedModel):
    plus_user = models.ForeignKey(PlusUser, related_name='plus_utilization', on_delete=models.DO_NOTHING)
    plan = models.ForeignKey(PlusPlans, related_name='plus_plans_for_utilization', on_delete=models.DO_NOTHING)
    utilization = JSONField(blank=False, null=False)

    class Meta:
        db_table = 'plus_user_utilization'
        unique_together = (('plus_user', 'plan'),)

    @classmethod
    def create_utilization(cls, plus_user_obj):
        plus_plan = plus_user_obj.plan
        utilization = plus_user_obj.get_utilization
        plus_utilize = cls.objects.create(plus_user=plus_user_obj, plan=plus_plan, utilization=utilization)


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
        from ondoc.plus.tasks import push_plus_buy_to_matrix
        from ondoc.notification.tasks import send_plus_membership_notifications
        if self.transaction_type == self.DEBIT:
            send_plus_membership_notifications.apply_async(({'user_id': self.plus_user.user.id}, ),
                                                     link=push_plus_buy_to_matrix.s(user_id=self.plus_user.user.id), countdown=1)

            # Activate the Docprime Care membership.
            self.plus_user.activate_care_membership()



    def save(self, *args, **kwargs):
        #should never be saved again
        if self.pk:
            return

        super().save(*args, **kwargs)

        # transaction_amount = int(self.amount)
        # if self.transaction_type == self.DEBIT:
        #     transaction_amount = -1*transaction_amount

        # master_policy_obj = self.user_insurance.master_policy
        # account_id = master_policy_obj.insurer_account.id
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

        @classmethod
        def get_custom_availabilities(cls):
            relations = {
                'SELF': 'Self',
                'SPOUSE': 'Spouse',
                'FATHER': 'Father',
                'MOTHER': 'Mother',
                'SON': 'Son',
                'DAUGHTER': 'Daughter',
                'SPOUSE_FATHER': 'Father-in-law',
                'SPOUSE_MOTHER': 'Mother-in-law',
                'BROTHER': 'Brother',
                'SISTER': 'Sister',
                'OTHERS': 'Others'
            }

            return relations

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
    relation = models.CharField(max_length=50, choices=Relations.as_choices(), default=None, null=True)
    pincode = models.PositiveIntegerField(default=None)
    address = models.TextField(default=None)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, default=None, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, related_name="plus_member", on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=20, choices=TITLE_TYPE_CHOICES, default=None)
    middle_name = models.CharField(max_length=50, null=True)
    city = models.CharField(max_length=100, null=True, default=None)
    district = models.CharField(max_length=100, null=True, default=None)
    state = models.CharField(max_length=100, null=True, default=None)
    state_code = models.CharField(max_length=10, default=None, null=True)
    plus_user = models.ForeignKey(PlusUser, related_name="plus_members", on_delete=models.DO_NOTHING, null=False, default=None)
    city_code = models.CharField(max_length=10, blank=True, null=True, default='')
    district_code = models.CharField(max_length=10, blank=True, null=True, default=None)
    is_primary_user = models.NullBooleanField()

    def get_full_name(self):
        return "{first_name} {last_name}".format(first_name=self.first_name, last_name=self.last_name)

    @classmethod
    def create_plus_members(cls, plus_user_obj, *args, **kwargs):

        members = kwargs.get('members_list')
        if not members:
            members = plus_user_obj.raw_plus_member
            members = json.loads(members)

        for member in members:
            user_profile = UserProfile.objects.get(id=member.get('profile'))
            is_primary_user = True if member['relation'] and member['relation']  == cls.Relations.SELF else False
            plus_members_obj = cls(first_name=member.get('first_name'), title=member.get('title'),
                                                     last_name=member.get('last_name'), dob=member.get('dob'),
                                                     email=member.get('email'), address=member.get('address'),
                                                     pincode=member.get('pincode'), phone_number=user_profile.phone_number,
                                                     gender=member.get('gender'), profile=user_profile, city=member.get('city'),
                                                     district=member.get('district'), state=member.get('state'),
                                                     state_code = member.get('state_code'), plus_user=plus_user_obj,
                                                     city_code=member.get('city_code'), district_code=member.get('district_code'),
                                                     relation=member.get('relation'), is_primary_user=is_primary_user)
            plus_members_obj.save()
            member_document_proofs = member.get('document_ids')
            if member_document_proofs:
                document_ids = list(map(lambda d: d.get('proof_file').id, member_document_proofs))
                DocumentsProofs.update_with_object(plus_members_obj, document_ids)

    class Meta:
        db_table = "plus_members"


class PlusLead(auth_model.TimeStampedModel):
    matrix_lead_id = models.IntegerField(null=True)
    extras = JSONField(default={})
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit())

    def after_commit(self):
        push_plus_lead_to_matrix.apply_async(({'id': self.id}, ))

    # get seconds elapsed since creation time

    # def get_creation_time_diff(self):
    #     now = datetime.utcnow().replace(tzinfo=utc)
    #     timediff = now - self.created_at
    #     return timediff.total_seconds()
    #
    # def get_lead_creation_wait_time(self):
    #     source = self.get_source()
    #     if source!='docprimechat':
    #         return 0
    #     tdiff = self.get_creation_time_diff()
    #     wait = 86400 - tdiff
    #     if wait<0:
    #         wait=0
    #     return wait
    #
    # def get_source(self):
    #     extras = self.extras
    #     lead_source = "InsuranceOPD"
    #     lead_data = extras.get('lead_data')
    #     if lead_data:
    #         provided_lead_source = lead_data.get('source')
    #         if type(provided_lead_source).__name__ == 'str' and provided_lead_source.lower() == 'docprimechat':
    #             lead_source = 'docprimechat'
    #
    #     return lead_source

    @classmethod
    def get_latest_lead_id(cls, user):
        insurance_lead = cls.objects.filter(user=user).order_by('id').last()
        if insurance_lead:
            return insurance_lead.matrix_lead_id

        return None

    @classmethod
    def create_lead_by_phone_number(cls, request):
        phone_number = request.data.get('phone_number', None)
        if not phone_number:
            return None

        # user_insurance_lead = cls.objects.filter(phone_number=phone_number).order_by('id').last()
        # if not user_insurance_lead:
        user_insurance_lead = cls(phone_number=phone_number)

        user_insurance_lead.extras = request.data
        user_insurance_lead.save()
        return True

    class Meta:
        db_table = 'plus_leads'


class PlusAppointmentMapping(auth_model.TimeStampedModel):
    plus_user = models.ForeignKey(PlusUser, related_name='appointment_mapping', on_delete=models.DO_NOTHING)
    plus_plan = models.ForeignKey(PlusPlans, related_name='plan_appointment', on_delete=models.DO_NOTHING)
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    amount = models.DecimalField(default=0, max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'plus_appointment_mapping'

