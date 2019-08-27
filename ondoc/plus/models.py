from django.db import models
from ondoc.account.models import MoneyPool
from ondoc.authentication import models as auth_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.validators import FileExtensionValidator
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from ondoc.account import models as account_model


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

    class Meta:
        db_table = 'plus_proposer'


class PlusPlans(auth_model.TimeStampedModel, LiveMixin):
    plan_name = models.CharField(max_length=300)
    proposer = models.ForeignKey(PlusProposer, related_name='plus_plans', on_delete=models.DO_NOTHING)
    internal_name = models.CharField(max_length=200, null=True)
    amount = models.PositiveIntegerField(default=0)
    tenure = models.PositiveIntegerField(default=1)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    total_allowed_members = models.PositiveSmallIntegerField(default=0)
    is_selected = models.BooleanField(default=False)

    class Meta:
        db_table = 'plus_plans'


class PlusThreshold(auth_model.TimeStampedModel, LiveMixin):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plus_threshold", on_delete=models.DO_NOTHING)
    opd_amount_limit = models.PositiveIntegerField(default=0)
    lab_amount_limit = models.PositiveIntegerField(default=0)
    package_amount_limit = models.PositiveIntegerField(default=0)
    custom_validation = JSONField(blank=False, null=False)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    class Meta:
        db_table = 'plus_threshold'

    def __str__(self):
        return str(self.plus_plan)


class PlusUser(auth_model.TimeStampedModel):
    ACTIVE = 1
    CANCELLED = 2
    EXPIRED = 3
    ONHOLD = 4
    CANCEL_INITIATE = 5
    CANCELLATION_APPROVED = 6

    STATUS_CHOICES = [(ACTIVE, "Active"), (CANCELLED, "Cancelled"), (EXPIRED, "Expired"), (ONHOLD, "Onhold"),
                      (CANCEL_INITIATE, 'Cancel Initiate'), (CANCELLATION_APPROVED, "Cancellation Approved")]

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

    class Meta:
        db_table = 'plus_users'