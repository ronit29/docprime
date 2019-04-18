from ondoc.api.pagination import paginate_queryset
from django.db import transaction
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer, IsNotAgent
from . import serializers
from ondoc.authentication.models import User
from ondoc.prescription import models as prescription_models
import logging
logger = logging.getLogger(__name__)


class PrescriptionGenerateViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsConsumer, IsNotAgent)

    def get_queryset(self):
        return prescription_models.objects.prefetch_related('compliment').filter(is_live=True)

    def prompt_close(self, request):
        serializer = serializers.RatingPromptCloseBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        resp = {}
        return Response(resp)

