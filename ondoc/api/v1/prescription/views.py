from ondoc.api.pagination import paginate_queryset
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer, IsNotAgent, IsDoctor
from . import serializers
from ondoc.authentication.models import User
from ondoc.prescription import models as prescription_models
from ondoc.diagnostic import models as diagnostic_models
from ondoc.api.v1 import utils
from django.utils import timezone
from django.core import serializers as django_serializers
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
        valid_data['serial_id'] = str(appointment.hospital.id) + '-' + str(appointment.doctor.id) + '-' + valid_data["serial_id"]
        try:
            if task == prescription_models.PresccriptionPdf.CREATE:
                # prescription_pdf = prescription_models.PresccriptionPdf.objects.create(id=valid_data.get("id"),
                #                                                                        medicines=valid_data.get('medicines'),
                #                                                                        special_instructions=valid_data.get('special_instructions'),
                #                                                                        lab_tests=valid_data.get('tests'),
                #                                                                        diagnoses=valid_data.get('diagnoses'),
                #                                                                        symptoms_complaints=valid_data.get('symptoms_complaints'),
                #                                                                        patient_details=valid_data.get('patient_details'),
                #                                                                        appointment_id=valid_data.get('appointment_id'),
                #                                                                        appointment_type=valid_data.get('appointment_type'),
                #                                                                        followup_instructions_date=valid_data.get('followup_date'),
                #                                                                        followup_instructions_reason=valid_data.get('followup_reason'))
                prescription_pdf = prescription_models.PresccriptionPdf.objects.create(**valid_data)
            else:
                prescription_pdf_queryset = prescription_models.PresccriptionPdf.objects.filter(id=valid_data.get("id"), appointment_id=valid_data.get("appointment_id"))
                model_serializer = serializers.PrescriptionPdfModelSerializer(prescription_pdf_queryset.first())
                prescription_models.PrescriptionHistory.objects.create(data=model_serializer.data)
                prescription_pdf_queryset.update(**valid_data)
                prescription_pdf = prescription_pdf_queryset.first()
        except Exception as e:
            logger.error("Error Creating PDF object " + str(e))
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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

    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return prescription_models.PresccriptionPdf.objects.none()

    # TODO - ADD SOURCE TYPE
    def save_component(self, request):
        serializer = serializers.PrescriptionComponentBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        model = dict(serializers.PrescriptionModelComponents.COMPONENT_CHOICES)[valid_data.get('type')]
        object = model.create_or_update(name=valid_data.get('name'), hospital_id=valid_data.get('hospital_id').id,
                                        source_type=prescription_models.PrescriptionEntity.PARTNERS_APP,
                                        quantity=valid_data.get('quantity'),
                                        dosage_type=valid_data.get('dosage_type'),
                                        time=valid_data.get('time'),
                                        duration_type=valid_data.get('duration_type'),
                                        duration=valid_data.get('duration'),
                                        is_before_meal=valid_data.get('is_before_meal'),
                                        additional_notes=valid_data.get('additional_notes'))
        model_serializer = dict(serializers.PrescriptionModelSerializerComponents.COMPONENT_CHOICES)[valid_data.get('type')](object)
        return Response({'status': 1, 'data': model_serializer.data})

    # TODO - ADD SOURCE TYPE
    def sync_component(self, request):
        serializer = serializers.PrescriptionComponentSyncSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        model = dict(serializers.PrescriptionModelComponents.COMPONENT_CHOICES)[valid_data.get('type')]
        if valid_data.get('hospital_id'):
            objects = model.objects.filter(Q(hospitals__contains=[valid_data['hospital_id'].id]) | Q(moderated=True))
        else:
            objects = model.objects.filter(moderated=True)
        resp = []
        model_serializer = dict(serializers.PrescriptionModelSerializerComponents.COMPONENT_CHOICES)[
            valid_data.get('type')]
        for obj in objects.all():
            resp.append(model_serializer(obj).data)
        lab_test_queryset = diagnostic_models.LabTest.objects.all()
        for obj in lab_test_queryset:
            resp.append({
                "id": obj.id,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
                "name": obj.name,
                "moderated": True,
                "hospitals": [],
                "source_type": None,
                "instruction": None,
            })
        return Response(resp)




