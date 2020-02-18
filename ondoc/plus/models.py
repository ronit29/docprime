import openpyxl
from dateutil.relativedelta import relativedelta
from django.db import models
import functools

from ondoc.api.v1.utils import CouponsMixin, plus_subscription_transform
from ondoc.authentication import models as auth_model
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from ondoc.account import models as account_model
from ondoc.authentication.models import UserProfile, RefundMixin, TransactionMixin
from ondoc.cart.models import Cart
from ondoc.common.helper import Choices
import json
from ondoc.authentication.models import UserProfile, User
from django.db import transaction
from django.db.models import Q
from ondoc.common.models import DocumentsProofs
from ondoc.corporate_booking.models import Corporates
from ondoc.coupon.models import Coupon

from ondoc.notification.tasks import push_plus_lead_to_matrix, set_order_dummy_transaction, update_random_coupons_consumption
    # set_order_dummy_transaction_for_corporate,

from ondoc.plus.usage_criteria import get_class_reference, get_price_reference, get_min_convenience_reference, \
    get_max_convenience_reference
from .enums import PlanParametersEnum, UtilizationCriteria, PriceCriteria
from datetime import datetime, timedelta
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from ondoc.crm import constants as const
from django.utils.timezone import utc
import reversion
from django.conf import settings
from django.utils.functional import cached_property
from .enums import UsageCriteria
from copy import deepcopy
from math import floor
import logging

logger = logging.getLogger(__name__)


# Mixin or dependency which will be injected in the class with the below mentioned behaviour.
class LiveMixin(models.Model):
    def save(self, *args, **kwargs):
        if self.enabled:
            self.is_live = True
        else:
            self.is_live = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


# Gold feature is associated with the entity who is liable for the feature. PlusProposer is Docprime and can be
# any entity in future such as Apollo, SBI, HDFC etc
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

    # Get the active plans associated with the object of plus proposer.
    @property
    def get_active_plans(self):
        return self.plus_plans.filter(is_live=True, is_retail=True).order_by('id')
        # index = 0
        # for plan in plans:
        #     if plan.plan_utmsources.all().exists():
        #         plans.pop(index)
        #     else:
        #         index += 1

        # return plans

    # Get all the plans associated with the object of plus proposer.
    @property
    def get_all_plans(self):
        return self.plus_plans.all().order_by('total_allowed_members')

    class Meta:
        db_table = 'plus_proposer'


# class CorporateGroup(auth_model.TimeStampedModel):
#     class CorporateType(Choices):
#         VIP = 'VIP'
#         GOLD = 'GOLD'
#
#     name = models.CharField(max_length=300, null=False, blank=False)
#     type = models.CharField(max_length=100, null=True, choices=CorporateType.as_choices())
#
#     def __str__(self):
#         return str(self.name)
#
#     class Meta:
#         db_table = 'plus_corporate_groups'


# All the Gold plans of all the proposers.
@reversion.register()
class PlusPlans(auth_model.TimeStampedModel, LiveMixin):
    plan_name = models.CharField(max_length=300)
    proposer = models.ForeignKey(PlusProposer, related_name='plus_plans', on_delete=models.DO_NOTHING)
    internal_name = models.CharField(max_length=200, null=True)
    mrp = models.PositiveIntegerField(default=0)
    deal_price = models.PositiveIntegerField(default=0)
    tax_rebate = models.PositiveIntegerField(default=0)
    tenure = models.PositiveIntegerField(default=1, help_text="Tenure is number of months of active subscription.")
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    total_allowed_members = models.PositiveSmallIntegerField(default=0)
    is_selected = models.BooleanField(default=False)
    features = JSONField(blank=False, null=False, default=dict)
    is_retail = models.NullBooleanField()
    plan_criteria = models.CharField(max_length=100, null=True, blank=False, choices=UsageCriteria.as_choices())
    price_criteria = models.CharField(max_length=100, null=True, blank=False, choices=PriceCriteria.as_choices())
    convenience_min_price_reference = models.CharField(max_length=100, null=True, blank=False, choices=PriceCriteria.as_choices())
    convenience_max_price_reference = models.CharField(max_length=100, null=True, blank=False, choices=PriceCriteria.as_choices())
    is_gold = models.NullBooleanField()
    default_single_booking = models.NullBooleanField()
    is_corporate = models.NullBooleanField()
    # corporate_group = models.ForeignKey(CorporateGroup, related_name='corporate_plan', null=True, blank=True, on_delete=models.DO_NOTHING)
    corporate = models.ForeignKey(Corporates, related_name='corporate_plan', null=True, blank=True,
                                        on_delete=models.DO_NOTHING)
    corporate_upper_limit_criteria = models.CharField(max_length=100, null=True, blank=True, choices=PriceCriteria.as_choices())
    corporate_doctor_upper_limit = models.PositiveIntegerField(null=True, blank=True)
    corporate_lab_upper_limit = models.PositiveIntegerField(null=True, blank=True)

    # Some plans are only applicable when utm params are passed. Like some plans are to be targeted with media
    # campaigns, emails or adwords etc.
    @classmethod
    def get_active_plans_via_utm(cls, utm):
        qs = PlusPlanUtmSourceMapping.objects.filter(utm_source__source=utm, plus_plan__is_live=True, plus_plan__enabled=True)
        if not qs:
            return []

        plans_via_utm = list(map(lambda obj: obj.plus_plan, qs))

        return plans_via_utm

    # Get all the plans
    @classmethod
    def all_active_plans(cls):
        return cls.objects.filter(is_live=True, enabled=True)

    def __str__(self):
        return "{}".format(self.plan_name)

    # Get convenience charge of specific plan.
    def get_convenience_charge(self, max_price, min_price, type):
        if not max_price or min_price or max_price <= 0 or min_price <= 0:
            return 0
        charge = 0
        if type == "DOCTOR":
            convenience_min_amount_obj = self.plan_parameters.filter(
                parameter__key='DOCTOR_MINIMUM_CAPPING_AMOUNT').first()
            convenience_max_amount_obj = self.plan_parameters.filter(
                parameter__key='DOCTOR_MAXIMUM_CAPPING_AMOUNT').first()
            convenience_percentage_obj = self.plan_parameters.filter(
                parameter__key='DOCTOR_CONVENIENCE_PERCENTAGE').first()
        elif type == "LABTEST":
            convenience_min_amount_obj = self.plan_parameters.filter(
                parameter__key='LAB_MINIMUM_CAPPING_AMOUNT').first()
            convenience_max_amount_obj = self.plan_parameters.filter(
                parameter__key='LAB_MAXIMUM_CAPPING_AMOUNT').first()
            convenience_percentage_obj = self.plan_parameters.filter(
                parameter__key='LAB_CONVENIENCE_PERCENTAGE').first()
        else:
            return 0
        min_cap = convenience_min_amount_obj.value if convenience_min_amount_obj else 0
        max_cap = convenience_max_amount_obj.value if convenience_max_amount_obj else 0
        if not min_cap or not max_cap or min_cap <= 0 or max_cap <= 0:
            return 0
        convenience_amount_list = []
        price_diff = int(max_price) - (min_price)
        if price_diff <= 0:
            return 0
        if price_diff <= min_cap:
            return 0
        convenience_amount_list.append(min_cap)
        convenience_amount_list.append(max_cap)
        convenience_percentage = convenience_percentage_obj.value if convenience_percentage_obj else 0
        if not convenience_percentage or convenience_percentage <= 0:
            return 0
        convenience_percentage = int(convenience_percentage)
        convenience_amount_through_percentage = (convenience_percentage/100) * float(price_diff)
        convenience_amount_through_percentage = int(convenience_amount_through_percentage)
        convenience_amount_list.append(convenience_amount_through_percentage)
        charge = min(convenience_amount_list)
        return charge

    # Get the default convenience charge.
    @classmethod
    def get_default_convenience_amount(cls, price_data, type, default_plan_query=None):
        charge = 0
        if not default_plan_query:
            default_plan = cls.objects.prefetch_related('plan_parameters', 'plan_parameters__parameter').filter(is_gold=True, is_selected=True).first()
            if not default_plan:
                default_plan = cls.objects.prefetch_related('plan_parameters', 'plan_parameters__parameter').filter(is_gold=True).first()

        else:
            default_plan = default_plan_query
        if not default_plan:
            return 0
        min_price_engine = get_min_convenience_reference(default_plan, "DOCTOR")
        if not min_price_engine:
            return 0
        min_price = min_price_engine.get_price(price_data)
        max_price_engine = get_max_convenience_reference(default_plan, "DOCTOR")
        if not max_price_engine:
            return 0
        max_price = max_price_engine.get_price(price_data)
        if max_price is None or min_price is None or max_price < 0 or min_price < 0:
            return 0
        convenience_min_amount_obj, convenience_max_amount_obj, convenience_percentage_obj = default_plan.get_convenience_object(type)
        min_cap = int(convenience_min_amount_obj.value) if convenience_min_amount_obj else 0
        max_cap = int(convenience_max_amount_obj.value) if convenience_max_amount_obj else 0
        if min_cap is None or max_cap is None or min_cap <= 0 or max_cap <= 0:
            return 0
        convenience_amount_list = []
        price_diff = int(max_price) - (min_price)
        if price_diff <= 0:
            return 0
        if price_diff <= min_cap:
            return 0
        min_cap_diff = int(price_diff - min_cap)
        if min_cap_diff <= 0:
            return 0
        convenience_amount_list.append(min_cap_diff)
        convenience_amount_list.append(max_cap)
        convenience_percentage = int(convenience_percentage_obj.value) if convenience_percentage_obj else 0
        if not convenience_percentage or convenience_percentage <= 0:
            return 0
        convenience_amount_through_percentage = (convenience_percentage / 100) * float(price_diff)
        convenience_amount_through_percentage = int(convenience_amount_through_percentage)
        convenience_amount_list.append(convenience_amount_through_percentage)
        charge = min(convenience_amount_list)
        return charge

    # Get associated convenience object according to the doctor and lab.
    def get_convenience_object(self, type):
        string = ''
        if type == "DOCTOR":
            string = 'DOCTOR'
        else:
            string = 'LAB'
        convenience_min_amount_obj = None
        convenience_max_amount_obj = None
        convenience_percentage_obj = None
        plan_parameters = self.plan_parameters.all()
        for param in plan_parameters:
            if param.parameter and param.parameter.key:
                if param.parameter.key == (string + '_MINIMUM_CAPPING_AMOUNT'):
                    convenience_min_amount_obj = param
                if param.parameter.key == (string + '_MAXIMUM_CAPPING_AMOUNT'):
                    convenience_max_amount_obj = param
                if param.parameter.key == (string + '_CONVENIENCE_PERCENTAGE'):
                    convenience_percentage_obj = param
            if convenience_percentage_obj and convenience_min_amount_obj and convenience_max_amount_obj:
                return convenience_min_amount_obj, convenience_max_amount_obj, convenience_percentage_obj

        return None, None, None

    # Get convenience amount.
    def get_convenience_amount(self, price, convenience_amount_obj, convenience_percentage_obj):
        if not price or price <= 0:
            return 0
        charge = 0
        convenience_amount = convenience_amount_obj.value if convenience_amount_obj else 0
        convenience_percentage = convenience_percentage_obj.value if convenience_percentage_obj else 0
        if (not convenience_amount and not convenience_percentage) or (convenience_amount == 0 and convenience_percentage == 0):
            return 0
        convenience_percentage = int(convenience_percentage)
        convenience_amount = int(convenience_amount)
        if convenience_percentage and convenience_percentage > 0:
            charge = (convenience_percentage/100) * price
            charge = floor(charge)
        elif convenience_amount and convenience_amount > 0:
            return convenience_amount
        else:
            return 0
        if charge <= convenience_amount:
            return charge
        else:
            return convenience_amount

    # Get price details
    def get_price_details(self, data, amount=0):
        coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(data, amount)
        if coupon_discount >= amount:
            effective_price = 0
        else:
            effective_price = amount - coupon_discount
        return {
            "amount": amount,
            "effective_price": effective_price,
            "coupon_discount": coupon_discount,
            "coupon_cashback": coupon_cashback,
            "coupon_list": coupon_list,
            "random_coupon_list": random_coupon_list
        }

    @classmethod
    def get_gold_plan(cls):
        plus_plans = cls.objects.prefetch_related('plan_parameters', 'plan_parameters__parameter').filter(
            is_gold=True)
        plan = None
        for plan in plus_plans:
            if plan.is_selected:
                plan = plan
                break
        if not plan:
            plan = plus_plans.first()
        return plan

    class Meta:
        db_table = 'plus_plans'
        # unique_together = (('is_selected', 'is_gold'), )


