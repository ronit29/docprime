from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.authentication.models import TimeStampedModel
from ondoc.diagnostic.models import LabTest
from ondoc.common.helper import Choices
from django.contrib.postgres.fields import JSONField

# Create your models here.


class IntegratorMapping(TimeStampedModel):
    class ServiceType(Choices):
        LabTest = 'LABTEST'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name="resource_contenttype")
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True, limit_choices_to={'is_package': False})
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_test_name = models.CharField(max_length=60, null=False, blank=False, default=None)
    is_active = models.BooleanField(default=False)

    @classmethod
    def get_if_third_party_integration(cls, test_id):
        mapping_wrt_test = cls.objects.filter(test__id=test_id, is_active=True).first()

        # Return if no test exist over here and it depicts that it is not a part of integrations.
        if not mapping_wrt_test:
            return None

        # Part of the integrations.
        if mapping_wrt_test.content_type == ContentType.objects.get(model='labtest'):
            return {
                'class_name': mapping_wrt_test.integrator_class_name,
                'service_type': mapping_wrt_test.service_type
            }

    class Meta:
        db_table = 'integrator_mapping'


class IntegratorProfileMapping(TimeStampedModel):
    class ServiceType(Choices):
        LabTest = 'PROFILES'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    package = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True, limit_choices_to={'is_package': True})
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_package_name = models.CharField(max_length=60, null=False, blank=False, default=None)
    is_active = models.BooleanField(default=False)

    @classmethod
    def get_if_third_party_integration(cls, package_id):
        mapping_wrt_package = cls.objects.filter(package__id=package_id, is_active=True).first()

        # Return if no package exist over here and it depicts that it is not a part of integrations.
        if not mapping_wrt_package:
            return None

        # Part of the integrations.
        if mapping_wrt_package.content_type == ContentType.objects.get(model='labtest'):
            return {
                'class_name': mapping_wrt_package.integrator_class_name,
                'service_type': mapping_wrt_package.service_type
            }

    class Meta:
        db_table = 'integrator_profile_mapping'
