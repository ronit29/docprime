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
from ondoc.common.models import BlacklistUser, BlockedStates
from ondoc.plus.models import (PlusProposer, PlusPlans, PlusThreshold, PlusMembers, PlusUser)
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
        if not user.is_anonymous and user.active_plus_user is not None:
            return Response(data={'certificate': True}, status=status.HTTP_200_OK)

        plus_proposer = self.get_queryset()
        body_serializer = serializers.PlusProposerSerializer(plus_proposer, context={'request': request}, many=True)
        resp['plus_data'] = body_serializer.data
        return Response(resp)


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
                    pre_insured_members['email'] = member['email']
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