# Utm Sources details.
class PlusPlanUtmSources(auth_model.TimeStampedModel):
    source = models.CharField(max_length=100, null=False, blank=False, unique=True)
    source_details = models.CharField(max_length=500, null=True, blank=True)
    create_lead = models.NullBooleanField()

    def __str__(self):
        return "{}".format(self.source)

    class Meta:
        db_table = 'plus_plan_utmsources'


# Utm source entity and plan mapping.
@reversion.register()
class PlusPlanUtmSourceMapping(auth_model.TimeStampedModel):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plan_utmsources", null=False, blank=False, on_delete=models.CASCADE)
    utm_source = models.ForeignKey(PlusPlanUtmSources, null=False, blank=False, on_delete=models.CASCADE)
    # value = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return "{} - {}".format(self.plus_plan, self.utm_source)

    class Meta:
        db_table = 'plus_plan_utmsources_mapping'


# Global Configurations objects for plus features.
class PlusPlanParameters(auth_model.TimeStampedModel):
    key = models.CharField(max_length=100, null=False, blank=False, choices=PlanParametersEnum.as_choices())
    details = models.CharField(max_length=500, null=False, blank=False)

    def __str__(self):
        return "{}".format(self.key)

    class Meta:
        db_table = 'plus_plan_parameters'


# Configurations associated to specific plus plans.
@reversion.register()
class PlusPlanParametersMapping(auth_model.TimeStampedModel):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plan_parameters", null=False, blank=False, on_delete=models.CASCADE)
    parameter = models.ForeignKey(PlusPlanParameters, null=False, blank=False, on_delete=models.CASCADE)
    value = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return "{} - ({} : {})".format(self.plus_plan, self.parameter, self.value )

    class Meta:
        db_table = 'plus_plan_parameters_mapping'


# Static contents for plus plans.
class PlusPlanContent(auth_model.TimeStampedModel):

    class PossibleTitles(Choices):
        SALIENT_FEATURES = 'SALIENT_FEATURES'
        WHATS_NOT_COVERED = 'WHATS_NOT_COVERED'

    plan = models.ForeignKey(PlusPlans, related_name="plan_content", on_delete=models.CASCADE)
    title = models.CharField(max_length=500, blank=False, choices=PossibleTitles.as_choices())
    content = models.TextField(blank=False)

    class Meta:
        db_table = 'plus_plan_content'


# Thresholds for Plus plans.
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


