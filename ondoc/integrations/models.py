from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.authentication.models import TimeStampedModel
from ondoc.diagnostic.models import LabTest
from ondoc.common.helper import Choices


# Create your models here.


class IntegratorMapping(TimeStampedModel):
    class ServiceType(Choices):
        LabTest = 'LABTEST'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name="resource_contenttype")
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    # # product can be lab tests.
    # product_content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name="product_contenttype")
    # product_object_id = models.PositiveIntegerField()
    # product_content_object = GenericForeignKey()

    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    interator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)

    @classmethod
    def get_if_third_party_integration(cls, test_id):
        mapping_wrt_test = cls.objects.filter(test__id=test_id).first()

        # Return if no test exist over here and it depicts that it is not a part of integrations.
        if not mapping_wrt_test:
            return None

        # Part of the integrations.
        if mapping_wrt_test.content_type == ContentType.objects.get(model='labtest'):
            return {
                'class_name': mapping_wrt_test.interator_class_name,
                'service_type': mapping_wrt_test.service_type
            }

    class Meta:
        db_table = 'integrator_mapping'
