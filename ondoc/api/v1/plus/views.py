import json
from django.conf import settings
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ondoc.authentication.backends import JWTAuthentication
from ondoc.authentication.models import User
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


class PlusProfileViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def profile(self, request):
        if settings.IS_PLUS_ACTIVE:
            user_id = request.user.pk
            resp = {}
            if user_id:

                user = User.objects.get(id=user_id)
                plus_user_obj = user.active_plus_user
                if not plus_user_obj or not plus_user_obj.is_valid():
                    return Response({"message": "Docprime Plus associated to user not found or expired."})

                resp['insured_members'] = plus_user_obj.plus_members.all().values('first_name', 'middle_name', 'last_name',
                                                                              'dob', 'relation')
                resp['purchase_date'] = plus_user_obj.purchase_date
                resp['expiry_date'] = plus_user_obj.expire_date
                resp['premium_amount'] = plus_user_obj.amount
                resp['proposer_name'] = plus_user_obj.get_primary_member_profile() if plus_user_obj.get_primary_member_profile() else ''
                
                resp['insurance_status'] = plus_user_obj.status
            else:
                return Response({"message": "User is not valid"},
                                status.HTTP_404_NOT_FOUND)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(resp)