# User who have purchased the plus or gold are maintained in this table.
@reversion.register()
class PlusUser(auth_model.TimeStampedModel, RefundMixin, TransactionMixin, CouponsMixin):
    from ondoc.account.models import MoneyPool
    from ondoc.coupon.models import Coupon
    PRODUCT_ID = account_model.Order.VIP_PRODUCT_ID

    ACTIVE = 1
    CANCELLED = 2
    EXPIRED = 3
    ONHOLD = 4
    CANCEL_INITIATE = 5
    CANCELLATION_APPROVED = 6
    INACTIVE = 7

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
    payment_type = models.PositiveSmallIntegerField(choices=const.PAY_CHOICES, default=const.PREPAID)
    coupon = models.ManyToManyField(Coupon, blank=True, null=True, related_name="plus_coupon")

    def add_user_profile_to_members(self, user_profile):
        members = [{
            'profile': user_profile.id,
            'dob': user_profile.dob,
            'email': user_profile.email,
            'gender': user_profile.gender,
            'is_primary_user': False,
            'first_name': user_profile.name
        }]
        PlusMembers.create_plus_members(self, members_list=members)

    # Purchased gold plan have few states , some are valid and some are not valid, check if plan is still valid or not.
    def is_valid(self):
        if self.expire_date >= timezone.now() and (self.status == self.ACTIVE):
            return True
        else:
            return False

    # Can appointment be booked via gold plan with respect to the appointment time.
    def is_appointment_valid(self, appointment_time):
        if self.expire_date >= appointment_time:
            return True
        else:
            return False

    # Get the gold plan associated to the user if any.
    @classmethod
    def get_by_user(cls, user):
        return cls.objects.filter(user=user).order_by('id').last()

    # Check if gold plans can be cancelled or not. If any appointment has booked, we cannot book.
    def can_be_cancelled(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        # Opd Appointments
        appointments_qs = OpdAppointment.objects.filter(plus_plan=self)
        completed_appointments = appointments_qs.filter(status=OpdAppointment.COMPLETED)
        if completed_appointments.exists():
            return {'reason': 'User has completed opd appointments', 'can_be_cancelled': False}

        # Lab Appointments
        appointments_qs = LabAppointment.objects.filter(plus_plan=self)
        completed_appointments = appointments_qs.filter(status=LabAppointment.COMPLETED)
        if completed_appointments.exists():
            return {'reason': 'User has completed lab appointments.', 'can_be_cancelled': False}

        return {'reason': 'Can be cancelled.', 'can_be_cancelled': True}

    # Get primary member profile of the gold plan.
    def get_primary_member_profile(self):
        insured_members = self.plus_members.filter().order_by('id')
        proposers = list(filter(lambda member: member.is_primary_user, insured_members))
        if proposers:
            return proposers[0]

        return None

    # get all the members associated with the gold policy.
    @cached_property
    def get_members(self):
        plus_members = self.plus_members.filter().order_by('id')
        return plus_members

    # check if test can be covered in the vip in respect to the price.
    def can_test_be_covered_in_vip(self, *args, **kwargs):
        mrp = kwargs.get('mrp')
        id = kwargs.get('id')

        if not mrp:
            return
        utilization_dict = self.get_utilization

    # can package be covered in the vip.
    def can_package_be_covered_in_vip(self, obj, *args, **kwargs):
        mrp = obj.mrp if obj else kwargs.get('mrp')
        # id = (obj.test.id if hasattr(obj, 'test') else obj.id) if obj else kwargs.get('id')
        if kwargs.get('id'):
            id = kwargs.get('id')
        elif obj.__class__.__name__ == 'LabTest':
            id = obj.id
        else:
            id = obj.test.id

        utilization_dict = self.get_utilization
        if utilization_dict.get('total_package_count_limit'):
            if utilization_dict['available_package_count'] > 0 and id in utilization_dict['allowed_package_ids']:
                return UtilizationCriteria.COUNT, True
            else:
                return UtilizationCriteria.COUNT, False
        else:
            if mrp <= utilization_dict['available_package_amount']:
                if utilization_dict['allowed_package_ids']:
                    if id in utilization_dict['allowed_package_ids']:
                        return UtilizationCriteria.AMOUNT, True
                    else:
                        return UtilizationCriteria.AMOUNT, False

                    # return UtilizationCriteria.AMOUNT, True if id in utilization_dict['allowed_package_ids'] else UtilizationCriteria.AMOUNT, False
                return UtilizationCriteria.AMOUNT, True
            else:
                return UtilizationCriteria.AMOUNT, False

    """
    Every gold plan is associated with bulk of features such as 
        1. Online chat
        2. Limit of appointments in context of count and amount.
        3. Min Max discount which can be availed.
        4. Total packages which are whitelisted of plan.
        
    Below property gives all the stats available such as all the limits user have availed and all the limits which can 
    be availed in future. Ex. 4 appointments have be booked and 2 remaing of total 6 appointments. 
    """
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
                                                                               PlanParametersEnum.PACKAGE_DISCOUNT,
                                                                               PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE,
                                                                               PlanParametersEnum.LAB_DISCOUNT,
                                                                               PlanParametersEnum.LABTEST_AMOUNT,
                                                                               PlanParametersEnum.LABTEST_COUNT,
                                                                               PlanParametersEnum.DOCTOR_CONSULT_DISCOUNT,
                                                                               PlanParametersEnum.DOCTOR_CONSULT_COUNT])

        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value
        
        resp['allowed_package_ids'] = list(map(lambda x: int(x), data.get('package_ids', '').split(','))) if data.get('package_ids') else []
        resp['doctor_consult_amount'] = int(data['doctor_consult_amount']) if data.get('doctor_consult_amount') and data.get('doctor_consult_amount').__class__.__name__ == 'str' else 0
        resp['doctor_amount_utilized'] = self.get_doctor_plus_appointment_amount()
        resp['lab_amount_utilized'] = self.get_labtest_plus_appointment_amount()
        resp['doctor_discount'] = int(data['doctor_consult_discount']) if data.get('doctor_consult_discount') and data.get('doctor_consult_discount').__class__.__name__ == 'str' else 0
        resp['lab_discount'] = int(data['lab_discount']) if data.get('lab_discount') and data.get('lab_discount').__class__.__name__ == 'str' else 0
        resp['package_discount'] = int(data['package_discount']) if data.get('package_discount') and data.get('package_discount').__class__.__name__ == 'str' else 0
        resp['doctor_amount_available'] = resp['doctor_consult_amount'] - resp['doctor_amount_utilized']
        resp['members_count_online_consultation'] = data['members_covered_in_package'] if data.get('members_covered_in_package') and data.get('members_covered_in_package').__class__.__name__ == 'str'  else 0
        resp['total_package_amount_limit'] = int(data['health_checkups_amount']) if data.get('health_checkups_amount') and data.get('health_checkups_amount').__class__.__name__ == 'str'  else 0
        resp['online_chat_amount'] = int(data['online_chat_amount']) if data.get('online_chat_amount') and data.get('online_chat_amount').__class__.__name__ == 'str'  else 0
        resp['total_package_count_limit'] = int(data['health_checkups_count']) if data.get('health_checkups_count') and data.get('health_checkups_count').__class__.__name__ == 'str'  else 0

        resp['available_package_amount'] = resp['total_package_amount_limit'] - int(self.get_package_plus_appointment_amount())
        resp['available_package_count'] = resp['total_package_count_limit'] - int(self.get_package_plus_appointment_count())

        resp['total_labtest_amount_limit'] = int(data['labtest_amount']) if data.get('labtest_amount') and data.get('labtest_amount').__class__.__name__ == 'str'  else 0
        resp['total_labtest_count_limit'] =  int(data['labtest_count']) if data.get('labtest_count') and data.get('labtest_count').__class__.__name__ == 'str'  else 0

        resp['available_labtest_amount'] = resp['total_labtest_amount_limit'] - int(self.get_labtest_plus_appointment_amount())
        resp['available_labtest_count'] = resp['total_labtest_count_limit'] - int(self.get_labtest_plus_appointment_count())
        resp['total_doctor_count_limit'] = int(data['doctor_consult_count']) if data.get('doctor_consult_count') and data.get('doctor_consult_discount').__class__.__name__ == 'str' else 0
        resp['available_doctor_count'] = resp['total_doctor_count_limit'] - int(self.get_doctor_plus_appointment_count())

        # resp['availabe_labtest_discount_count'] = resp['total_labtest_count_limit']

        return resp

    # Get count of doctor appointments which have been booked via gold policy.
    def get_doctor_plus_appointment_count(self):
        from ondoc.doctor.models import OpdAppointment
        opd_appointments_count = OpdAppointment.objects.filter(plus_plan=self).exclude(status=OpdAppointment.CANCELLED).count()
        return opd_appointments_count

    """
    An appointment data has to be validated that it can be covered in the gold policy or not. Some appointments are 
    fully covered and some are partially. Partially covered appointments are charged with amount.
    All the appointments under gold plans or vip plans are to be passed at each point before appointment creation.
    """
    def validate_plus_appointment(self, appointment_data, *args, **kwargs):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        OPD = "OPD"
        LAB = "LAB"
        appointment_type = OPD if "doctor" in appointment_data else LAB
        price_data = OpdAppointment.get_price_details(appointment_data, self) if appointment_type == OPD else LabAppointment.get_price_details(appointment_data, self)
        mrp = int(price_data.get('mrp'))
        response_dict = {
            "is_vip_member": False,
            "plus_user_id": None,
            "cover_under_vip": "",
            "vip_amount_deducted": 0,
            "amount_to_be_paid": mrp,
            "vip_convenience_amount": 0
        }

        # discount calculation on mrp
        coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(
            appointment_data, mrp)
        if coupon_discount >= mrp:
            response_dict['amount_to_be_paid'] = 0
        else:
            response_dict['amount_to_be_paid'] = mrp - coupon_discount

        if appointment_data.get('payment_type') == OpdAppointment.COD:
            return response_dict
        profile = appointment_data.get('profile', None)
        user = profile.user
        plus_user = user.active_plus_user
        if not plus_user and appointment_data.get('plus_plan', None):
            plus_user = user.get_temp_plus_user
        if not plus_user:
            return response_dict
        if not appointment_data.get('plus_plan', None):
            plus_members = plus_user.plus_members.filter(profile=profile)
            if not plus_members.exists():
                return response_dict

        response_dict['is_vip_member'] = True

        if appointment_type == OPD:
            deal_price = price_data.get('deal_price', 0)
            fees = price_data.get('fees', 0)
            cod_deal_price = price_data.get('consultation').get('cod_deal_price', 0) if (price_data.get('consultation') and price_data.get('consultation').get('cod_deal_price')) else 0
            # price_data = {"mrp": int(price_data.get('mrp')), "deal_price": int(deal_price),
            #               "cod_deal_price": int(cod_deal_price),
            #               "fees": int(fees)}

            calculated_convenience_amount = price_data.get('total_convenience_charge')
            if calculated_convenience_amount is None:
                calculated_convenience_amount = PlusPlans.get_default_convenience_amount(price_data, "DOCTOR",
                                                                                         plus_user.plan)

            response_dict['vip_convenience_amount'] = calculated_convenience_amount
            price_engine = get_price_reference(plus_user, "DOCTOR")
            if not price_engine:
                price = int(price_data.get('mrp'))
            else:
                price = price_engine.get_price(price_data)
            engine = get_class_reference(plus_user, "DOCTOR")
            response_dict['vip_gold_price'] = fees
            if not engine:
                return response_dict

            doctor = appointment_data['doctor']
            hospital = appointment_data['hospital']
            if doctor.enabled_for_online_booking and hospital.enabled_for_online_booking and \
                    hospital.enabled_for_prepaid and hospital.is_enabled_for_plus_plans() and \
                    doctor.enabled_for_plus_plans:

                # engine_response = engine.validate_booking_entity(cost=mrp, utilization=kwargs.get('utilization'))
                engine_response = engine.validate_booking_entity(cost=price, utilization=kwargs.get('utilization'), mrp=mrp, deal_price=deal_price, calculated_convenience_amount=calculated_convenience_amount)

                # discount calculation on amount to be paid
                amount_to_be_paid = engine_response.get('amount_to_be_paid', mrp)
                # convenience_charge = calculated_convenience_amount
                amount_to_be_paid += calculated_convenience_amount
                response_dict['vip_convenience_amount'] = calculated_convenience_amount
                response_dict['amount_to_be_paid'] = amount_to_be_paid
                coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(
                    appointment_data, amount_to_be_paid)
                if coupon_discount >= amount_to_be_paid:
                    response_dict['amount_to_be_paid'] = 0
                else:
                    response_dict['amount_to_be_paid'] = amount_to_be_paid - coupon_discount

                response_dict['cover_under_vip'] = engine_response.get('is_covered', False)
                response_dict['plus_user_id'] = plus_user.id
                response_dict['vip_amount_deducted'] = engine_response.get('vip_amount_deducted', 0)

                # Only for cart items.
                if kwargs.get('utilization') and response_dict['cover_under_vip'] and response_dict['vip_amount_deducted']:
                    engine.update_utilization(kwargs.get('utilization'), response_dict['vip_amount_deducted'])

        elif appointment_type == LAB:
            lab = appointment_data['lab']
            if lab and lab.is_enabled_for_plus_plans():
                mrp = int(price_data.get('mrp'))
                # final_price = mrp + price_data['home_pickup_charges']

                # price_data = {"mrp": int(price_data.get('mrp')), "deal_price": int(price_data.get('deal_price')),
                #               "cod_deal_price": int(price_data.get('deal_price')),
                #               "fees": int(price_data.get('fees'))}
                calculated_convenience_amount = price_data.get('total_convenience_charge', 0)
                # if calculated_convenience_amount is None:
                #     calculated_convenience_amount = PlusPlans.get_default_convenience_amount(price_data, "LABTEST", plus_user.plan)

                response_dict['vip_convenience_amount'] = calculated_convenience_amount
                price_engine = get_price_reference(plus_user, "LABTEST")
                if not price_engine:
                    price = int(price_data.get('mrp'))
                else:
                    price = price_engine.get_price(price_data)
                final_price = price + price_data['home_pickup_charges']
                entity = "PACKAGE" if appointment_data['test_ids'][0].is_package else "LABTEST"
                engine = get_class_reference(plus_user, entity)
                response_dict['vip_gold_price'] = int(price_data.get('fees'))
                if appointment_data['test_ids']:
                    # engine_response = engine.validate_booking_entity(cost=final_price, id=appointment_data['test_ids'][0].id, utilization=kwargs.get('utilization'))
                    mrp_with_home_pickup = mrp + price_data['home_pickup_charges']
                    engine_response = engine.validate_booking_entity(cost=final_price, id=appointment_data['test_ids'][0].id, utilization=kwargs.get('utilization'), mrp=mrp_with_home_pickup, price_engine_price=price, deal_price=int(price_data.get('deal_price')), calculated_convenience_amount=calculated_convenience_amount)

                    if not engine_response:
                        return response_dict

                    # discount calculation on amount to be paid
                    amount_to_be_paid = engine_response.get('amount_to_be_paid', final_price)
                    price_with_conveince_fees = price + calculated_convenience_amount

                    amount_to_be_paid += calculated_convenience_amount
                    response_dict['vip_convenience_amount'] = calculated_convenience_amount

                    coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(
                        appointment_data, price_with_conveince_fees)
                    if coupon_discount >= amount_to_be_paid:
                        response_dict['amount_to_be_paid'] = 0
                    else:
                        response_dict['amount_to_be_paid'] = amount_to_be_paid - coupon_discount

                    response_dict['cover_under_vip'] = engine_response.get('is_covered', False)
                    response_dict['plus_user_id'] = plus_user.id
                    response_dict['vip_amount_deducted'] = engine_response.get('vip_amount_deducted', 0)
                    # response_dict['amount_to_be_paid'] = engine_response.get('amount_to_be_paid', final_price)

                    # Only for cart items.
                    if kwargs.get('utilization') and response_dict['cover_under_vip'] and response_dict['vip_amount_deducted']:
                        engine.update_utilization(kwargs.get('utilization'), response_dict['vip_amount_deducted'])

        return response_dict

    # validates the incoming cart item along with the existing cart items.
    def validate_cart_items(self, appointment_data, request):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        vip_data_dict = {
            "is_vip_member": True,
            "cover_under_vip": False,
            "vip_amount": 0,
            "plus_user_id": None,
            "vip_convenience_amount": 0
        }
        vip_valid_dict = self.validate_plus_appointment(appointment_data)
        vip_data_dict['vip_convenience_amount'] = vip_valid_dict.get('vip_convenience_amount')
        if not vip_valid_dict.get('cover_under_vip'):
            return vip_data_dict

        user = self.user
        cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True)
        OPD = "OPD"
        LAB = "LAB"

        appointment_type = OPD if "doctor" in appointment_data else LAB
        deep_utilization = deepcopy(self.get_utilization)
        for item in cart_items:
            try:
                validated_item = item.validate(request)
                self.validate_plus_appointment(validated_item, utilization=deep_utilization)
            except Exception as e:
                pass
        current_item_price_data = OpdAppointment.get_price_details(
            appointment_data, self) if appointment_type == OPD else LabAppointment.get_price_details(appointment_data, self)
        current_item_mrp = int(current_item_price_data.get('mrp', 0))
        cod_deal_price = current_item_price_data.get('consultation').get('cod_deal_price') if current_item_price_data \
                            and current_item_price_data.get('consultation') and current_item_price_data.get('consultation').get('cod_deal_price') else 0
        if 'doctor' in appointment_data:
            price_data = {"mrp": int(current_item_price_data.get('mrp')), "deal_price": int(current_item_price_data.get('deal_price')),
                          "cod_deal_price": int(cod_deal_price),
                          "fees": int(current_item_price_data.get('fees'))}
            price_engine = get_price_reference(request.user.active_plus_user, "DOCTOR")
            if not price_engine:
                price = current_item_mrp
            else:
                price = price_engine.get_price(price_data)
            plan = request.user.active_plus_user.plan if request.user.active_plus_user else None
            # vip_data_dict['vip_convenience_amount'] = PlusPlans.get_default_convenience_amount(price_data, "DOCTOR", default_plan_query=plan)
            vip_data_dict['vip_convenience_amount'] = vip_valid_dict.get('vip_convenience_amount', 0)
            engine = get_class_reference(self, "DOCTOR")
            vip_data_dict['vip_gold_price'] = int(current_item_price_data.get('fees'))
            if engine:
                # vip_response = engine.validate_booking_entity(cost=current_item_mrp, utilization=deep_utilization)
                vip_response = engine.validate_booking_entity(cost=price, mrp=current_item_mrp, utilization=deep_utilization, deal_price=int(current_item_price_data.get('deal_price', 0)))
                vip_data_dict['vip_amount'] = vip_response.get('amount_to_be_paid')
                vip_data_dict['amount_to_be_paid'] = vip_response.get('amount_to_be_paid')
                vip_data_dict['cover_under_vip'] = vip_response.get('is_covered')
                vip_data_dict['plus_user_id'] = self.id

            else:
                return vip_data_dict
        else:
            tests = appointment_data.get('test_ids', [])
            for test in tests:
                entity = "LABTEST" if not test.is_package else "PACKAGE"
                price_data = {"mrp": int(current_item_price_data.get('mrp')),
                              "deal_price": int(current_item_price_data.get('deal_price')),
                              "cod_deal_price": int(current_item_price_data.get('deal_price')),
                              "fees": int(current_item_price_data.get('fees'))}
                price_engine = get_price_reference(request.user.active_plus_user, "LABTEST")
                if not price_engine:
                    price = current_item_mrp
                else:
                    price = price_engine.get_price(price_data)
                plan = request.user.active_plus_user.plan if request.user.active_plus_user else None
                # vip_data_dict['vip_convenience_amount'] = PlusPlans.get_default_convenience_amount(price_data, "LABTEST", default_plan_query=plan)
                vip_data_dict['vip_convenience_amount'] = vip_valid_dict.get('vip_convenience_amount', 0)
                engine = get_class_reference(self, entity)
                vip_data_dict['vip_gold_price'] = int(current_item_price_data.get('fees'))
                if engine:
                    # vip_response = engine.validate_booking_entity(cost=current_item_mrp, utilization=deep_utilization)
                    vip_response = engine.validate_booking_entity(cost=price, utilization=deep_utilization, mrp=current_item_mrp, price_engine_price=price, deal_price=int(current_item_price_data.get('deal_price', 0)))
                    vip_data_dict['vip_amount'] = vip_response.get('amount_to_be_paid')
                    vip_data_dict['amount_to_be_paid'] = vip_response.get('amount_to_be_paid')
                    vip_data_dict['cover_under_vip'] = vip_response.get('is_covered')
                    vip_data_dict['plus_user_id'] = self.id
                else:
                    return vip_data_dict
        vip_data_dict['is_gold_member'] = True if request.user.active_plus_user.plan.is_gold else False
        return vip_data_dict

    # Get count of lab appointments which have been booked via gold policy.
    def get_labtest_plus_appointment_count(self):
        from ondoc.diagnostic.models import LabAppointment
        labtest_count = 0
        lab_appointments = LabAppointment.objects.filter(plus_plan=self).exclude(status=LabAppointment.CANCELLED)
        if not lab_appointments:
            return 0

        for lab_appointment in lab_appointments:
            labtest_count = labtest_count + len(list(filter(lambda lab_test: not lab_test.test.is_package, lab_appointment.test_mappings.all())))
        return labtest_count

    # Get total amount of lab appointments which have been booked via gold policy.
    def get_labtest_plus_appointment_amount(self):
        from ondoc.diagnostic.models import LabAppointment

        import functools
        labtest_amount = 0
        lab_appointments_ids = LabAppointment.objects.filter(plus_plan=self).exclude(status=LabAppointment.CANCELLED).values_list('id', flat=True)



        content_type = ContentType.objects.get_for_model(LabAppointment)
        appointment_mappings = PlusAppointmentMapping.objects.filter(object_id__in=lab_appointments_ids, content_type=content_type)
        if not appointment_mappings:
            return 0

        appointment_mappings_amount = list(map(lambda appointment: appointment.amount, appointment_mappings))
        labtest_amount = labtest_amount + functools.reduce(lambda a, b: a + b, appointment_mappings_amount)

        return labtest_amount

    # Get total count of package appointments which have been booked via gold policy.
    def get_package_plus_appointment_count(self):
        from ondoc.diagnostic.models import LabAppointment
        package_count = 0
        lab_appointments = LabAppointment.objects.filter(plus_plan=self).exclude(status=LabAppointment.CANCELLED)
        if not lab_appointments:
            return 0

        for lab_appointment in lab_appointments:
            package_count = package_count + len(list(filter(lambda lab_test: lab_test.test.is_package, lab_appointment.test_mappings.all())))
        return package_count

    # Get total amount of package appointments which have been booked via gold policy.
    def get_package_plus_appointment_amount(self):
        from ondoc.diagnostic.models import LabAppointment

        import functools
        package_amount = 0
        lab_appointments_ids = LabAppointment.objects.filter(plus_plan=self).exclude(status=LabAppointment.CANCELLED).values_list('id', flat=True)
        content_type = ContentType.objects.get_for_model(LabAppointment)
        appointment_mappings = PlusAppointmentMapping.objects.filter(object_id__in=lab_appointments_ids, content_type=content_type)
        if not appointment_mappings:
            return 0

        appointment_mappings_amount = list(map(lambda appointment: appointment.amount, appointment_mappings))
        package_amount = package_amount + functools.reduce(lambda a, b: a + b, appointment_mappings_amount)

        return package_amount

    # Get amount of doctor appointments which have been booked via gold policy.
    def get_doctor_plus_appointment_amount(self):
        import functools
        from ondoc.doctor.models import OpdAppointment
        # total_mrp = 0
        opd_appointments_ids = OpdAppointment.objects.filter(plus_plan=self).exclude(status=OpdAppointment.CANCELLED).values_list('id', flat=True)

        content_type = ContentType.objects.get_for_model(OpdAppointment)
        appointment_mappings = PlusAppointmentMapping.objects.filter(object_id__in=opd_appointments_ids, content_type=content_type)
        if not appointment_mappings:
            return 0

        opd_appointments_amount = list(map(lambda appointment: appointment.amount, appointment_mappings))
        total_mrp = functools.reduce(lambda a, b: a + b, opd_appointments_amount)
        return total_mrp

    # create or update the profile of the plus member.
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
                    if member.get('email'):
                        profile.email = member.get('email', None)
                    if member.get('gender'):
                        profile.gender = member.get('gender', None)
                    if member.get('dob'):
                        profile.dob = member.get('dob')
                    # profile.is_default_user = True
                    # if member['relation'] == PlusMembers.Relations.SELF:
                    # if member['is_primary_user']:
                    #
                    # else:
                    #     profile.is_default_user = False
                    profile.save()

                profile = profile.id
        # Create Profile if not exist with name or not exist in profile id from request
        else:
            phone_number = member.get('phone_number') if member.get('phone_number') else user.phone_number
            data = {'name': name, 'email': member.get('email'), 'user_id': user.id,
                    'dob': member.get('dob'), 'is_default_user': False, 'is_otp_verified': False,
                    'phone_number': phone_number, 'gender': member.get('gender')}
            # if member['is_primary_user']:
            #     data['is_default_user'] = True
            profile_obj = UserProfile.objects.filter(user_id=user.id).first()
            if not profile_obj and member['is_primary_user']:
                data['is_default_user'] = True
            else:
                data['is_default_user'] = False

            member_profile = UserProfile.objects.create(**data)
            profile = member_profile.id

        return profile

    # get all the enabled hospitals in the gold policy.
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

    # create the gold policy after successful payment along with the gold members.
    @classmethod
    def create_plus_user(cls, plus_data, user):
        from ondoc.doctor.models import OpdAppointment
        members = deepcopy(plus_data['plus_members'])
        coupon_list = plus_data.pop("coupon", None)
        random_coupon_list = plus_data.get("random_coupon_list", None)

        for member in members:
            member['profile'] = cls.profile_create_or_update(member, user)
            member['dob'] = str(member['dob'])
            # member['profile'] = member['profile'].id if member.get('profile') else None
        plus_data['plus_members'] = members

        plus_membership_obj = cls.objects.create(plan=plus_data['plus_plan'],
                                                          user=plus_data['user'],
                                                          raw_plus_member=json.dumps(plus_data['plus_members']),
                                                          purchase_date=plus_data['purchase_date'],
                                                          expire_date=plus_data['expire_date'],
                                                          amount=plus_data['effective_price'],
                                                          order=plus_data['order'],
                                                          payment_type=const.PREPAID,
                                                          status=cls.ACTIVE)

        if coupon_list:
            plus_membership_obj.coupon.add(*coupon_list)
        PlusMembers.create_plus_members(plus_membership_obj)
        PlusUserUtilization.create_utilization(plus_membership_obj)
        if random_coupon_list:
            update_random_coupons_consumption.apply_async((random_coupon_list), countdown=5)
        return plus_membership_obj

    # Care product is also an addon which user get after purchase of gold policy.
    def activate_care_membership(self):
        from ondoc.subscription_plan.models import Plan, UserPlanMapping

        if UserPlanMapping.objects.filter(user=self.user).exists():
            return

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

    def get_vip_amount(self, utilization, mrp):
        available_amount = int(utilization.get('doctor_amount_available', 0))
        available_discount = int(utilization.get('doctor_discount', None))
        if not available_discount or available_discount == 0 :
            amount = 0 if available_amount >= mrp else (mrp - available_amount)
            return amount
        amount = self.get_discounted_amount(utilization, mrp)
        return amount

    def get_discounted_amount(self, utilization, mrp):
        # mrp = doctor_obj.mrp
        available_amount = utilization.get('doctor_amount_available', 0)
        doctor_discount = utilization.get('doctor_discount', None)
        if not doctor_discount or doctor_discount == 0:
            final_amount = 0 if available_amount >= mrp else (mrp - available_amount)
            return final_amount
        discounted_amount = int(doctor_discount * mrp / 100)
        final_amount = mrp - discounted_amount
        return final_amount

    # Get cancellation brekup.
    def get_cancellation_breakup(self):
        wallet_refund = cashback_refund = 0
        if self.money_pool:
            wallet_refund, cashback_refund = self.money_pool.get_refund_breakup(self.amount)
        elif self.price_data:
            wallet_refund = self.price_data["wallet_amount"]
            cashback_refund = self.price_data["cashback_amount"]
        else:
            wallet_refund = self.effective_price

        return wallet_refund, cashback_refund

    # operations which are needs to be performed after policy purchase.
    def after_commit_tasks(self, *args, **kwargs):
        from ondoc.api.v1.plus.plusintegration import PlusIntegration
        from ondoc.account.models import  UserReferred, Order

        if kwargs.get('is_fresh'):
            PlusIntegration.create_vip_lead_after_purchase(self)
            PlusIntegration.assign_coupons_to_user_after_purchase(self)
            UserReferred.credit_after_completion(self.user, self, Order.GOLD_PRODUCT_ID)

    # Process policy cancellation.
    def process_cancellation(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.subscription_plan.models import Plan, UserPlanMapping
        care_obj = UserPlanMapping.objects.filter(user=self.user).order_by('id').last()
        if care_obj:
            care_obj.status = UserPlanMapping.CANCELLED
            care_obj.is_active = False
            care_obj.save()

        self.action_refund()

        # Cancel all the appointments which are created using the plus membership.

        # Opd Appointments
        appointments_qs = OpdAppointment.objects.filter(plus_plan=self)
        to_be_cancelled_appointments = appointments_qs.all().exclude(status__in=[OpdAppointment.COMPLETED, OpdAppointment.CANCELLED])
        for appointment in to_be_cancelled_appointments:
            # appointment.status = OpdAppointment.CANCELLED
            # appointment.save()
            appointment.action_cancelled(True)

        # Lab Appointments
        appointments_qs = LabAppointment.objects.filter(plus_plan=self)
        to_be_cancelled_appointments = appointments_qs.all().exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED])
        for appointment in to_be_cancelled_appointments:
            # appointment.status = LabAppointment.CANCELLED
            # appointment.save()
            appointment.action_cancelled(True)

    def process_cancel_initiate(self):
        pass
        # from ondoc.doctor.models import OpdAppointment
        # from ondoc.diagnostic.models import LabAppointment
        # from ondoc.subscription_plan.models import Plan, UserPlanMapping
        # care_obj = UserPlanMapping.objects.filter(user=self.user).order_by('id').last()
        # if care_obj:
        #     care_obj.status = UserPlanMapping.CANCELLED
        #     care_obj.is_active = False
        #     care_obj.save()
        #
        # self.action_refund()
        #
        # # Cancel all the appointments which are created using the plus membership.
        #
        # # Opd Appointments
        # appointments_qs = OpdAppointment.objects.filter(plus_plan=self)
        # to_be_cancelled_appointments = appointments_qs.all().exclude(status__in=[OpdAppointment.COMPLETED, OpdAppointment.CANCELLED])
        # for appointment in to_be_cancelled_appointments:
        #     appointment.status = OpdAppointment.CANCELLED
        #     appointment.save()
        #
        # # Lab Appointments
        # appointments_qs = LabAppointment.objects.filter(plus_plan=self)
        # to_be_cancelled_appointments = appointments_qs.all().exclude(status__in=[LabAppointment.COMPLETED, LabAppointment.CANCELLED])
        # for appointment in to_be_cancelled_appointments:
        #     appointment.status = LabAppointment.CANCELLED
        #     appointment.save()

    def save(self, *args, **kwargs):
        is_fresh = False
        if not self.pk:
            is_fresh = True
        
        db_instance = None
        if self.pk:
            db_instance = PlusUser.objects.filter(id=self.id).first()
            
        if db_instance and self.status == self.CANCELLED and db_instance.status != self.CANCELLED:
            self.process_cancellation()

        if db_instance and self.status == self.CANCEL_INITIATE and db_instance.status != self.CANCEL_INITIATE:
            self.process_cancel_initiate()

        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit_tasks(is_fresh=is_fresh))

    # prepare data after all the validation which is utilized after payment to create the policy.
    @classmethod
    def create_fulfillment_data(cls, data):
        from ondoc.doctor.models import OpdAppointment
        plus_user = dict()
        resp = {}
        plus_plan = data.get('plus_plan')
        profile = data.get('profile', None)
        name = profile.name.split(' ', 1)
        first_name = name[0]
        last_name = name[1] if name[1:] else ''
        dob = profile.dob
        email = profile.email
        phone_number = profile.phone_number
        plus_members = []

        member = {"first_name": first_name, "last_name": last_name, "dob": dob, "email": email, "phone_number": phone_number, "profile": profile.id if profile else None, "is_primary_user": True}
        primary_user_profile = UserProfile.objects.filter(user_id=profile.user.pk, is_default_user=True).values('id', 'name',
                                                                                                      'email',
                                                                                                      'gender',
                                                                                                      'user_id',
                                                                                                      'phone_number',
                                                                                                                'dob').first()
        plus_members.append(member.copy())
        transaction_date = datetime.datetime.now()
        expiry_date = transaction_date + relativedelta(months=int(plus_plan.tenure))
        expiry_date = expiry_date - timedelta(days=1)
        expiry_date = datetime.datetime.combine(expiry_date, datetime.datetime.max.time())
        amount = plus_plan.deal_price
        plus_user = {'proposer': plus_plan.proposer.id, 'plus_plan': plus_plan.id,
                          'purchase_date': transaction_date, 'expire_date': expiry_date, 'amount': amount,
                          'user': profile.user.id, "plus_members": plus_members, "effective_price": amount}

        resp = {"profile_detail": primary_user_profile, "user": profile.user.id, "plus_user": plus_user,
                "plus_plan": plus_plan.id, "effective_price": amount, "payment_type": OpdAppointment.PREPAID}

        return resp

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

    # Create utilization of individual user.
    @classmethod
    def create_utilization(cls, plus_user_obj):
        plus_plan = plus_user_obj.plan
        utilization = plus_user_obj.get_utilization
        plus_utilize = cls.objects.create(plus_user=plus_user_obj, plan=plus_plan, utilization=utilization)


