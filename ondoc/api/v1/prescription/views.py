from ondoc.api.pagination import paginate_queryset
from django.db import transaction
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status

# from ondoc.api.v1.prescription.serializers import AppointmentPrescriptionSerializer
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer, IsNotAgent, IsDoctor
from . import serializers
from ondoc.authentication.models import User
from ondoc.prescription import models as prescription_models
from ondoc.diagnostic import models as diagnostic_models
from ondoc.api.v1 import utils
from django.utils import timezone
from decimal import Decimal
import logging, random
logger = logging.getLogger(__name__)
from datetime import datetime


class PrescriptionGenerateViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return prescription_models.PresccriptionPdf.objects.none()

    def generate(self, request):
        serializer = serializers.GeneratePrescriptionPDFBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        task = valid_data.pop("task")
        appointment = valid_data.pop("appointment")
        appointment_id = valid_data.pop("appointment_id")
        if not valid_data.get('is_encrypted'):
            valid_data['serial_id'] = str(appointment.hospital.id) + '-' + str(appointment.doctor.id) + '-' + valid_data["serial_id"]
        try:
            if task == prescription_models.PresccriptionPdf.CREATE:
                prescription_pdf = prescription_models.PresccriptionPdf.objects.create(**valid_data,
                                                                                       opd_appointment=appointment if valid_data.get(
                                                                                           'appointment_type') == prescription_models.PresccriptionPdf.DOCPRIME_OPD else None,
                                                                                       offline_opd_appointment=appointment if valid_data.get(
                                                                                           'appointment_type') == prescription_models.PresccriptionPdf.OFFLINE else None)
            else:
                prescription_pdf = valid_data.pop("prescription_pdf")
                model_serializer = serializers.PrescriptionPDFModelSerializer(prescription_pdf)
                prescription_models.PrescriptionHistory.objects.create(prescription=prescription_pdf,
                                                                       data=model_serializer.data)
                prescription_pdf.serial_id = valid_data.get('serial_id')
                prescription_pdf.symptoms_complaints = valid_data.get('symptoms_complaints')
                prescription_pdf.lab_tests = valid_data.get('lab_tests')
                prescription_pdf.special_instructions = valid_data.get('special_instructions')
                prescription_pdf.diagnoses = valid_data.get('diagnoses')
                prescription_pdf.patient_details = valid_data.get('patient_details')
                prescription_pdf.medicines = valid_data.get('medicines')
                if valid_data.get('appointment_type') == prescription_models.PresccriptionPdf.DOCPRIME_OPD:
                    prescription_pdf.opd_appointment = appointment
                else:
                    prescription_pdf.offline_opd_appointment = appointment
                prescription_pdf.appointment_type = valid_data.get('appointment_type')
                prescription_pdf.followup_instructions_date = valid_data.get('followup_instructions_date')
                prescription_pdf.followup_instructions_reason = valid_data.get('followup_instructions_reason')
                prescription_pdf.is_encrypted = valid_data.get('is_encrypted')
                prescription_pdf.save()
        except Exception as e:
            logger.error("Error Creating PDF object " + str(e))
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not valid_data.get("is_encrypted"):
            try:
                file = prescription_pdf.get_pdf(appointment)
                prescription_pdf.prescription_file = file
                prescription_pdf.save()
            except Exception as e:
                logger.error("Error saving PDF object " + str(e))
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        response = serializers.PrescriptionResponseSerializer(prescription_pdf, many=False, context={"request": request})
        return Response(response.data)


class PrescriptionComponentsViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return prescription_models.PresccriptionPdf.objects.none()

    @staticmethod
    def create_objects(data):
        model = dict(serializers.PrescriptionModelComponents.COMPONENT_CHOICES)[data.get('type')]
        object = model.create_or_update(name=data.get('name'), hospital_id=data.get('hospital_id').id,
                                        source_type=prescription_models.PrescriptionEntity.PARTNERS_APP)
        model_serializer = dict(serializers.PrescriptionModelSerializerComponents.COMPONENT_CHOICES)[data.get('type')](object)
        return model_serializer.data

    def save_components(self, request):
        serializer = serializers.BulkCreatePrescriptionComponentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data['data']
        resp = list()
        for data in valid_data:
            created_object = self.create_objects(data)
            resp.append(created_object)
        return Response({'status': 1, 'data': resp})

    def sync_component(self, request):
        serializer = serializers.PrescriptionComponentSyncSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        model = dict(serializers.PrescriptionModelComponents.COMPONENT_CHOICES)[valid_data.get('type')]
        updated_at = valid_data.get('updated_at')
        obj = model.objects
        if updated_at:
            obj = obj.filter(updated_at__date__gte=updated_at)

        if valid_data.get('hospital_id'):
            obj = obj.filter(Q(hospitals__contains=[valid_data['hospital_id'].id]) | Q(moderated=True))
        else:
            obj = obj.filter(moderated=True)
        resp = []
        model_serializer = dict(serializers.PrescriptionModelSerializerComponents.COMPONENT_CHOICES)[valid_data.get('type')]

        resp = model_serializer(obj, many=True).data
        if model == prescription_models.PrescriptionTests:
            if updated_at:
                lab_test_queryset = diagnostic_models.LabTest.objects.filter(updated_at__date__gte=updated_at)
            else:
                lab_test_queryset = diagnostic_models.LabTest.objects.all()
            test_serializer = serializers.PrescriptionLabTestSerializer(lab_test_queryset, many=True)
            resp = resp + test_serializer.data

        return Response(resp)


class AppointmentPrescriptionViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, )

    # def ask_prescription(self, request):
    #     user = request.user
    #     insurance = user.active_insurance
    #     if not insurance:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
    #
    #     serializer = AppointmentPrescriptionSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     valid_data = serializer.validated_data
    #
    #     lab = valid_data.get('lab')
    #     lab_pricing_group = lab.lab_pricing_group
    #     available_lab_test_qs = lab_pricing_group.available_lab_tests.all().filter(test__in=valid_data.get('lab_test'))
    #     mrp = Decimal(0)
    #     for available_lab_test in available_lab_test_qs:
    #         agreed_price = available_lab_test.custom_agreed_price if available_lab_test.custom_agreed_price else available_lab_test.computed_agreed_price
    #         mrp = mrp + agreed_price
    #
    #     start_date = valid_data.get('start_date').date()
    #
    #     resp = insurance.validate_limit_usages(mrp)
    #
    #     return Response(resp)

    def upload_prescription(self, request, *args, **kwargs):
        user = request.user
        insurance = user.active_insurance
        plus_user = user.active_plus_user
        if not insurance and not plus_user:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'User do not have active insurance/VIP Plan.'})

        data = dict()
        document_data = {}
        data['user'] = user.id
        data['prescription_file'] = request.data['prescription_file']
        serializer = serializers.AppointmentPrescriptionUploadSerializer(data=data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        prescription_obj = serializer.save()
        document_data['id'] = prescription_obj.id
        document_data['data'] = serializer.data
        return Response(document_data)


