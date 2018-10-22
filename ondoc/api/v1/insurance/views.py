from rest_framework import viewsets
from . import serializers
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse
from ondoc.account import models as account_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans)
from ondoc.authentication.models import UserProfile
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions
import json
import datetime
from ondoc.authentication.models import User
from ondoc.api.v1 import utils


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
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter()

    def memberlist(self, request):

        serializer = serializers.InsuredTransactionIdsSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data

        result = list()
        if parameters.get('ids'):

            for id in parameters.get('ids'):
                resp = id.insured_members
                # resp = {}
                # resp = {"id": id.id, "first_name": id.first_name, "last_name": id.last_name, "dob": id.dob, "email":id.email,
                #         "relation": id.relation, "gender": id.gender, "phone_number": id.phone_number, "hypertension": id.hypertension,
                #         "liver_disease": id.liver_disease, "heart_disease": id.heart_disease, "diabetes": id.diabetes}
                result.append(resp)

        return Response({"insured_members": result})

    def update(self, request):
        serializer = serializers.InsuredMemberIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data

        member_id = parameters.get('id')

        if member_id:

            resp = {}

            if parameters.get('hypertension'):
                member_id.hypertension = parameters.get('hypertension')

            if parameters.get('liver_disease'):
                member_id.liver_disease = parameters.get('liver_disease')

            if parameters.get('heart_disease'):
                member_id.heart_disease = parameters.get('heart_disease')

            if parameters.get('diabetes'):
                member_id.diabetes = parameters.get('diabetes')

            resp = {"id": member_id.id, "first_name": member_id.first_name, "last_name": member_id.last_name, "dob": member_id.dob,
                    "email":member_id.email, "relation": member_id.relation, "gender": member_id.gender, "phone_number": member_id.phone_number,
                    "hypertension": member_id.hypertension, "liver_disease": member_id.liver_disease, "heart_disease": member_id.heart_disease,
                    "diabetes": member_id.diabetes}

        return Response(resp)



    def summary(self, request):
        serializer = serializers.InsuredMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        members = valid_data.get("members")
        resp = {}

        if valid_data:
            user = request.user
            logged_in_user_id = None
            pre_insured_members = {}
            insured_members_list = []
            for member in members:
                profile = {}
                name = member['first_name'] + " " + member['last_name']
                dob = member['dob']
                current_date = datetime.datetime.now().date()
                days_diff = current_date - dob
                days_diff = days_diff.days
                years_diff = days_diff / 365
                years_diff = int(years_diff)
                if valid_data.get('insurance_plan'):
                    insurance_threshold = InsuranceThreshold.objects.filter(insurance_plan_id=
                                                                        valid_data.get('insurance_plan').id,
                                                                        insurer_id=valid_data.get('insurer')).first()
                    adult_max_age = insurance_threshold.max_age
                    adult_min_age = insurance_threshold.min_age
                    child_min_age = insurance_threshold.child_min_age
                    if member['member_type'] == "adult":
                        if (adult_max_age >= years_diff) and (adult_min_age <= years_diff):
                            pre_insured_members['dob'] = member['dob']
                        elif adult_max_age <= years_diff:
                            return Response({"message": "Adult Age would be less than " + str(adult_max_age) + " years"},
                                            status.HTTP_404_NOT_FOUND)
                        elif adult_min_age >= years_diff:
                            return Response({"message": "Adult Age would be more than " + str(adult_min_age) + " years"},
                                            status.HTTP_404_NOT_FOUND)
                    if member['member_type'] == "child":
                        if child_min_age <= days_diff:
                            pre_insured_members['dob'] = member['dob']
                        else:
                            return Response({"message": "Child Age would be more than " + str(child_min_age) + " days"},
                                            status.HTTP_404_NOT_FOUND)
                    # pre_insured_members['profile'] = UserProfile.objects.filter(id=profile.id).values()
                    # User Profile creation or updation
                if member['profile']:

                    profile = UserProfile.objects.filter(id=member['profile'].id).values('id', 'name', 'email',
                                                                                         'gender', 'user_id', 'dob',
                                                                                         'phone_number')

                    if profile.exists():
                        if profile[0].get('user_id') == request.user.pk:
                            member_profile = profile.update(name=name, email=member['email'], gender=member['gender'],
                                                            dob=member['dob'])

                            if member['relation'].lower() == 'self'.lower():
                                logged_in_user_id = member['profile'].id

                        else:
                            return Response({"message": "User is not valid"},
                                            status.HTTP_404_NOT_FOUND)

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
                        logged_in_user_id = member_profile.id

                pre_insured_members['first_name'] = member['first_name']
                pre_insured_members['last_name'] = member['last_name']

                pre_insured_members['address'] = member['address']
                pre_insured_members['pincode'] = member['pincode']
                pre_insured_members['email'] = member['email']
                pre_insured_members['relation'] = member['relation']
                pre_insured_members['member_profile'] = profile

                insured_members_list.append(pre_insured_members.copy())

            insurer = Insurer.objects.filter(id=valid_data.get('insurer').id).values()
            insurance_plan = InsurancePlans.objects.filter(id=valid_data.get('insurance_plan').id).values()
            user_profile = UserProfile.objects.filter(id=logged_in_user_id, user_id=request.user.pk).values('id','name',
                                                                                                         'email',
                                                                                                         'gender',
                                                                                                         'user_id',
                                                                                                         'dob',
                                                                                                         'phone_number')
            # user = User.objects.filter(id=request.user.pk).values('id','phone_number', 'email', 'user_type',
            #                                                       'is_superuser', 'is_active', 'is_staff')

            resp['insurance'] = {"profile": user_profile[0], "members": insured_members_list, "insurer": insurer[0],
                                 "insurance_plan": insurance_plan[0], "user": request.user.pk}
            return Response(resp)

    def create(self, request):
        insurance_data = request.data.get('insurance')
        insurance_plan = insurance_data.get('insurance_plan')
        insurer = insurance_data.get('insurer')
        insured_member = insurance_data.get('members')
        if insurance_plan:
            amount = insurance_plan.get('amount')
        resp = {}
        order = account_models.Order.objects.create(
            product_id=account_models.Order.INSURANCE_PRODUCT_ID,
            action=account_models.Order.INSURANCE_CREATE,
            action_data=insurance_data,
            amount=amount,
            reference_id=1,
            payment_status=account_models.Order.PAYMENT_PENDING
        )
        # resp['data'], resp["payment_required"] = utils.payment_details(request, order)
        return Response(resp)