# Transaction of gold purchase.
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

    # After successful transaction we perform few operations.
    def after_commit_tasks(self):
        from ondoc.plus.tasks import push_plus_buy_to_matrix
        from ondoc.notification.tasks import send_plus_membership_notifications
        if self.transaction_type == self.DEBIT:
            send_plus_membership_notifications.apply_async(({'user_id': self.plus_user.user.id}, ),
                                                     link=push_plus_buy_to_matrix.s(user_id=self.plus_user.user.id), countdown=1)

            # Activate the Docprime Care membership.
            if self.plus_user.get_utilization and self.plus_user.get_utilization.get('online_chat_amount'):
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


# Associated gold members.
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
    pincode = models.PositiveIntegerField(default=None, null=True)
    address = models.TextField(default=None, null=True)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, default=None, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, related_name="plus_member", on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=20, choices=TITLE_TYPE_CHOICES, default=None, null=True)
    middle_name = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, default=None, blank=True)
    district = models.CharField(max_length=100, null=True, default=None, blank=True)
    state = models.CharField(max_length=100, null=True, default=None, blank=True)
    state_code = models.CharField(max_length=10, default=None, null=True, blank=True)
    plus_user = models.ForeignKey(PlusUser, related_name="plus_members", on_delete=models.DO_NOTHING, null=False, default=None)
    city_code = models.CharField(max_length=10, blank=True, null=True, default='')
    district_code = models.CharField(max_length=10, blank=True, null=True, default=None)
    is_primary_user = models.NullBooleanField()

    # get full name of plus members.
    def get_full_name(self):
        return "{first_name} {last_name}".format(first_name=self.first_name, last_name=self.last_name)

    # create gold members.
    @classmethod
    def create_plus_members(cls, plus_user_obj, *args, **kwargs):

        members = kwargs.get('members_list', None)
        if members is None:
            members = plus_user_obj.raw_plus_member
            members = json.loads(members)

        for member in members:
            user_profile = UserProfile.objects.get(id=member.get('profile'))
            is_primary_user = member['is_primary_user']
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


