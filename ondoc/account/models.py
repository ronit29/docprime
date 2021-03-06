from django.db import models
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from django.utils.functional import cached_property
from pandas.core.common import flatten

from ondoc.authentication.models import TimeStampedModel, User, UserProfile, Merchant, AssociatedMerchant, SoftDelete
from ondoc.account.tasks import refund_curl_task
from ondoc.coupon.models import Coupon
from ondoc.notification.models import AppNotification, NotificationAction
from ondoc.notification.tasks import process_payout, save_pg_response
# from ondoc.diagnostic.models import LabAppointment
# from ondoc.matrix.tasks import push_order_to_matrix
from django.db import transaction
from django.db.models import Sum, Q, F, Max
from datetime import datetime, timedelta
from django.utils import timezone
from ondoc.api.v1.utils import refund_curl_request, form_pg_refund_data, opdappointment_transform, \
    labappointment_transform, payment_details, insurance_reverse_transform, plan_subscription_reverse_transform, \
    plus_subscription_transform, single_booking_payment_details
from django.conf import settings
from rest_framework import status
from copy import deepcopy
import hashlib
import copy
import json
import logging
import requests
import datetime
import itertools
from decimal import Decimal
from ondoc.notification.tasks import set_order_dummy_transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import string
import random
import decimal
from django.conf import settings
from ondoc.plus.enums import UtilizationCriteria

logger = logging.getLogger(__name__)


