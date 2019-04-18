from ondoc.api.pagination import paginate_queryset
from django.db import transaction
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer, IsNotAgent, IsDoctor
from . import serializers
from ondoc.authentication.models import User
from ondoc.prescription import models as prescription_models
from ondoc.api.v1 import utils
from django.utils import timezone
import logging, random
logger = logging.getLogger(__name__)
from datetime import datetime


class PrescriptionGenerateViewSet(viewsets.GenericViewSet):

    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated, IsDoctor)

    def get_queryset(self):
        return prescription_models.PresccriptionPdf.objects.none()

    def generate(self, request):
        serializer = serializers.GeneratePrescriptionPDFBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        prescription_pdf = prescription_models.PresccriptionPdf.objects.create(medicines=valid_data.get('medicines'),
                                                                               observations=valid_data.get('observation'),
                                                                               appointment_id=valid_data.get('appointment_id'),
                                                                               appointment_type=valid_data.get('appointment_type'),
                                                                               symptoms=valid_data.get('symptoms'))
        file = prescription_pdf.get_pdf()
        what = file

        return Response({'status': 1})

