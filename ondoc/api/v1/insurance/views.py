from ondoc.api.v1.utils import insurance_transform
from rest_framework import viewsets

from ondoc.api.v1.utils import payment_details
from . import serializers
from rest_framework.response import Response
from ondoc.account import models as account_models
from ondoc.doctor import models as doctor_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans, UserInsurance,
                                    InsuranceTransaction)
from ondoc.authentication.models import UserProfile
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions
from django.db.models import F
import datetime
from django.db import transaction
from ondoc.authentication.models import User


class ListInsuranceViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def list(self, request):
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
        data['id'] = request.query_params.get('id')
        serializer = serializers.InsuredTransactionIdsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        parameter = serializer.validated_data
        member_list = InsuranceTransaction.objects.filter(id=parameter['id'].id).values('insured_members',
                                                                                        insurer_name=F('insurer__name'))

        return Response(member_list[0])

    def update(self, request):
        serializer = serializers.InsuredMemberIdsSerializer(data=request.data.get('members'), many=True)
        serializer.is_valid(raise_exception=True)
        member_list = serializer.validated_data
        for member in member_list:
            insured_member = InsuredMembers.objects.filter(id=member.get('id').id).first()
            if not member.get('hypertension') is None:
                insured_member.hypertension = member.get('hypertension')
            if not member.get('diabetes') is None:
                insured_member.diabetes = member.get('diabetes')
            if not member.get('heart_disease') is None:
                insured_member.heart_disease = member.get('heart_disease')
            if not member.get('liver_disease') is None:
                insured_member.liver_disease = member.get('liver_disease')
            insured_member.save()
        return Response({"message": "User Profile Updated Successfully"}, status.HTTP_200_OK)

    # def summary(self, request):
    #     serializer = serializers.InsuredMemberSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     valid_data = serializer.validated_data
    #
    #     members = valid_data.get("members")
    #     resp = {}
    #
    #     if valid_data:
    #         user = request.user
    #         logged_in_user_id = None
    #         pre_insured_members = {}
    #         insured_members_list = []
    #         for member in members:
    #             profile = {}
    #             name = member['first_name'] + " " + member['last_name']
    #             dob = member['dob']
    #             # Calculate day difference between dob and current date
    #             current_date = datetime.datetime.now().date()
    #             days_diff = current_date - dob
    #             days_diff = days_diff.days
    #             years_diff = days_diff / 365
    #             years_diff = int(years_diff)
    #             if valid_data.get('insurance_plan'):
    #                 # Age Validation for parent and child
    #                 insurance_threshold = InsuranceThreshold.objects.filter(insurance_plan_id=
    #                                                                     valid_data.get('insurance_plan').id,
    #                                                                     insurer_id=valid_data.get('insurer')).first()
    #                 adult_max_age = insurance_threshold.max_age
    #                 adult_min_age = insurance_threshold.min_age
    #                 child_min_age = insurance_threshold.child_min_age
    #                 # Age validation for parent in years
    #                 if member['member_type'] == "adult":
    #                     if (adult_max_age >= years_diff) and (adult_min_age <= years_diff):
    #                         pre_insured_members['dob'] = member['dob']
    #                     elif adult_max_age <= years_diff:
    #                         return Response({"message": "Adult Age would be less than " + str(adult_max_age) + " years"},
    #                                         status.HTTP_404_NOT_FOUND)
    #                     elif adult_min_age >= years_diff:
    #                         return Response({"message": "Adult Age would be more than " + str(adult_min_age) + " years"},
    #                                         status.HTTP_404_NOT_FOUND)
    #                 # Age validation for child in days
    #                 if member['member_type'] == "child":
    #                     if child_min_age <= days_diff:
    #                         pre_insured_members['dob'] = member['dob']
    #                     else:
    #                         return Response({"message": "Child Age would be more than " + str(child_min_age) + " days"},
    #                                         status.HTTP_404_NOT_FOUND)
    #
    #             # User Profile creation or updation
    #             if member['profile'] or UserProfile.objects.filter(name=name, user=request.user).exists():
    #                 # Check whether Profile exist with same name
    #                 existing_profile = UserProfile.objects.filter(name=name, user=request.user).first()
    #                 if member['profile']:
    #                     profile = UserProfile.objects.filter(id=member['profile'].id).values('id', 'name', 'email',
    #                                                                                      'gender', 'user_id', 'dob',
    #                                                                                      'phone_number').first()
    #                 else:
    #                     if existing_profile:
    #                         profile = UserProfile.objects.filter(id=existing_profile.id).values('id', 'name', 'email',
    #                                                                                              'gender', 'user_id',
    #                                                                                              'dob',
    #                                                                                              'phone_number').first()
    #
    #                 if profile:
    #                     if profile.get('user_id') == request.user.pk:
    #                         member_profile = profile.update(name=name, email=member['email'], gender=member['gender'],
    #                                                         dob=member['dob'])
    #
    #                         if member['relation'].lower() == 'self'.lower():
    #                             if member['profile']:
    #                                 logged_in_user_id = member['profile'].id
    #                             else:
    #                                 logged_in_user_id = existing_profile.id
    #                     else:
    #                         return Response({"message": "User is not valid"},
    #                                         status.HTTP_404_NOT_FOUND)
    #
    #             # Create Profile if not exist with name or not exist in profile id from request
    #             else:
    #                 member_profile = UserProfile.objects.create(name=name,
    #                                                             email=member['email'], gender=member['gender'],
    #                                                             user_id=request.user.pk, dob=member['dob'],
    #                                                             is_default_user=False, is_otp_verified=False,
    #                                                             phone_number=request.user.phone_number)
    #                 profile = {'id': member_profile.id, 'name': member_profile.name, 'email': member_profile.email,
    #                            'gender': member_profile.gender, 'user_id': member_profile.user_id,
    #                            'dob': member_profile.dob, 'phone_number': member_profile.phone_number}
    #
    #                 if member['relation'].lower() == 'self'.lower():
    #                     logged_in_user_id = member_profile.id
    #
    #             pre_insured_members['first_name'] = member['first_name']
    #             pre_insured_members['last_name'] = member['last_name']
    #
    #             pre_insured_members['address'] = member['address']
    #             pre_insured_members['pincode'] = member['pincode']
    #             pre_insured_members['email'] = member['email']
    #             pre_insured_members['relation'] = member['relation']
    #             pre_insured_members['member_profile'] = profile
    #
    #             insured_members_list.append(pre_insured_members.copy())
    #
    #         insurer = Insurer.objects.filter(id=valid_data.get('insurer').id).values()
    #         insurance_plan = InsurancePlans.objects.filter(id=valid_data.get('insurance_plan').id).values()
    #         user_profile = UserProfile.objects.filter(id=logged_in_user_id, user_id=request.user.pk).values('id','name',
    #                                                                                                      'email',
    #                                                                                                      'gender',
    #                                                                                                      'user_id',
    #                                                                                                      'dob',
    #                                                                                                      'phone_number')
    #
    #         resp['insurance'] = {"profile_detail": user_profile[0], "insured_members": insured_members_list, "insurer": insurer[0],
    #                              "insurance_plan": insurance_plan[0], "user": request.user.pk}
    #         return Response(resp)


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
        serializer = serializers.InsuredMemberSerializer(data=request.data.get('insurance'))
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
            for member in members:
                if valid_data.get('insurance_plan'):
                    # Age Validation for parent and child
                    insurance_threshold = InsuranceThreshold.objects.filter(insurance_plan_id=
                                                                            valid_data.get('insurance_plan').id,
                                                                            insurer_id=valid_data.get(
                                                                                'insurer')).first()
                    # pre_insured_members['dob'] = self.age_validate(member, insurance_threshold)
                    dob = self.age_validate(member, insurance_threshold)
                    if dob[0]:
                        pre_insured_members['dob'] = member['dob']
                    else:
                        return Response(dob[1], status=status.HTTP_404_NOT_FOUND)

                # User Profile creation or updation
                profile = self.profile_create_or_update(member, request)
                if profile[0]:
                    member_profile = profile[1]
                    logged_in_user_profile_id = profile[2]
                else:
                    return Response({"message": "User is not valid"},
                                status.HTTP_404_NOT_FOUND)

                pre_insured_members['first_name'] = member['first_name']
                pre_insured_members['last_name'] = member['last_name']
                pre_insured_members['address'] = member['address']
                pre_insured_members['pincode'] = member['pincode']
                pre_insured_members['email'] = member['email']
                pre_insured_members['relation'] = member['relation']
                pre_insured_members['member_profile'] = member_profile

                insured_members_list.append(pre_insured_members.copy())

            user_profile = UserProfile.objects.filter(id=logged_in_user_profile_id, user_id=request.user.pk).values('id'
                                                                                                        ,'name',
                                                                                                        'email',
                                                                                                        'gender',
                                                                                                        'user_id',
                                                                                                        'dob',
                                                                                                        'phone_number')
            user_profile = user_profile[0]
        insurer = Insurer.objects.filter(id=valid_data.get('insurer').id).values('id', 'name', 'max_float',
                                                                                 'min_float').first()
        insurance_plan = InsurancePlans.objects.filter(id=valid_data.get('insurance_plan').id).values('id', 'amount',
                                                                                                      'insurer_id',
                                                                                                      'type',
                                                                                                      'policy_tenure'
                                                                                                      ).first()
        transaction_date = datetime.datetime.now()
        if insurance_plan:
            amount = insurance_plan.get('amount')
        insurance_transaction = {'insurer': insurer.get('id'),
                                 'insurance_plan': insurance_plan.get('id'),
                                 'transaction_date': transaction_date, 'status_type': InsuranceTransaction.CREATED,
                                 'amount': amount, 'user': request.user.pk}
        user_insurance = {'insurer': insurer,
                          'insurance_plan': insurance_plan,
                          'user': request.user.pk}

        insurance_data['insurance'] = {"profile_detail": user_profile, "insured_members": insured_members_list,
                                       "insurer": insurer, "insurance_plan": insurance_plan,
                                       "user": request.user.pk, "insurance_transaction": insurance_transaction,
                                       "user_insurance": user_insurance}

        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance

        resp['is_agent'] = False
        if hasattr(request, 'agent') and request.agent:
            resp['is_agent'] = True

        insurance_data = insurance_transform(insurance_data)

        if (request.data.get('payment_type') == doctor_models.OpdAppointment.PREPAID and
                    balance < amount or resp['is_agent']):

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
            wallet_amount = 0
            if request.data.get('payment_type') == doctor_models.OpdAppointment.PREPAID:
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
            resp["data"] = {'id': insurance_object}

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

                    if member['relation'].lower() == 'self'.lower():
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

            if member['relation'].lower() == 'self'.lower():
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
            user_insurance = UserInsurance.objects.filter(user=user).values('insured_members',
                                                                            'purchase_date',
                                                                            'expiry_date',
                                                                            'policy_number',
                                                                            insurer_name=F('insurer__name'),
                                                                            insurance_amount=F('insurance_transaction__amount'),
                                                                            )
            resp['profile'] = user_insurance[0]
        else:
            return Response({"message": "User is not valid"},
                            status.HTTP_404_NOT_FOUND)

        return Response(resp)

