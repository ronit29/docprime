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


class ListInsuranceViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def list(self, request):
        user = request.user
        user_insurance = UserInsurance.objects.filter(user_id=request.user).last()
        if user_insurance and user_insurance.is_valid():
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        insurer_data = self.get_queryset()
        body_serializer = serializers.InsurerSerializer(insurer_data, many=True)
        return Response(body_serializer.data)


class InsuredMemberViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def memberlist(self, request):
        data = {}
        result = {}
        data['id'] = request.query_params.get('id')
        serializer = serializers.UserInsuranceIdsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        parameter = serializer.validated_data
        user_insurance = UserInsurance.objects.get(id=parameter.get('id').id)
        result['insurer_logo'] = user_insurance.insurance_plan.insurer.logo
        member_list = user_insurance.members.all().order_by('id').values('id', 'first_name', 'last_name', 'relation')
        result['members'] = member_list
        disease = InsuranceDisease.objects.filter(is_live=True).values('id', 'disease')
        result['disease'] = disease
        return Response(result)

    def update(self, request):
        resp ={}
        members = request.data.get('members')
        member_serializer = InsuredMemberIdSerializer(data=members, many=True)
        member_serializer.is_valid(raise_exception=True)
        for member in members:
            member_id = member.get('id')
            disease_list = member.get('disease')
            disease_serializer = InsuranceDiseaseIdSerializer(data=disease_list, many=True)
            disease_serializer.is_valid(raise_exception=True)
            for disease in disease_list:
                InsuranceDiseaseResponse.objects.create(disease_id=disease.get('id'), member_id=member_id,
                                                        response=disease.get('response'))
        return Response({"message": "Disease Profile Updated Successfully"}, status.HTTP_200_OK)


class InsuranceOrderViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def age_validate(self, member, insurance_threshold):
        message = {}
        dob_flag = False
        # Calculate day difference between dob and current date
        current_date = datetime.datetime.now().date()
        days_diff = current_date - member['dob']
        days_diff = days_diff.days
        years_diff = days_diff / 365
        years_diff = int(years_diff)
        adult_max_age = insurance_threshold.max_age
        adult_min_age = insurance_threshold.min_age
        child_min_age = insurance_threshold.child_min_age
        # Age validation for parent in years
        if member['member_type'] == "adult":
            if (adult_max_age >= years_diff) and (adult_min_age <= years_diff):
                dob_flag = True
            elif adult_max_age <= years_diff:
                message = {"message": "Adult Age would be less than " + str(adult_max_age) + " years"}
            elif adult_min_age >= years_diff:
                message = {"message": "Adult Age would be more than " + str(adult_min_age) + " years"}
        # Age validation for child in days
        if member['member_type'] == "child":
            if child_min_age <= days_diff:
                dob_flag = True
            else:
                message = {"message": "Child Age would be more than " + str(child_min_age) + " days"}
        return dob_flag, message

    @transaction.atomic
    def create_order(self, request):
        user = request.user

        user_insurance = UserInsurance.objects.filter(user=user).last()
        if user_insurance and user_insurance.is_valid():
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        serializer = serializers.InsuredMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        amount = None
        members = valid_data.get("members")
        resp = {}
        insurance_data = {}

        if valid_data:
            user = request.user
            logged_in_user_id = None
            pre_insured_members = {}
            insured_members_list = []
            insurance_plan = request.data.get('insurance_plan')
            for member in members:
                if insurance_plan:
                    # Age Validation for parent and child
                    insurance_threshold = InsuranceThreshold.objects.filter(insurance_plan_id=
                                                                            insurance_plan).first()
                    dob_flag, error_message = self.age_validate(member, insurance_threshold)
                    if dob_flag:
                        pre_insured_members['dob'] = member['dob']
                    else:
                        return Response(error_message, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({"message": "Insurance Plan is not Valid"}, status=status.HTTP_404_NOT_FOUND)
                # User Profile creation or updation
                # profile_flag, profile, profile_id = self.profile_create_or_update(member, request)
                # if profile_flag:
                #     member_profile = profile
                #     logged_in_user_profile_id = profile_id
                # else:
                #     return Response({"message": "User is not valid"},
                #                 status.HTTP_404_NOT_FOUND)

                pre_insured_members['title'] = member['title']
                pre_insured_members['first_name'] = member['first_name']
                pre_insured_members['middle_name'] = member['middle_name']
                pre_insured_members['last_name'] = member['last_name']
                pre_insured_members['address'] = member['address']
                pre_insured_members['pincode'] = member['pincode']
                pre_insured_members['email'] = member['email']
                pre_insured_members['relation'] = member['relation']
                # pre_insured_members['profile'] = member_profile.get('id')
                if member['profile']:
                    pre_insured_members['profile'] = member['profile'].id
                else:
                    pre_insured_members['profile'] = member['profile']
                pre_insured_members['gender'] = member['gender']
                pre_insured_members['member_type'] = member['member_type']
                pre_insured_members['town'] = member['town']
                pre_insured_members['district'] = member['district']
                pre_insured_members['state'] = member['state']

                insured_members_list.append(pre_insured_members.copy())

                if member['relation'] == 'self':
                    if member['profile']:
                        user_profile = UserProfile.objects.filter(id=member['profile'].id, user_id=request.user.pk).values('id'
                                                                                                            ,'name',
                                                                                                            'email',
                                                                                                            'gender',
                                                                                                            'user_id',
                                                                                                            'dob',
                                                                                                            'phone_number')

                        if user_profile:
                            user_profile = user_profile[0]
                    else:
                        user_profile = {"name": member['first_name'] + " " + member['last_name'], "email":
                            member['email'], "gender": member['gender'], "dob": member['dob']}

        insurance_plan = InsurancePlans.objects.get(id=request.data.get('insurance_plan'))
        transaction_date = datetime.datetime.now()
        if insurance_plan:
            amount = insurance_plan.amount

        expiry_date = transaction_date + timedelta(days=insurance_plan.policy_tenure*365)
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

    def profile_create_or_update(self, member, request):
        profile = {}
        profile_flag = True
        name = "{fname} {lname}".format(fname=member['first_name'], lname=member['last_name'])
        if member['profile'] or UserProfile.objects.filter(name__iexact=name, user=request.user).exists():
            # Check whether Profile exist with same name
            existing_profile = UserProfile.objects.filter(name__iexact=name, user=request.user).first()
            if member['profile']:
                profile = UserProfile.objects.filter(id=member['profile'].id).values('id', 'name', 'email',
                                                                                     'gender', 'user_id', 'dob',
                                                                                     'phone_number').first()
            else:
                if existing_profile:
                    profile = UserProfile.objects.filter(id=existing_profile.id).values('id', 'name', 'email',
                                                                                        'gender', 'user_id',
                                                                                        'dob',
                                                                                        'phone_number').first()

            if profile:
                if profile.get('user_id') == request.user.pk:
                    member_profile = profile.update(name=name, email=member['email'], gender=member['gender'],
                                                    dob=member['dob'])

                    # if member['relation'].lower() == 'self'.lower():
                    if member['profile']:
                        logged_in_user_profile_id = member['profile'].id
                    else:
                        logged_in_user_profile_id = existing_profile.id
                else:
                    profile_flag = False
                    # return Response({"message": "User is not valid"},
                    #                 status.HTTP_404_NOT_FOUND)

        # Create Profile if not exist with name or not exist in profile id from request
        else:
            member_profile = UserProfile.objects.create(name=name,
                                                        email=member['email'], gender=member['gender'],
                                                        user_id=request.user.pk, dob=member['dob'],
                                                        is_default_user=False, is_otp_verified=False,
                                                        phone_number=request.user.phone_number)
            profile = {'id': member_profile.id, 'name': member_profile.name, 'email': member_profile.email,
                       'gender': member_profile.gender, 'user_id': member_profile.user_id,
                       'dob': member_profile.dob, 'phone_number': member_profile.phone_number}

            # if member['relation'].lower() == 'self'.lower():
            logged_in_user_profile_id = member_profile.id

        return profile_flag, profile, logged_in_user_profile_id


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
            resp['insurer_img'] = str(insurer.logo)
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

