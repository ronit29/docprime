import json
from django.conf import settings
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ondoc.authentication.backends import JWTAuthentication
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser)
from . import serializers


class PlusListViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return PlusProposer.objects.filter(is_live=True)

    def list(self, request):
        resp = {}
        user = request.user
        if not user.is_anonymous and user.active_plus_user is not None:
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        plus_proposer = self.get_queryset()
        body_serializer = serializers.PlusProposerSerializer(plus_proposer, context={'request': request}, many=True)
        resp['plus_data'] = body_serializer.data
        return Response(resp)


class PlusOrderViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def create_order(self, request):
        resp = {}
        user = request.user
        if not user.is_anonymous and user.active_plus_user is not None:
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)