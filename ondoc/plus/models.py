from django.db import models
from ondoc.authentication import models as auth_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.validators import FileExtensionValidator


# Create your models here.


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


class PlusThreshold(auth_model.TimeStampedModel, LiveMixin):
    plus_plan = models.ForeignKey(PlusPlans, related_name="plus_threshold", on_delete=models.DO_NOTHING)
    opd_amount_limit = models.PositiveIntegerField(default=0)
    lab_amount_limit = models.PositiveIntegerField(default=0)
    package_amount_limit = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return str(self.plus_plan)