# Lead which are gained for gold policy.
class PlusLead(auth_model.TimeStampedModel):
    matrix_lead_id = models.IntegerField(null=True)
    extras = JSONField(default={})
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit())

    # After lead creation, few tasks are to be performed.
    def after_commit(self):
        push_plus_lead_to_matrix.apply_async(({'id': self.id}, ))

    # Get latest lead id of user.
    @classmethod
    def get_latest_lead_id(cls, user):
        insurance_lead = cls.objects.filter(user=user).order_by('id').last()
        if insurance_lead:
            return insurance_lead.matrix_lead_id

        return None

    # create lead by phone number.
    @classmethod
    def create_lead_by_phone_number(cls, request):
        phone_number = request.data.get('phone_number', None)
        if not phone_number:
            return None

        # user_insurance_lead = cls.objects.filter(phone_number=phone_number).order_by('id').last()
        # if not user_insurance_lead:
        plus_lead = cls(phone_number=phone_number)

        plus_lead.extras = request.data
        plus_lead.save()
        return plus_lead

    class Meta:
        db_table = 'plus_leads'


# Mappings of appointment and policy.
class PlusAppointmentMapping(auth_model.TimeStampedModel):
    plus_user = models.ForeignKey(PlusUser, related_name='appointment_mapping', on_delete=models.DO_NOTHING)
    plus_plan = models.ForeignKey(PlusPlans, related_name='plan_appointment', on_delete=models.DO_NOTHING)
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    amount = models.DecimalField(default=0, max_digits=10, decimal_places=2)
    extra_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    # get amount which has been utilized by policy holder in terms of appointment.
    @classmethod
    def get_vip_amount(cls, plus_user, content_type):
        from ondoc.doctor.models import OpdAppointment
        vip_amount = 0
        objects = cls.objects.filter(content_type=content_type, plus_user=plus_user)
        valid_objects = list(filter(lambda obj: obj.content_object.status != OpdAppointment.CANCELLED, objects))
        valid_amounts = list(map(lambda o: o.amount, valid_objects))
        if valid_amounts:
            vip_amount = functools.reduce(lambda a, b: a + b, valid_amounts)
        return vip_amount

    # get count which has been utilized by policy holder in terms of appointment.
    @classmethod
    def get_count(cls, plus_user, content_type):
        from ondoc.doctor.models import OpdAppointment
        objects = cls.objects.filter(content_type=content_type, plus_user=plus_user)
        valid_objects = list(filter(lambda obj: obj.content_object.status != OpdAppointment.CANCELLED, objects))
        return len(valid_objects)

    class Meta:
        db_table = 'plus_appointment_mapping'


