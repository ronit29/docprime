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
        appointment_id = valid_data.pop("appointment_id")
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
                # prescription_pdf_queryset = prescription_models.PresccriptionPdf.objects.filter(id=valid_data.get("id"),
                #                                                                                 appointment_id=valid_data.get("appointment_id"))
                model_serializer = serializers.PrescriptionPDFModelSerializer(prescription_pdf)
                prescription_models.PrescriptionHistory.objects.create(prescription=prescription_pdf,
                                                                       data=model_serializer.data)
                # prescription_pdf_queryset.update(**valid_data)
                # prescription_pdf = prescription_pdf_queryset.first()
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
                prescription_pdf.followup_date = valid_data.get('followup_date')
                prescription_pdf.followup_reason = valid_data.get('followup_reason')
                prescription_pdf.save()
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
                "instructions": None,
            })
        return Response(resp)




