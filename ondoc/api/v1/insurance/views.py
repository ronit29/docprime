import json

from django.conf import settings
from django.forms import model_to_dict

from ondoc.api.v1.insurance.serializers import InsuredMemberIdSerializer, InsuranceDiseaseIdSerializer, \
    MemberListSerializer, MemberSerializer, InsuranceCityEligibilitySerializer
from ondoc.api.v1.utils import insurance_transform
from django.core.serializers import serialize
from rest_framework import viewsets
from django.core import serializers as core_serializer
import math

from ondoc.api.v1.utils import payment_details
from ondoc.common.models import BlacklistUser, BlockedStates
from ondoc.diagnostic.models import LabAppointment, Lab
from ondoc.doctor.models import OpdAppointment
from . import serializers
from rest_framework.response import Response
from ondoc.account import models as account_models
from ondoc.doctor import models as doctor_models
from ondoc.insurance.models import (Insurer, InsuredMembers, InsuranceThreshold, InsurancePlans, UserInsurance,
                                    InsuranceLead,
                                    InsuranceTransaction, InsuranceDisease, InsuranceDiseaseResponse, StateGSTCode,
                                    InsuranceDummyData, InsuranceCancelMaster, InsuranceCity, InsuranceDistrict,
                                    EndorsementRequest, InsuredMemberDocument, InsuranceEligibleCities, UserBank)

from ondoc.authentication.models import UserProfile
from ondoc.authentication.backends import JWTAuthentication
from ondoc.api.v1.utils import RawSql
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions
from django.db.models import F, Window
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
        search = request.query_params.get('search')
        if (not type or not latitude or not longitude) or \
                (not starts_with and type == 'doctor'):
            return Response({'count':0,'total_count':0, 'results':[]})

        if not starts_with:
            params = dict()
            params['latitude'] = latitude
            params['longitude'] = longitude
            result = list()

            labs_query = '''select l.network_id,l.name, 'lab' as type,eu.url,l.city,l.id, 
             st_distance(l.location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326))/1000  distance 
             from lab_network ln inner join lab l on l.network_id = ln.id
            inner join entity_urls eu on l.id = eu.entity_id and eu.sitemap_identifier='LAB_PAGE' and eu.is_valid=true
            where l.is_live=true and l.is_test_lab=false and ln.id in (43, 18, 65, 22) and St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326),l.location, 15000) 
            order by ST_Distance(l.location, St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326)) '''
            labs = RawSql(labs_query, params).fetch_all()
            temp_dict = set()
            for lab in labs:
                if len(temp_dict) == 4:
                    break
                if not lab.get('network_id') in temp_dict:
                    result.append(lab)
                    temp_dict.add(lab.get('network_id'))

            total_count_query= "select count(distinct entity_id) from insurance_covered_entity where type= %(type)s"
            total_count = RawSql(total_count_query, {'type':type}).fetch_all()[0].get('count')

            resp = dict()
            resp["starts_with"] = None
            resp["count"] = len(result)
            resp["total_count"] = total_count
            resp["distance_count"] = len(result)
            resp["results"] = result

            return Response(resp)

        else:
            starts_with = starts_with.lower()

            params = {'type':type,'latitude':latitude,'longitude':longitude,'starts_with':starts_with+'%'}

            query_string = "select * from (select x.*, rank() over(partition by entity_id order by distance) "\
            " rnk from (select mt.*, st_distance(location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326))/1000 "\
            " distance from  insurance_covered_entity mt where type=(%(type)s) and "

            if type =='doctor' and search == 'specialization':
                params['comma_separated_starts_with'] = '%,' + starts_with+'%'
                query_string += " ((specialization_search_key like (%(starts_with)s)) or (specialization_search_key like (%(comma_separated_starts_with)s) )) and "
                # query_string += " ((specialization_search_key like (%(starts_with)s)) or (specialization_search_key like concat('%,',(%(starts_with)s))) ) and "
            else:
                query_string += ' search_key like %(starts_with)s and '

            query_string += " st_dwithin(location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326),15000) "\
            " )x )y where rnk=1 order by distance"

            results = RawSql(query_string, params).fetch_all()

            distance_count_query = "select count(distinct entity_id) from insurance_covered_entity where type= %(type)s "\
            " and st_dwithin(location,st_setsrid(st_point((%(longitude)s),(%(latitude)s)), 4326),15000)"
            distance_count = RawSql(distance_count_query, {'type':type,'latitude':latitude,'longitude':longitude}).fetch_all()[0].get('count')

            total_count_query= "select count(distinct entity_id) from insurance_covered_entity where type= %(type)s"
            total_count = RawSql(total_count_query, {'type':type}).fetch_all()[0].get('count')

            data_list = []
            for r in results:
                data_list.append({'name':r.get('name'), 'distance':math.ceil(r.get('distance')), 'id':r.get('entity_id'),\
                'type':r.get('type'), 'city':r.get('data',{}).get('city'),'url':r.get('data',{}).get('url'),\
                'specializations':r.get('data',{}).get('specializations')})

            resp = dict()
            resp["starts_with"] = starts_with
            resp["count"] = len(data_list)
            resp["total_count"] = total_count
            resp["distance_count"] = distance_count
            resp["results"] = data_list

            return Response(resp)