# Data which user has filled in process of purchase of gold policy. User data is saved in this table.
class PlusDummyData(auth_model.TimeStampedModel):
    class DataType(Choices):
        PLAN_PURCHASE = 'PLAN_PURCHASE'
        SINGLE_PURCHASE = 'SINGLE_PURCHASE'

    user = models.ForeignKey(User, related_name='plus_user_dummy_data', on_delete=models.DO_NOTHING)
    data = JSONField(null=False, blank=False)
    data_type = models.CharField(max_length=100, null=True, choices=DataType.as_choices())

    class Meta:
        db_table = 'plus_dummy_data'


# For the single flow, dummy gold policy is been created which is converted to actual policy after purchase.
class TempPlusUser(auth_model.TimeStampedModel):
    user = models.ForeignKey(User, related_name='temp_plus_user', on_delete=models.DO_NOTHING)
    plan = models.ForeignKey(PlusPlans, related_name='temp_plus_plan', on_delete=models.DO_NOTHING)
    raw_plus_member = JSONField(blank=True, null=True, default=list)
    profile = models.ForeignKey(UserProfile, related_name='temp_plus_user_profile', on_delete=models.DO_NOTHING)
    deleted = models.BooleanField(default=0)
    is_utilized = models.NullBooleanField()

    class Meta:
        db_table = 'temp_plus_user'

    # Conversion of temp appointment data to valid gold appointment in the case of single flow.
    @classmethod
    def temp_appointment_to_plus_appointment(cls, appointment_data):
        from ondoc.account.models import  Order
        if "plus_plan" in appointment_data and appointment_data['plus_plan']:

            temp_plus_obj = cls.objects.filter(user__id=appointment_data['user'], id=int(appointment_data['plus_plan']),
                                                        profile__id=appointment_data['profile'],
                                                        is_utilized=None).first()
            if temp_plus_obj:
                temp_plus_obj.is_utilized = True
                temp_plus_obj.save()

                sibling_order = Order.objects.filter(user__id=appointment_data['user'], product_id=Order.GOLD_PRODUCT_ID,
                                                     reference_id__isnull=False).order_by('-id').first()
                if sibling_order:
                    plus_obj = PlusUser.objects.filter(id=sibling_order.reference_id).first()
                    appointment_data['plus_plan'] = plus_obj.id

        return appointment_data

    """
        An appointment data has to be validated that it can be covered in the gold policy or not. Some appointments are 
        fully covered and some are partially. Partially covered appointments are charged with amount.
        All the appointments under gold plans or vip plans are to be passed at each point before appointment creation.
    """
    def validate_plus_appointment(self, appointment_data, *args, **kwargs):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        OPD = "OPD"
        LAB = "LAB"
        appointment_type = OPD if "doctor" in appointment_data else LAB
        price_data = OpdAppointment.get_price_details(appointment_data, self) if appointment_type == OPD else LabAppointment.get_price_details(appointment_data, self)
        mrp = int(price_data.get('mrp'))
        response_dict = {
            "is_vip_member": False,
            "plus_user_id": None,
            "cover_under_vip": "",
            "vip_amount_deducted": 0,
            "amount_to_be_paid": mrp,
            "vip_convenience_amount": 0
        }

        # discount calculation on mrp
        # coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(appointment_data, mrp)
        coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []
        if coupon_discount >= mrp:
            response_dict['amount_to_be_paid'] = 0
        else:
            response_dict['amount_to_be_paid'] = mrp - coupon_discount

        if appointment_data.get('payment_type') == OpdAppointment.COD:
            return response_dict
        profile = appointment_data.get('profile', None)
        user = profile.user
        plus_user = user.active_plus_user
        if not plus_user and appointment_data.get('plus_plan', None):
            plus_user = user.get_temp_plus_user
        if not plus_user:
            return response_dict
        if not appointment_data.get('plus_plan', None):
            plus_members = plus_user.plus_members.filter(profile=profile)
            if not plus_members.exists():
                return response_dict

        response_dict['is_vip_member'] = True

        if appointment_type == OPD:
            deal_price = price_data.get('deal_price', 0)
            fees = price_data.get('fees', 0)
            cod_deal_price = price_data.get('consultation').get('cod_deal_price', 0) if (price_data.get('consultation') and price_data.get('consultation').get('cod_deal_price')) else 0
            # price_data = {"mrp": int(price_data.get('mrp')), "deal_price": int(deal_price),
            #               "cod_deal_price": int(cod_deal_price),
            #               "fees": int(fees)}
            vip_convenience_amount = price_data.get('total_convenience_charge')
            response_dict['vip_convenience_amount'] = vip_convenience_amount
            price_engine = get_price_reference(plus_user, "DOCTOR")
            if not price_engine:
                price = int(price_data.get('mrp'))
            else:
                price = price_engine.get_price(price_data)
            engine = get_class_reference(plus_user, "DOCTOR")
            response_dict['vip_gold_price'] = fees
            if not engine:
                return response_dict

            doctor = appointment_data['doctor']
            hospital = appointment_data['hospital']
            if doctor.enabled_for_online_booking and hospital.enabled_for_online_booking and \
                    hospital.enabled_for_prepaid and hospital.is_enabled_for_plus_plans() and \
                    doctor.enabled_for_plus_plans:

                # engine_response = engine.validate_booking_entity(cost=mrp, utilization=kwargs.get('utilization'))
                engine_response = engine.validate_booking_entity(cost=price, utilization=kwargs.get('utilization'), mrp=mrp, deal_price=deal_price, calculated_convenience_amount=vip_convenience_amount)

                # discount calculation on amount to be paid
                amount_to_be_paid = engine_response.get('amount_to_be_paid', mrp)
                amount_to_be_paid += vip_convenience_amount
                response_dict['amount_to_be_paid'] = amount_to_be_paid
                # coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(appointment_data, amount_to_be_paid)
                coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []
                if coupon_discount >= amount_to_be_paid:
                    response_dict['amount_to_be_paid'] = 0
                else:
                    response_dict['amount_to_be_paid'] = amount_to_be_paid - coupon_discount

                response_dict['cover_under_vip'] = engine_response.get('is_covered', False)
                response_dict['plus_user_id'] = plus_user.id
                response_dict['vip_amount_deducted'] = engine_response.get('vip_amount_deducted', 0)

                # Only for cart items.
                if kwargs.get('utilization') and response_dict['cover_under_vip'] and response_dict['vip_amount_deducted']:
                    engine.update_utilization(kwargs.get('utilization'), response_dict['vip_amount_deducted'])

        elif appointment_type == LAB:
            lab = appointment_data['lab']
            if lab and lab.is_enabled_for_plus_plans():
                mrp = int(price_data.get('mrp'))
                # final_price = mrp + price_data['home_pickup_charges']

                # price_data = {"mrp": int(price_data.get('mrp')), "deal_price": int(price_data.get('deal_price')),
                #               "cod_deal_price": int(price_data.get('deal_price')),
                #               "fees": int(price_data.get('fees'))}
                calculated_convenience_amount = price_data.get('total_convenience_charge', 0)
                response_dict['vip_convenience_amount'] = calculated_convenience_amount
                price_engine = get_price_reference(plus_user, "LABTEST")
                if not price_engine:
                    price = int(price_data.get('mrp'))
                else:
                    price = price_engine.get_price(price_data)
                final_price = price + price_data['home_pickup_charges']
                entity = "PACKAGE" if appointment_data['test_ids'][0].is_package else "LABTEST"
                engine = get_class_reference(plus_user, entity)
                response_dict['vip_gold_price'] = int(price_data.get('fees'))
                if appointment_data['test_ids']:
                    # engine_response = engine.validate_booking_entity(cost=final_price, id=appointment_data['test_ids'][0].id, utilization=kwargs.get('utilization'))
                    mrp_with_home_pickup = mrp + price_data['home_pickup_charges']
                    engine_response = engine.validate_booking_entity(cost=final_price,
                                                                     id=appointment_data['test_ids'][0].id,
                                                                     utilization=kwargs.get('utilization'),
                                                                     mrp=mrp_with_home_pickup, price_engine_price=price,
                                                                     deal_price=int(price_data.get('deal_price')), calculated_convenience_amount=calculated_convenience_amount)

                    if not engine_response:
                        return response_dict

                    # discount calculation on amount to be paid
                    amount_to_be_paid = engine_response.get('amount_to_be_paid', final_price)
                    amount_to_be_paid += calculated_convenience_amount
                    # coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(appointment_data, price + calculated_convenience_amount)
                    coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []
                    if coupon_discount >= amount_to_be_paid:
                        response_dict['amount_to_be_paid'] = 0
                    else:
                        response_dict['amount_to_be_paid'] = amount_to_be_paid - coupon_discount

                    response_dict['cover_under_vip'] = engine_response.get('is_covered', False)
                    response_dict['plus_user_id'] = plus_user.id
                    response_dict['vip_amount_deducted'] = engine_response.get('vip_amount_deducted', 0)
                    # response_dict['amount_to_be_paid'] = engine_response.get('amount_to_be_paid', final_price)

                    # Only for cart items.
                    if kwargs.get('utilization') and response_dict['cover_under_vip'] and response_dict[
                        'vip_amount_deducted']:
                        engine.update_utilization(kwargs.get('utilization'), response_dict['vip_amount_deducted'])

        return response_dict

    """
        Every gold plan is associated with bulk of features such as 
            1. Online chat
            2. Limit of appointments in context of count and amount.
            3. Min Max discount which can be availed.
            4. Total packages which are whitelisted of plan.

        Below property gives all the stats available such as all the limits user have availed and all the limits which can 
        be availed in future. Ex. 4 appointments have be booked and 2 remaing of total 6 appointments. 
        """
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
                                                                          PlanParametersEnum.PACKAGE_DISCOUNT,
                                                                          PlanParametersEnum.TOTAL_TEST_COVERED_IN_PACKAGE,
                                                                          PlanParametersEnum.LAB_DISCOUNT,
                                                                          PlanParametersEnum.LABTEST_AMOUNT,
                                                                          PlanParametersEnum.LABTEST_COUNT,
                                                                          PlanParametersEnum.DOCTOR_CONSULT_DISCOUNT,
                                                                          PlanParametersEnum.DOCTOR_CONSULT_COUNT])

        for pp in plan_parameters:
            data[pp.parameter.key.lower()] = pp.value

        resp['allowed_package_ids'] = list(map(lambda x: int(x), data.get('package_ids', '').split(','))) if data.get(
            'package_ids') else []
        resp['doctor_consult_amount'] = int(data['doctor_consult_amount']) if data.get(
            'doctor_consult_amount') and data.get('doctor_consult_amount').__class__.__name__ == 'str' else 0
        resp['doctor_amount_utilized'] = 0
        resp['doctor_discount'] = int(data['doctor_consult_discount']) if data.get(
            'doctor_consult_discount') and data.get('doctor_consult_discount').__class__.__name__ == 'str' else 0
        resp['lab_discount'] = int(data['lab_discount']) if data.get('lab_discount') and data.get(
            'lab_discount').__class__.__name__ == 'str' else 0
        resp['package_discount'] = int(data['package_discount']) if data.get('package_discount') and data.get(
            'package_discount').__class__.__name__ == 'str' else 0
        resp['doctor_amount_available'] = resp['doctor_consult_amount']
        resp['members_count_online_consultation'] = data['members_covered_in_package'] if data.get(
            'members_covered_in_package') and data.get('members_covered_in_package').__class__.__name__ == 'str'  else 0
        resp['total_package_amount_limit'] = int(data['health_checkups_amount']) if data.get(
            'health_checkups_amount') and data.get('health_checkups_amount').__class__.__name__ == 'str'  else 0
        resp['online_chat_amount'] = int(data['online_chat_amount']) if data.get('online_chat_amount') and data.get(
            'online_chat_amount').__class__.__name__ == 'str'  else 0
        resp['total_package_count_limit'] = int(data['health_checkups_count']) if data.get(
            'health_checkups_count') and data.get('health_checkups_count').__class__.__name__ == 'str'  else 0

        resp['available_package_amount'] = resp['total_package_amount_limit']
        resp['available_package_count'] = resp['total_package_count_limit']

        resp['total_labtest_amount_limit'] = int(data['labtest_amount']) if data.get('labtest_amount') and data.get(
            'labtest_amount').__class__.__name__ == 'str'  else 0
        resp['total_labtest_count_limit'] = int(data['labtest_count']) if data.get('labtest_count') and data.get(
            'labtest_count').__class__.__name__ == 'str'  else 0

        resp['available_labtest_amount'] = resp['total_labtest_amount_limit']
        resp['available_labtest_count'] = resp['total_labtest_count_limit']
        resp['total_doctor_count_limit'] = int(data['doctor_consult_count']) if data.get(
            'doctor_consult_count') and data.get('doctor_consult_discount').__class__.__name__ == 'str' else 0
        resp['available_doctor_count'] = resp['total_doctor_count_limit']

        # resp['availabe_labtest_discount_count'] = resp['total_labtest_count_limit']

        return resp


