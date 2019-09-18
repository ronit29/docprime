import json
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ondoc.api.v1.utils import plus_subscription_transform, payment_details
from ondoc.authentication.backends import JWTAuthentication
from ondoc.account import models as account_models
from ondoc.authentication.models import User, UserProfile
from ondoc.common.models import BlacklistUser, BlockedStates, DocumentsProofs
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser, PlusLead)
from . import serializers
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


class PlusListViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return PlusProposer.objects.filter(is_live=True)

    def list(self, request):
        resp = {}
        user = request.user
        if user and not user.is_anonymous and user.is_authenticated and (user.active_plus_user or user.inactive_plus_user):
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        plus_proposer = self.get_queryset()
        body_serializer = serializers.PlusProposerSerializer(plus_proposer, context={'request': request}, many=True)
        resp['plus_data'] = body_serializer.data
        return Response(resp)


class PlusOrderLeadViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def create_plus_lead(self, request):
        # latitude = request.data.get('latitude', None)
        # longitude = request.data.get('longitude', None)
        #
        # if latitude or longitude:
        #     city_name = InsuranceEligibleCities.get_nearest_city(latitude, longitude)
        #     if not city_name:
        #         return Response({'success': False, 'is_insured': False})

        phone_number = request.data.get('phone_number', None)
        if phone_number:
            user = User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).first()
            if not user:
                user = request.user
        else:
            user = request.user

        if not user.is_anonymous and user.is_authenticated:
            # plus_lead = PlusLead.objects.filter(user=user).order_by('id').last()

            plus_user = user.active_plus_user

            if plus_user and plus_user.is_valid():
                return Response({'success': True, "is_plus_user": True})

            # if not plus_lead:
            #     plus_lead = PlusLead(user=user)
            # elif plus_lead and plus_user and not plus_user.is_valid():
            #     active_plus_lead = PlusLead.objects.filter(created_at__gte=plus_user.expire_date, user=user).order_by('created_at').last()
            #     if not active_plus_lead:
            #         plus_lead = PlusLead(user=user)
            #     else:
            #         plus_lead = active_plus_lead
            plus_lead = PlusLead(user=user, phone_number=user.phone_number)

            plus_lead.extras = request.data
            plus_lead.save()

            return Response({'success': True, 'is_plus_user': False})
        else:
            lead = PlusLead.create_lead_by_phone_number(request)
            if not lead:
                return Response({'success': False, 'is_plus_user': False})

            return Response({'success': True, 'is_plus_user': False})


class PlusOrderViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def create_order(self, request):
        user = request.user
        phone_number = user.phone_number
        blocked_state = BlacklistUser.get_state_by_number(phone_number, BlockedStates.States.VIP)
        if blocked_state:
            return Response({'error': blocked_state.message}, status=status.HTTP_400_BAD_REQUEST)

        if user.active_insurance:
            return Response({'error': 'User has already purchased the OPD Insurance.'})

        if settings.IS_PLUS_ACTIVE:
            user = request.user
            plus_subscription = user.active_plus_user
            if plus_subscription and plus_subscription.is_valid():
                return Response(data={'certificate': True}, status=status.HTTP_200_OK)

            serializer = serializers.PlusMembersSerializer(data=request.data, context={'request': request})
            if not serializer.is_valid() and serializer.errors:
                logger.error(str(serializer.errors))

            serializer.is_valid(raise_exception=True)
            valid_data = serializer.validated_data
            amount = None
            members = valid_data.get("members")
            resp = {}
            insurance_data = {}
            plus_plan_id = request.data.get('plan_id')
            if not plus_plan_id:
                return Response({"message": "Plus Plan is not Valid"}, status=status.HTTP_404_NOT_FOUND)
            if valid_data:
                user = request.user
                pre_insured_members = {}
                plus_members = []

                for member in members:
                    pre_insured_members['dob'] = member['dob']
                    pre_insured_members['title'] = member['title']
                    pre_insured_members['first_name'] = member['first_name']
                    pre_insured_members['last_name'] = member.get('last_name') if member.get('last_name') else ''
                    pre_insured_members['address'] = member['address']
                    pre_insured_members['pincode'] = member['pincode']
                    pre_insured_members['city'] = member['city']
                    pre_insured_members['city_code'] = member['city_code']
                    pre_insured_members['email'] = member['email']
                    pre_insured_members['relation'] = member['relation']
                    pre_insured_members['profile'] = member.get('profile').id if member.get(
                        'profile') is not None else None

                    plus_members.append(pre_insured_members.copy())

                    if member['relation'] == PlusMembers.Relations.SELF:
                        if member['profile']:
                            user_profile = UserProfile.objects.filter(id=member['profile'].id,
                                                                      user_id=request.user.pk).values('id', 'name',
                                                                                                      'email',
                                                                                                      'gender',
                                                                                                      'user_id',
                                                                                                      'phone_number').first()

                            user_profile['dob'] = member['dob']

                        else:
                            last_name = member.get('last_name') if member.get('last_name') else ''
                            user_profile = {"name": member['first_name'] + " " + last_name, "email":
                                member['email'], "dob": member['dob']}

            plus_plan = PlusPlans.objects.get(id=plus_plan_id)
            transaction_date = datetime.datetime.now()
            amount = plus_plan.deal_price

            expiry_date = transaction_date + relativedelta(years=int(plus_plan.tenure))
            expiry_date = expiry_date - timedelta(days=1)
            expiry_date = datetime.datetime.combine(expiry_date, datetime.datetime.max.time())
            plus_user_data = {'proposer': plus_plan.proposer.id, 'plus_plan': plus_plan.id,
                                   'purchase_date': transaction_date, 'expire_date': expiry_date, 'amount': amount,
                                   'user': request.user.pk, "plus_members": plus_members}
            plus_subscription_data = {"profile_detail": user_profile, "plus_plan": plus_plan.id,
                              "user": request.user.pk, "plus_user": plus_user_data}

            consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance

            # visitor_info = None
            # try:
            #     from ondoc.api.v1.tracking.views import EventCreateViewSet
            #     with transaction.atomic():
            #         event_api = EventCreateViewSet()
            #         visitor_id, visit_id = event_api.get_visit(request)
            #         visitor_info = {"visitor_id": visitor_id, "visit_id": visit_id}
            # except Exception as e:
            #     logger.log("Could not fecth visitor info - " + str(e))

            resp['is_agent'] = False
            if hasattr(request, 'agent') and request.agent:
                resp['is_agent'] = True

            plus_data = plus_subscription_transform(plus_subscription_data)

            if balance < amount or resp['is_agent']:
                payable_amount = amount - balance
                order = account_models.Order.objects.create(
                    product_id=account_models.Order.VIP_PRODUCT_ID,
                    action=account_models.Order.VIP_CREATE,
                    action_data=plus_data,
                    amount=payable_amount,
                    cashback_amount=0,
                    wallet_amount=balance,
                    user=user,
                    payment_status=account_models.Order.PAYMENT_PENDING,
                    # visitor_info=visitor_info
                )
                resp["status"] = 1
                resp['data'], resp["payment_required"] = payment_details(request, order)
            else:
                wallet_amount = amount

                order = account_models.Order.objects.create(
                    product_id=account_models.Order.VIP_PRODUCT_ID,
                    action=account_models.Order.VIP_CREATE,
                    action_data=plus_data,
                    amount=0,
                    wallet_amount=wallet_amount,
                    cashback_amount=0,
                    user=user,
                    payment_status=account_models.Order.PAYMENT_PENDING,
                    # visitor_info=visitor_info
                )

                plus_object, wallet_amount, cashback_amount = order.process_order()
                resp["status"] = 1
                resp["payment_required"] = False
                resp["data"] = {'id': plus_object.id}
                resp["data"] = {
                    "orderId": order.id,
                    "type": "plus_membership",
                    "id": plus_object.id if plus_object else None
                }
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(resp)

    @transaction.atomic
    def add_members(self, request):
        user = request.user

        inactive_plus_subscription = user.inactive_plus_user
        if not inactive_plus_subscription:
            return Response({'error': 'User has not purchased the VIP plan.'})

        phone_number = user.phone_number
        blocked_state = BlacklistUser.get_state_by_number(phone_number, BlockedStates.States.VIP)
        if blocked_state:
            return Response({'error': blocked_state.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.PlusMembersSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid() and serializer.errors:
            logger.error(str(serializer.errors))

        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        members_to_be_added = valid_data.get('members')

        # Remove the proposer profile. Proposer is only allowed to upload the document proofs.

        counter = 0
        self_counter = -1
        for member in members_to_be_added:
            if member.get('relation') == PlusMembers.Relations.SELF:
                self_counter = counter
                if member.get('document_ids'):
                    proposer_profile = inactive_plus_subscription.get_primary_member_profile()
                    if proposer_profile:
                        document_ids = list(map(lambda d: d.get('proof_file').id, member.get('document_ids')))
                        DocumentsProofs.update_with_object(proposer_profile, document_ids)
            else:
                member['profile'] = PlusUser.profile_create_or_update(member, user)

            counter += 1

        members_to_be_added.pop(self_counter)

        PlusMembers.create_plus_members(inactive_plus_subscription, members_list=members_to_be_added)
        inactive_plus_subscription.status = PlusUser.ACTIVE
        inactive_plus_subscription.save()
        return Response({'success': True})


class PlusProfileViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )

    def dashboard(self, request):
        resp = {}
        if request.query_params.get('is_dashboard'):
            user = request.user
            plus_user = PlusUser.objects.filter(user=user).order_by('-id').first()
        elif(request.query_params.get('id') and not request.query_params.get('is_dashboard')):
            plus_user_id = request.query_params.get('id')
            plus_user = PlusUser.objects.filter(id=plus_user_id).first()
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not plus_user:
            return Response(status=status.HTTP_404_NOT_FOUND)

        plus_members = plus_user.plus_members.all()
        if len(plus_members) > 1:
            resp['is_member_allowed'] = False
        else:
            resp['is_member_allowed'] = True
        plus_plan_queryset = PlusPlans.objects.filter(id=plus_user.plan.id)
        plan_body_serializer = serializers.PlusPlansSerializer(plus_plan_queryset, context={'request': request}, many=True)
        resp['plan'] = plan_body_serializer.data
        plus_user_body_serializer = serializers.PlusUserModelSerializer(plus_user, context={'request': request})
        resp['user'] = plus_user_body_serializer.data
        # member_relations = plus_user.plus_members.all().values_list('relation', flat=True)
        available_relations = PlusMembers.Relations.get_custom_availabilities()
        available_relations.pop(PlusMembers.Relations.SELF)
        resp['relation_master'] = available_relations
        return Response({'data': resp})

