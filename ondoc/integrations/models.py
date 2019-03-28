from django.conf import settings
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
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True)
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_test_name = models.CharField(max_length=60, null=False, blank=False, default=None)
    name_params_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    @classmethod
    def get_if_third_party_integration(cls, network_id=None):
        if network_id:
            mapping = cls.objects.filter(object_id=network_id, is_active=True).first()
        else:
            return None

        # Return if no test exist over here and it depicts that it is not a part of integrations.
        if not mapping:
            return None

        # Part of the integrations.
        if mapping.content_type == ContentType.objects.get(model='labnetwork'):
            return {
                'class_name': mapping.integrator_class_name,
                'service_type': mapping.service_type
            }

    class Meta:
        db_table = 'integrator_mapping'


class IntegratorProfileMapping(TimeStampedModel):
    class ServiceType(Choices):
        LabTest = 'PROFILES'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    package = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True)
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_package_name = models.CharField(max_length=60, null=False, blank=False, default=None)
    integrator_type = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(default=False)

    @classmethod
    def get_if_third_party_integration(cls, package_id):
        mapping_wrt_package = cls.objects.filter(package__id=package_id, is_active=True).first()

        # Return if no package exist over here and it depicts that it is not a part of integrations.
        if not mapping_wrt_package:
            return None

        # Part of the integrations.
        if mapping_wrt_package.content_type == ContentType.objects.get(model='labnetwork'):
            return {
                'class_name': mapping_wrt_package.integrator_class_name,
                'service_type': mapping_wrt_package.service_type
            }

    class Meta:
        db_table = 'integrator_profile_mapping'


class IntegratorResponse(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING) # model id
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    lead_id = models.CharField(max_length=40, null=True, blank=True)
    dp_order_id = models.CharField(max_length=40, null=True, blank=True)
    integrator_order_id = models.CharField(max_length=40, null=True, blank=True)
    response_data = JSONField(blank=True, null=True)
    report_received = models.BooleanField(default=False)

    class Meta:
        db_table = 'integrator_response'

    @classmethod
    def get_order_summary(cls):
        from ondoc.integrations import service

        integrator_responses = IntegratorResponse.objects.all()
        for integrator_response in integrator_responses:
            if integrator_response.integrator_class_name == 'Thyrocare':
                if settings.THYROCARE_INTEGRATION_ENABLED:
                    is_thyrocare_enabled = True
                else:
                    is_thyrocare_enabled = False
            else:
                is_thyrocare_enabled = True

            if is_thyrocare_enabled:
                integrator_obj = service.create_integrator_obj(integrator_response.integrator_class_name)
                integrator_obj.get_order_summary(integrator_response)

        print("Order Summary for Thyrocare Complete")


class IntegratorReport(TimeStampedModel):
    integrator_response = models.ForeignKey(IntegratorResponse, on_delete=models.CASCADE, null=False)
    pdf_url = models.TextField(null=True, blank=True)
    xml_url = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'integrator_report'


class IntegratorHistory(TimeStampedModel):
    PUSHED_AND_NOT_ACCEPTED = 1
    PUSHED_AND_ACCEPTED = 2
    NOT_PUSHED = 3
    CANCELLED = 4

    STATUS_CHOICES = [(PUSHED_AND_NOT_ACCEPTED, 'Pushed and not accepted, Manage Manually'),
                      (PUSHED_AND_ACCEPTED, 'Pushed and accepted'),
                      (NOT_PUSHED, 'Not pushed, Manage Manually'),
                      (CANCELLED, 'Cancel')]

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    retry_count = models.PositiveIntegerField()
    status = models.PositiveSmallIntegerField(default=NOT_PUSHED, choices=STATUS_CHOICES)
    api_status = models.PositiveIntegerField()
    request_data = JSONField(blank=False, null=False)
    response_data = JSONField(blank=False, null=False)
    api_name = models.CharField(max_length=40, null=False, blank=False)
    api_endpoint = models.TextField(blank=False, null=False)
    accepted_through = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        db_table = 'integrator_history'

    @classmethod
    def create_history(cls, appointment, request, response, url, api_name, integrator_name, api_status, retry_count, status, mode):
        # Need to send arguments as args or kwargs
        lab_appointment_content_type = ContentType.objects.get_for_model(appointment)
        history_obj = IntegratorHistory.objects.filter(content_type=lab_appointment_content_type, object_id=appointment.id,
                                                       status=status, retry_count=retry_count, api_name=api_name).last()
        if not history_obj:
            IntegratorHistory.objects.create(content_type=lab_appointment_content_type, object_id=appointment.id, retry_count=retry_count,
                                             status=status, request_data=request, response_data=response, api_endpoint=url,
                                             api_name=api_name, integrator_class_name=integrator_name, api_status=api_status,
                                             accepted_through=mode)


class IntegratorTestMapping(TimeStampedModel):
    class ServiceType(Choices):
        LabTest = 'LABTEST'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True)
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_test_name = models.CharField(max_length=60, null=False, blank=False, default=None)
    name_params_required = models.BooleanField(default=False)
    test_type = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'integrator_test_mapping'