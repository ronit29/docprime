from ondoc.api.v1.insurance.serializers import InsuredMemberIdSerializer, InsuranceDiseaseIdSerializer
from ondoc.api.v1.utils import insurance_transform
from rest_framework import viewsets
from django.core import serializers as core_serializer

from ondoc.api.v1.utils import payment_details
from . import serializers
from rest_framework.response import Response
from ondoc.account import models as account_models
from ondoc.doctor import models as doctor_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans, UserInsurance,
                                    InsuranceTransaction, InsuranceDisease, InsuranceDiseaseResponse)
from ondoc.authentication.models import UserProfile
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions
from django.db.models import F
import datetime
from django.db import transaction
from ondoc.authentication.models import User
from datetime import timedelta
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


class ListInsuranceViewSet(viewsets.GenericViewSet):
    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def list(self, request):
        user = request.user
        user_insurance = UserInsurance.objects.filter(user_id=request.user).last()
        if user_insurance and user_insurance.is_valid():
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        insurer_data = self.get_queryset()
        body_serializer = serializers.InsurerSerializer(insurer_data,context={'request': request}, many=True)
        return Response(body_serializer.data)


class InsuredMemberViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def memberlist(self, request):
        data = {}
        result = {}
        data['id'] = request.query_params.get('id')
        serializer = serializers.UserInsuranceIdsSerializer(data=data)
        if not serializer.is_valid() and serializer.errors:
            logger.error(str(serializer.errors))
        serializer.is_valid(raise_exception=True)
        parameter = serializer.validated_data
        user_insurance = UserInsurance.objects.get(id=parameter.get('id').id)
        result['insurer_logo'] = request.build_absolute_uri(user_insurance.insurance_plan.insurer.logo.url) \
            if user_insurance.insurance_plan.insurer.logo is not None and \
               user_insurance.insurance_plan.insurer.logo.name else None
        member_list = user_insurance.members.all().order_by('id').values('id', 'first_name', 'last_name', 'relation')
        result['members'] = member_list
        disease = InsuranceDisease.objects.filter(is_live=True).values('id', 'disease')
        result['disease'] = disease
        return Response(result)

    def update(self, request):
        resp ={}
        members = request.data.get('members')
        member_serializer = InsuredMemberIdSerializer(data=members, many=True)
        if not member_serializer.is_valid() and member_serializer.errors:
            logger.error(str(member_serializer.errors))
        member_serializer.is_valid(raise_exception=True)
        for member in members:
            member_id = member.get('id')
            disease_list = member.get('disease')
            disease_serializer = InsuranceDiseaseIdSerializer(data=disease_list, many=True)
            if not disease_serializer.is_valid() and disease_serializer.errors:
                logger.error(str(disease_serializer.errors))

            disease_serializer.is_valid(raise_exception=True)
            for disease in disease_list:
                InsuranceDiseaseResponse.objects.create(disease_id=disease.get('id'), member_id=member_id,
                                                        response=disease.get('response'))
        return Response({"message": "Disease Profile Updated Successfully"}, status.HTTP_200_OK)


class InsuranceOrderViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def create_order(self, request):

        user = request.user

        user_insurance = UserInsurance.objects.filter(user=user).last()
        if user_insurance and user_insurance.is_valid():
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        serializer = serializers.InsuredMemberSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid() and serializer.errors:
            logger.error(str(serializer.errors))

        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        amount = None
        members = valid_data.get("members")
        resp = {}
        insurance_data = {}
        insurance_plan = request.data.get('insurance_plan')
        if not insurance_plan:
            return Response({"message": "Insurance Plan is not Valid"}, status=status.HTTP_404_NOT_FOUND)
        if valid_data:
            user = request.user
            pre_insured_members = {}
            insured_members_list = []

            for member in members:
                pre_insured_members['dob'] = member['dob']
                pre_insured_members['title'] = member['title']
                pre_insured_members['first_name'] = member['first_name']
                pre_insured_members['middle_name'] = member['middle_name']
                pre_insured_members['last_name'] = member['last_name']
                pre_insured_members['address'] = member['address']
                pre_insured_members['pincode'] = member['pincode']
                pre_insured_members['email'] = member['email']
                pre_insured_members['relation'] = member['relation']
                pre_insured_members['profile'] = member.get('profile').id if member.get('profile') is not None else None
                pre_insured_members['gender'] = member['gender']
                pre_insured_members['member_type'] = member['member_type']
                pre_insured_members['town'] = member['town']
                pre_insured_members['district'] = member['district']
                pre_insured_members['state'] = member['state']

                insured_members_list.append(pre_insured_members.copy())

                if member['relation'] == 'self':
                    if member['profile']:
                        user_profile = UserProfile.objects.filter(id=member['profile'].id,
                                                                  user_id=request.user.pk).values('id', 'name', 'email',
                                                                                                'gender', 'user_id',
                                                                                                'dob', 'phone_number').first()

                    else:
                        user_profile = {"name": member['first_name'] + " " + member['last_name'], "email":
                            member['email'], "gender": member['gender'], "dob": member['dob']}

        insurance_plan = InsurancePlans.objects.get(id=request.data.get('insurance_plan'))
        transaction_date = datetime.datetime.now()
        amount = insurance_plan.amount

        expiry_date = transaction_date + timedelta(days=insurance_plan.policy_tenure*364)
        expiry_date = datetime.datetime.combine(expiry_date, datetime.datetime.max.time())
        user_insurance = {'insurer': insurance_plan.insurer_id, 'insurance_plan': insurance_plan.id, 'purchase_date':
                            transaction_date, 'expiry_date': expiry_date, 'premium_amount': amount,
                            'user': request.user.pk, "insured_members": insured_members_list}
        insurance_data = {"profile_detail": user_profile, "insurance_plan": insurance_plan.id,
                          "user": request.user.pk, "user_insurance": user_insurance}

        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance

        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            resp['is_agent'] = True

        insurance_data = insurance_transform(insurance_data)

        if balance < amount or resp['is_agent']:

            payable_amount = amount - balance

            order = account_models.Order.objects.create(
                product_id=account_models.Order.INSURANCE_PRODUCT_ID,
                action=account_models.Order.INSURANCE_CREATE,
                action_data=insurance_data,
                amount=payable_amount,
                wallet_amount=balance,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            resp["status"] = 1
            resp['data'], resp["payment_required"] = payment_details(request, order)
        else:
            wallet_amount = amount

            order = account_models.Order.objects.create(
                product_id=account_models.Order.INSURANCE_PRODUCT_ID,
                action=account_models.Order.INSURANCE_CREATE,
                action_data=insurance_data,
                amount=0,
                wallet_amount=wallet_amount,
                payment_status=account_models.Order.PAYMENT_PENDING
            )

            insurance_object = order.process_order()
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {'id': insurance_object.id}

        return Response(resp)


class InsuranceProfileViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def profile(self, request):
        user_id = request.user.pk
        resp = {}
        if user_id:

            user = User.objects.get(id=user_id)
            user_insurance = UserInsurance.objects.filter(user=user).last()
            if not user_insurance or not user_insurance.is_valid():
                return Response({"message": "Insurance not found or expired."})
            insurer = user_insurance.insurance_plan.insurer
            resp['insured_members'] = user_insurance.members.all().values('first_name', 'last_name', 'dob', 'relation')
            resp['purchase_date'] = user_insurance.purchase_date
            resp['expiry_date'] = user_insurance.expiry_date
            resp['policy_number'] = user_insurance.policy_number
            resp['insurer_name'] = insurer.name
            resp['insurer_img'] = request.build_absolute_uri(insurer.logo.url) if insurer.logo is not None and insurer.logo.name else None
            resp['coi_url'] = request.build_absolute_uri(user_insurance.coi.url) if user_insurance.coi is not None and \
                                                                                    user_insurance.coi.name else None
            resp['premium_amount'] = user_insurance.premium_amount
            resp['proposer_name'] = user_insurance.members.all().filter(relation='self').values('first_name',
                                                                                                'middle_name',
                                                                                                'last_name')
        else:
            return Response({"message": "User is not valid"},
                            status.HTTP_404_NOT_FOUND)

        return Response(resp)


class InsuranceValidationViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def validation(self, request):
        resp = {}
        resp['is_user_insured'] = False
        resp['is_insurance_cover'] = False
        resp['insurance_threshold'] = 0
        resp['insurance_message'] = ""
        user = request.user
        serializer = serializers.InsuranceValidationSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid() and serializer.errors:
            logger.error(str(serializer.errors))

        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        resp = {}
        user_insurance = user.purchased_insurance.filter().order_by('id').last()
        if user_insurance and user_insurance.is_valid():
            threshold = user_insurance.insurance_plan.threshold.filter().first()
            if not user_insurance.is_appointment_valid(valid_data.get('time_slot_start')):
                resp['is_user_insured'] = True
                resp['is_insurance_cover'] = False
                resp['insurance_threshold'] = threshold.opd_amount_limit
                resp['insurance_message'] = "Appointment date not covered under insurance tenure."
                return Response(resp)
            # if type == "doctor":
                # if not user_insurance.is_opd_appointment_count_valid(valid_data):
                #     resp['is_user_insured'] = True
                #     resp['is_insurance_cover'] = False
                #     resp['insurance_threshold'] = threshold.opd_amount_limit
                #     resp['insurance_failure_message'] = "Monthly visit for the doctor exceeded"
            if valid_data.get('doctor'):
                is_appointment_insured, insurance_id, insurance_message = user_insurance.doctor_specialization_validation(valid_data)
                resp['is_user_insured'] = True
                resp['is_insurance_cover'] = is_appointment_insured
                resp['insurance_threshold'] = threshold.opd_amount_limit
                resp['insurance_message'] = insurance_message
                return Response(resp)
            elif valid_data.get('lab'):
                resp['is_user_insured'] = True
                resp['is_insurance_cover'] = True
                resp['insurance_threshold'] = threshold.lab_amount_limit
                resp['insurance_message'] = "Cover Under Insurance"
                return Response(resp)
            else:
                resp['is_user_insured'] = True
                resp['is_insurance_cover'] = False
                resp['insurance_threshold'] = threshold.lab_amount_limit
                resp['insurance_message'] = "There is no doctor or lab selected for insurance"
                return Response(resp)
        else:
            resp['is_user_insured'] = False
            resp['is_insurance_cover'] = False
            resp['insurance_threshold'] = 0
            resp['insurance_message'] = ""
        return Response(resp)

