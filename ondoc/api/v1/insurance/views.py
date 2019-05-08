from django.conf import settings

from ondoc.api.v1.insurance.serializers import InsuredMemberIdSerializer, InsuranceDiseaseIdSerializer
from ondoc.api.v1.utils import insurance_transform
from django.core.serializers import serialize
from rest_framework import viewsets
from django.core import serializers as core_serializer
import math

from ondoc.api.v1.utils import payment_details
from ondoc.diagnostic.models import LabAppointment
from ondoc.doctor.models import OpdAppointment
from . import serializers
from rest_framework.response import Response
from ondoc.account import models as account_models
from ondoc.doctor import models as doctor_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans, UserInsurance, InsuranceLead,
                                    InsuranceTransaction, InsuranceDisease, InsuranceDiseaseResponse, StateGSTCode,
                                    InsuranceDummyData, InsuranceCancelMaster)
from ondoc.authentication.models import UserProfile
from ondoc.authentication.backends import JWTAuthentication
from ondoc.api.v1.utils import RawSql
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
from dateutil.relativedelta import relativedelta

class InsuranceNetworkViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return None

    def list(self, request):

        type = request.query_params.get('type')
        if type not in ('doctor','lab'):
            type = None
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        starts_with = request.query_params.get('starts_with')
        if not type or not latitude or not longitude or not starts_with:
            return Response({'count':0,'total_count':0, 'results':[]})

        starts_with = starts_with.lower()

        params = {'type':type,'latitude':latitude,'longitude':longitude,'starts_with':starts_with+'%'}

        query_string = "select * from (select x.*, rank() over(partition by entity_id order by distance) "\
        " rnk from (select mt.*, st_distance(location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326))/1000 "\
        " distance from  insurance_covered_entity mt where type=%(type)s and search_key like (%(starts_with)s) and "\
        " st_dwithin(location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326),15000) "\
        " )x )y where rnk=1 order by name"

        results = RawSql(query_string, params).fetch_all()

        total_count_query= "select count(distinct entity_id) from insurance_covered_entity where type= %(type)s"
        total_count = RawSql(total_count_query, {'type':type}).fetch_all()[0].get('count')

        data_list = []
        for r in results:
            data_list.append({'name':r.get('name'), 'distance;':math.ceil(r.get('distance')), 'id':r.get('entity_id'),\
            'type':r.get('type'), 'city':r.get('data',{}).get('city'),'url':r.get('data',{}).get('url')})

        resp = dict()
        resp["starts_with"] = starts_with
        resp["count"] = len(data_list)
        resp["total_count"] = total_count
        resp["results"] = data_list

        return Response(resp)


class ListInsuranceViewSet(viewsets.GenericViewSet):
    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def list(self, request):
        if settings.IS_INSURANCE_ACTIVE:
            resp = {}
            user = request.user
            if not user.is_anonymous:
                user_insurance = UserInsurance.get_user_insurance(request.user)
                if user_insurance and user_insurance.is_profile_valid():
                    return Response(data={'certificate': True}, status=status.HTTP_200_OK)

            insurer_data = self.get_queryset()
            body_serializer = serializers.InsurerSerializer(insurer_data, context={'request': request}, many=True)
            state_code = StateGSTCode.objects.filter(is_live=True)
            state_code_serializer = serializers.StateGSTCodeSerializer(state_code, context={'request': request}, many=True)
            resp['insurance'] = body_serializer.data
            resp['state'] = state_code_serializer.data
            # return Response(body_serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(resp)


class InsuredMemberViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def memberlist(self, request):
        if settings.IS_INSURANCE_ACTIVE:
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
            member_list = user_insurance.members.all().order_by('id').values('id', 'first_name', 'last_name', 'relation'
                                                                             , 'gender')
            result['members'] = member_list
            disease = InsuranceDisease.objects.filter(is_live=True).values('id', 'disease', 'is_female_related')
            result['disease'] = disease
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(result)

    def update(self, request):
        if settings.IS_INSURANCE_ACTIVE:
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
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "Disease Profile Updated Successfully"}, status.HTTP_200_OK)


class InsuranceOrderViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def create_banner_lead(self, request):
        user = request.user
        user_insurance_lead = InsuranceLead.objects.filter(user=user).order_by('id').last()
        user_insurance = user.purchased_insurance.filter().order_by('id').last()

        if user.active_insurance:
            return Response({'success': True})

        if not user_insurance_lead:
            user_insurance_lead = InsuranceLead(user=user)
        elif user_insurance_lead and user_insurance and not user_insurance.is_valid():
            active_insurance_lead = InsuranceLead.objects.filter(created_at__gte=user_insurance.expiry_date, user=user).order_by('created_at').last()
            if not active_insurance_lead:
                user_insurance_lead = InsuranceLead(user=user)
            else:
                user_insurance_lead = active_insurance_lead

        user_insurance_lead.extras = request.data
        user_insurance_lead.save()

        return Response({'success': True})

    @transaction.atomic
    def create_order(self, request):
        if settings.IS_INSURANCE_ACTIVE:
            user = request.user
            user_insurance = UserInsurance.get_user_insurance(user)
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
                    pre_insured_members['middle_name'] = member.get('middle_name') if member.get('middle_name') else ''
                    pre_insured_members['last_name'] = member.get('last_name') if member.get('last_name') else ''
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
                    pre_insured_members['state_code'] = member['state_code']

                    insured_members_list.append(pre_insured_members.copy())

                    if member['relation'] == 'self':
                        if member['profile']:
                            user_profile = UserProfile.objects.filter(id=member['profile'].id,
                                                                      user_id=request.user.pk).values('id', 'name', 'email',
                                                                                                    'gender', 'user_id',
                                                                                                      'phone_number').first()

                            user_profile['dob'] = member['dob']

                        else:
                            last_name = member.get('last_name') if member.get('last_name') else ''
                            user_profile = {"name": member['first_name'] + " " + last_name, "email":
                                member['email'], "gender": member['gender'], "dob": member['dob']}

            insurance_plan = InsurancePlans.objects.get(id=request.data.get('insurance_plan'))
            transaction_date = datetime.datetime.now()
            amount = insurance_plan.amount

            expiry_date = transaction_date + relativedelta(years=int(insurance_plan.policy_tenure))
            expiry_date = expiry_date - timedelta(days=1)
            expiry_date = datetime.datetime.combine(expiry_date, datetime.datetime.max.time())
            user_insurance_data = {'insurer': insurance_plan.insurer_id, 'insurance_plan': insurance_plan.id, 'purchase_date':
                                transaction_date, 'expiry_date': expiry_date, 'premium_amount': amount,
                                'user': request.user.pk, "insured_members": insured_members_list}
            insurance_data = {"profile_detail": user_profile, "insurance_plan": insurance_plan.id,
                              "user": request.user.pk, "user_insurance": user_insurance_data}

            consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance

            visitor_info = None
            try:
                from ondoc.api.v1.tracking.views import EventCreateViewSet
                with transaction.atomic():
                    event_api = EventCreateViewSet()
                    visitor_id, visit_id = event_api.get_visit(request)
                    visitor_info = {"visitor_id": visitor_id, "visit_id": visit_id}
            except Exception as e:
                logger.log("Could not fecth visitor info - " + str(e))

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
                    cashback_amount=0,
                    wallet_amount=balance,
                    user=user,
                    payment_status=account_models.Order.PAYMENT_PENDING,
                    visitor_info = visitor_info
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
                    cashback_amount=0,
                    user=user,
                    payment_status=account_models.Order.PAYMENT_PENDING,
                    visitor_info=visitor_info
                )

                insurance_object, wallet_amount, cashback_amount = order.process_order()
                resp["status"] = 1
                resp["payment_required"] = False
                resp["data"] = {'id': insurance_object.id}
                resp["data"] = {
                    "orderId": order.id,
                    "type": "insurance",
                    "id": insurance_object.id if insurance_object else None
                }
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(resp)


class InsuranceProfileViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def profile(self, request):
        if settings.IS_INSURANCE_ACTIVE:
            user_id = request.user.pk
            resp = {}
            if user_id:

                user = User.objects.get(id=user_id)
                user_insurance = UserInsurance.get_user_insurance(user)
                if not user_insurance or not user_insurance.is_profile_valid():
                    return Response({"message": "Insurance not found or expired."})
                insurer = user_insurance.insurance_plan.insurer
                resp['insured_members'] = user_insurance.members.all().values('first_name', 'middle_name', 'last_name',
                                                                              'dob', 'relation')
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
                resp['insurance_status'] = user_insurance.status
                opd_appointment_count = OpdAppointment.get_insured_completed_appointment(user_insurance)
                lab_appointment_count = LabAppointment.get_insured_completed_appointment(user_insurance)
                if opd_appointment_count > 0 or lab_appointment_count > 0:
                    resp['is_cancel_allowed'] = False
                    resp['is_endorsement_allowed'] = False
                else:
                    resp['is_cancel_allowed'] = True
                    resp['is_endorsement_allowed'] = True
            else:
                return Response({"message": "User is not valid"},
                                status.HTTP_404_NOT_FOUND)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
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


class InsuranceDummyDataViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def push_dummy_data(self, request):
        try:
            user = request.user
            data = request.data
            InsuranceDummyData.objects.create(user=user, data=data)
            return Response(data="save successfully!!", status=status.HTTP_200_OK )
        except Exception as e:
            logger.log(str(e))
            return Response(data="could not save data", status=status.HTTP_200_OK)

    def show_dummy_data(self, request):
        user = request.user
        res = {}
        if not user:
            res['error'] = "user not found"
            return Response(error=res, status=status.HTTP_200_OK)
        dummy_data = InsuranceDummyData.objects.filter(user=user).order_by('-id').first()
        if not dummy_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_200_OK)
        member_data = dummy_data.data
        if not member_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_200_OK)
        res['data'] = member_data
        return Response(data=res, status=status.HTTP_200_OK)


class InsuranceCancelViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @transaction.atomic()
    def insurance_cancel(self, request):
        user = request.user
        user_insurance = UserInsurance.objects.filter(user=user).last()
        res = {}
        if not user_insurance:
            res['error'] = "Insurance not found"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        if not user.active_insurance:
            res['error'] = "Insurance is not active"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

        responsible_user = request.user
        user_insurance._responsible_user = responsible_user if responsible_user and not responsible_user.is_anonymous else None

        opd_appointment_count = OpdAppointment.get_insured_completed_appointment(user_insurance)
        lab_appointment_count = LabAppointment.get_insured_completed_appointment(user_insurance)
        if opd_appointment_count > 0 or lab_appointment_count > 0:
            res['error'] = "One of the OPD or LAB Appointment have been completed, Cancellation could not be processed"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        response = user_insurance.process_cancellation()
        return Response(data=response, status=status.HTTP_200_OK)

    def cancel_master(self,request):
        user = request.user
        res = {}
        user_insurance = user.active_insurance
        if not user_insurance:
            res['error'] = "Insurance not found for the user"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        policy_purchase_date = user_insurance.purchase_date
        policy_expiry_date = user_insurance.expiry_date
        policy_number = user_insurance.policy_number
        cancel_master = list(InsuranceCancelMaster.objects.filter(insurer=user_insurance.insurance_plan.insurer).order_by(
            '-refund_percentage').values('min_days', 'max_days', 'refund_percentage'))
        if not cancel_master:
            res['error'] = "Insurance Cancel Master not found"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

        res['purchase_date'] = policy_purchase_date
        res['expiry_date'] = policy_expiry_date
        res['policy_number'] = policy_number
        res['cancel_master'] = cancel_master

        return Response(data=res, status=status.HTTP_200_OK)
