from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.authentication.models import TimeStampedModel
from ondoc.diagnostic.models import LabTest


# Create your models here.


class IntegratorMapping(TimeStampedModel):
    # Resource can be Lab, Lab Network, Hospitals etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name="resource_contenttype")
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    # # product can be lab tests.
    # product_content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name="product_contenttype")
    # product_object_id = models.PositiveIntegerField()
    # product_content_object = GenericForeignKey()

    test_id = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    interator_class_name = models.CharField(max_length=40, null=False, blank=False)

    class Meta:
        db_table = 'integrator_mapping'
