from django.db import models
from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator

from django.contrib.postgres.fields import JSONField
# Create your models here.


class DemoElastic(TimeStampedModel):
    query = models.TextField(null=True, blank=False)

    elastic_url = models.URLField(null=True, default=None, blank=False)
    elastic_alias = models.CharField(max_length=100, null=True, default=None, blank=False)
    primary_index = models.CharField(max_length=100, null=True, default=None, blank=False)
    secondary_index_a = models.CharField(max_length=100, null=True, default=None, blank=False)
    secondary_index_b = models.CharField(max_length=100, null=True, default=None, blank=False)
    primary_index_mapping_data = JSONField(default={})
    secondary_index_mapping_data = JSONField(default={})

    active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super(DemoElastic, self).save(*args, **kwargs)

    class Meta:
        db_table = "demo_elastic"
