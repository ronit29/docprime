from ondoc.authentication import models as auth_models
from ondoc.api.v1 import utils as v1_utils
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ondoc.authentication.backends import JWTAuthentication
from django.contrib.auth import get_user_model
import logging
from django.db.models import Q, F
from rest_framework.response import Response


User = get_user_model()
logger = logging.getLogger(__name__)


class ManageableLabsViewSet(viewsets.GenericViewSet):
    
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    def get_queryset(self):
        return auth_models.GenericLabAdmin.objects.none()

    def list(self, request):
        user = request.user
        response = []
        manageable_lab_list = auth_models.GenericLabAdmin.objects.filter(user=user, is_disabled=False)\
                                                                 .select_related('lab')

        for data in manageable_lab_list:
            obj = {}
            obj['lab'] = data.lab.id
            obj['lab_name'] = data.lab.name
            obj['is_live'] = data.lab.is_live
            obj['licence'] = data.lab.license
            response.append(obj)

        return Response(response)