class ListInsuranceViewSet(viewsets.GenericViewSet):
    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Insurer.objects.filter(is_live=True)

    def check_is_insurance_available(self, request):
        data = {
            'latitude': request.query_params.get('latitude'),
            'longitude': request.query_params.get('longitude')
        }
        serializer = InsuranceCityEligibilitySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        city_name = InsuranceEligibleCities.get_nearest_city(data.get('latitude'), data.get('longitude'))
        if not city_name:
            return Response({'available': False})

        return Response({'available': True})

    def list(self, request):
        if settings.IS_INSURANCE_ACTIVE:
            resp = {}
            user = request.user
            if not user.is_anonymous:
                user_insurance = UserInsurance.get_user_insurance(request.user)
                if user_insurance and user_insurance.is_profile_valid() and not self.strtobool(request.query_params.get("is_endorsement")):
                    return Response(data={'certificate': True}, status=status.HTTP_200_OK)

            insurer_data = self.get_queryset()
            if self.strtobool(request.query_params.get("is_endorsement")):
                body_serializer = serializers.EndorseEnableInsurerSerializer(insurer_data, context={'request': request}, many=True)
            else:
                body_serializer = serializers.InsurerSerializer(insurer_data, context={'request': request}, many=True)
            state_code = StateGSTCode.objects.filter(is_live=True)
            state_code_serializer = serializers.StateGSTCodeSerializer(state_code, context={'request': request}, many=True)
            resp['insurance'] = body_serializer.data
            resp['state'] = state_code_serializer.data
            # return Response(body_serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(resp)

    def strtobool(self, val):
        if val == 'true':
            return True
        else:
            return False



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
    # permission_classes = (IsAuthenticated,)

    def create_banner_lead(self, request):
        latitude = request.data.get('latitude', None)
        longitude = request.data.get('longitude', None)

        if latitude or longitude:
            city_name = InsuranceEligibleCities.get_nearest_city(latitude, longitude)
            if not city_name:
                return Response({'success': False, 'is_insured': False})

        phone_number = request.data.get('phone_number', None)
        if phone_number:
            user = User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).first()
            if not user:
                user = request.user
        else:
            user = request.user

        if not user.is_anonymous:
            user_insurance_lead = InsuranceLead.objects.filter(user=user).order_by('id').last()
            user_insurance = user.purchased_insurance.filter().order_by('id').last()

            if user.active_insurance:
                return Response({'success': True, "is_insured": True})

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

            return Response({'success': True, 'is_insured': False})
        else:
            lead = InsuranceLead.create_lead_by_phone_number(request)
            if not lead:
                return Response({'success': False, 'is_insured': False})

            return Response({'success': True, 'is_insured': False})


    @transaction.atomic
    def create_order(self, request):
        user = request.user
        phone_number = user.phone_number
        blocked_state = BlacklistUser.get_state_by_number(phone_number, BlockedStates.States.INSURANCE)
        if blocked_state:
            return Response({'error': blocked_state.message}, status=status.HTTP_400_BAD_REQUEST)


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
                if not hasattr(request, 'agent') and (opd_appointment_count > 0 or lab_appointment_count > 0) :
                    resp['is_cancel_allowed'] = False
                    resp['is_endorsement_allowed'] = False
                else:
                    resp['is_cancel_allowed'] = True
                    resp['is_endorsement_allowed'] = True
                members = user_insurance.get_members()
                is_endorsement_exist = False
                for member in members:
                    if not (hasattr(request, 'agent')) and EndorsementRequest.is_endorsement_exist(member):
                        is_endorsement_exist = True
                        resp['is_endorsement_allowed'] = False
                        break
                resp['is_endorsement_exist'] = is_endorsement_exist
                if user_insurance.status != UserInsurance.ACTIVE:
                    resp['is_endorsement_exist'] = False
                    resp['is_endorsement_allowed'] = False
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
            InsuranceDummyData.objects.create(user=user, data=data, type=InsuranceDummyData.BOOKING)
            return Response(data="save successfully!!", status=status.HTTP_200_OK )
        except Exception as e:
            logger.error(str(e))
            return Response(data="could not save data", status=status.HTTP_400_BAD_REQUEST)

    def show_dummy_data(self, request):
        user = request.user
        res = {}
        if not user:
            res['error'] = "user not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        dummy_data = InsuranceDummyData.objects.filter(user=user, type=InsuranceDummyData.BOOKING).order_by('-id').first()
        if not dummy_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        member_data = dummy_data.data
        if not member_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        res['data'] = member_data
        return Response(data=res, status=status.HTTP_200_OK)

    def push_endorsement_data(self, request):
        try:
            user = request.user
            data = request.data
            InsuranceDummyData.objects.create(user=user, data=data, type=InsuranceDummyData.ENDORSEMENT)
            return Response(data="save successfully!!", status=status.HTTP_200_OK )
        except Exception as e:
            logger.error(str(e))
            return Response(data="could not save data", status=status.HTTP_400_BAD_REQUEST)

    def show_endorsement_data(self, request):
        user = request.user
        res = {}
        if not user:
            res['error'] = "user not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        rendorsement_data = InsuranceDummyData.objects.filter(user=user, type=InsuranceDummyData.ENDORSEMENT).order_by('-id').first()
        if not rendorsement_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        member_data = rendorsement_data.data
        if not member_data:
            res['error'] = "data not found"
            return Response(error=res, status=status.HTTP_400_BAD_REQUEST)
        res['data'] = member_data
        return Response(data=res, status=status.HTTP_200_OK)


class InsuranceCancelViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @transaction.atomic()
    def insurance_cancel(self, request):
        res = {}
        data = request.data
        user = request.user
        user_insurance = user.active_insurance
        if not user_insurance:
            res["error"] = "Insurance not found for the user"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        data['insurance'] = user_insurance.id
        serializer = serializers.UserBankSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_data = serializer.validated_data
        UserBank.objects.create(bank_name=user_data.get('bank_name'), account_number=user_data.get('account_number'),
                                account_holder_name=user_data.get('account_holder_name'), ifsc_code=user_data.get('ifsc_code'),
                                bank_address=user_data.get('bank_address'), insurance=user_insurance)
        user_insurance._user = user if user and not user.is_anonymous else None
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
        res['phone_number'] = user.phone_number

        return Response(data=res, status=status.HTTP_200_OK)


class InsuranceEndorsementViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_endorsement_data(self, request):
        user = request.user
        user_insurance = user.active_insurance
        res = {}
        if not user_insurance:
            res['error'] = "Insurance not found for the user"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        if not user_insurance.status == UserInsurance.ACTIVE:
            res['error'] = "Active Insurance not found for the user"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        members = user_insurance.get_members()
        if not members:
            res['error'] = "No members found for the user insurance"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
        res['insurance_plan'] = user_insurance.insurance_plan.id
        member_serializer = MemberSerializer(members, context={'request': request}, many=True)
        members_data = member_serializer.data
        for member in members_data:
            city_name = member.get('town', None)
            district_name = member.get('district', None)
            city_code = InsuranceCity.get_city_code_with_name(city_name)
            district_code = InsuranceDistrict.get_district_code_with_name(district_name)
            member['city_code'] = city_code
            member['district_code'] = district_code
        res['members'] = members_data
        return Response(data=res, status=status.HTTP_200_OK)

    @transaction.atomic()
    def create(self, request):
        user = request.user
        res = {}
        if not user.active_insurance:
            res['error'] = "Active insurance not found for User"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

        # appointment should not be completed in insurance mode for endorsement!!
        opd_completed_appointments = OpdAppointment.get_insured_completed_appointment(user.active_insurance)
        lab_completed_appointments = LabAppointment.get_insured_completed_appointment(user.active_insurance)
        if not hasattr(request, 'agent') and (opd_completed_appointments > 0 or lab_completed_appointments > 0):
            res['error'] = "One of the OPD or LAB Appointment have been completed, could not process endorsement!!"
            return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.EndorseMemberSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid() and serializer.errors:
            logger.error(str(serializer.errors))
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        for member in valid_data.get('members'):
            insured_member_obj = InsuredMembers.objects.filter(id=member.get('member').id).first()
            if not insured_member_obj:
                res['error'] = "Insured Member details not found for member"
                return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

            # endorsement could not process if already process and in Pending Status!!
            endorsement_request = EndorsementRequest.is_endorsement_exist(insured_member_obj)
            if endorsement_request:
                res['error'] = "Endorsement request already in process for member {}!!".format(member.get('first_name'))
                return Response(data=res, status=status.HTTP_200_OK)

            insurance_obj = insured_member_obj.user_insurance
            if not insurance_obj:
                res['error'] = "User Insurance not found for member {}".format(member.get('first_name'))
                return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

            # endorsement only create when some changes in member details pushed with flag!!
            if member.get('is_change', None):
                document = insured_member_obj.is_document_available()
                if not document:
                    res['error'] = "Document required for member {}".format(member.get('first_name'))
                    return Response(data=res, status=status.HTTP_400_BAD_REQUEST)

                member['insurance_id'] = insurance_obj.id
                member['member_id'] = insured_member_obj.id
                document_ids = []
                document_objs = member.get('image_ids')
                if not document_objs:
                    res['error'] = "Document Image Ids not found for member {}".format(member.get('first_name'))
                    return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
                for document in document_objs:
                    document_id = document.get('document_image').id
                    document_ids.append(document_id)

                end_obj = EndorsementRequest.create(member)
                member_documents = InsuredMemberDocument.objects.filter(id__in=document_ids)
                for document in member_documents:
                    document.is_enabled = True
                    document.endorsement_request = end_obj
                    document.save()

        user_insurance = user.active_insurance
        EndorsementRequest.process_endorsment_notifications(EndorsementRequest.PENDING, user_insurance.user)

        res['success'] = 'Your endorsement request has been successfully submitted.'
        return Response(data=res, status=status.HTTP_200_OK)

    def upload(self, request, *args, **kwargs):
        data = dict()
        document_data = {}
        member = request.query_params.get('member')
        data['member'] = member
        data['document_image'] = request.data['document_image']
        serializer = serializers.UploadMemberDocumentSerializer(data=data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        doc_obj = serializer.save()
        document_data['id'] = doc_obj.id
        document_data['data'] = serializer.data
        return Response(document_data)


class UserBankViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def upload(self, request):
        data = dict()
        document_data = {}
        data['document_image'] = request.data['document_image']
        if not request.user.active_insurance:
            return Response(data="User is not cover under insurance", status=status.HTTP_400_BAD_REQUEST)
        data['insurance'] = request.user.active_insurance.id
        serializer = serializers.UploadUserBankDocumentSerializer(data=data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        doc_obj = serializer.save()
        document_data['id'] = doc_obj.id
        document_data['data'] = serializer.data
        return Response(document_data)

    # def create(self, request):
    #     res = {}
    #     data = request.data
    #     user = request.user
    #     user_insurance = user.active_insurance
    #     if not user_insurance:
    #         res["error"] = "Insurance not found for the user"
    #         return Response(data=res, status=status.HTTP_400_BAD_REQUEST)
    #     data['insurance'] = user_insurance.id
    #     serializer = serializers.UserBankSerializer(data=data, context={'request': request})
    #     serializer.is_valid(raise_exception=True)
    #     serializer.save()
    #     return Response(data="Successfully uploaded!!", status=status.HTTP_200_OK)