class Order(TimeStampedModel):
    OPD_APPOINTMENT_RESCHEDULE = 1
    OPD_APPOINTMENT_CREATE = 2
    LAB_APPOINTMENT_RESCHEDULE = 3
    LAB_APPOINTMENT_CREATE = 4
    INSURANCE_CREATE = 5
    SUBSCRIPTION_PLAN_BUY = 6
    CHAT_CONSULTATION_CREATE = 7
    PROVIDER_ECONSULT_PAY = 8
    VIP_CREATE = 11
    GOLD_CREATE = 12
    CORP_VIP_CREATE = 13

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_FAILURE = 3
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, "Payment Accepted"),
        (PAYMENT_PENDING, "Payment Pending"),
        (PAYMENT_FAILURE, "Payment Failure")
    )
    ACTION_CHOICES = (("", "Select"), (OPD_APPOINTMENT_RESCHEDULE, 'Opd Reschedule'),
                      (OPD_APPOINTMENT_CREATE, "Opd Create"),
                      (LAB_APPOINTMENT_CREATE, "Lab Create"),
                      (LAB_APPOINTMENT_RESCHEDULE, "Lab Reschedule"),
                      (INSURANCE_CREATE, "Insurance Create"),
                      (SUBSCRIPTION_PLAN_BUY, "Subscription Plan Buy"),
                      (CHAT_CONSULTATION_CREATE, "Chat Consultation Create"),
                      (VIP_CREATE, "Vip create"),
                      (GOLD_CREATE, "Gold create"),
                      (PROVIDER_ECONSULT_PAY, "Provider Econsult Pay"),
                      )
    DOCTOR_PRODUCT_ID = 1
    LAB_PRODUCT_ID = 2
    INSURANCE_PRODUCT_ID = 3
    SUBSCRIPTION_PLAN_PRODUCT_ID = 4
    CHAT_PRODUCT_ID = 5
    PROVIDER_ECONSULT_PRODUCT_ID = 6
    VIP_PRODUCT_ID = 11
    GOLD_PRODUCT_ID = 8
    CORP_VIP_PRODUCT_ID = 9
    PARTNER_LAB_ORDER_PRODUCT_ID = 13
    PRODUCT_IDS = [(DOCTOR_PRODUCT_ID, "Doctor Appointment"), (LAB_PRODUCT_ID, "LAB_PRODUCT_ID"),
                   (INSURANCE_PRODUCT_ID, "INSURANCE_PRODUCT_ID"),
                   (SUBSCRIPTION_PLAN_PRODUCT_ID, "SUBSCRIPTION_PLAN_PRODUCT_ID"),
                   (CHAT_PRODUCT_ID, "CHAT_PRODUCT_ID"),
                   (VIP_PRODUCT_ID, 'VIP_PRODUCT_ID'),
                   (GOLD_PRODUCT_ID, 'GOLD_PRODUCT_ID'),
                   (PROVIDER_ECONSULT_PRODUCT_ID, "Provider Econsult"),
                   (PARTNER_LAB_ORDER_PRODUCT_ID, "Partner Lab Order"),
                   ]

    product_id = models.SmallIntegerField(choices=PRODUCT_IDS, blank=True, null=True)
    reference_id = models.BigIntegerField(blank=True, null=True)
    action = models.PositiveSmallIntegerField(blank=True, null=True, choices=ACTION_CHOICES)
    action_data = JSONField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    wallet_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    error_status = models.CharField(max_length=250, verbose_name="Error", blank=True, null=True)
    is_viewable = models.BooleanField(verbose_name='Is Viewable', default=True)
    matrix_lead_id = models.PositiveIntegerField(null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name="orders", blank=True, null=True)
    cart = models.ForeignKey('cart.Cart', on_delete=models.CASCADE, related_name="order", blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name="orders")
    visitor_info = JSONField(blank=True, null=True)
    single_booking = models.ForeignKey('self', on_delete=models.CASCADE, related_name="single_booking_order", blank=True, null=True)

    def __str__(self):
        return "{}".format(self.id)

    def is_corporate_plus_plan(self):
        from ondoc.plus.models import PlusUser
        plus_user = PlusUser.objects.filter(id=self.reference_id).first()
        if not plus_user or not plus_user.plan or not plus_user.plan.is_corporate:
            return None
        return plus_user

    def is_vip_appointment(self):
        appt = self.getAppointment()
        if appt.__class__.__name__ not in ['LabAppointment', 'OpdAppointment']:
            return False
        if appt.plus_plan and appt.plus_plan.plan and not appt.plus_plan.plan.is_gold:
            return True
        return False

    def get_vip_amount_to_be_paid(self):
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.doctor.models import OpdAppointment
        appt = self.getAppointment()
        if isinstance(appt, LabAppointment):
            return appt.agreed_price
        elif isinstance(appt, OpdAppointment):
            return appt.fees
        else:
            return (self.amount or 0) + (self.wallet_amount or 0)

    # def get_insurance_data_for_pg(self):
    #     from ondoc.insurance.models import UserInsurance
    #
    #     data = {}
    #     user_insurance = None
    #     if self.product_id == Order.INSURANCE_PRODUCT_ID:
    #         user_insurance = UserInsurance.objects.filter(order=self).first()
    #         if user_insurance:
    #             data['insurerCode'] = str(user_insurance.insurance_plan.insurer.insurer_merchant_code)
    #     elif (self.product_id in (self.DOCTOR_PRODUCT_ID,self.LAB_PRODUCT_ID)):
    #         if not self.is_parent() and self.booked_using_insurance():
    #         # if self.is_parent():
    #         #     raise Exception('cannot get insurance for parent order')
    #             appt = self.getAppointment()
    #             if appt and appt.insurance:
    #                 user_insurance = appt.insurance
    #                 transactions = user_insurance.order.getTransactions()
    #                 if not transactions:
    #                     raise Exception('No transactions found for appointment insurance.')
    #                 insurance_order_transaction = transactions[0]
    #                 data['refOrderId'] = str(insurance_order_transaction.order_id)
    #                 data['refOrderNo'] = str(insurance_order_transaction.order_no)
    #                 #data['insurerCode'] = str(user_insurance.insurance_plan.insurer.insurer_merchant_code)
    #                 #data['insurerCode'] = "advancePay"
    #
    #     return data

    def get_additional_data_for_pg(self):
        from ondoc.insurance.models import UserInsurance
        from ondoc.plus.models import PlusUser

        data = {}
        user_insurance = None
        plus_user = None
        if self.product_id == Order.INSURANCE_PRODUCT_ID:
            user_insurance = UserInsurance.objects.filter(order=self).first()
            if user_insurance:
                data['insurerCode'] = str(user_insurance.insurance_plan.insurer.insurer_merchant_code)
        elif self.product_id in [Order.CORP_VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID]:
            plus_user = PlusUser.objects.filter(order=self).first()
            if plus_user and plus_user.plan and not plus_user.plan.is_gold:
                data['insurerCode'] = settings.VIP_MERCHANT_CODE
            elif plus_user and plus_user.plan and plus_user.plan.is_gold:
                data['insurerCode'] = settings.GOLD_MERCHANT_CODE
        elif (self.product_id in (self.DOCTOR_PRODUCT_ID,self.LAB_PRODUCT_ID)):
            if not self.is_parent() and self.booked_using_insurance():
                appt = self.getAppointment()
                if appt and appt.insurance:
                    user_insurance = appt.insurance
                    transactions = user_insurance.order.getTransactions()
                    if not transactions:
                        raise Exception('No transactions found for appointment insurance.')
                    insurance_order_transaction = transactions[0]
                    data['refOrderId'] = str(insurance_order_transaction.order_id)
                    data['refOrderNo'] = str(insurance_order_transaction.order_no)
            if self.booking_using_vip_plan():
                appt = self.getAppointment()
                if appt and appt.plus_plan:
                    plus_user = appt.plus_plan
                    transactions = plus_user.order.getTransactions()
                    parent_product_id = self.CORP_VIP_PRODUCT_ID if appt.plus_plan.plan.is_corporate else self.VIP_PRODUCT_ID
                    if not transactions:
                        raise Exception("No transaction found for appointment vip")
                    vip_order_transaction = transactions[0]
                    data['refOrderId'] = str(vip_order_transaction.order_id)
                    data['refOrderNo'] = str(vip_order_transaction.order_no)
                    data['parentProductId'] = str(parent_product_id)

        return data

    # Check if dummy txn needs to be created or not for order
    def dummy_transaction_allowed(self):
        if (not self.is_parent() and not self.booked_using_insurance()) or self.getTransactions():
            return False

        return True

    # Check if order booked through insurance
    def booked_using_insurance(self):
        if self.is_parent():
            raise Exception('Not implemented for parent orders')
        appt = self.getAppointment()
        if appt and hasattr(appt, 'insurance_id') and appt.insurance_id:
            return True
        return False

    def booking_using_vip_plan(self):
        appt = self.getAppointment()
        if appt and appt.plus_plan and appt.plus_plan.plan and not appt.plus_plan.plan.is_gold:
            return True
        return False

    # check if order is a parent or child
    def is_parent(self):
        return self.parent_id is None

    # To disable pending orders
    @classmethod
    def disable_pending_orders(cls, appointment_details, product_id, action):
        if product_id == Order.DOCTOR_PRODUCT_ID:
            Order.objects.filter(
                action_data__doctor=appointment_details.get("doctor"),
                action_data__hospital=appointment_details.get("hospital"),
                action_data__profile=appointment_details.get("profile"),
                action_data__user=appointment_details.get("user"),
                product_id=product_id,
                is_viewable=True,
                payment_status=Order.PAYMENT_PENDING,
                action=action,
            ).update(is_viewable=False)
        elif product_id == Order.LAB_PRODUCT_ID:
            Order.objects.filter(
                action_data__lab=appointment_details.get("lab"),
                # action_data__test_ids=appointment_details.get("test_ids"),
                action_data__profile=appointment_details.get("profile"),
                action_data__user=appointment_details.get("user"),
                product_id=product_id,
                is_viewable=True,
                payment_status=Order.PAYMENT_PENDING,
                action=action,
            ).update(is_viewable=False)

    # Check if order is cod or not
    @cached_property
    def is_cod_order(self):
        if self.orders.exists():
            orders_to_process = self.orders.all()
        else:
            orders_to_process = [self]
        return len(orders_to_process) == 1 and all([child_order.get_cod_to_prepaid_appointment() for child_order in orders_to_process])

    # To changes cod appointment into prepaid
    def get_cod_to_prepaid_appointment(self, update_order_and_appointment=False):
        from ondoc.doctor.models import OpdAppointment
        if self.product_id != self.DOCTOR_PRODUCT_ID:
            return None
        if not self.reference_id:
            return None
        opd_obj = OpdAppointment.objects.exclude(
            status__in=[OpdAppointment.CANCELLED, OpdAppointment.COMPLETED]).filter(id=self.reference_id).first()
        if not opd_obj:
            return None
        if opd_obj.payment_type != OpdAppointment.COD:
            return None
        if update_order_and_appointment:
            self.payment_type = OpdAppointment.PREPAID
            opd_obj.payment_type = OpdAppointment.PREPAID
            effective_price = 0
            prepaid_deal_price = self.action_data.get('prepaid_deal_price') or self.action_data.get('deal_price')
            coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(self.action_data, prepaid_deal_price)
            if coupon_discount >= prepaid_deal_price:
                effective_price = 0
            else:
                effective_price = prepaid_deal_price - coupon_discount
            # self.action_data['appointment_id'] = self.reference_id
            self.action_data['payment_type'] = OpdAppointment.PREPAID
            self.action_data['effective_price'] = effective_price
            # self.action_data['deal_price'] = prepaid_deal_price
            opd_obj.effective_price = Decimal(effective_price)
            opd_obj.is_cod_to_prepaid = True
            opd_obj.deal_price = prepaid_deal_price
            opd_obj.save()
        return opd_obj

    @transaction.atomic
    def process_order(self, convert_cod_to_prepaid=False):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.api.v1.plus.serializers import PlusUserSerializer
        from ondoc.plus.models import PlusUser, PlusTransaction
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.provider.models import EConsultation
        from ondoc.chat.models import ChatConsultation
        from ondoc.api.v1.doctor.serializers import OpdAppTransactionModelSerializer
        from ondoc.api.v1.diagnostic.serializers import LabAppTransactionModelSerializer
        from ondoc.api.v1.insurance.serializers import UserInsuranceSerializer
        from ondoc.api.v1.diagnostic.serializers import PlanTransactionModelSerializer
        from ondoc.api.v2.doctor.serializers import EConsultTransactionModelSerializer
        from ondoc.subscription_plan.models import UserPlanMapping
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction
        from ondoc.api.v1.chat.serializers import ChatTransactionModelSerializer
        from ondoc.plus.models import PlusAppointmentMapping, TempPlusUser

        appointment_data = self.action_data
        # consumer_account = ConsumerAccount.objects.get_or_create(user=appointment_data['user'])
        # consumer_account = ConsumerAccount.objects.select_for_update().get(user=appointment_data['user'])
        consumer_account = ConsumerAccount.objects.get_or_create(user=self.user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)


        # skip if order already processed, except if appointment is COD and can be converted to prepaid
        cod_to_prepaid_app = None
        if self.reference_id:
            if convert_cod_to_prepaid:
                cod_to_prepaid_app = self.get_cod_to_prepaid_appointment(True)
            if not cod_to_prepaid_app:
                # Instant refund for already process VIP and Insurance orders
                if self.product_id in [self.INSURANCE_PRODUCT_ID, self.VIP_PRODUCT_ID, self.GOLD_PRODUCT_ID]:
                    ctx_objs = consumer_account.debit_refund()
                    if ctx_objs:
                        for ctx_obj in ctx_objs:
                            ConsumerRefund.initiate_refund(appointment_data['user'], ctx_obj)

                raise Exception("Order already processed - " + str(self.id))

        # Initial validations for appointment data
        user_insurance_data = None
        plus_user_data = None
        # Check if payment is required at all, only when payment is required we debit consumer's account
        payment_not_required = False
        if self.product_id == self.DOCTOR_PRODUCT_ID:
            appointment_data = TempPlusUser.temp_appointment_to_plus_appointment(appointment_data)
            serializer = OpdAppTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
            if appointment_data['payment_type'] in [OpdAppointment.VIP, OpdAppointment.GOLD]:
                if not appointment_data.get('plus_plan'):
                    raise Exception('Plus plan not found.')
                if appointment_data['plus_amount'] > 0:
                    payment_not_required = False
                else:
                    payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.COD:
                if self.reference_id and cod_to_prepaid_app:
                    payment_not_required = False
                else:
                    payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.INSURANCE:
                payment_not_required = True
        elif self.product_id == self.LAB_PRODUCT_ID:
            appointment_data = TempPlusUser.temp_appointment_to_plus_appointment(appointment_data)
            serializer = LabAppTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
            if appointment_data['payment_type'] == OpdAppointment.COD:
                payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.INSURANCE:
                payment_not_required = True
            elif appointment_data['payment_type'] in [OpdAppointment.VIP, OpdAppointment.GOLD]:
                if not appointment_data.get('plus_plan'):
                    raise Exception('Plus plan not found.')
                if appointment_data['plus_amount'] > 0:
                    payment_not_required = False
                else:
                    payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.PLAN:
                payment_not_required = True
        elif self.product_id == self.INSURANCE_PRODUCT_ID:
            insurance_data = deepcopy(self.action_data)
            insurance_data = insurance_reverse_transform(insurance_data)
            insurance_data['user_insurance']['order'] = self.id
            serializer = UserInsuranceSerializer(data=insurance_data.get('user_insurance'))
            serializer.is_valid(raise_exception=True)
            user_insurance_data = serializer.validated_data
        elif self.product_id == self.SUBSCRIPTION_PLAN_PRODUCT_ID:
            serializer = PlanTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
        elif self.product_id == self.PROVIDER_ECONSULT_PRODUCT_ID:
            serializer = EConsultTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
        elif self.product_id == self.CHAT_PRODUCT_ID:
            serializer = ChatTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            consultation_data = serializer.validated_data
        elif self.product_id in [self.VIP_PRODUCT_ID, self.GOLD_PRODUCT_ID]:
            plus_data = deepcopy(self.action_data)
            plus_data = plan_subscription_reverse_transform(plus_data)
            plus_data['plus_user']['order'] = self.id
            serializer = PlusUserSerializer(data=plus_data.get('plus_user'))
            serializer.is_valid(raise_exception=True)
            plus_user_data = serializer.validated_data

        appointment_obj = None
        order_dict = dict()
        amount = None
        promotional_amount = 0
        total_balance = consumer_account.get_total_balance()
        _responsible_user=None
        _source=None
        plus_amount = 0
        convenience_amount = 0
        if '_responsible_user' in appointment_data:
            _responsible_user = appointment_data.pop('_responsible_user')
        if '_source' in appointment_data:
            _source = appointment_data.pop('_source')
        if 'plus_amount' in appointment_data:
            plus_amount = appointment_data.pop('plus_amount')
            convenience_amount = int(appointment_data.pop('vip_convenience_amount'))

        if self.action == Order.OPD_APPOINTMENT_CREATE:
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
                if self.reference_id:
                    appointment_obj = cod_to_prepaid_app
                else:
                    appointment_obj = OpdAppointment.create_appointment(appointment_data, responsible_user=_responsible_user, source=_source)
                    if appointment_obj.plus_plan:
                        data = {"plus_user": appointment_obj.plus_plan, "plus_plan": appointment_obj.plus_plan.plan,
                                "content_object": appointment_obj, 'amount': plus_amount, 'extra_charge': convenience_amount}
                        PlusAppointmentMapping.objects.create(**data)

                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price
        elif self.action == Order.LAB_APPOINTMENT_CREATE:
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
                appointment_obj = LabAppointment.create_appointment(appointment_data, responsible_user=_responsible_user, source=_source)

                if appointment_obj.plus_plan:
                    data = {"plus_user": appointment_obj.plus_plan, "plus_plan": appointment_obj.plus_plan.plan,
                            "content_object": appointment_obj, 'amount': plus_amount, 'extra_charge': convenience_amount}
                    PlusAppointmentMapping.objects.create(**data)

                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price
        elif self.action == Order.OPD_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = OpdAppointment.objects.get(pk=appointment_data.get("id"))
            if total_balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
        elif self.action == Order.LAB_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = LabAppointment.objects.get(pk=appointment_data.get("id"))
            if total_balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }

        elif self.action == Order.INSURANCE_CREATE:
            user = User.objects.get(id=self.action_data.get('user'))
            if not user:
                raise Exception('User Not Found for Order' + str(self.id))
            if user.active_insurance:
                raise Exception('User Insurance already purchased for user' + str(user.id))
            if consumer_account.balance >= user_insurance_data['premium_amount']:
                appointment_obj = UserInsurance.create_user_insurance(user_insurance_data, user)
                amount = appointment_obj.premium_amount
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                insurer = appointment_obj.insurance_plan.insurer
                # InsuranceTransaction.objects.create(user_insurance=appointment_obj,
                #                                     account=appointment_obj.master_policy_reference.apd_account,
                #                                     transaction_type=InsuranceTransaction.DEBIT, amount=amount)
                InsuranceTransaction.objects.create(user_insurance=appointment_obj,
                                                    account=appointment_obj.master_policy.insurer_account,
                                                    transaction_type=InsuranceTransaction.DEBIT, amount=amount)

        elif self.action in [Order.VIP_CREATE, Order.GOLD_CREATE]:
            user = User.objects.get(id=self.action_data.get('user'))
            if not user:
                raise Exception('User Not Found for Order' + str(self.id))
            if user.active_plus_user:
                raise Exception('User has already subscribed to VIP plan.' + str(user.id))
            if consumer_account.balance >= plus_user_data['effective_price']:
                appointment_obj = PlusUser.create_plus_user(plus_user_data, user)
                amount = appointment_obj.amount
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                proposer = appointment_obj.plan.proposer
                # InsuranceTransaction.objects.create(user_insurance=appointment_obj,
                #                                     account=appointment_obj.master_policy_reference.apd_account,
                #                                     transaction_type=InsuranceTransaction.DEBIT, amount=amount)
                PlusTransaction.objects.create(plus_user=appointment_obj,
                                               transaction_type=InsuranceTransaction.DEBIT, amount=amount)

        elif self.action == Order.SUBSCRIPTION_PLAN_BUY:
            amount = Decimal(appointment_data.get('extra_details').get('payable_amount', float('inf')))
            if consumer_account.balance >= amount:
                new_appointment_data = appointment_data
                coupon = appointment_data.pop('coupon', [])
                coupon_data = {
                    "random_coupons": new_appointment_data.pop("coupon_data", [])
                }
                appointment_obj = UserPlanMapping(**new_appointment_data)
                appointment_obj.coupon_data = coupon_data
                appointment_obj.save()

                if coupon:
                    appointment_obj.coupon.add(*coupon)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
        elif self.action == Order.PROVIDER_ECONSULT_PAY:
            amount = appointment_data["effective_price"]
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
                appointment_obj = EConsultation.objects.filter(id=appointment_data.get('id')).first()
                if appointment_obj:
                    appointment_obj.update_consultation()
                    order_dict = {
                        "reference_id": appointment_obj.id,
                        "payment_status": Order.PAYMENT_ACCEPTED
                    }
        elif self.action == Order.CHAT_CONSULTATION_CREATE:
            if total_balance >= appointment_data.get("effective_price"):
                amount = Decimal(appointment_data.get("amount"))
                promotional_amount = consultation_data.pop('promotional_amount')
                appointment_obj = ChatConsultation(**consultation_data)
                appointment_obj.save()
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price

        if order_dict:
            self.update_order(order_dict)

        wallet_amount = cashback_amount = 0
        # If payment is required and appointment is created successfully, debit consumer's account
        if appointment_obj and not payment_not_required:
            wallet_amount, cashback_amount = consumer_account.debit_schedule(appointment_obj, self.product_id, amount)
        # update appointment with price breakup
        if appointment_obj:
            appointment_obj.price_data = {"wallet_amount": int(wallet_amount), "cashback_amount": int(cashback_amount)}
            appointment_obj.save()

            if promotional_amount:
                appointment_obj.price_data["promotional_amount"] = int(promotional_amount)
                appointment_obj.save()
                ConsumerAccount.credit_cashback(consultation_data.get('user'), promotional_amount, appointment_obj, self.product_id)

        return appointment_obj, wallet_amount, cashback_amount

    def process_plus_user_upload_order(self):
        from ondoc.api.v1.plus.serializers import PlusUserSerializer
        from ondoc.plus.models import PlusUser
        from ondoc.plus.models import PlusTransaction
        from ondoc.insurance.models import InsuranceTransaction

        plus_data = deepcopy(self.action_data)
        plus_data = plan_subscription_reverse_transform(plus_data)
        plus_data['plus_user']['order'] = self.id
        serializer = PlusUserSerializer(data=plus_data.get('plus_user'))
        serializer.is_valid(raise_exception=True)
        plus_user_data = serializer.validated_data
        user = User.objects.get(id=self.action_data.get('user'))
        plus_user_obj = PlusUser.create_plus_user(plus_user_data, user)
        amount = plus_user_obj.amount
        order_dict = {
            "reference_id": plus_user_obj.id,
            "payment_status": Order.PAYMENT_ACCEPTED
        }
        self.update_order(order_dict)
        PlusTransaction.objects.create(plus_user=plus_user_obj,
                                       transaction_type=InsuranceTransaction.DEBIT, amount=amount)

        self.change_payment_status(Order.PAYMENT_ACCEPTED)

        money_pool = MoneyPool.objects.create(wallet=0, cashback=0, logs=[])

        if plus_user_obj:
            PlusUser.objects.filter(id=plus_user_obj.id).update(money_pool=money_pool)
        return plus_user_obj

    @transaction.atomic
    def process_insurance_order(self, consumer_account, user_insurance_data):

        from ondoc.api.v1.insurance.serializers import UserInsuranceSerializer
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction
        from ondoc.authentication.models import User
        user = User.objects.get(id=self.action_data.get('user'))
        user_insurance_obj = None
        if consumer_account.balance >= user_insurance_data['premium_amount']:
            user_insurance_obj = UserInsurance.create_user_insurance(user_insurance_data, user)
            amount = user_insurance_obj.premium_amount
            # order_dict = {
            #     "reference_id": user_insurance_obj.id,
            #     "payment_status": Order.PAYMENT_ACCEPTED
            # }
            insurer = user_insurance_obj.insurance_plan.insurer
            InsuranceTransaction.objects.create(user_insurance=user_insurance_obj, account=insurer.float.all().first(),
                                                transaction_type=InsuranceTransaction.DEBIT, amount=amount)
        return user_insurance_obj

    def update_order(self, data):
        self.reference_id = data.get("reference_id", self.reference_id)
        self.payment_status = data.get("payment_status", self.payment_status)
        self.save()

    def appointment_details(self):
        from ondoc.doctor.models import Doctor
        from ondoc.diagnostic.models import AvailableLabTest, Lab
        ops_data = dict()
        user = User.objects.filter(pk=self.action_data.get("user")).first()
        user_number = None
        user_id = None
        if user:
            user_number = user.phone_number
            user_id = user.id
        if self.product_id == self.LAB_PRODUCT_ID:
            lab_name = None
            test_names = None
            lab = Lab.objects.filter(pk=self.action_data.get("lab")).first()
            available_lab_test = AvailableLabTest.objects.filter(pk__in=self.action_data.get("lab_test"))
            if lab:
                lab_name = lab.name

            if available_lab_test:
                test_names = ""
                for obj in available_lab_test:
                    if test_names:
                        test_names += ", "
                    test_names += obj.test.name

            ops_data = {
                "time_of_appointment": self.action_data.get("time_slot_start"),
                "lab_name": lab_name,
                "test_names": test_names,
                "profile_name": self.action_data.get("profile_detail").get("name"),
                "user_number": user_number,
                "user_id": user_id,
                "order_id": self.id
            }
        elif self.product_id == self.DOCTOR_PRODUCT_ID:
            doctor_name = None
            hospital_name = None
            profile_name = None
            doctor = Doctor.objects.filter(pk=self.action_data.get("doctor")).first()
            if doctor:
                doctor_name = doctor.name
                hospital = doctor.hospitals.filter(pk=self.action_data.get("hospital")).first()
                if hospital:
                    hospital_name = hospital.name
            if user:
                user_number = user.phone_number
            ops_data = {
                "time_of_appointment": self.action_data.get("time_slot_start"),
                "doctor_name": doctor_name,
                "hospital_name": hospital_name,
                "profile_name": self.action_data.get("profile_detail").get("name"),
                "user_number": user_number,
                "user_id": user_id,
                "order_id": self.id
            }

        return ops_data

    def get_doctor_prices(self):
        total_deal_price = Decimal(self.action_data.get('deal_price'))
        total_mrp = Decimal(self.action_data.get('mrp'))
        total_agreed_price = Decimal(self.action_data.get('fees'))
        procedures_details = self.action_data.get('extra_details', [])
        procedures_deal_price, procedures_mrp, procedures_agreed_price = 0, 0, 0
        for procedure in procedures_details:
            procedures_mrp += procedure.get('mrp')
            procedures_deal_price += procedure.get('deal_price')
            procedures_agreed_price += procedure.get('agreed_price')
        doctor_deal_price = total_deal_price - procedures_deal_price
        doctor_mrp = total_mrp - procedures_mrp
        doctor_agreed_price = total_agreed_price - procedures_agreed_price
        return doctor_deal_price, doctor_mrp, doctor_agreed_price

    def getAppointment(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.subscription_plan.models import UserPlanMapping
        from ondoc.insurance.models import UserInsurance
        from ondoc.plus.models import PlusUser

        if self.orders.exists():
            completed_order = self.orders.filter(reference_id__isnull=False).first()
            return completed_order.getAppointment() if completed_order else None

        if not self.reference_id:
            return None

        if self.product_id == self.LAB_PRODUCT_ID:
            return LabAppointment.objects.filter(id=self.reference_id).first()
        elif self.product_id == self.DOCTOR_PRODUCT_ID:
            return OpdAppointment.objects.filter(id=self.reference_id).first()
        elif self.product_id == self.SUBSCRIPTION_PLAN_PRODUCT_ID:
            return UserPlanMapping.objects.filter(id=self.reference_id).first()
        elif self.product_id == self.INSURANCE_PRODUCT_ID:
            return UserInsurance.objects.filter(id=self.reference_id).first()
        elif self.product_id == self.VIP_PRODUCT_ID or self.product_id == self.GOLD_PRODUCT_ID or self.product_id == self.CORP_VIP_PRODUCT_ID:
            return PlusUser.objects.filter(id=self.reference_id).first()
        return None

    # To get order total amount
    def get_total_price(self):
        if not self.is_parent() and self.booked_using_insurance():
            return 0

        if self.is_corporate_plus_plan():
            return 0

        if self.is_vip_appointment():
            total_price = self.get_vip_amount_to_be_paid()
            return total_price

        if self.parent:
            raise Exception("Cannot calculate price on a child order")

        return ( self.amount or 0 ) + ( self.wallet_amount or 0 )

    # This method is use to get transaction of a order
    def getTransactions(self):
        # if trying to get txn on a child order, recurse for its parent instead

        # for insurance dummy transaction should be created on child order
        # for other bookings it should be created on parent order
        if not self.is_parent() and not self.booked_using_insurance():
            return self.parent.getTransactions()

        all_txn = None
        if self.txn.exists():
            all_txn = self.txn.all()
        elif self.dummy_txn.exists():
            all_txn = self.dummy_txn.all()
        # elif self.parent and self.parent.dummy_txn.exists():
        #     all_txn = self.parent.dummy_txn.all()
        return all_txn

    @classmethod
    def get_total_payable_amount(cls, fulfillment_data):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.plus.models import PlusUser
        from ondoc.plus.models import TempPlusUser
        payable_amount = 0
        for app in fulfillment_data:
            if app.get('payment_type') == OpdAppointment.VIP or app.get('payment_type') == OpdAppointment.GOLD:
                plus_user = PlusUser.objects.filter(id=app.get('plus_plan')).first()
                if not plus_user:
                    plus_user = TempPlusUser.objects.filter(id=app.get('plus_plan'), deleted=0).first()
                if not plus_user:
                    payable_amount += app.get('effective_price')
                    return payable_amount
                payable_amount = payable_amount + int(app.get('effective_price', 0))
            if app.get("payment_type") == OpdAppointment.PREPAID:
                payable_amount += app.get('effective_price')
        return payable_amount

    @classmethod
    def get_single_booking_total_payable_amount(cls, app):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.plus.models import PlusUser
        from ondoc.plus.models import TempPlusUser
        payable_amount = 0
        if app.get('payment_type') == OpdAppointment.VIP or app.get('payment_type') == OpdAppointment.GOLD:
            plus_user = PlusUser.objects.filter(id=app.get('plus_plan')).first()
            if not plus_user:
                plus_user = TempPlusUser.objects.filter(id=app.get('plus_plan'), deleted=0).first()
            if not plus_user:
                payable_amount += app.get('effective_price')
                return payable_amount
            payable_amount = payable_amount + int(app.get('effective_price', 0))
        if app.get("payment_type") == OpdAppointment.PREPAID:
            payable_amount += app.get('effective_price')
        return payable_amount

    @classmethod
    def transfrom_cart_items(cls, request, cart_items):
        fulfillment_data = []
        for item in cart_items:
            validated_data = item.validate(request)
            fd = item.get_fulfillment_data(validated_data, request)
            fd["cart_item_id"] = item.id
            fulfillment_data.append(fd)
        return fulfillment_data

    @classmethod
    @transaction.atomic()
    def create_order(cls, request, cart_items, use_wallet=True):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.matrix.tasks import push_order_to_matrix, push_order_to_spo

        fulfillment_data = cls.transfrom_cart_items(request, cart_items)
        user = request.user
        resp = {}
        balance = 0
        cashback_balance = 0

        if use_wallet:
            consumer_account = ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance
            cashback_balance = consumer_account.cashback

        total_balance = balance + cashback_balance
        payable_amount = cls.get_total_payable_amount(fulfillment_data)

        # utility to fetch and save visitor info for an parent order
        visitor_info = None
        try:
            # from ondoc.api.v1.tracking.views import EventCreateViewSet
            # with transaction.atomic():
            #     event_api = EventCreateViewSet()
            #     #visitor_id, visit_id = event_api.get_visit(request)
            #     #visitor_info = { "visitor_id": visitor_id, "visit_id": visit_id, "from_app": request.data.get("from_app", None), "app_version": request.data.get("app_version", None)}
            visitor_info = {"from_app": request.data.get("from_app", None),
                            "app_version": request.data.get("app_version", None)}
        except Exception as e:
            logger.info("Could not fetch visitor info - " + str(e))

        # create a Parent order to accumulate sub-orders
        process_immediately = False
        if total_balance >= payable_amount:
            cashback_amount = min(cashback_balance, payable_amount)
            wallet_amount = max(0, int(payable_amount) - int(cashback_amount))
            pg_order = cls.objects.create(
                amount= 0,
                wallet_amount= wallet_amount,
                cashback_amount= cashback_amount,
                payment_status= cls.PAYMENT_PENDING,
                user=user,
                product_id=1, # remove later
                visitor_info=visitor_info
            )
            process_immediately = True
        else:
            amount_from_pg = max(0, payable_amount - total_balance)
            required_amount = payable_amount
            cashback_amount = min(required_amount, cashback_balance)
            wallet_amount = 0
            if cashback_amount < required_amount:
                wallet_amount = min(balance, required_amount - cashback_amount)

            pg_order = cls.objects.create(
                amount= amount_from_pg,
                wallet_amount= wallet_amount,
                cashback_amount= cashback_amount,
                payment_status= cls.PAYMENT_PENDING,
                user=user,
                product_id=1,  # remove later
                visitor_info=visitor_info
            )
            push_order_to_matrix.apply_async(
                ({'order_id': pg_order.id},),
                eta=timezone.now() + timezone.timedelta(minutes=settings.LEAD_VALIDITY_BUFFER_TIME))
        # building separate orders for all fulfillments
        fulfillment_data = copy.deepcopy(fulfillment_data)
        order_list = []
        for appointment_detail in fulfillment_data:
            product_id = Order.DOCTOR_PRODUCT_ID if appointment_detail.get('doctor') else Order.LAB_PRODUCT_ID
            action = None

            if product_id == cls.DOCTOR_PRODUCT_ID:
                appointment_detail = opdappointment_transform(appointment_detail)
                action = cls.OPD_APPOINTMENT_CREATE
            elif product_id == cls.LAB_PRODUCT_ID:
                appointment_detail = labappointment_transform(appointment_detail)
                action = cls.LAB_APPOINTMENT_CREATE

            extra_info = {
                'utm_tags': request.data.get('utm_tags', {}),
                'visitor_info': request.data.get('visitor_info', {})
            }

            appointment_detail['extras'] = extra_info

            if appointment_detail.get('payment_type') == OpdAppointment.PREPAID:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=pg_order,
                    cart_id=appointment_detail.get("cart_item_id", None),
                    user=user
                )
            elif appointment_detail.get('payment_type') in [OpdAppointment.INSURANCE, OpdAppointment.VIP, OpdAppointment.GOLD]:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=pg_order,
                    cart_id=appointment_detail.get("cart_item_id", None),
                    user=user
                )

            elif appointment_detail.get('payment_type') == OpdAppointment.COD or appointment_detail.get('payment_type') == OpdAppointment.PLAN:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=pg_order,
                    cart_id=appointment_detail["cart_item_id"],
                    user=user
                )

            order_list.append(order)
            if order.action_data.get('spo_data', None):
                try:
                    push_order_to_spo.apply_async(({'order_id': order.id},), countdown=5)
                except Exception as e:
                    logger.log("Could not push order to spo - " + str(e))

        if process_immediately:
            appointment_ids = pg_order.process_pg_order()

            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {
                "orderId" : pg_order.id,
                "type" : appointment_ids.get("type", "all"),
                "id" : appointment_ids.get("id", None)
            }
            resp["appointments"] = appointment_ids

        else:
            resp["status"] = 1
            resp['data'], resp["payment_required"] = payment_details(request, pg_order)

        # raise Exception("ROLLBACK FOR TESTING")

        return resp

    @classmethod
    def transform_single_booking_items(cls, request, items):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.plus.models import PlusUser
        fulfillment_data = []
        for item in items:
            plus_user_data = PlusUser.create_fulfillment_data(item)
            fulfillment_data.append(plus_user_data)
            if 'doctor' in item:
                price_data = OpdAppointment.get_price_details(item)
                fd = OpdAppointment.create_fulfillment_data(request.user, item, price_data)
            else:
                price_data = LabAppointment.get_price_details(item)
                fd = LabAppointment.create_fulfillment_data(request.user, item, price_data, request)
            # fd["cart_item_id"] = item.id
            fulfillment_data.append(fd)
        return fulfillment_data

    @classmethod
    @transaction.atomic()
    def create_new_order(cls, request, valid_data, use_wallet=False):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.matrix.tasks import push_order_to_matrix, push_order_to_spo

        fulfillment_data = cls.transform_single_booking_items(request, [valid_data])
        user = request.user
        resp = {}
        balance = 0
        cashback_balance = 0
        single_booking_id = None
        payable_amount = None

        if use_wallet:
            consumer_account = ConsumerAccount.objects.get_or_create(user=user)
            consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)
            balance = consumer_account.balance
            cashback_balance = consumer_account.cashback

        # total_balance = balance + cashback_balance

        # utility to fetch and save visitor info for an parent order
        visitor_info = None
        # try:
        #     from ondoc.api.v1.tracking.views import EventCreateViewSet
        #     with transaction.atomic():
        #         event_api = EventCreateViewSet()
        #         visitor_id, visit_id = event_api.get_visit(request)

        # ADD THIS IF NEED INFO #
        #     visitor_info = {"from_app": request.data.get("from_app", None),
        #                         "app_version": request.data.get("app_version", None)}
        #
        # except Exception as e:
        #     logger.info("Could not fetch visitor info - " + str(e))

        # building separate orders for all fulfillments
        fulfillment_data = copy.deepcopy(fulfillment_data)
        order_list = []
        for appointment_detail in fulfillment_data:
            payable_amount = cls.get_single_booking_total_payable_amount(appointment_detail)
            action = None
            if appointment_detail.get('doctor'):
                product_id = Order.DOCTOR_PRODUCT_ID
            elif appointment_detail.get('lab'):
                product_id = Order.LAB_PRODUCT_ID
            else:
                if not valid_data.get('plus_plan').is_gold:
                    product_id = Order.VIP_PRODUCT_ID
                else:
                    product_id = Order.GOLD_PRODUCT_ID

            if product_id == cls.DOCTOR_PRODUCT_ID:
                appointment_detail = opdappointment_transform(appointment_detail)
                action = cls.OPD_APPOINTMENT_CREATE
            elif product_id == cls.LAB_PRODUCT_ID:
                appointment_detail = labappointment_transform(appointment_detail)
                action = cls.LAB_APPOINTMENT_CREATE
            else:
                if not valid_data.get('plus_plan').is_gold:
                    action = Order.VIP_CREATE
                else:
                    action = Order.GOLD_CREATE

                appointment_detail = plus_subscription_transform(appointment_detail)

            extra_info = {
                'utm_tags': request.data.get('utm_tags', {}),
                'visitor_info': request.data.get('visitor_info', {})
            }

            appointment_detail['extras'] = extra_info

            if appointment_detail.get('payment_type') in [OpdAppointment.GOLD]:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=None,
                    cart_id=appointment_detail.get('cart_item_id', None),
                    user=user,
                    amount=payable_amount
                )
            else:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=None,
                    cart_id=appointment_detail.get("cart_item_id", None),
                    user=user,
                    amount=payable_amount
                )
            if product_id == Order.GOLD_PRODUCT_ID:
                single_booking_id = order.id

            order_list.append(order)

            if order.action_data.get('spo_data', None):
                try:
                    push_order_to_spo.apply_async(({'order_id': order.id},), countdown=5)
                except Exception as e:
                    logger.log("Could not push order to spo - " + str(e))

        for order in order_list:
            if not order.product_id == Order.GOLD_PRODUCT_ID:
                order.single_booking_id = single_booking_id
                order.save()
        resp["status"] = 1
        resp['data'], resp["payment_required"] = single_booking_payment_details(request, order_list)

        # raise Exception("ROLLBACK FOR TESTING")

        return resp

    @transaction.atomic()
    def process_pg_order(self, convert_cod_to_prepaid=False):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.insurance.models import UserInsurance
        from ondoc.subscription_plan.models import UserPlanMapping
        from ondoc.chat.models import ChatConsultation
        from ondoc.insurance.models import InsuranceDoctorSpecializations
        from ondoc.plus.models import PlusUser

        from ondoc.provider.models import EConsultation
        orders_to_process = []
        if self.orders.exists():
            orders_to_process = self.orders.all()
        else:
            orders_to_process = [self]

        total_cashback_used = total_wallet_used = 0
        opd_appointment_ids = []
        plus_ids = []
        lab_appointment_ids = []
        insurance_ids = []
        user_plan_ids = []
        econsult_ids = []
        chat_plan_ids = []
        user = self.user
        plus_user = user.active_plus_user
        user_insurance_obj = user.active_insurance

        gyno_count = 0
        onco_count = 0
        if user_insurance_obj:
            specialization_count_dict = InsuranceDoctorSpecializations.get_already_booked_specialization_appointments(user, user_insurance_obj)
            gyno_count = specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST,{}).get('count', 0)
            onco_count = specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST,{}).get('count', 0)

        for order in orders_to_process:
            try:
                is_process = True
                app_data = order.action_data if order.action_data else {}
                doctor = app_data.get('doctor', None)

                if doctor:
                    if app_data.get('payment_type') == OpdAppointment.INSURANCE and not user_insurance_obj:
                        is_process = False
                    if user_insurance_obj and app_data.get('payment_type') == OpdAppointment.INSURANCE:
                        doctor_specialization_tuple = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(doctor)
                        if doctor_specialization_tuple:
                            doctor_specialization = doctor_specialization_tuple[1]
                            if doctor_specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST:
                               if gyno_count >= settings.INSURANCE_GYNECOLOGIST_LIMIT:
                                    is_process = False
                               else:
                                    gyno_count += 1

                            if doctor_specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST:
                                if onco_count >= settings.INSURANCE_ONCOLOGIST_LIMIT:
                                    is_process = False
                                else:
                                    onco_count += 1
                    if app_data.get('payment_type') == OpdAppointment.VIP and plus_user:
                        is_process = True
                    if not is_process:
                        raise Exception("Insurance invalidate, Could not process entire order")

                curr_app, curr_wallet, curr_cashback = order.process_order(convert_cod_to_prepaid)

                # appointment was not created - due to insufficient balance, do not process
                if not curr_app:
                    continue
                if order.product_id == Order.DOCTOR_PRODUCT_ID:
                    opd_appointment_ids.append(curr_app.id)
                elif order.product_id == Order.LAB_PRODUCT_ID:
                    lab_appointment_ids.append(curr_app.id)
                elif order.product_id == Order.INSURANCE_PRODUCT_ID:
                    insurance_ids.append(curr_app.id)
                elif order.product_id == Order.SUBSCRIPTION_PLAN_PRODUCT_ID:
                    user_plan_ids.append(curr_app.id)
                elif order.product_id == Order.PROVIDER_ECONSULT_PRODUCT_ID:
                    econsult_ids.append(curr_app.id)
                elif order.product_id == Order.CHAT_PRODUCT_ID:
                    chat_plan_ids.append(curr_app.id)
                elif order.product_id in [Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID]:
                    plus_ids.append(curr_app.id)

                total_cashback_used += curr_cashback
                total_wallet_used += curr_wallet

                # trigger event for new appointment creation
                if self.visitor_info:
                    curr_app.trigger_created_event(self.visitor_info)

                # mark cart item delete after order process
                if order.cart:
                    order.cart.mark_delete()
            except Exception as e:
                raise Exception("Error in processing order - " + str(e))

        if not opd_appointment_ids and not lab_appointment_ids and not insurance_ids and not user_plan_ids and not econsult_ids and not chat_plan_ids and not plus_ids:
            raise Exception("Could not process entire order")

        # mark order processed:
        self.change_payment_status(Order.PAYMENT_ACCEPTED)

        # if order is done without PG transaction, then make an async task to create a dummy transaction and set it.
        if not self.getTransactions():
            try:
                transaction.on_commit(lambda: set_order_dummy_transaction.apply_async((self.id, self.get_user_id(),), countdown=5))
            except Exception as e:
                logger.error(str(e))

        money_pool = MoneyPool.objects.create(wallet=total_wallet_used, cashback=total_cashback_used, logs=[])

        if opd_appointment_ids:
            OpdAppointment.objects.filter(id__in=opd_appointment_ids).update(money_pool=money_pool)
        if lab_appointment_ids:
            LabAppointment.objects.filter(id__in=lab_appointment_ids).update(money_pool=money_pool)
        if insurance_ids:
            UserInsurance.objects.filter(id__in=insurance_ids).update(money_pool=money_pool)
        if user_plan_ids:
            UserPlanMapping.objects.filter(id__in=user_plan_ids).update(money_pool=money_pool)
        if econsult_ids:
            EConsultation.objects.filter(id__in=econsult_ids).update(money_pool=money_pool)
        if chat_plan_ids:
            ChatConsultation.objects.filter(id__in=chat_plan_ids).update(money_pool=money_pool)
        if plus_ids:
            PlusUser.objects.filter(id__in=plus_ids).update(money_pool=money_pool)

        resp = {"opd": opd_appointment_ids , "lab": lab_appointment_ids, "plan": user_plan_ids,
                 "insurance": insurance_ids, "econsultation": econsult_ids, "chat" : chat_plan_ids, "plus": plus_ids, "type": "all", "id": None }
        # Handle backward compatibility, in case of single booking, return the booking id

        if (len(opd_appointment_ids) + len(lab_appointment_ids) + len(user_plan_ids) + len(insurance_ids) + len(econsult_ids) + len(chat_plan_ids) + len(plus_ids)) == 1:
            result_type = "all"
            result_id = None
            if len(opd_appointment_ids) > 0:
                result_type = "doctor"
                result_id = opd_appointment_ids[0]
            elif len(lab_appointment_ids) > 0:
                result_type = "lab"
                result_id = lab_appointment_ids[0]
            elif len(user_plan_ids) > 0:
                result_type = "plan"
                result_id = user_plan_ids[0]
            elif len(insurance_ids) > 0:
                result_type = "insurance"
                result_id = insurance_ids[0]
            elif len(econsult_ids) > 0:
                result_type = "econsultation"
                result_id = econsult_ids[0]
            elif len(chat_plan_ids) > 0:
                result_type = "chat"
                result_id = chat_plan_ids[0]
            elif len(plus_ids) > 0:
                result_type = "plus"
                result_id = plus_ids[0]
            # resp["type"] = "doctor" if len(opd_appointment_ids) > 0 else "lab"
            # resp["id"] = opd_appointment_ids[0] if len(opd_appointment_ids) > 0 else lab_appointment_ids[0]
            resp["type"] = result_type
            resp["id"] = result_id
        return resp

    def validate_user(self, user=None):
        if not user:
            return True
        order_user_id = self.get_user_id()
        return order_user_id == user.id

    def get_user_id(self):
        if self.user:
            return self.user.id
        if self.action_data and "user" in self.action_data:
            return self.action_data["user"]
        return None

    @transaction.atomic()
    def change_payment_status(self, status):
        order_obj = Order.objects.select_for_update().get(id=self.id)
        if status == order_obj.payment_status or order_obj.payment_status == Order.PAYMENT_ACCEPTED:
            return False

        order_obj.payment_status = status
        order_obj.save()
        return True

    class Meta:
        db_table = "order"

    @cached_property
    def get_deal_price_without_coupon(self):
        deal_price = 0
        if self.is_parent():
            for order in self.orders.all():
                deal_price += Decimal(order.action_data.get('deal_price', '0.00'))
        else:
            if self.product_id == Order.INSURANCE_PRODUCT_ID:
                deal_price = self.amount
            else:
                deal_price = Decimal(self.action_data.get('deal_price', '0.00'))
        return deal_price

    @cached_property
    def get_amount_without_pg_coupon(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        amount = self.amount
        used_pgspecific_coupons = self.used_pgspecific_coupons
        used_pgspecific_coupons_ids = list(map(lambda x: x.id, used_pgspecific_coupons)) if used_pgspecific_coupons else []
        if self.is_parent():
            for order in self.orders.all():
                if self.product_id == Order.DOCTOR_PRODUCT_ID or self.product_id == Order.LAB_PRODUCT_ID:
                    if self.product_id == Order.DOCTOR_PRODUCT_ID:
                        obj = OpdAppointment()
                    elif self.product_id == Order.LAB_PRODUCT_ID:
                        obj = LabAppointment()
                    order_coupons_ids = order.action_data['coupon']
                    for coupon_id in order_coupons_ids:
                        if coupon_id in used_pgspecific_coupons_ids:
                            coupon = Coupon.objects.filter(pk=coupon_id).first()
                            if coupon:
                                amount += obj.get_discount(coupon, Decimal(order.action_data['deal_price']))
        return amount

    def used_coupons(self):
        coupons_ids = []
        if self.is_parent():
            for order in self.orders.all():
                coupons_ids.append(order.action_data.get('coupon'))
        else:
            coupons_ids.append(self.action_data.get('coupon'))

        coupons_ids = list(itertools.chain(*coupons_ids))
        coupons = Coupon.objects.filter(pk__in=coupons_ids)
        return coupons

    @cached_property
    def used_pgspecific_coupons(self):
        used_pgspecific_coupons = None
        used_coupons = self.used_coupons()
        if used_coupons:
            used_pgspecific_coupons = list(filter(lambda x: x.payment_option, used_coupons))

        return used_pgspecific_coupons

    def update_fields_after_coupon_remove(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        amount = self.amount
        if self.is_parent():
            used_pgspecific_coupons = self.used_pgspecific_coupons
            if used_pgspecific_coupons:
                used_pgspecific_coupons_ids = list(map(lambda x: x.id, used_pgspecific_coupons))
                for order in self.orders.all():
                    if order.product_id == Order.DOCTOR_PRODUCT_ID or order.product_id == Order.LAB_PRODUCT_ID:
                        if order.action_data:
                            if self.product_id == Order.DOCTOR_PRODUCT_ID:
                                obj = OpdAppointment()
                            elif self.product_id == Order.LAB_PRODUCT_ID:
                                obj = LabAppointment()
                            order_coupons_ids = order.action_data['coupon']
                            for coupon_id in order_coupons_ids:
                                if coupon_id in used_pgspecific_coupons_ids:
                                    coupon = Coupon.objects.filter(pk=coupon_id).first()
                                    if coupon:
                                        pg_coupon_discount = obj.get_discount(coupon, Decimal(order.action_data['deal_price']))
                                        amount += pg_coupon_discount
                                        order.action_data['effective_price'] = str(Decimal(order.action_data['effective_price']) + pg_coupon_discount)
                                        order.action_data['discount'] = str(Decimal(order.action_data['discount']) - pg_coupon_discount)
                                        order.action_data['coupon'].remove(coupon_id)
                                        order.save()
                self.amount = amount
                self.save()

        return True


class PgTransaction(TimeStampedModel, SoftDelete):
    PG_REFUND_SUCCESS_OK_STATUS = '1'
    PG_REFUND_FAILURE_OK_STATUS = '0'
    PG_REFUND_FAILURE_STATUS = 'FAIL'
    PG_REFUND_ALREADY_REQUESTED_STATUS = 'ALREADY_REQUESTED'

    REFUND_UPDATE_FAILURE_STATUS = 'REFUND_FAILURE_BY_PG'

    DOCTOR_APPOINTMENT = 1
    LAB_APPOINTMENT = 2
    CREDIT = 0
    DEBIT = 1
    TYPE_CHOICES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    NODAL1 = 1
    NODAL2 = 2
    CURRENT_ACCOUNT = 3
    NODAL_CHOICES = [(NODAL1, "Nodal 1"), (NODAL2, "Nodal 2"), (CURRENT_ACCOUNT, "Current Account")]

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.BigIntegerField(blank=True, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, related_name="txn")
    #order_id = models.PositiveIntegerField()
    order_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=50, null=True, blank=True)
    response_code = models.CharField(max_length=50)
    bank_id = models.CharField(max_length=50, null=True, blank=True)
    transaction_date = models.DateTimeField(auto_now=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    currency = models.CharField(max_length=15, null=True, blank=True)
    status_code = models.IntegerField()
    pg_name = models.CharField(max_length=100, null=True, blank=True)
    status_type = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, null=True)
    pb_gateway_name = models.CharField(max_length=100, null=True, blank=True)
    payment_captured = models.BooleanField(default=False)
    nodal_id = models.SmallIntegerField(choices=NODAL_CHOICES, null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
            Save PG transaction and credit consumer account, with amount paid at PaymentGateway.
        """
        update_consumer_account = False
        if self.id is None:
            update_consumer_account = True

        super(PgTransaction, self).save(*args, **kwargs)

        if update_consumer_account:
            consumer_account = ConsumerAccount.objects.get_or_create(user=self.user)
            consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)
            pg_data = vars(self)
            pg_data['user'] = self.user
            consumer_account.credit_payment(pg_data, pg_data['amount'])

    @classmethod
    def get_transactions(cls, user, amount):
        max_ref_date = timezone.now() - timedelta(days=ConsumerRefund.MAXREFUNDDAYS)
        refund_queryset = (
            ConsumerRefund.objects.filter(user=user, pg_transaction__isnull=False).values(
                'pg_transaction').
            annotate(refunded_amount=Sum('refund_amount'), pg_tx_amount=Max('pg_transaction__amount')))
        pg_rem_bal = dict()
        if refund_queryset:
            for data in refund_queryset:
                pg_rem_bal[data['pg_transaction']] = data['pg_tx_amount'] - data['refunded_amount']

        pgtx_obj = cls.objects.filter(user=user, created_at__gte=max_ref_date)
        new_pg_obj = list()
        if pgtx_obj.exists():
            for pg_data in pgtx_obj:
                if pg_rem_bal.get(pg_data.id) is not None:
                    if pg_rem_bal[pg_data.id] > 0:
                        pg_data.amount = pg_rem_bal[pg_data.id]
                        new_pg_obj.append(pg_data)
                else:
                    new_pg_obj.append(pg_data)

            if new_pg_obj:
                new_pg_obj = sorted(new_pg_obj, key=lambda k: k.amount, reverse=True)

        pgtx_details = list()
        index = 0

        refund_amount = amount
        while refund_amount > 0 and index < len(new_pg_obj):
            available_transaction = new_pg_obj[index]

            refund_entry = {'id': available_transaction,
                            'amount': min(available_transaction.amount, refund_amount)}

            pgtx_details.append(refund_entry)
            index += 1
            refund_amount -= refund_entry['amount']

        if refund_amount > 0:
            pgtx_details.append({'id': None, 'amount': refund_amount})

        return pgtx_details

    @classmethod
    def get_transactions_v2(cls, user, ctx_obj):
        pgtx_details = list()

        pg_txns = PgTransaction.objects.filter(user=user, transaction_id=ctx_obj.transaction_id, order_id=ctx_obj.order_id)

        if pg_txns:
            for pg_txn in pg_txns:
                pgtx_details.append({'id': pg_txn, 'amount': ctx_obj.amount})

        return pgtx_details

    @classmethod
    def is_valid_hash(cls, data, product_id):
        client_key = secret_key = ""
        if product_id in [Order.DOCTOR_PRODUCT_ID, Order.SUBSCRIPTION_PLAN_PRODUCT_ID, Order.CHAT_PRODUCT_ID, Order.PROVIDER_ECONSULT_PRODUCT_ID, Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID]:
            client_key = settings.PG_CLIENT_KEY_P1
            secret_key = settings.PG_SECRET_KEY_P1
        elif product_id == Order.LAB_PRODUCT_ID:
            client_key = settings.PG_CLIENT_KEY_P2
            secret_key = settings.PG_SECRET_KEY_P2
        elif product_id == Order.INSURANCE_PRODUCT_ID:
            client_key = settings.PG_CLIENT_KEY_P3
            secret_key = settings.PG_SECRET_KEY_P3
        pg_hash = None
        temp_data = copy.deepcopy(data)
        if temp_data.get("hash"):
            pg_hash = temp_data.pop("hash")
        calculated_hash, prehashed_str = cls.create_incomming_pg_hash(temp_data, client_key, secret_key)
        if pg_hash != calculated_hash:
            logger.error(
                "Hash Mismatch with Calculated Hash - " + calculated_hash + " pre-hashed string - " + prehashed_str + " pg response data - " + json.dumps(
                    data))

        return True if pg_hash == calculated_hash else False

    @classmethod
    def create_incomming_pg_hash(cls, data, key1, key2):
        data_to_verify = ''
        for k in sorted(data.keys()):
            if str(data[k]).upper() != 'NULL':
                data_to_verify = data_to_verify + k + '=' + str(data[k]) + ';'
        encrypted_data_to_verify = key2 + '|' + data_to_verify + '|' + key1
        encrypted_message_object = hashlib.sha256(str(encrypted_data_to_verify).encode())

        encrypted_message_digest = encrypted_message_object.hexdigest()
        return encrypted_message_digest, encrypted_data_to_verify

    # class Meta:
    #     db_table = "pg_transaction"

    @classmethod
    def create_pg_hash(cls, data, key1, key2):
        data_to_verify = ''
        for k in sorted(data.keys()):
            if str(data[k]):
                data_to_verify = data_to_verify + k + '=' + str(data[k]) + ';'
        encrypted_data_to_verify = key2 + '|' + data_to_verify + '|' + key1
        encrypted_message_object = hashlib.sha256(str(encrypted_data_to_verify).encode())

        encrypted_message_digest = encrypted_message_object.hexdigest()
        return encrypted_message_digest

    def is_preauth(self):
        return self.status_type == 'TXN_AUTHORIZE' or self.status_type == '27'

    def has_refunded(self):
        from ondoc.account.models import ConsumerRefund
        refund_obj = ConsumerRefund.objects.filter(pg_transaction_id=self.id).first()
        if refund_obj:
            return True

        return False

    class Meta:
        db_table = "pg_transaction"
        # unique_together = (("order", "order_no", "deleted"),)

        unique_together = (("order", "order_no", "deleted", "transaction_id"),)


class DummyTransactions(TimeStampedModel):
    PG_REFUND_SUCCESS_OK_STATUS = '1'
    PG_REFUND_FAILURE_OK_STATUS = '0'
    PG_REFUND_FAILURE_STATUS = 'FAIL'
    PG_REFUND_ALREADY_REQUESTED_STATUS = 'ALREADY_REQUESTED'

    REFUND_UPDATE_FAILURE_STATUS = 'REFUND_FAILURE_BY_PG'

    DOCTOR_APPOINTMENT = 1
    LAB_APPOINTMENT = 2
    CREDIT = 0
    DEBIT = 1
    TYPE_CHOICES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    INSURANCE_NODAL_TRANSFER = 'insurance_nodal_transfer'

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.BigIntegerField(blank=True, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, related_name="dummy_txn")
    order_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=50, null=True, blank=True)
    response_code = models.CharField(max_length=50, null=True, blank=True)
    bank_id = models.CharField(max_length=50, null=True, blank=True)
    transaction_date = models.DateTimeField(auto_now=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    currency = models.CharField(max_length=15, null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    pg_name = models.CharField(max_length=100, null=True, blank=True)
    status_type = models.CharField(max_length=50, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    pb_gateway_name = models.CharField(max_length=100, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "dummy_transaction"


class MoneyPool(TimeStampedModel):
    wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    logs = JSONField(default=[])

    def get_completed_appointments(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        opd_apps = self.opd_apps.filter(status=OpdAppointment.COMPLETED)[:]
        lab_apps = self.lab_apps.filter(status=LabAppointment.COMPLETED)[:]

        completed_appointments = [*opd_apps, *lab_apps]

        def compare_app(obj):
            history = obj.history.filter(status=obj.COMPLETED).first()
            if history:
                return history.created_at
            return obj.updated_at

        if completed_appointments:
            completed_appointments = sorted(completed_appointments, key=compare_app)

        return completed_appointments

    @transaction.atomic()
    def get_refund_breakup(self, amount):
        # sanity if, pool is empty and refund is still required
        if amount > (self.wallet + self.cashback):
            raise Exception("Pool Balance insufficient")

        wallet_refund = min(self.wallet, amount)
        cashback_refund = min(self.cashback, amount - wallet_refund)

        self.wallet -= wallet_refund
        self.cashback -= cashback_refund
        self.save()

        return wallet_refund, cashback_refund

    def save(self, *args, **kwargs):
        database_instance = MoneyPool.objects.filter(id=self.id).first()
        log = {
            "initial" : { "wallet" : 0, "cashback": 0 },
            "final": { "wallet": 0, "cashback": 0 },
            "timestamp" : str(timezone.now())
        }

        log["final"]["wallet"] = int(self.wallet)
        log["final"]["cashback"] = int(self.cashback)

        if database_instance:
            log["initial"]["wallet"] = int(database_instance.wallet)
            log["initial"]["cashback"] = int(database_instance.cashback)

        self.logs.append(log)
        super().save(*args, **kwargs)

    class Meta:
        db_table = "money_pool"


class ConsumerAccount(TimeStampedModel):
    user = models.OneToOneField(User, blank=True, null=True, on_delete=models.SET_NULL)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # To get user's wallet balance
    def get_total_balance(self):
        return self.balance + self.cashback

    def credit_payment(self, pg_data, amount):
        self.balance += amount
        action = ConsumerTransaction.PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.consumer_tx_pg_data(pg_data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def credit_cancellation(self, appointment_obj, product_id, wallet_refund, cashback_refund):
        wallet_refund_amount = wallet_refund
        cashback_refund_amount = cashback_refund

        self.balance += wallet_refund_amount
        self.cashback += cashback_refund_amount

        action = ConsumerTransaction.CANCELLATION
        tx_type = PgTransaction.CREDIT

        cashback_txn = None
        wallet_txn = None
        ctxn_objs = ConsumerTransaction.objects.select_for_update().filter(user_id=appointment_obj.user_id,
                                                                          reference_id=appointment_obj.id,
                                                                          action=ConsumerTransaction.SALE)
        # assuming max 2 sale entries
        for ctxn_obj in ctxn_objs:
            if ctxn_obj.source == ConsumerTransaction.CASHBACK_SOURCE:
                cashback_txn = ctxn_obj
            else:
                wallet_txn = ctxn_obj

        if cashback_refund_amount:
            if cashback_txn:
                cashback_txn.balance += cashback_refund_amount
                cashback_txn.save()
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_refund_amount, action, tx_type, ConsumerTransaction.CASHBACK_SOURCE)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        if wallet_refund_amount:
            if wallet_txn:
                wallet_txn.balance += wallet_refund_amount
                wallet_txn.save()
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, wallet_refund_amount, action, tx_type, ConsumerTransaction.WALLET_SOURCE)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        self.save()

    def debit_refund(self, txn_entity_obj=None, initiate_refund=1):
        ctx_objs = []
        if txn_entity_obj:
            ctx_sale_objs = ConsumerTransaction.objects.select_for_update().filter(user_id=txn_entity_obj.user_id,
                                                                                  reference_id=txn_entity_obj.id,
                                                                                  type=PgTransaction.DEBIT,
                                                                                  action=ConsumerTransaction.SALE)

            parent_ref = True

            if ctx_sale_objs:
                balance_refund = False
                reference_id = txn_entity_obj.id
                for ctx_sale_obj in ctx_sale_objs:
                    if ctx_sale_obj.ref_txns:
                        ctx_objs.append(ctx_sale_obj.debit_from_ref_txn(self, 0, parent_ref, initiate_refund,
                                                                        balance_refund, reference_id))
                    if ctx_sale_obj.balance and ctx_sale_obj.balance > 0:
                        if ctx_sale_obj.source == ConsumerTransaction.WALLET_SOURCE:
                            ctx_objs.append(ctx_sale_obj.debit_from_balance(self))

                    ctx_sale_obj.save()

        # refund wallet amount
        if self.balance:
            old_txn_objs = ConsumerTransaction.get_transactions(self.user, [ConsumerTransaction.PAYMENT, ConsumerTransaction.SALE])
            if old_txn_objs:
                parent_ref = True
                balance_refund = True
                for old_txn_obj in old_txn_objs:
                    if old_txn_obj.ref_txns:
                        ctx_objs.append(old_txn_obj.debit_from_ref_txn(self, 0, parent_ref, initiate_refund, balance_refund, old_txn_obj.reference_id))
                    if old_txn_obj.balance and old_txn_obj.balance > 0:
                        if old_txn_obj.action == ConsumerTransaction.PAYMENT or (
                                old_txn_obj.action == ConsumerTransaction.SALE and old_txn_obj.source == ConsumerTransaction.WALLET_SOURCE):
                            ctx_objs.append(old_txn_obj.debit_from_balance(self))
                    old_txn_obj.save()
            else:
                if self.balance:
                    amount = self.balance
                    self.balance = 0
                    action = ConsumerTransaction.REFUND
                    tx_type = PgTransaction.DEBIT
                    consumer_tx_data = self.consumer_tx_pg_data({"user": self.user}, amount, action, tx_type)
                    # consumer_tx_data = self.form_consumer_tx_data({"user": self.user}, amount, action, tx_type)
                    ctx_obj = ConsumerTransaction.objects.create(**consumer_tx_data)
                    ctx_objs.append(ctx_obj)

        self.save()
        ctx_objs = list(flatten(ctx_objs))
        ctx_objs = list(filter(None, ctx_objs))
        return ctx_objs

    def debit_schedule(self, appointment_obj, product_id, amount):
        cashback_txns_used = wallet_txns_used = []
        cashback_deducted = 0
        order = appointment_obj.get_order()
        if not product_id in [Order.SUBSCRIPTION_PLAN_PRODUCT_ID, Order.INSURANCE_PRODUCT_ID, Order.VIP_PRODUCT_ID, Order.GOLD_PRODUCT_ID]:
            if order and order.cashback_amount:
                cashback_deducted = min(self.cashback, amount)
                cashback_txns = ConsumerTransaction.objects.select_for_update().filter(user=self.user,
                                                                                       balance__gt=0)\
                    .filter(Q(action__in=[ConsumerTransaction.CASHBACK_CREDIT, ConsumerTransaction.REFERRAL_CREDIT])|
                            Q(action=ConsumerTransaction.SALE, source=ConsumerTransaction.CASHBACK_SOURCE)).order_by("created_at")
                cashback_txns_used = ConsumerTransaction.update_txn_balance(cashback_txns, cashback_deducted)
                self.cashback -= cashback_deducted

        balance_deducted = min(self.balance, amount-cashback_deducted)
        if order and order.wallet_amount:
            pg_txns = ConsumerTransaction.get_transactions(self.user, [ConsumerTransaction.PAYMENT, ConsumerTransaction.SALE])
            wallet_txns_used = ConsumerTransaction.update_txn_balance(pg_txns, balance_deducted)
        else:
            pg_txns = []
            pg_txn = ConsumerTransaction.objects.select_for_update().filter(user=self.user, action=ConsumerTransaction.PAYMENT,
                                                               balance__gt=0).order_by("-created_at").first()
            pg_txns.append(pg_txn)
            wallet_txns_used = ConsumerTransaction.update_txn_balance(pg_txns, balance_deducted)
        self.balance -= balance_deducted

        action = ConsumerTransaction.SALE
        tx_type = PgTransaction.DEBIT

        if cashback_deducted:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_deducted, action, tx_type, ConsumerTransaction.CASHBACK_SOURCE, cashback_txns_used)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        if balance_deducted:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, balance_deducted, action, tx_type, ConsumerTransaction.WALLET_SOURCE, wallet_txns_used)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        self.save()
        return balance_deducted, cashback_deducted

    def credit_schedule(self, appointment_obj, product_id, amount):
        self.balance += amount
        action = ConsumerTransaction.RESCHEDULE_PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def debit_promotional(self, appointment_obj):
        cashback_deducted = balance_deducted = promotional_amount_debit = 0
        if hasattr(appointment_obj, 'promotional_amount'):
            promotional_amount_debit = appointment_obj.promotional_amount

        if promotional_amount_debit:
            cashback_deducted = min(self.cashback, promotional_amount_debit)
            self.cashback -= cashback_deducted

            balance_deducted = min(self.balance, promotional_amount_debit - cashback_deducted)
            self.balance -= balance_deducted

            action = ConsumerTransaction.PROMOTIONAL_DEBIT
            tx_type = PgTransaction.DEBIT

            if cashback_deducted:
                consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, appointment_obj.PRODUCT_ID,
                                                                     cashback_deducted, action, tx_type,
                                                                     ConsumerTransaction.CASHBACK_SOURCE)
                ConsumerTransaction.objects.create(**consumer_tx_data)

            if balance_deducted:
                consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, appointment_obj.PRODUCT_ID,
                                                                     balance_deducted, action, tx_type,
                                                                     ConsumerTransaction.WALLET_SOURCE)
                ConsumerTransaction.objects.create(**consumer_tx_data)

            self.save()
        return balance_deducted, cashback_deducted

    @classmethod
    def credit_cashback(cls, user, cashback_amount, appointment_obj, product_id):
        # check if cashback already credited
        if ConsumerTransaction.objects.filter(product_id=product_id, action=ConsumerTransaction.CASHBACK_CREDIT, reference_id=appointment_obj.id).exists():
            return

        consumer_account = cls.objects.select_for_update().get(user=user)
        consumer_account.cashback += int(cashback_amount)
        action = ConsumerTransaction.CASHBACK_CREDIT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = consumer_account.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        consumer_account.save()

    @classmethod
    def credit_referral(cls, user, cashback_amount, appointment_obj=None, product_id=None):
        consumer_account = cls.objects.get_or_create(user=user)
        consumer_account = cls.objects.select_for_update().get(user=user)

        consumer_account.cashback += int(cashback_amount)
        action = ConsumerTransaction.REFERRAL_CREDIT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = consumer_account.consumer_tx_appointment_data(user, None, product_id, cashback_amount,
                                                                         action, tx_type, ConsumerTransaction.CASHBACK_SOURCE)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        consumer_account.save()

        try:
            context = {
                "title": "Referral Bonus",
                "body": ("Rs. " + str(int(cashback_amount)) + " Referral Bonus Received"),
                "url": "/wallet",
                "action_type": NotificationAction.CASHBACK_CREDITED,
            }

            AppNotification.send_notification(user=user, notification_type=NotificationAction.CASHBACK_CREDITED,
                                              context=context)
        except Exception as e:
            logger.error(str(e))

    def consumer_tx_pg_data(self, data, amount, action, tx_type):
        consumer_tx_data = dict()
        consumer_tx_data['user'] = data['user']
        consumer_tx_data['product_id'] = data.get('product_id')
        consumer_tx_data['reference_id'] = data.get('reference_id')
        consumer_tx_data['transaction_id'] = data.get('transaction_id')
        consumer_tx_data['order_id'] = data.get('order_id')
        consumer_tx_data['type'] = tx_type
        consumer_tx_data['action'] = action
        consumer_tx_data['amount'] = amount
        if action == ConsumerTransaction.PAYMENT and tx_type == PgTransaction.CREDIT:
            consumer_tx_data['balance'] = amount
        return consumer_tx_data

    def consumer_tx_appointment_data(self, user, app_obj, product_id, amount, action, tx_type, source=None, ref_txns=None):
        if source is None:
            source = ConsumerTransaction.WALLET_SOURCE

        consumer_tx_data = dict()
        consumer_tx_data['user'] = user
        if product_id is not None:
            consumer_tx_data['product_id'] = product_id
        if app_obj:
            consumer_tx_data['reference_id'] = app_obj.id
            order = app_obj.get_order()
            consumer_tx_data['order_id'] = order.id
        else:
            consumer_tx_data['reference_id'] = None
            consumer_tx_data['order_id'] = None
        consumer_tx_data['type'] = tx_type
        consumer_tx_data['action'] = action
        consumer_tx_data['amount'] = amount
        consumer_tx_data['source'] = source
        if tx_type == PgTransaction.CREDIT and not action == ConsumerTransaction.CANCELLATION:
            consumer_tx_data['balance'] = amount
        if ref_txns:
            consumer_tx_data['ref_txns'] = ref_txns

        return consumer_tx_data

    class Meta:
        db_table = "consumer_account"


class ConsumerTransaction(TimeStampedModel, SoftDelete):
    CANCELLATION = 0
    PAYMENT = 1
    REFUND = 2
    SALE = 3
    RESCHEDULE_PAYMENT = 4
    CASHBACK_CREDIT = 5
    REFERRAL_CREDIT = 6
    PROMOTIONAL_DEBIT = 7

    WALLET_SOURCE = 1
    CASHBACK_SOURCE = 2

    SOURCE_TYPE = [(WALLET_SOURCE, "Wallet"), (CASHBACK_SOURCE, "Cashback")]
    action_list = ["Cancellation", "Payment", "Refund", "Sale", "CashbackCredit", "ReferralCredit", "PromotionalDebit"]
    ACTION_CHOICES = list(enumerate(action_list, 0))
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS, blank=True, null=True)
    reference_id = models.BigIntegerField(blank=True, null=True)
    order_id = models.IntegerField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    # pg_transaction = models.ForeignKey(PgTransaction, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.SmallIntegerField(choices=PgTransaction.TYPE_CHOICES)
    action = models.SmallIntegerField(choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.SmallIntegerField(choices=SOURCE_TYPE, blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=decimal.Decimal(0))
    ref_txns = JSONField(blank=True, null=True)

    def save(self, *args, **kwargs):
        database_instance = ConsumerTransaction.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.app_commit_tasks(database_instance))

    def app_commit_tasks(self, old_instance):
        from ondoc.notification import tasks as notification_tasks
        if not old_instance and self.type == PgTransaction.DEBIT and self.action == self.action_list.index('Refund'):
            try:
                notification_tasks.refund_breakup_sms_task.apply_async((self.id,), countdown=1)
            except Exception as e:
                logger.error(str(e))

    def debit_from_ref_txn(self, consumer_account, refund_amount=0, parent_ref=False, initiate_refund=1,
                           balance_refund=0, reference_id=None):
        ctx_objs = []
        ref_txns = self.ref_txns
        # todo - use python filter here to avoid db call
        ref_txn_objs = ConsumerTransaction.objects.filter(id__in=list(ref_txns.keys())).order_by('id')
        for ref_txn_obj in ref_txn_objs:
            cashback_txn = False
            is_preauth_txn = False
            if parent_ref and not refund_amount:
                if balance_refund:
                    refund_amount = self.balance
                else:
                    refund_amount = decimal.Decimal(ref_txns.get(str(ref_txn_obj.id), 0))
            if ref_txn_obj.action in [ConsumerTransaction.CASHBACK_CREDIT, ConsumerTransaction.REFERRAL_CREDIT]:
                cashback_txn = True
            elif ref_txn_obj.action == ConsumerTransaction.SALE and ref_txn_obj.source == ConsumerTransaction.CASHBACK_SOURCE:
                cashback_txn = True
            if ref_txn_obj.ref_txns or ref_txn_obj.action == ConsumerTransaction.PAYMENT:
                ref_refund_amount = min(decimal.Decimal(ref_txns.get(str(ref_txn_obj.id), 0)), refund_amount)
                refund_amount -= ref_refund_amount
                if ref_txn_obj.action == ConsumerTransaction.PAYMENT:
                    ref_txn_obj.balance += ref_refund_amount
                    ctx_obj = ref_txn_obj.debit_from_balance(consumer_account, reference_id)
                else:
                    ctx_obj = ref_txn_obj.debit_from_ref_txn(consumer_account, ref_refund_amount, False, 1, 0, reference_id)
            else:
                ref_refund_amount = refund_amount
                if not cashback_txn and ref_refund_amount:
                    ctx_obj = ref_txn_obj.debit_txn_refund(consumer_account, ref_refund_amount, reference_id)
                else:
                   ctx_obj = None
            if self.balance and not cashback_txn and parent_ref and ref_refund_amount:
                if (self.balance - ref_refund_amount) >= 0:
                    self.balance -= ref_refund_amount
                else:
                    logger.info('Balance refund error: ' + str(self.id) + ', Refund: ' + str(refund_amount))

            if initiate_refund:
                if not cashback_txn:
                    ctx_objs.append(ctx_obj)
            else:
                pg_txn = PgTransaction.objects.filter(user=self.user, order_id=ref_txn_obj.order_id).order_by(
                    '-created_at').first()
                if pg_txn.is_preauth() or pg_txn.status_type == 'TXN_RELEASE':
                    is_preauth_txn = True
                if pg_txn:
                    if not is_preauth_txn:
                        ctx_objs.append(ctx_obj)
                else:
                    if not cashback_txn:
                        ctx_objs.append(ctx_obj)

            if ref_txn_obj.balance and ref_txn_obj.balance > 0 and not cashback_txn and not is_preauth_txn:
                ctx_objs.append(ref_txn_obj.debit_from_balance(consumer_account, reference_id))
        self.save()

        return ctx_objs

    def debit_txn_refund(self, consumer_account, refund_amount, reference_id=None):
        tx_obj = PgTransaction.objects.filter(order_id=self.order_id).order_by('-created_at').first()
        ctx_obj = None
        data = dict()
        data["user"] = self.user
        if tx_obj:
            data["product_id"] = tx_obj.product_id
            data["reference_id"] = reference_id
            data["transaction_id"] = tx_obj.transaction_id
            data["order_id"] = tx_obj.order_id if tx_obj else None
        if refund_amount:
            if (consumer_account.balance - refund_amount) >= 0:
                consumer_account.balance -= refund_amount
                consumer_tx_data = consumer_account.consumer_tx_pg_data(data, refund_amount, ConsumerTransaction.REFUND, PgTransaction.DEBIT)
                ctx_obj = ConsumerTransaction.objects.create(**consumer_tx_data)
            else:
                logger.error('Balance refund error: ' + str(consumer_account.id) + ', Refund: ' + str(refund_amount))

        return ctx_obj

    def debit_from_balance(self, consumer_account, reference_id=None):
        ctx_objs = []
        if self.balance:
            pg_ctx_obj = ConsumerTransaction.objects.filter(user=self.user, action=ConsumerTransaction.PAYMENT,
                                                            order_id=self.order_id).last()
            if pg_ctx_obj:
                ctx_obj = pg_ctx_obj.debit_txn_refund(consumer_account, self.balance, reference_id)
                if ctx_obj:
                    self.balance = 0
                    self.save()
                    ctx_objs.append(ctx_obj)
            else: # if order_id not found in self
                cancel_ctx_obj = ConsumerTransaction.objects.filter(user=self.user, action=ConsumerTransaction.CANCELLATION,
                                                                reference_id=self.reference_id).last()
                if cancel_ctx_obj and cancel_ctx_obj.order_id:
                    pg_ctx_obj = ConsumerTransaction.objects.filter(user=self.user, action=ConsumerTransaction.PAYMENT,
                                                                    order_id=cancel_ctx_obj.order_id).last()
                    if pg_ctx_obj:
                        ctx_obj = pg_ctx_obj.debit_txn_refund(consumer_account, self.balance, reference_id)
                        if ctx_obj:
                            self.balance = 0
                            self.save()
                            ctx_objs.append(ctx_obj)
                    else:
                        logger.error(
                            'Balance refund error: ' + str(consumer_account.id) + ', Refund: ' + str(self.balance))
                else:
                    logger.error(
                        'Balance refund error: ' + str(consumer_account.id) + ', Refund: ' + str(self.balance))
        return ctx_objs

    @classmethod
    def valid_appointment_for_cancellation(cls, app_id, product_id):
        return not cls.objects.filter(type=PgTransaction.CREDIT, reference_id=app_id, product_id=product_id,
                                      action=cls.CANCELLATION).exists()

    @classmethod
    def get_transactions(cls, user, actions=[]):
        # consumer_txns = cls.objects.select_for_update().filter(user=user, action__in=actions, type=txn_type, balance__gt=0).order_by("created_at")
        #source = source if source else [ConsumerTransaction.WALLET_SOURCE, ConsumerTransaction.CASHBACK_SOURCE]
        consumer_txns = cls.objects.select_for_update().filter(user=user, action__in=actions,
                                                               balance__gt=0).order_by("created_at")
        return consumer_txns

    @classmethod
    def update_txn_balance(cls, txns, amount):
        txns_used = {}
        if txns:
            for txn in txns:
                if amount:
                    balance_amount = min(txn.balance, amount)
                    txn.balance -= balance_amount
                    amount -= balance_amount
                    txns_used.update({txn.id: str(balance_amount)})
                    txn.save()
                else:
                    break
        return txns_used

    class Meta:
        db_table = 'consumer_transaction'


class ConsumerRefund(TimeStampedModel):
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'

    REFUND_INITIATED_TO_PG = 'REFUND_INITIATED_TO_PG'
    REFUND_SUCCESS_BY_PG = 'REFUND_SUCCESS_BY_PG'
    REFUND_FAILURE_BY_PG = 'REFUND_FAILURE_BY_PG'

    PENDING = 1
    REQUESTED = 5
    COMPLETED = 10
    ARCHIVED = 15
    MAXREFUNDDAYS = 700
    state_type = [(PENDING, "Pending"), (COMPLETED, "Completed"), (REQUESTED, "Requested"), (ARCHIVED, "Archived")]
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    consumer_transaction = models.ForeignKey(ConsumerTransaction, on_delete=models.DO_NOTHING)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pg_transaction = models.ForeignKey(PgTransaction, related_name='pg_refund', blank=True, null=True, on_delete=models.DO_NOTHING)
    refund_state = models.PositiveSmallIntegerField(choices=state_type, default=PENDING)
    refund_initiated_at = models.DateTimeField(blank=True, null=True)

    #FIELDs AS DIRECTED IN DOCNEW-1865
    bank_arn = models.CharField(null=True, blank=True, max_length=64)
    bankRefNum = models.CharField(null=True, blank=True, max_length=64)
    refundDate = models.DateTimeField(null=True, blank=True)
    refundId = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        database_instance = ConsumerRefund.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.app_commit_tasks(database_instance))

    def app_commit_tasks(self, old_instance):
        from ondoc.notification import tasks as notification_tasks
        if old_instance and old_instance.refund_state != self.refund_state and self.refund_state == self.COMPLETED:
            try:
                notification_tasks.refund_completed_sms_task.apply_async((self.id,), countdown=1)
            except Exception as e:
                logger.error(str(e))

    @classmethod
    def initiate_refund(cls, user, ctx_obj):
        BATCH_SIZE = 100
        if ctx_obj.order_id:
            pgtx_list = PgTransaction.get_transactions_v2(user, ctx_obj)
        else:
            pgtx_list = PgTransaction.get_transactions(user, ctx_obj.amount)
        refund_obj_data = list()
        consumer_refund_objs = list()
        num = 0
        for tx in pgtx_list:
            temp_data = {
                'user': ctx_obj.user,
                'consumer_transaction': ctx_obj,
                'refund_amount': tx['amount'],
                'pg_transaction': tx['id']
            }
            if num == BATCH_SIZE:
                obj = cls.objects.bulk_create(refund_obj_data, batch_size=BATCH_SIZE)
                consumer_refund_objs.extend(obj)
                refund_obj_data = list()
                num = 0
            # refund_data.append(temp_data)
            refund_obj_data.append(cls(**temp_data))
            num += 1
        if num:
            obj = cls.objects.bulk_create(refund_obj_data, batch_size=BATCH_SIZE)
            consumer_refund_objs.extend(obj)

        try:
            pg_data = form_pg_refund_data(consumer_refund_objs)
            # transaction.on_commit(lambda: refund_curl_request(pg_data))
        except Exception as e:
            logger.error("Error in refund celery - " + str(e))

    class Meta:
        db_table = "consumer_refund"

    @classmethod
    def schedule_refund_task(cls, consumer_refund_objs):
        pg_data = form_pg_refund_data(consumer_refund_objs)
        refund_curl_request(pg_data)

    def schedule_refund(self):
        from ondoc.account.mongo_models import PgLogs as PgLogsMongo
        pg_data = form_pg_refund_data([self, ])
        for req_data in pg_data:
            if settings.AUTO_REFUND:
                try:
                    token = settings.PG_REFUND_AUTH_TOKEN
                    headers = {
                        "auth": token,
                        "Content-Type": "application/json"
                    }
                    url = settings.PG_REFUND_URL
                    # For test only
                    # url = 'http://localhost:8000/api/v1/doctor/test'
                    print(url)
                    response = requests.post(url, data=json.dumps(req_data), headers=headers)
                    if settings.SAVE_LOGS:
                        save_pg_response.apply_async(
                            (PgLogsMongo.REFUND_REQUEST_RESPONSE, req_data.get('orderId'), req_data.get('refNo'), response.json(), req_data, req_data.get('user'),),
                            eta=timezone.localtime(), queue=settings.RABBITMQ_LOGS_QUEUE)
                    if response.status_code == status.HTTP_200_OK:
                        resp_data = response.json()
                        if resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_SUCCESS_OK_STATUS:
                            self.update_refund_status_on_resp(req_data["refNo"])
                        elif (resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                              resp_data.get("status") is not None and str(
                                    resp_data["status"]) == PgTransaction.PG_REFUND_ALREADY_REQUESTED_STATUS):
                            self.update_refund_status_on_resp(req_data["refNo"])
                            print("Already Requested")
                        elif (resp_data.get("ok") is None or
                              (str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                               (resp_data.get("status") is None or str(resp_data["status"]) == PgTransaction.PG_REFUND_FAILURE_STATUS))):
                            print("Refund Failure")
                            raise Exception("Wrong response - " + str(response.content))
                        else:
                            print("Incorrect response")
                            raise Exception("Wrong response - " + str(response.content))
                    else:
                        raise Exception("Invalid Http response status - " + str(response.content))
                except Exception as e:
                    # todo - temporary commented to avoid sentry logs
                    # logger.error("Error in Refund of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
                    print("Error in Refund of user with data - " + json.dumps(req_data) + " with exception - " + str(e))

    @classmethod
    def request_pending_refunds(cls):
        consumer_refund_objs = cls.objects.filter(refund_state=cls.PENDING)
        for obj in consumer_refund_objs:
            obj.schedule_refund()

    @classmethod
    def update_refund_status_on_resp(cls, pk):
        with transaction.atomic():
            refund_queryset = cls.objects.select_for_update().filter(pk=pk).first()
            if refund_queryset:
                refund_queryset.refund_state = ConsumerRefund.REQUESTED
                if not refund_queryset.refund_initiated_at:
                    refund_queryset.refund_initiated_at = timezone.now()
                refund_queryset.save()
                print("Status Updated")

    @classmethod
    def refund_status_request(cls, requested_refund):
        from ondoc.account.mongo_models import PgLogs as PgLogsMongo
        if settings.AUTO_REFUND:
            order_id = None
            if requested_refund.pg_transaction:
                order_id = requested_refund.pg_transaction.order_id
            url = settings.PG_REFUND_STATUS_API_URL
            token = settings.PG_REFUND_AUTH_TOKEN
            headers = {
                "auth": token
            }
            response = requests.get(url=url, params={"refId": requested_refund.id}, headers=headers)
            url_with_params = url + "?refId=" + str(requested_refund.id)
            json_url = '{"url": "%s"}' % url_with_params
            if order_id:
                if settings.SAVE_LOGS:
                    save_pg_response.apply_async(
                        (PgLogsMongo.REQUESTED_REFUND_RESPONSE, order_id, requested_refund.pg_transaction_id, response.json(),
                         json_url, requested_refund.user_id), eta=timezone.localtime(), queue=settings.RABBITMQ_LOGS_QUEUE)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                temp_data = resp_data.get("data")
                code = None
                try:
                    if temp_data:
                        for d in temp_data:
                            if "code" in d:
                                code = d.get("code")
                except:
                    pass
                if resp_data.get("ok") and str(resp_data["ok"]) == cls.SUCCESS_OK_STATUS and code is not None and \
                        code == ConsumerRefund.REFUND_SUCCESS_BY_PG:
                    with transaction.atomic():
                        obj = cls.objects.select_for_update().get(id=requested_refund.id)
                        if obj.refund_state != cls.COMPLETED:
                            obj.refund_state = cls.COMPLETED
                            obj.save()
                            print("status updated for - " + str(obj.id))
                else:
                    pass
                    #logger.error("Invalid ok status or code mismatch - " + str(response.content))

    @classmethod
    def update_refund_status(cls):
        # refund_ids = cls.objects.filter(refund_state=cls.REQUESTED).values_list('id', flat=True)
        # for ref_id in refund_ids:
        #     cls.refund_status_request(ref_id)
        requested_refunds = cls.objects.filter(refund_state=cls.REQUESTED)
        for requested_refund in requested_refunds:
            cls.refund_status_request(requested_refund)


class Invoice(TimeStampedModel):
    PRODUCT_IDS = Order.PRODUCT_IDS
    reference_id = models.PositiveIntegerField()
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS)
    file = models.FileField(upload_to='payment_receipt', null=True, blank=True)


class OrderLog(TimeStampedModel):
    product_id = models.CharField(max_length=10, blank=True, null=True)
    referer_data = JSONField(blank=True, null=True)
    url = models.CharField(max_length=250, blank=True, null=True)
    order_id = models.CharField(max_length=20, blank=True, null=True)
    appointment_id = models.CharField(max_length=20, blank=True, null=True)
    user = models.CharField(max_length=20, blank=True, null=True)
    is_agent = models.BooleanField(default=False)
    pg_data = JSONField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "order_log"


class MerchantPayout(TimeStampedModel):

    PENDING = 1
    ATTEMPTED = 2
    PAID = 3
    INITIATED = 4
    INPROCESS = 5
    FAILED_FROM_QUEUE = 6
    FAILED_FROM_DETAIL = 7
    ARCHIVE = 8
    AUTOMATIC = 1
    MANUAL = 2

    PROVIDER_PAYOUT = 1
    REVENUE_PAYOUT = 2

    DoctorPayout = Order.DOCTOR_PRODUCT_ID
    LabPayout = Order.LAB_PRODUCT_ID
    InsurancePremium = Order.INSURANCE_PRODUCT_ID
    BookingTypeChoices = [(DoctorPayout,'Doctor Booking'),(LabPayout,'Lab Booking'),(InsurancePremium,'Insurance Purchase')]

    NEFT = "NEFT"
    IMPS = "IMPS"
    IFT = "IFT"
    INTRABANK_IDENTIFIER = "KKBK"
    STATUS_CHOICES = [(PENDING, 'Pending'), (ATTEMPTED, 'ATTEMPTED'), (PAID, 'Paid'), (INITIATED, 'Initiated'), (INPROCESS, 'In Process'), (FAILED_FROM_QUEUE, 'Failed from Queue'), (FAILED_FROM_DETAIL, 'Failed from Detail'), (ARCHIVE, 'Archive')]
    PAYMENT_MODE_CHOICES = [(NEFT, 'NEFT'), (IMPS, 'IMPS'), (IFT, 'IFT')]
    TYPE_CHOICES = [(AUTOMATIC, 'Automatic'), (MANUAL, 'Manual')]
    PAYOUT_TYPE_CHOICES = [(PROVIDER_PAYOUT, 'Provider Payout'), (REVENUE_PAYOUT, 'Revenue Payout')]

    payment_mode = models.CharField(max_length=100, blank=True, null=True, choices=PAYMENT_MODE_CHOICES)
    payout_ref_id = models.IntegerField(null=True, unique=True)
    charged_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_approved = models.BooleanField(default=False)
    status = models.PositiveIntegerField(default=PENDING, choices=STATUS_CHOICES)
    payout_time = models.DateTimeField(null=True, blank=True)
    request_data = JSONField(blank=True, default='', editable=False)
    api_response = JSONField(blank=True, null=True)
    status_api_response = JSONField(blank=True, default='', editable=False)
    retry_count = models.PositiveIntegerField(default=0)
    paid_to = models.ForeignKey(Merchant, on_delete=models.DO_NOTHING, related_name='payouts', null=True)
    utr_no = models.CharField(max_length=500, blank=True, default='')
    pg_status = models.CharField(max_length=500, blank=True, default='')
    type = models.PositiveIntegerField(default=None, choices=TYPE_CHOICES, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey()
    booking_type = models.IntegerField(null=True, blank=True, choices=BookingTypeChoices)
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    recreated_from = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True)
    remarks = models.TextField(max_length=100, null=True, blank=True)
    payout_type = models.PositiveIntegerField(default=None, choices=PAYOUT_TYPE_CHOICES, null=True, blank=True)

    def save(self, *args, **kwargs):

        first_instance = False
        if not self.id:
            first_instance = True

        if self.payout_type == self.PROVIDER_PAYOUT or self.payout_type is None:
            if self.id and not self.is_insurance_premium_payout() and hasattr(self,'process_payout') and self.process_payout and (self.status==self.PENDING or self.status==self.ATTEMPTED) and self.type==self.AUTOMATIC:
                self.type = self.AUTOMATIC
                self.update_billed_to_content_type()
                # if not self.content_object:
                #     self.content_object = self.get_billed_to()
                # if not self.paid_to:
                #     self.paid_to = self.get_merchant()

                try:
                    has_txn, order_data, appointment = self.has_transaction()
                    if has_txn:
                        # # Moved this to process payout
                        # if self.status == self.PENDING:
                        #     self.status = self.ATTEMPTED
                        transaction.on_commit(lambda: process_payout.apply_async((self.id,), countdown=3))
                    else:
                        transaction.on_commit(lambda: set_order_dummy_transaction.apply_async((order_data.id, appointment.user_id,), countdown=5))
                except Exception as e:
                    logger.error(str(e))

            if self.type == self.MANUAL and self.utr_no and self.status == self.PENDING:
                self.status = self.PAID

            if self.utr_no and self.booking_type == self.InsurancePremium and self.paid_to != Merchant.objects.filter(id=settings.DOCPRIME_NODAL2_MERCHANT).first():
                self.create_insurance_transaction()

            if (not first_instance and self.status != self.PENDING) and not self.booking_type == self.InsurancePremium:
                from ondoc.matrix.tasks import push_appointment_to_matrix

                appointment = self.get_corrosponding_appointment()

                if appointment and appointment.__class__.__name__ == 'LabAppointment':
                    transaction.on_commit(lambda: push_appointment_to_matrix.apply_async(({'type': 'LAB_APPOINTMENT', 'appointment_id': appointment.id, 'product_id': 5,
                                                                                           'sub_product_id': 2},), countdown=15))
                elif appointment and appointment.__class__.__name__ == 'OpdAppointment':
                    transaction.on_commit(lambda: push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': appointment.id, 'product_id': 5,
                                                                                           'sub_product_id': 2},), countdown=15))
        else:
            if self.id and hasattr(self, 'process_payout') and self.process_payout and (self.status == self.PENDING or self.status == self.ATTEMPTED):
                revenue_payout = RevenuePayoutMapping.objects.filter(revenue_payout_id=self.id).first()
                provider_payout = revenue_payout.provider_payout
                try:
                    has_txn, order_data, appointment = provider_payout.has_transaction()
                    if has_txn:
                        transaction.on_commit(lambda: process_payout.apply_async((self.id,), countdown=3))
                except Exception as e:
                    logger.error(str(e))

        super().save(*args, **kwargs)

        if first_instance:
            MerchantPayout.objects.filter(id=self.id).update(payout_ref_id=self.id)

    # # @classmethod
    # def creating_pending_insurance_transactions(cls):
    #     pending = cls.objects.filter(booking_type=cls.InsurancePremium, utr_no__isnull=False)
    #     for p in pending:
    #         if p.utr_no:
    #             p.create_insurance_transaction()

    # # Get appointment object from merchant payout
    def get_corrosponding_appointment(self):
        appointment = None
        if self.booking_type == Order.DOCTOR_PRODUCT_ID:
            appointment = self.opd_appointment.all().first()
        elif self.booking_type == Order.LAB_PRODUCT_ID:
            appointment = self.lab_appointment.all().first()

        return appointment

    # Check if insurance txn needs to be create or not
    def should_create_insurance_transaction(self):
        from ondoc.insurance.models import InsuranceTransaction

        premium_amount = None
        transferred_amount = 0
        user_insurance = None
        all_payouts = None
        pms = PayoutMapping.objects.filter(payout=self).first()
        if pms:
            user_insurance = pms.content_object
        if user_insurance:
            premium_amount = user_insurance.premium_amount
            all_payouts = PayoutMapping.objects.filter(object_id=user_insurance.id, content_type_id=\
                ContentType.objects.get_for_model(user_insurance).id).\
                exclude(payout__paid_to_id=settings.DOCPRIME_NODAL2_MERCHANT).exclude(payout=self)

            all_payouts = [x.payout for x in all_payouts]
            transfers = InsuranceTransaction.objects.filter(user_insurance=user_insurance,\
             transaction_type=InsuranceTransaction.CREDIT, reason=InsuranceTransaction.PREMIUM_PAYOUT)

            if not transfers:
                return True

            if not all_payouts and transfers:
                return False

            transfers = list(transfers)

            for transfer in transfers:
                transferred_amount += transfer.amount
            total_payouts = len(all_payouts)
            counter = 0

            for payout in all_payouts:
                for transfer in transfers:
                    if not hasattr(payout,'_removed'):
                        payout._removed = False
                    if not hasattr(transfer,'_removed'):
                        transfer._removed = False

                    if not payout._removed and not transfer._removed and payout.payable_amount == transfer.amount:
                        transfer._removed = True
                        payout._removed = True

            all_payouts = [x for x in all_payouts if hasattr(x, '_removed') and not x._removed]
            transfers = [x for x in transfers if hasattr(x, '_removed') and not x._removed]
            if len(transfers)==0 and (transferred_amount+self.payable_amount)<=premium_amount:
                return True

    # Create transaction for insurance
    def create_insurance_transaction(self):
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction
        if self.should_create_insurance_transaction():
            user_insurance = self.get_user_insurance()
            # InsuranceTransaction.objects.create(user_insurance=user_insurance,
            #     # account = user_insurance.insurance_plan.insurer.float.first(),
            #     account=user_insurance.master_policy_reference.apd_account,
            #     transaction_type=InsuranceTransaction.CREDIT,
            #     amount=self.payable_amount,
            #     reason=InsuranceTransaction.PREMIUM_PAYOUT)
            InsuranceTransaction.objects.create(user_insurance=user_insurance,
                                                account=user_insurance.master_policy.insurer_account,
                                                transaction_type=InsuranceTransaction.CREDIT,
                                                amount=self.payable_amount,
                                                reason=InsuranceTransaction.PREMIUM_PAYOUT)

    # Get insurance transaction
    def get_insurance_transaction(self):
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction
        if not self.booking_type == self.InsurancePremium:
            raise Exception('Not implemented for non insurance premium payouts')
        user_insurance = self.get_user_insurance()
        existing = user_insurance.transactions.filter(reason=InsuranceTransaction.PREMIUM_PAYOUT)
        return existing

    # Get user insurance object
    def get_user_insurance(self):
        ui = self.user_insurance.all()
        if len(ui)>1:
            raise Exception('Multiple user insurance found for a single payout')
        if len(ui)==1:
            return ui.first()

        pms = PayoutMapping.objects.filter(payout=self).first()
        user_insurance = pms.content_object
        return user_insurance

    # Update payout status
    def update_status(self, status):
        if status == 'attempted':
            self.status = self.ATTEMPTED
        elif status == 'initiated':
            self.status = self.INITIATED
        self.save()

    # This method is use for showing payout info on appointment page CRM
    @staticmethod
    def get_merchant_payout_info(obj):
        """obj is either a labappointment or an opdappointment"""
        from django.utils.safestring import mark_safe
        result = ""
        if obj.merchant_payout:
            result += "Status : {}<br>".format(dict(MerchantPayout.STATUS_CHOICES)[obj.merchant_payout.status])
            if obj.merchant_payout.utr_no:
                result += "UTR No. : {}<br>".format(obj.merchant_payout.utr_no)
            if obj.merchant_payout.paid_to:
                result += "Paid To : {}<br>".format(obj.merchant_payout.paid_to)
        return mark_safe(result)

    # Get appointment from payout
    def get_appointment(self):
        if self.payout_type == self.REVENUE_PAYOUT:
            revenue_payout = RevenuePayoutMapping.objects.filter(revenue_payout_id=self.id).first()
            if revenue_payout:
                provider_payout = revenue_payout.provider_payout
            else:
                return None
        else:
            provider_payout = self

        if provider_payout.lab_appointment.all():
            return provider_payout.lab_appointment.all()[0]
        elif provider_payout.opd_appointment.all():
            return provider_payout.opd_appointment.all()[0]
        elif provider_payout.user_insurance.all():
            return provider_payout.user_insurance.all()[0]
        return None

    # Check if amount need to transfer to different nodal
    def is_nodal_transfer(self):
        merchant = Merchant.objects.filter(id=settings.DOCPRIME_NODAL2_MERCHANT).first()
        if self.paid_to == merchant:
            return True

    # Get insurance premium txn
    def get_insurance_premium_transactions(self):
        user_insurance = self.get_user_insurance()
        if self.is_nodal_transfer():
            return DummyTransactions.objects.filter(transaction_type=DummyTransactions.INSURANCE_NODAL_TRANSFER,
                                             reference_id=user_insurance.id, product_id=Order.INSURANCE_PRODUCT_ID)

        trans = DummyTransactions.objects.filter(reference_id=user_insurance.id,\
                    product_id=Order.INSURANCE_PRODUCT_ID).\
                    exclude(transaction_type=DummyTransactions.INSURANCE_NODAL_TRANSFER)

        if len(trans)>1:
            raise Exception('multiple transactions found')

        if trans and trans[0].amount == self.payable_amount:
            return trans

        non_refunded_trans = list()
        trans = PgTransaction.objects.filter(order=user_insurance.order)
        if len(trans) > 1:
            for pg_txn in trans:
                if not pg_txn.has_refunded():
                    non_refunded_trans.append(pg_txn)

        if len(non_refunded_trans) > 1:
            raise Exception('multiple transactions found')

        # TO DO - Check for TDS
        if non_refunded_trans and non_refunded_trans[0].amount == self.payable_amount:
            return non_refunded_trans

        from ondoc.insurance.models import UserInsurance
        uis = UserInsurance.objects.filter(user=user_insurance.user)
        if len(uis)==1:
            trans = PgTransaction.objects.filter(user=user_insurance.user, product_id=Order.INSURANCE_PRODUCT_ID)
            if len(trans)==1 and trans[0].amount == self.payable_amount:
                return trans

        return []

    # Check if payout related to insurance premium or not
    def is_insurance_premium_payout(self):
        if self.booking_type == Order.INSURANCE_PRODUCT_ID:
            return True

        # if self.get_user_insurance():
        #     return True
        return False

    def get_or_create_insurance_premium_transaction(self):
        from ondoc.account.mongo_models import PgLogs as PgLogsMongo
        #transaction already created no need to proceed
        transaction = None
        transaction = self.get_insurance_premium_transactions()

        if len(transaction)==1:
            return transaction.first()
        elif len(transaction)>1:
            raise Exception('multiple nodal transfers found.')
        else:
            transaction = None

        user_insurance = self.get_user_insurance()

        req_data = dict()
        try:
            #order_row = Order.objects.filter(id=order_id).first()
            user = user_insurance.user

            if not user:
                raise Exception('user is required')
            token = settings.PG_DUMMY_TRANSACTION_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_DUMMY_TRANSACTION_URL
            #insurance_data = order_row.get_insurance_data_for_pg()

            name = user_insurance.get_primary_member_profile().get_full_name()


            req_data = {
                "customerId": user.id,
                "mobile": user.phone_number,
                "email": user.email or "dummyemail@docprime.com",
                "productId": user_insurance.order.INSURANCE_PRODUCT_ID,
                "orderId": user_insurance.order.id,
                "name": name,
                "txAmount": 0,
                "couponCode": "",
                "couponAmt": str(self.payable_amount),
                "paymentMode": "DC",
                "AppointmentId": user_insurance.id,
                "buCallbackSuccessUrl": "",
                "buCallbackFailureUrl": ""
            }
            if not self.is_nodal_transfer():
                req_data["insurerCode"] = "apolloDummy"

            for key in req_data:
                req_data[key] = str(req_data[key])

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if settings.SAVE_LOGS:
                save_pg_response.apply_async((PgLogsMongo.DUMMY_TXN, user_insurance.order.id, None, response.json(), req_data, user.id,), eta=timezone.localtime(), queue=settings.RABBITMQ_LOGS_QUEUE)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                #logger.error(resp_data)
                if resp_data.get("ok") is not None and resp_data.get("ok") == 1:
                    tx_data = {}
                    tx_data['user'] = user
                    tx_data['product_id'] = user_insurance.order.INSURANCE_PRODUCT_ID
                    tx_data['order_no'] = resp_data.get('orderNo')
                    tx_data['order_id'] = user_insurance.order.id
                    tx_data['reference_id'] = user_insurance.id
                    tx_data['type'] = DummyTransactions.CREDIT
                    tx_data['amount'] = self.payable_amount
                    tx_data['payment_mode'] = "DC"
                    if self.is_nodal_transfer():
                        tx_data['transaction_type'] = DummyTransactions.INSURANCE_NODAL_TRANSFER

                    transaction = DummyTransactions.objects.create(**tx_data)
                    #print("SAVED DUMMY TRANSACTION")
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))

        except Exception as e:
            logger.error("Error in Setting Dummy Transaction of payout - " + str(self.id) + " with exception - " + str(e))
        return transaction

    # This method is use for processing insurance premium payouts
    def process_insurance_premium_payout(self):
        from ondoc.api.v1.utils import create_payout_checksum
        from collections import OrderedDict
        payout_status = None

        try:
            # if not self.is_nodal_transfer():
            #     raise Exception('Incorrect method called for payout')

            if self.status == self.PAID or self.utr_no:
                return True

            transaction = self.get_insurance_premium_transactions()
            if not transaction:
                raise Exception('No transaction found for insurance premium payout')

            if len(transaction) > 1:
                raise Exception("Insurance premium transfers cannot have multiple transactions")

            default_payment_mode = self.get_default_payment_mode()
            merchant = self.get_merchant()
            user_insurance = self.get_user_insurance()

            if not merchant or not user_insurance:
                raise Exception("Insufficient Data " + str(self))

            if not merchant.verified_by_finance or not merchant.enabled:
                raise Exception("Merchant is not verified or is not enabled. " + str(self))

            req_data = {"payload": [], "checkSum": ""}

            txn = transaction[0]

            curr_txn = OrderedDict()
            curr_txn["idx"] = 0
            curr_txn["orderNo"] = txn.order_no
            curr_txn["orderId"] = txn.order.id
            curr_txn["txnAmount"] = str(txn.amount)

            #curr_txn["txnAmount"] = str(0)

            # curr_txn["txnAmount"] = str(self.payable_amount)
            curr_txn["settledAmount"] = str(self.payable_amount)
            curr_txn["merchantCode"] = self.paid_to.id
            if txn.transaction_id:
                curr_txn["pgtxId"] = txn.transaction_id

            curr_txn["refNo"] = self.payout_ref_id
            curr_txn["bookingId"] = user_insurance.id
            curr_txn["paymentType"] = default_payment_mode
            if isinstance(txn, DummyTransactions) and txn.amount>0:
                curr_txn["txnAmount"] = str(0)

            req_data["payload"].append(curr_txn)

            self.request_data = req_data

            req_data["checkSum"] = create_payout_checksum(req_data["payload"], Order.INSURANCE_PRODUCT_ID)
            headers = {
                "auth": settings.PG_REFUND_AUTH_TOKEN,
                "Content-Type": "application/json"
            }
            url = settings.PG_SETTLEMENT_URL
            resp_data = None

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            resp_data = response.json()

            if response.status_code == status.HTTP_200_OK:
                if resp_data.get("ok") is not None and resp_data.get("ok") == '1':
                    success_payout = False
                    result = resp_data.get('result')
                    if result:
                        for res_txn in result:
                            success_payout = res_txn['status'] == "SUCCESSFULLY_INSERTED"

                    if success_payout:
                        payout_status = {"status": 1, "response": resp_data}
                    else:
                        logger.error("payout failed for request data - " + str(req_data))
                        payout_status = {"status": 0, "response": resp_data}

            if payout_status:
                self.api_response = payout_status.get("response")
                if payout_status.get("status"):
                    self.payout_time = datetime.datetime.now()
                    self.status = self.PAID
                else:
                    self.retry_count += 1

                self.save()

        except Exception as e:
            logger.error("Error in processing payout - with exception - " + str(e))

        if payout_status and payout_status.get("status"):
            return True

    # To get merchant billing information
    def get_billed_to(self):
        if self.content_object:
            return self.content_object
        appt = self.get_appointment()
        if appt and appt.get_billed_to:
            return appt.get_billed_to
        return ''

    # Get default payment mode for payout
    def get_default_payment_mode(self):
        default_payment_mode = None
        merchant = self.get_merchant()
        if merchant and merchant.ifsc_code:
            ifsc_code = merchant.ifsc_code
            if ifsc_code.upper().startswith(self.INTRABANK_IDENTIFIER):
                default_payment_mode = self.IFT
            else:
                default_payment_mode = MerchantPayout.NEFT

        return default_payment_mode

    # Get payout merchant
    def get_merchant(self):
        if self.paid_to:
            return self.paid_to
        appt = self.get_appointment()
        if appt and appt.get_merchant:
            return appt.get_merchant
        return ''

    def has_transaction(self):
        appointment = self.get_appointment()
        if not appointment:
            raise Exception("Insufficient Data " + str(self))

        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()
        if not order_data:
            raise Exception("Order not found for given payout")

        all_txn = order_data.getTransactions()

        return bool(all_txn and all_txn.count() > 0), order_data, appointment

    def get_pg_order_no(self):
        order_no = None
        appointment = self.get_appointment()
        if not appointment:
            return None
        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()
        if not order_data:
            dt = DummyTransactions.objects.filter(reference_id=appointment.id).order_by('-id').first()
            if dt:
                return dt.order_no
        else:
            all_txn = order_data.getTransactions()
            if all_txn:
                return all_txn[0].order_no

    def get_order_id(self):
        order_id = None
        appointment = self.get_appointment()
        if not appointment:
            return None
        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()
        if order_data:
            order_id = order_data.id

        return order_id

    def update_status_from_pg(self):
        from ondoc.account.mongo_models import PgLogs as PgLogsMongo
        with transaction.atomic():
            # if self.pg_status=='SETTLEMENT_COMPLETED' or self.utr_no or self.type ==self.MANUAL:
            #     return

            order_no = None
            order_id = None
            url = settings.SETTLEMENT_DETAILS_API
            if self.is_insurance_premium_payout():
                txn = self.get_insurance_premium_transactions()
                if txn:
                    order_no = txn[0].order_no
                    order_id = txn[0].order_id

            else:
                order_no = self.get_pg_order_no()
                order_id = self.get_order_id()

            if order_no:
                req_data = {"orderNo": order_no}
                req_data["hash"] = self.create_checksum(req_data)

                headers = {"auth": settings.SETTLEMENT_AUTH, "Content-Type": "application/json"}

                response = requests.post(url, data=json.dumps(req_data), headers=headers)
                if order_id:
                    if settings.SAVE_LOGS:
                        save_pg_response.apply_async((PgLogsMongo.PAYOUT_SETTLEMENT_DETAIL, order_id, None, response.json(), req_data, None), eta=timezone.localtime(), queue=settings.RABBITMQ_LOGS_QUEUE)
                if response.status_code == status.HTTP_200_OK:
                    resp_data = response.json()
                    self.status_api_response = resp_data
                    if resp_data.get('ok') == 1 and len(resp_data.get('settleDetails')) > 0:
                        details = resp_data.get('settleDetails')
                        for d in details:
                            if d.get('refNo') == str(self.payout_ref_id) or\
                                    (not self.payout_ref_id and d.get('orderNo') == order_no):
                                self.utr_no = d.get('utrNo', '')
                                self.pg_status = d.get('txStatus', '')
                                if self.utr_no:
                                    self.status = self.PAID
                                if d.get('txStatus', '') == "SETTLEMENT_FAILURE":
                                    self.status = self.FAILED_FROM_DETAIL
                                break
                    self.save()

    def create_checksum(self, data):

        accesskey = settings.PG_CLIENT_KEY_P1
        secretkey = settings.PG_SECRET_KEY_P1
        checksum = ''

        keylist = sorted(data)
        for k in keylist:
            if data[k] is not None:
                curr = k + '=' + str(data[k]) + ';'
                checksum += curr

        checksum = accesskey + "|" + checksum + "|" + secretkey
        checksum_hash = hashlib.sha256(str(checksum).encode())
        checksum_hash = checksum_hash.hexdigest()
        return checksum_hash

    # This method is use to re create
    def recreate_failed_payouts(self):
        # # recreate payout only when status is failed
        if self.status == self.FAILED_FROM_DETAIL or self.status == self.FAILED_FROM_QUEUE or self.merchant_has_advance_payment():
            new_obj = MerchantPayout(recreated_from=self)
            new_obj.payable_amount = self.payable_amount
            new_obj.charged_amount = self.charged_amount
            new_obj.booking_type = self.booking_type
            new_obj.tds_amount = self.tds_amount
            new_obj.payout_type = self.payout_type
            if self.payout_type == self.REVENUE_PAYOUT:
                new_obj.paid_to_id = self.paid_to_id

            if self.booking_type == self.InsurancePremium:
                new_obj.content_type_id = self.content_type_id
                new_obj.object_id = self.object_id
                new_obj.type = MerchantPayout.AUTOMATIC
                new_obj.paid_to = self.paid_to

            # update appointment payout id
            appointment = self.get_appointment()
            if appointment:
                new_obj.save()
                MerchantPayout.objects.filter(id=self.id).update(status=self.ARCHIVE)
                if self.payout_type == self.PROVIDER_PAYOUT or self.payout_type is None:
                    appointment.update_payout_id(new_obj.id)
                if self.payout_type == self.REVENUE_PAYOUT:
                    RevenuePayoutMapping.update_mapping(self.id, new_obj.id)
                print('New payout created for ' + str(self.id))

    # Update merchant and billing amount when changed
    def update_billed_to_content_type(self):
        merchant = self.get_merchant()
        if merchant:
            current_associated_merchant = AssociatedMerchant.objects.filter(merchant_id=merchant.id, object_id=self.object_id, content_type_id=self.content_type_id).first()
            if current_associated_merchant and current_associated_merchant.verified:
                pass
            else:
                appt = self.get_appointment()
                if appt and appt.get_billed_to:
                    billed_to = appt.get_billed_to
                    self.content_object = billed_to

                content_type = ContentType.objects.get_for_model(billed_to)
                am = AssociatedMerchant.objects.filter(content_type_id=content_type, object_id=billed_to.id).first()
                if am and not am.merchant_id == self.paid_to_id:
                    if appt and appt.get_merchant:
                        self.paid_to = appt.get_merchant

    @transaction.atomic
    def get_advance_amount_obj(self):
        adv_amt_obj = AdvanceMerchantAmount.objects.select_for_update().filter(merchant_id=self.paid_to_id).first()
        return adv_amt_obj

    # Check if merchant has advance payment.
    def merchant_has_advance_payment(self):
        adv_amt_obj = self.get_advance_amount_obj()
        if adv_amt_obj and adv_amt_obj.amount > 0:
            return True

        return False

    # Get advance payout amount
    def get_advance_balance(self):
        adv_amt_obj = self.get_advance_amount_obj()
        if adv_amt_obj:
            return adv_amt_obj.amount

        return None

    # Update payout if merchant has advance payment and marked it paid
    @transaction.atomic
    def update_payout_for_advance_available(self):
        adv_amt_obj = self.get_advance_amount_obj()
        balance = self.get_advance_balance()
        if balance > 0:
            if balance >= self.payable_amount:
                self.status = self.PAID
                self.remarks = "Marked as Paid from advance payout"
                adv_amt_obj.amount = balance - self.payable_amount
            elif balance < self.payable_amount:
                remaining_amt = self.payable_amount - balance
                self.remarks = "Total payable {}, Paid {} from advance payout".format(self.payable_amount, balance)
                self.payable_amount = remaining_amt
                adv_amt_obj.amount = 0.0
            adv_amt_obj.save()
            self.payout_ref_id = self.id
            self.save()

    # Get nodal account for payout
    @property
    def get_nodal_id(self):
        from ondoc.doctor.models import OpdAppointment
        if self.booking_type == self.InsurancePremium:
            return 2
        else:
            appointment = self.get_appointment()
            if appointment.payment_type == OpdAppointment.INSURANCE:
                return 2
            elif appointment.payment_type == OpdAppointment.PREPAID:
                return 1
            else:
                return 1

    # Check payout is paid or not
    def paid_to_provider(self):
        if self.status == self.PAID and self.pg_status == 'SETTLEMENT_COMPLETED' and self.utr_no:
            return True

        return False

    # Transfer revenue from nodal to current a/c.
    @classmethod
    def create_appointment_revenue_payout(cls):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from django.db.models import Q

        # Manage Revenue Transfer - Add a flag in appointments
        opd_appointments = OpdAppointment.objects.filter((Q(payment_type=OpdAppointment.PREPAID) | Q(payment_type=OpdAppointment.GOLD)) & Q(status=OpdAppointment.COMPLETED) & Q(revenue_transferred=None))
        lab_appointments = LabAppointment.objects.filter((Q(payment_type=OpdAppointment.PREPAID) | Q(payment_type=OpdAppointment.GOLD)) & Q(status=OpdAppointment.COMPLETED) & Q(revenue_transferred=None))

        for opd_appointment in opd_appointments:
            appointment_payout = opd_appointment.merchant_payout
            if appointment_payout:
                if appointment_payout.paid_to_provider():
                    appointment_payout.transfer_revenue_to_current_account(opd_appointment)

        for lab_appointment in lab_appointments:
            appointment_payout = lab_appointment.merchant_payout
            if appointment_payout:
                if appointment_payout.paid_to_provider():
                    appointment_payout.transfer_revenue_to_current_account(lab_appointment)

    def transfer_revenue_to_current_account(self, appointment):
        try:
            revenue = appointment.get_revenue()
            if revenue > 0:
                # Adding new revenue payout
                self.generate_revenue_payout(appointment, revenue)
            else:
                appointment.update_appointment_revenue_transferred()
        except Exception as e:
            print(e)
            pass

    def generate_revenue_payout(self, appointment, revenue):
        payout = MerchantPayout(paid_to_id=settings.DOCPRIME_CURRENT_AC_MERCHANT, charged_amount=0.0, payable_amount=revenue,
                                booking_type=self.booking_type, payout_type=self.REVENUE_PAYOUT)
        payout.save()
        # Add revenue mapping
        rpm = RevenuePayoutMapping(provider_payout=self, content_object=appointment, revenue_payout=payout)
        rpm.save()

        appointment.update_appointment_revenue_transferred()

    class Meta:
        db_table = "merchant_payout"


class RevenuePayoutMapping(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey()
    provider_payout = models.ForeignKey(MerchantPayout, on_delete=models.SET_NULL, null=True, related_name='provider_payout')
    revenue_payout = models.ForeignKey(MerchantPayout, on_delete=models.SET_NULL, null=True, related_name='revenue_payout')

    @classmethod
    def update_mapping(cls, payout_id, revenue_payout_id):
        RevenuePayoutMapping.objects.filter(revenue_payout_id=payout_id).update(revenue_payout_id=revenue_payout_id)

    class Meta:
        db_table = "revenue_payout_mapping"


class PayoutMapping(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey()
    payout = models.ForeignKey(MerchantPayout, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "payout_mapping"


class UserReferrals(TimeStampedModel):
    SIGNUP_CASHBACK = settings.REFERRAL_CASHBACK_AMOUNT
    COMPLETION_CASHBACK = settings.REFERRAL_CASHBACK_AMOUNT

    code = models.CharField(max_length=10, unique=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, unique=True, related_name='referral')

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generateCode()
        super().save(*args, **kwargs)

    def generateCode(self):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "user_referrals"


class UserReferred(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, unique=True)
    referral_code = models.ForeignKey(UserReferrals, on_delete=models.DO_NOTHING)
    used = models.BooleanField(default=False)

    @classmethod
    @transaction.atomic
    def credit_after_completion(cls, user, appointment_obj, product_id):
        referred_obj = cls.objects.filter(user=user, used=False).first()
        if referred_obj:
            referral_obj = referred_obj.referral_code
            ConsumerAccount.credit_referral(referral_obj.user, UserReferrals.COMPLETION_CASHBACK, appointment_obj, product_id)
            referred_obj.used = True
            referred_obj.save()

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "user_referred"


class PgLogs(TimeStampedModel):
    decoded_response = JSONField(blank=True, null=True)
    coded_response = models.TextField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "pg_log"


class MerchantPayoutLog(TimeStampedModel):
    merchant_payout = models.ForeignKey(MerchantPayout, on_delete=models.DO_NOTHING, null=True)
    error = models.TextField(null=True, blank=True)
    is_fixed = models.BooleanField(default=False)
    req_data = JSONField(blank=True, null=True)
    res_data = JSONField(blank=True, null=True)
    endpoint = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "merchant_payout_log"

    @classmethod
    def create_log(cls, payout, error, **kwargs):
        payout_log = MerchantPayoutLog(merchant_payout=payout)
        payout_log.error = error
        payout_log.save()


class MerchantPayoutBulkProcess(TimeStampedModel):
    payout_ids = models.TextField(null=False, blank=False, help_text="Enter comma separated payout ids here.")

    class Meta:
        db_table = "merchant_payout_bulk_process"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit_tasks())

    def after_commit_tasks(self):
        # payout_ids_list = list()
        payout_ids = self.payout_ids
        if payout_ids:
            payout_ids_list = self.payout_ids.split(',')
        try:
            merchant_payouts = MerchantPayout.objects.filter(id__in=payout_ids_list)
            for mp in merchant_payouts:
                if mp.id and not mp.is_insurance_premium_payout() and mp.status == mp.PENDING:
                    mp.type = mp.AUTOMATIC
                    mp.process_payout = True
                    mp.save()
        except Exception as e:
            logger.error("Error in processing bulk payout - with exception - " + str(e))


class PgStatusCode(TimeStampedModel):
    code = models.PositiveSmallIntegerField(default=1)
    message = models.TextField(blank=False, null=False)

    class Meta:
        db_table = "pg_status_code"


class PaymentProcessStatus(TimeStampedModel):
    INITIATE = 1
    AUTHORIZE = 2
    SUCCESS = 3
    FAILURE = 4
    CAPTURE = 5
    RELEASE = 6

    STATUS_CHOICES = [(INITIATE, "Initiate"), (AUTHORIZE, "Authorize"),
                      (SUCCESS, "Success"), (FAILURE, "Failure"),
                      (CAPTURE, "Capture"), (RELEASE, "Release")]

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, null=True)
    current_status = models.PositiveSmallIntegerField(default=1, editable=False, choices=STATUS_CHOICES)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.CharField(blank=True, max_length=50, null=True)

    class Meta:
        db_table = "payment_process_status"

    @classmethod
    def save_single_payment_status(cls, current_status, args):
        user_id = args.get('user_id')
        order_ids = args.get('order_ids')
        status_code = args.get('status_code')
        source = args.get('source')

        for order_id in order_ids:
            if not order_id:
                continue

            payment_process_status = PaymentProcessStatus.objects.filter(order_id=order_id).first()
            if not payment_process_status:
                payment_process_status = PaymentProcessStatus(order_id=order_id)

            if user_id:
                payment_process_status.user_id = user_id
            payment_process_status.status_code = status_code
            payment_process_status.source = source
            payment_process_status.current_status = current_status

            payment_process_status.save()

    @classmethod
    def save_payment_status(cls, current_status, args):
        user_id = args.get('user_id')
        order_id = args.get('order_id')
        status_code = args.get('status_code')
        source = args.get('source')

        if order_id:
            payment_process_status = PaymentProcessStatus.objects.filter(order_id=order_id).first()
            if not payment_process_status:
                payment_process_status = PaymentProcessStatus(order_id=order_id)

            if user_id:
                payment_process_status.user_id = user_id
            payment_process_status.status_code = status_code
            payment_process_status.source = source
            payment_process_status.current_status = current_status

            payment_process_status.save()

    @classmethod
    def get_status_type(cls, status_code, txStatus):
        try:
            status_code = int(status_code)
        except KeyError:
            logger.error("ValueError : statusCode is not type integer")
            status_code = None

        if status_code and status_code == 1:
            if txStatus == 'TXN_AUTHORIZE' or txStatus == '27':
                return PaymentProcessStatus.AUTHORIZE
            else:
                return PaymentProcessStatus.SUCCESS

        if status_code and status_code == 20 and txStatus == 'TXN_SUCCESS':
            return PaymentProcessStatus.CAPTURE

        if status_code and status_code == 22 and txStatus == 'TXN_RELEASE':
            return PaymentProcessStatus.RELEASE

        return PaymentProcessStatus.FAILURE


class AdvanceMerchantAmount(TimeStampedModel):
    merchant = models.ForeignKey(Merchant, on_delete=models.DO_NOTHING, null=False, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)

    class Meta:
        db_table = "advance_merchant_amount"


class AdvanceMerchantPayout(TimeStampedModel):
    PENDING = 1
    ATTEMPTED = 2
    PAID = 3
    INITIATED = 4
    INPROCESS = 5
    FAILED_FROM_QUEUE = 6
    FAILED_FROM_DETAIL = 7
    AUTOMATIC = 1
    MANUAL = 2

    DoctorPayout = Order.DOCTOR_PRODUCT_ID
    LabPayout = Order.LAB_PRODUCT_ID
    InsurancePremium = Order.INSURANCE_PRODUCT_ID
    BookingTypeChoices = [(DoctorPayout, 'Doctor Booking'), (LabPayout, 'Lab Booking'),
                          (InsurancePremium, 'Insurance Purchase')]

    NEFT = "NEFT"
    IMPS = "IMPS"
    IFT = "IFT"
    INTRABANK_IDENTIFIER = "KKBK"
    STATUS_CHOICES = [(PENDING, 'Pending'), (ATTEMPTED, 'ATTEMPTED'), (PAID, 'Paid'), (INITIATED, 'Initiated'),
                      (INPROCESS, 'In Process'), (FAILED_FROM_QUEUE, 'Failed from Queue'),
                      (FAILED_FROM_DETAIL, 'Failed from Detail')]
    PAYMENT_MODE_CHOICES = [(NEFT, 'NEFT'), (IMPS, 'IMPS'), (IFT, 'IFT')]
    TYPE_CHOICES = [(AUTOMATIC, 'Automatic'), (MANUAL, 'Manual')]

    payment_mode = models.CharField(max_length=100, blank=True, null=True, choices=PAYMENT_MODE_CHOICES)
    payout_ref_id = models.IntegerField(null=True, unique=True)
    charged_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_approved = models.BooleanField(default=False)
    status = models.PositiveIntegerField(default=PENDING, choices=STATUS_CHOICES)
    payout_time = models.DateTimeField(null=True, blank=True)
    request_data = JSONField(blank=True, default='', editable=False)
    api_response = JSONField(blank=True, null=True)
    status_api_response = JSONField(blank=True, default='', editable=False)
    retry_count = models.PositiveIntegerField(default=0)
    paid_to = models.ForeignKey(Merchant, on_delete=models.DO_NOTHING, null=True)
    utr_no = models.CharField(max_length=500, blank=True, default='')
    pg_status = models.CharField(max_length=500, blank=True, default='')
    type = models.PositiveIntegerField(default=None, choices=TYPE_CHOICES, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey()
    booking_type = models.IntegerField(null=True, blank=True, choices=BookingTypeChoices)
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    recreated_from = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True)

    class Meta:
        db_table = "advance_merchant_payout"

    @classmethod
    def copy_nodel2_merchant_payouts(cls, payout_ids):
        mps = MerchantPayout.objects.filter(id__in=payout_ids)
        for mp in mps:
            with transaction.atomic():
                advance_payout_obj = AdvanceMerchantPayout(id=mp.id)
                advance_payout_obj.__dict__ = mp.__dict__.copy()
                advance_payout_obj.save()
                # Save total amount
                adv_amt_obj = AdvanceMerchantAmount.objects.filter(merchant_id=mp.paid_to_id).first()
                if adv_amt_obj and adv_amt_obj.amount:
                    adv_amt_obj.amount = decimal.Decimal(adv_amt_obj.amount) + mp.payable_amount
                    adv_amt_obj.total_amount = decimal.Decimal(adv_amt_obj.total_amount) + mp.payable_amount
                else:
                    adv_amt_obj = AdvanceMerchantAmount(merchant_id=mp.paid_to_id)
                    adv_amt_obj.amount = mp.payable_amount
                    adv_amt_obj.total_amount = mp.payable_amount
                adv_amt_obj.save()
                print("payout id " + str(mp.id) + " saved")




