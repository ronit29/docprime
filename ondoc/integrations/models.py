from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.authentication.models import TimeStampedModel
from ondoc.common.helper import Choices
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db import transaction
import reversion
from ondoc.doctor.models import DoctorClinic
from ondoc.matrix.tasks import push_appointment_to_matrix
from ondoc.diagnostic.models import TestParameter
import logging

logger = logging.getLogger(__name__)
# Create your models here.


class IntegratorMapping(TimeStampedModel):
    from ondoc.diagnostic.models import LabTest

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
    from ondoc.diagnostic.models import LabTest

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
        is_integrator_enabled = False
        for integrator_response in integrator_responses:
            if integrator_response.integrator_class_name == 'Thyrocare':
                if settings.THYROCARE_INTEGRATION_ENABLED:
                    is_integrator_enabled = True
            elif integrator_response.integrator_class_name == 'Lalpath':
                if settings.LAL_PATH_INTEGRATION_ENABLED:
                    is_integrator_enabled = True
            else:
                is_integrator_enabled = False

            if is_integrator_enabled:
                integrator_obj = service.create_integrator_obj(integrator_response.integrator_class_name)
                integrator_obj.get_order_summary(integrator_response)

        print("Order Summary for Thyrocare Complete")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        push_to_matrix = True
        transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix))

    def app_commit_tasks(self, push_to_matrix):
        if push_to_matrix:
            # Push the appointment data to the matrix
            try:
                push_appointment_to_matrix.apply_async(
                    ({'type': 'LAB_APPOINTMENT', 'appointment_id': self.object_id, 'product_id': 5,
                      'sub_product_id': 2},), countdown=5)
            except Exception as e:
                logger.error(str(e))


class IntegratorReport(TimeStampedModel):
    integrator_response = models.ForeignKey(IntegratorResponse, on_delete=models.CASCADE, null=False)
    pdf_url = models.TextField(null=True, blank=True)
    xml_url = models.TextField(null=True, blank=True)
    json_data = JSONField(null=True, default={})

    def get_transformed_report(self):
        from collections import OrderedDict
        json_data = self.json_data
        response = {}

        if json_data.__class__.__name__ == 'list' and json_data:
            response['name'] = json_data[0].get('NAME')
            response['tests'] = {}
            for test_json in json_data:
                integrator_test = IntegratorTestMapping.objects.filter(integrator_test_name=test_json['TESTS']).first()
                if not integrator_test:
                    continue

                response['tests'][integrator_test.test.id] = {}

                test_parameter_list = list()
                test_parameter_list.extend(test_json['RED'])
                test_parameter_list.extend(test_json['WHITE'])

                test_parameter_list_dict = OrderedDict()
                for tp in test_parameter_list:
                    test_parameter_list_dict[tp.get('TEST_CODE')] = tp
                
                parameter_dict = {}

                test_parameter_code_list = list(map(lambda x: x.get('TEST_CODE'), test_parameter_list))
                integrator_test_parameter_mappings = IntegratorTestParameterMapping.objects.filter(integrator_test_name__in=[test_parameter_code_list])
                for it in integrator_test_parameter_mappings:
                    parameter_dict[it.id] = test_parameter_list_dict.get(it.integrator_test_name)

                response['tests'][integrator_test.test.id]['parameters'] = parameter_dict

        return response

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


class IntegratorCity(TimeStampedModel):
    city_name = models.CharField(max_length=60, null=True, blank=True)
    city_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'integrator_city'


@reversion.register()
class IntegratorTestMapping(TimeStampedModel):
    from ondoc.diagnostic.models import LabTest

    class ServiceType(Choices):
        LabTest = 'LABTEST'

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True)
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    service_type = models.CharField(max_length=30, choices=ServiceType.as_choices(), null=False, blank=False, default=None)
    integrator_product_data = JSONField(blank=True, null=True)
    integrator_test_name = models.CharField(max_length=150, null=False, blank=False)
    name_params_required = models.BooleanField(default=False)
    test_type = models.CharField(max_length=30, null=True, blank=True)
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
        db_table = 'integrator_test_mapping'