# class Corporate(auth_model.TimeStampedModel):
#     name = models.CharField(max_length=300, null=False, blank=False)
#     address = models.CharField(max_length=500, null=True, blank=True)
#     # corporate_group = models.ForeignKey(CorporateGroup, related_name='corporate_group', null=False, blank=False, on_delete=models.DO_NOTHING)
#
#     class Meta:
#         db_table = 'plus_corporates'


class PlusUserUpload(auth_model.TimeStampedModel):
    CASH = 1
    CHEQUE = 2
    NEFT = 4
    OTHER = 3
    PAYMENT_THROUGH_CHOICES = ((CASH, 'CASH'), (CHEQUE, "CHEQUE"), (OTHER, "OTHER"), (NEFT, "NEFT"))

    file = models.FileField(default=None, null=False, upload_to='insurance/upload', validators=[FileExtensionValidator(allowed_extensions=['xls', 'xlsx'])])
    amount = models.PositiveIntegerField(default=None, null=True, blank=True)
    paid_through = models.PositiveSmallIntegerField(null=True, blank=True, choices=PAYMENT_THROUGH_CHOICES)
    payment_proof = models.FileField(default=None, null=True, blank=True, upload_to='insurance/upload/payment_proof')
    cheque_number = models.CharField(max_length=100, null=True, blank=True)

    def save(self, *args, **kwargs):
        # should never be saved again
        if self.pk:
            return

        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit_tasks())

    def after_commit_tasks(self):
        file = self.file
        wb = openpyxl.load_workbook(file)

        # getting a particular sheet by name out of many sheets
        worksheet = wb.active
        excel_data = list()
        headers = list()

        # iterating over the rows and
        # getting value from each cell in row in dict
        i = 0
        for row in worksheet.iter_rows():
            j = 0
            data = {}
            for cell in row:
                if i == 0:
                    headers.append(str(cell.value))
                else:
                    data[headers[j]] = cell.value
                    j = j + 1
            i = i + 1
            excel_data.append(data)
        for data in excel_data:
            if data:
                try:
                    with transaction.atomic():
                        if data['is_primary_member'] == 1:
                            user = self.create_user(data)
                            excel_data = list(filter(None, excel_data))
                            if not user.active_plus_user:
                                member_list = []
                                for user_member_data in excel_data:
                                    if str(user_member_data.get('primary_phone_number', 0)) == str(user.phone_number):
                                        member_list.append(user_member_data)
                                fetched_data = self.get_plus_user_data(member_list, data, user)
                                plus_user_data = fetched_data.get('plus_data')
                                amount = fetched_data.get('amount')
                                order = self.create_order(plus_user_data, amount, user)
                                plus_user_obj = order.process_plus_user_upload_order()
                                if not plus_user_obj:
                                    raise Exception("Something Went Wrong")
                                order = plus_user_obj.order
                                # if order is done without PG transaction, then make an async task to create a dummy transaction and set it.
                                if not order.getTransactions():
                                    try:
                                        transaction.on_commit(
                                            lambda: set_order_dummy_transaction.apply_async(
                                                (order.id, plus_user_obj.user_id,), countdown=5))
                                    except Exception as e:
                                        logger.error(str(e))
                except Exception as e:
                    raise Exception(e)

    def create_user(self, data):
        phone_number = data['phone_number']
        if not phone_number:
            raise Exception('Phone number does not exist')
        user = User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).first()

        if not user:
            user = User.objects.create(phone_number=phone_number, user_type=User.CONSUMER)

        return user

    def get_plus_user_members_data(self, export_data, data):
        plus_user_members = list()
        phone_number = data.get('phone_number', None)
        if phone_number:
            primary_member_data = self.get_member_info(data, primary_member_data={}, primary=True)
            plus_user_members.append(primary_member_data)
            for member in export_data:
                if not member['relationship'] == 'Self':
                    secondary_member_data = self.get_member_info(member, primary_member_data, primary=False)
                    plus_user_members.append(secondary_member_data)

        return plus_user_members

    def get_member_info(self, member, primary_member_data, primary):
        members_dict = dict()
        name = member.get('plus_member_name', '')
        if not name:
            raise Exception('Name is mandatory for Plus User')

        name = name.split(' ')
        first_name = ''
        middle_name = ''
        last_name = ''
        if len(name) > 1 and len(name) == 2:
            first_name = name[0]
            last_name = name[1]
        elif len(name) > 1 and len(name) > 2:
            first_name = name[0]
            middle_name = name[1]
            last_name = name[2]
        else:
            first_name = name[0]
            middle_name = ''
            last_name = ''
        if member.get('gender', None) == "Male" or member.get('gender', None) == "MALE" or member.get('gender') == "male":
            gender = 'm'
        else:
            gender = 'f'
        members_dict['first_name'] = first_name
        members_dict['middle_name'] = middle_name
        members_dict['last_name'] = last_name
        # members_dict['dob'] = member['dob'].strftime("%Y-%m-%d") if member['dob'] else ''
        members_dict['dob'] = datetime.datetime.strptime(member['dob'], '%Y-%m-%d') if member['dob'] else ''
        members_dict['dob'] = str(members_dict['dob'].date()) if members_dict['dob'] else ''
        members_dict['gender'] = gender
        members_dict['relation'] = member.get('relation', '')
        members_dict['phone_number'] = member.get('phone_number', None)
        if not primary and not member.get('email', ''):
            members_dict['email'] = primary_member_data['email']
        else:
            members_dict['email'] = member.get('email')
        members_dict['profile'] = None
        if primary:
            members_dict['is_primary_user'] = True
        else:
            members_dict['is_primary_user'] = False

        return members_dict

    def get_plus_user_data(self, excel_data, data, user):
        from dateutil.relativedelta import relativedelta
        members = self.get_plus_user_members_data(excel_data, data)
        transaction_date = datetime.datetime.now()
        plus_plan = data['plan_id']
        plan = PlusPlans.objects.filter(pk=plus_plan).first()
        if not plan and not plan.is_corporate or plan.is_retail:
            raise Exception("Selected Plan is not belongs to Corporate or belongs to Retail plan, "
                            "Please select correct plan")
        members_count = len(excel_data)
        if int(plan.total_allowed_members) < members_count:
            raise Exception("Total members is greater than allowed members")
        if plan:
            amount = plan.deal_price
            expiry_date = transaction_date + relativedelta(months=int(plan.tenure))
            expiry_date = expiry_date - timedelta(days=1)
            expiry_date = datetime.datetime.combine(expiry_date, datetime.datetime.max.time())
            expiry_date = expiry_date

            # if plan.total_allowed_members < len(members):
            #     raise Exception('Only ' + str(plan.total_allowed_members) + ' members are allowed in selected plan for ' + data['first_name'])

        if data['relationship'] == 'Self' or data['relationship'] == 'SELF' or data['relationship'] == 'self':
            user_profile = UserProfile.objects.filter(user_id=user.pk).first()
            if user_profile:
                user_profile = {"name": user_profile.name, "email": user_profile.email, "gender": user_profile.gender,
                                "dob": user_profile.dob, "profile": user_profile.id}
            else:
                user_profile = {"name": data['plus_member_name'], "email": data['email'], "gender": data['gender'],
                                "dob": data['dob'] if data['dob'] else '', "profile": None}

        plus_user_data = {'proposer': plan.proposer.id, 'plus_plan': plan.id,
                          'purchase_date': transaction_date, 'expire_date': expiry_date, 'amount': int(amount),
                          'user': user.id, "plus_members": members,
                          'effective_price': int(amount)}

        plus_subscription_data = {"profile_detail": user_profile, "plus_plan": plan.id,
                                  "user": user.pk, "plus_user": plus_user_data}

        plus_data = plus_subscription_transform(plus_subscription_data)

        return {'plus_data': plus_data, "amount": amount}

    def create_order(self, plus_user_data, amount, user):
        from ondoc.account import models as account_models
        visitor_info = None

        order = account_models.Order.objects.create(
            product_id=account_models.Order.CORP_VIP_PRODUCT_ID,
            action=account_models.Order.CORP_VIP_CREATE,
            action_data=plus_user_data,
            amount=amount,
            cashback_amount=0,
            wallet_amount=0,
            user=user,
            payment_status=account_models.Order.PAYMENT_PENDING,
            visitor_info=visitor_info
        )
        return order

    class Meta:
        db_table = 'plus_user_upload'