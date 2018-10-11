from rest_framework import viewsets
from . import serializers
from rest_framework.response import Response
from django.http import JsonResponse
from ondoc.account import models as account_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans)
from ondoc.authentication.models import UserProfile
import json
import datetime


class ListInsuranceViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Insurer.objects.filter()

    def list(self, request):
        insurer_data = self.get_queryset()
        body_serializer = serializers.InsurerSerializer(insurer_data, many=True)

        # body_serializer.is_valid(raise_exception=True)
        # valid_data = body_serializer.validated_data
        return Response(body_serializer.data)


class InsuredMemberViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Insurer.objects.filter()

    def summary(self, request):
        serializer = serializers.InsuredMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        members = valid_data.get("members")
        resp = {}

        if valid_data:
            if request.data.get('profile'):
                profile = UserProfile.objects.get(id=request.data.get('profile'))
                pre_insured_members = {}
                insured_members_list = []
                for member in members:

                    pre_insured_members['profile'] = UserProfile.objects.filter(id=profile.id).values()
                    pre_insured_members['first_name'] = member['first_name']
                    pre_insured_members['last_name'] = member['last_name']
                    pre_insured_members['dob'] = member['dob']
                    pre_insured_members['address'] = member['address']
                    pre_insured_members['pincode'] = member['pincode']
                    pre_insured_members['email'] = member['email']
                    pre_insured_members['relation'] = member['relation']

                    insured_members_list.append(pre_insured_members)

            insured_members = {"insurer": valid_data.get('insurer'), "insurance_plan": valid_data.get('insurance_plan'),
                               "insured_members": insured_members_list}

            insurance_transaction = {"insurer": valid_data.get('insurer'),
                                     "insurance_plan": valid_data.get('insurance_plan'),
                                     "user": request.user, "reference_id": " ", "order_id": "",
                                     "type": account_models.PgTransaction.DEBIT, "payment_mode": "",
                                     "response_code": "", "transaction_date": "", "transaction_id": "",
                                     "status": "TODO"}

            insurer = Insurer.objects.filter(id=valid_data.get('insurer').id).values()
            insurance_plan = InsurancePlans.objects.filter(id=valid_data.get('insurance_plan').id).values()
            resp['insurance'] = {"members": insured_members_list, "insurer": insurer, "insurance_plan": insurance_plan}
            return Response(resp)

    def create(self, request):

        insurance_data = request.data.get('insurance')

        order = account_models.Order.objects.create(
            product_id=account_models.Order.INSURANCE_PRODUCT_ID,
            action=account_models.Order.INSURANCE_CREATE,
            action_data=insurance_data,
            amount=3000,
            reference_id=1,
            payment_status=account_models.Order.PAYMENT_PENDING
        )