class IntegratorTestParameterMapping(TimeStampedModel):
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    integrator_test_name = models.CharField(max_length=60, null=True, blank=True)
    test_parameter_chat = models.ForeignKey('diagnostic.TestParameterChat', on_delete=models.CASCADE, null=True)
    response_data = JSONField(blank=True, null=True)
    test_parameter = models.ForeignKey(TestParameter, related_name='integrator_mapped_parameters', on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = 'integrator_test_parameter_mapping'


class IntegratorHospitalMappings(TimeStampedModel):
    from ondoc.doctor.models import Hospital
    integrator_hospital_name = models.CharField(max_length=60, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'integrator_hospital_mappings'


class IntegratorDoctorMappings(TimeStampedModel):
    integrator_doctor_id = models.PositiveIntegerField()
    integrator_hospital_id = models.PositiveIntegerField(null=True)
    title = models.CharField(max_length=10, null=True, blank=True)
    first_name = models.CharField(max_length=160, null=False, blank=False)
    middle_name = models.CharField(max_length=40, null=True, blank=True)
    last_name = models.CharField(max_length=40, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    qualification = models.TextField(null=True, blank=True)
    specialities = models.CharField(max_length=100, null=True, blank=True)
    hospital_name = models.CharField(max_length=100, null=False, blank=False)
    city = models.CharField(max_length=40, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    primary_contact = models.CharField(max_length=20, null=True, blank=True)
    secondary_contact = models.CharField(max_length=20, null=True, blank=True)
    emergency_contact = models.CharField(max_length=20, null=True, blank=True)
    helpline_sos = models.CharField(max_length=20, null=True, blank=True)
    integrator_doctor_data = JSONField(blank=True, null=True)
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE, null=True)
    is_active = models.BooleanField(default=False)
    integrator_class_name = models.CharField(max_length=30, null=False, blank=False)

    @classmethod
    def get_if_third_party_integration(cls, doctor_clinic_id=None):
        if doctor_clinic_id:
            dc_mapping = IntegratorDoctorClinicMapping.objects.filter(doctor_clinic_id=doctor_clinic_id).first()
            # mapping = cls.objects.filter(doctor_clinic_id=doctor_clinic_id, is_active=True).first()
        else:
            return None

        # Return if no test exist over here and it depicts that it is not a part of integrations.
        if not dc_mapping:
            return None

        mapping = cls.objects.filter(id=dc_mapping.integrator_doctor_mapping_id).first()
        # Part of the integrations.
        return {'class_name': mapping.integrator_class_name, 'id': mapping.id}

    class Meta:
        db_table = 'integrator_doctor_mappings'


class IntegratorLabTestParameterMapping(TimeStampedModel):
    integrator_class_name = models.CharField(max_length=40, null=False, blank=False)
    integrator_test_parameter_code = models.CharField(max_length=60, null=True, blank=True, unique=True)
    integrator_test_name = models.CharField(max_length=100, null=True, blank=True, unique=True)
    test_parameter = models.ForeignKey(TestParameter, related_name='integrator_mapped_test_parameters', on_delete=models.DO_NOTHING, null=True)

    class Meta:
        db_table = 'integrator_lab_test_parameter_mapping'
        unique_together = (('integrator_class_name', 'integrator_test_parameter_code'), )


class IntegratorTestCityMapping(TimeStampedModel):
    integrator_city = models.ForeignKey(IntegratorCity, null=True, on_delete=models.DO_NOTHING)
    integrator_test_mapping = models.ForeignKey(IntegratorTestMapping, null=True, on_delete=models.DO_NOTHING, related_name='mapped_city_test')

    class Meta:
        db_table = 'integrator_test_city_mapping'


class IntegratorLabCode(TimeStampedModel):
    from ondoc.diagnostic.models import Lab
    lab_code = models.CharField(max_length=30, null=True, blank=True)
    warehouse_code = models.CharField(max_length=50, null=True, blank=True)
    lab = models.ForeignKey(Lab, null=False, blank=False, related_name='lab_code', on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'integrator_lab_code'


class IntegratorHospitalCode(TimeStampedModel):
    from ondoc.doctor.models import Hospital
    city_code = models.CharField(max_length=30, null=True, blank=True)
    clinic_code = models.CharField(max_length=50, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, null=False, blank=False, related_name='hos_code', on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'integrator_hospital_code'


class IntegratorDoctorClinicMapping(TimeStampedModel):
    integrator_doctor_mapping = models.ForeignKey(IntegratorDoctorMappings, null=False, blank=False, related_name='integrator_doctor', on_delete=models.DO_NOTHING)
    doctor_clinic = models.ForeignKey(DoctorClinic, null=False, blank=False, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'integrator_doctor_clinic_mapping'
