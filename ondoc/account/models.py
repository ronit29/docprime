from django.db import models
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from django.utils.functional import cached_property

from ondoc.authentication.models import TimeStampedModel, User, UserProfile, Merchant
from ondoc.account.tasks import refund_curl_task
from ondoc.notification.models import AppNotification, NotificationAction
from ondoc.notification.tasks import process_payout
# from ondoc.diagnostic.models import LabAppointment
# from ondoc.matrix.tasks import push_order_to_matrix
from django.db import transaction
from django.db.models import Sum, Q, F, Max
from datetime import datetime, timedelta
from django.utils import timezone
from ondoc.api.v1.utils import refund_curl_request, form_pg_refund_data, opdappointment_transform, \
    labappointment_transform, payment_details, insurance_reverse_transform
from django.conf import settings
from rest_framework import status
from copy import deepcopy
import hashlib
import copy
import json
import logging
import requests
import datetime
from decimal import Decimal
from ondoc.notification.tasks import set_order_dummy_transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import string
import random

logger = logging.getLogger(__name__)


class Order(TimeStampedModel):
    OPD_APPOINTMENT_RESCHEDULE = 1
    OPD_APPOINTMENT_CREATE = 2
    LAB_APPOINTMENT_RESCHEDULE = 3
    LAB_APPOINTMENT_CREATE = 4
    INSURANCE_CREATE = 5
    SUBSCRIPTION_PLAN_BUY = 6
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
                      (INSURANCE_CREATE, "Insurance Create"),(SUBSCRIPTION_PLAN_BUY, "Subscription Plan Buy"))
    DOCTOR_PRODUCT_ID = 1
    LAB_PRODUCT_ID = 2
    INSURANCE_PRODUCT_ID = 3
    SUBSCRIPTION_PLAN_PRODUCT_ID = 4
    PRODUCT_IDS = [(DOCTOR_PRODUCT_ID, "Doctor Appointment"), (LAB_PRODUCT_ID, "LAB_PRODUCT_ID"),
                   (INSURANCE_PRODUCT_ID, "INSURANCE_PRODUCT_ID"),(SUBSCRIPTION_PLAN_PRODUCT_ID, "SUBSCRIPTION_PLAN_PRODUCT_ID")]

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
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True)
    visitor_info = JSONField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.id)

    def get_insurance_data_for_pg(self):
        from ondoc.insurance.models import UserInsurance

        data = {}
        user_insurance = None
        if self.product_id == Order.INSURANCE_PRODUCT_ID:
            user_insurance = UserInsurance.objects.filter(order=self).first()
            if user_insurance:
                data['merchCode'] = str(user_insurance.insurance_plan.insurer.insurer_merchant_code)
        elif (self.product_id in (self.DOCTOR_PRODUCT_ID,self.LAB_PRODUCT_ID)):
            if not self.is_parent() and self.booked_using_insurance():
            # if self.is_parent():
            #     raise Exception('cannot get insurance for parent order')
                appt = self.getAppointment()
                if appt and appt.insurance:
                    user_insurance = appt.insurance
                    transactions = user_insurance.order.getTransactions()
                    if not transactions:
                        raise Exception('No transactions found for appointment insurance.')
                    insurance_order_transaction = transactions[0]
                    data['refOrderId'] = str(insurance_order_transaction.order_id)
                    data['refOrderNo'] = str(insurance_order_transaction.order_no)
                    data['merchCode'] = str(user_insurance.insurance_plan.insurer.insurer_merchant_code)

        return data

    def dummy_transaction_allowed(self):
        if (not self.is_parent() and not self.booked_using_insurance()) or self.getTransactions():
            return False

        return True

    def booked_using_insurance(self):
        if self.is_parent():
            raise Exception('Not implemented for parent orders')
        appt = self.getAppointment()
        if appt and appt.insurance_id:
            return True
        return False

    def is_parent(self):
        return self.parent_id is None

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

    @cached_property
    def is_cod_order(self):
        if self.orders.exists():
            orders_to_process = self.orders.all()
        else:
            orders_to_process = [self]
        return len(orders_to_process) == 1 and all([child_order.get_cod_to_prepaid_appointment() for child_order in orders_to_process])

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
            # self.action_data['appointment_id'] = self.reference_id
            self.action_data['payment_type'] = OpdAppointment.PREPAID
            self.action_data['effective_price'] = self.action_data['deal_price']  # TODO : SHASHANK_SINGH set to correct price
            opd_obj.effective_price = Decimal(self.action_data['deal_price'])
            opd_obj.is_cod_to_prepaid = True
            opd_obj.save()
        return opd_obj

    @transaction.atomic
    def process_order(self, convert_cod_to_prepaid=False):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.api.v1.doctor.serializers import OpdAppTransactionModelSerializer
        from ondoc.api.v1.diagnostic.serializers import LabAppTransactionModelSerializer
        from ondoc.api.v1.insurance.serializers import UserInsuranceSerializer
        from ondoc.api.v1.diagnostic.serializers import PlanTransactionModelSerializer
        from ondoc.subscription_plan.models import UserPlanMapping
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction

        # skip if order already processed, except if appointment is COD and can be converted to prepaid
        cod_to_prepaid_app = None
        if self.reference_id:
            if convert_cod_to_prepaid:
                cod_to_prepaid_app = self.get_cod_to_prepaid_appointment(True)
            if not cod_to_prepaid_app:
                raise Exception("Order already processed - " + str(self.id))

        # Initial validations for appointment data
        appointment_data = self.action_data
        user_insurance_data = None
        # Check if payment is required at all, only when payment is required we debit consumer's account
        payment_not_required = False
        if self.product_id == self.DOCTOR_PRODUCT_ID:
            serializer = OpdAppTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
            if appointment_data['payment_type'] == OpdAppointment.COD:
                if self.reference_id and cod_to_prepaid_app:
                    payment_not_required = False
                else:
                    payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.INSURANCE:
                payment_not_required = True
        elif self.product_id == self.LAB_PRODUCT_ID:
            serializer = LabAppTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
            if appointment_data['payment_type'] == OpdAppointment.COD:
                payment_not_required = True
            elif appointment_data['payment_type'] == OpdAppointment.INSURANCE:
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

        consumer_account = ConsumerAccount.objects.get_or_create(user=appointment_data['user'])
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=appointment_data['user'])

        appointment_obj = None
        order_dict = dict()
        amount = None
        total_balance = consumer_account.get_total_balance()

        if self.action == Order.OPD_APPOINTMENT_CREATE:
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
                if self.reference_id:
                    appointment_obj = cod_to_prepaid_app
                else:
                    appointment_obj = OpdAppointment.create_appointment(appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price
        elif self.action == Order.LAB_APPOINTMENT_CREATE:
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
                appointment_obj = LabAppointment.create_appointment(appointment_data)
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

        return appointment_obj, wallet_amount, cashback_amount

    @transaction.atomic
    def process_insurance_order(self, consumer_account,user_insurance_data):

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
        return None

    def get_total_price(self):
        if not self.is_parent() and self.booked_using_insurance():
            return 0

        if self.parent:
            raise Exception("Cannot calculate price on a child order")

        return ( self.amount or 0 ) + ( self.wallet_amount or 0 )

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
        return all_txn

    @classmethod
    def get_total_payable_amount(cls, fulfillment_data):
        from ondoc.doctor.models import OpdAppointment
        payable_amount = 0
        for app in fulfillment_data:
            if app.get("payment_type") == OpdAppointment.PREPAID:
                payable_amount += app.get('effective_price')
        return payable_amount

    @classmethod
    def transfrom_cart_items(cls, request, cart_items):
        fulfillment_data = []
        for item in cart_items:
            validated_data = item.validate(request)
            fd = item.get_fulfillment_data(validated_data)
            fd["cart_item_id"] = item.id
            fulfillment_data.append(fd)
        return fulfillment_data

    @classmethod
    @transaction.atomic()
    def create_order(cls, request, cart_items, use_wallet=True):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.matrix.tasks import push_order_to_matrix

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
            from ondoc.api.v1.tracking.views import EventCreateViewSet
            with transaction.atomic():
                event_api = EventCreateViewSet()
                visitor_id, visit_id = event_api.get_visit(request)
                visitor_info = { "visitor_id": visitor_id, "visit_id": visit_id, "from_app": request.data.get("from_app", None), "app_version": request.data.get("app_version", None)}
        except Exception as e:
            logger.log("Could not fecth visitor info - " + str(e))

        # create a Parent order to accumulate sub-orders
        process_immediately = False
        if total_balance >= payable_amount:
            cashback_amount = min(cashback_balance, payable_amount)
            wallet_amount = max(0, payable_amount - cashback_amount)
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
                ({'order_id': pg_order.id},), countdown=5)
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

            if appointment_detail.get('payment_type') == OpdAppointment.PREPAID:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=pg_order,
                    cart_id=appointment_detail["cart_item_id"],
                    user=user
                )
            elif appointment_detail.get('payment_type') == OpdAppointment.INSURANCE:
                order = cls.objects.create(
                    product_id=product_id,
                    action=action,
                    action_data=appointment_detail,
                    payment_status=cls.PAYMENT_PENDING,
                    parent=pg_order,
                    cart_id=appointment_detail["cart_item_id"],
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

    @transaction.atomic()
    def process_pg_order(self, convert_cod_to_prepaid=False):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.insurance.models import UserInsurance
        from ondoc.subscription_plan.models import UserPlanMapping
        from ondoc.insurance.models import InsuranceDoctorSpecializations
        orders_to_process = []
        if self.orders.exists():
            orders_to_process = self.orders.all()
        else:
            orders_to_process = [self]

        total_cashback_used = total_wallet_used = 0
        opd_appointment_ids = []
        lab_appointment_ids = []
        insurance_ids = []
        user_plan_ids = []
        user = self.user
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
                app_data = order.action_data
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

                total_cashback_used += curr_cashback
                total_wallet_used += curr_wallet

                # trigger event for new appointment creation
                if self.visitor_info:
                    curr_app.trigger_created_event(self.visitor_info)

                # mark cart item delete after order process
                if order.cart:
                    order.cart.mark_delete()
            except Exception as e:
                logger.error(str(e))

        if not opd_appointment_ids and not lab_appointment_ids and not insurance_ids and not user_plan_ids:
            raise Exception("Could not process entire order")

        # mark order processed:
        self.change_payment_status(Order.PAYMENT_ACCEPTED)

        # if order is done without PG transaction, then make an async task to create a dummy transaction and set it.
        if not self.getTransactions():
            try:
                transaction.on_commit(
                    lambda: set_order_dummy_transaction.apply_async((self.id, self.get_user_id(),),
                                                                    countdown=5))
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

        resp = { "opd" : opd_appointment_ids , "lab" : lab_appointment_ids, "plan": user_plan_ids,
                 "insurance": insurance_ids, "type" : "all", "id" : None }
        # Handle backward compatibility, in case of single booking, return the booking id

        if (len(opd_appointment_ids) + len(lab_appointment_ids) + len(user_plan_ids) + len(insurance_ids)) == 1:
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


class PgTransaction(TimeStampedModel):
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

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
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
    transaction_id = models.CharField(max_length=100, unique=True)
    pb_gateway_name = models.CharField(max_length=100, null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
            Save PG transaction and credit consumer account, with amount paid at PaymentGateway.
        """
        super(PgTransaction, self).save(*args, **kwargs)
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
    def is_valid_hash(cls, data, product_id):
        client_key = secret_key = ""
        if product_id == Order.DOCTOR_PRODUCT_ID or product_id == Order.SUBSCRIPTION_PLAN_PRODUCT_ID:
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

    class Meta:
        db_table = "pg_transaction"

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

    class Meta:
        db_table = "pg_transaction"


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

        if cashback_refund_amount:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_refund_amount, action, tx_type, ConsumerTransaction.CASHBACK_SOURCE)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        if wallet_refund_amount:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, wallet_refund_amount, action, tx_type, ConsumerTransaction.WALLET_SOURCE)
            ConsumerTransaction.objects.create(**consumer_tx_data)
            
        self.save()

    def debit_refund(self):
        amount = self.balance
        self.balance = 0
        action = ConsumerTransaction.REFUND
        tx_type = PgTransaction.DEBIT
        consumer_tx_data = self.consumer_tx_pg_data({"user": self.user}, amount, action, tx_type)
        # consumer_tx_data = self.form_consumer_tx_data({"user": self.user}, amount, action, tx_type)
        ctx_obj = ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()
        return ctx_obj

    def debit_schedule(self, appointment_obj, product_id, amount):
        if product_id == Order.SUBSCRIPTION_PLAN_PRODUCT_ID or product_id == Order.INSURANCE_PRODUCT_ID:
            cashback_deducted = 0
        else:
            cashback_deducted = min(self.cashback, amount)
            self.cashback -= cashback_deducted

        balance_deducted = min(self.balance, amount-cashback_deducted)
        self.balance -= balance_deducted

        action = ConsumerTransaction.SALE
        tx_type = PgTransaction.DEBIT

        if cashback_deducted:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_deducted, action, tx_type, ConsumerTransaction.CASHBACK_SOURCE)
            ConsumerTransaction.objects.create(**consumer_tx_data)

        if balance_deducted:
            consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, balance_deducted, action, tx_type, ConsumerTransaction.WALLET_SOURCE)
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

    @classmethod
    def credit_cashback(cls, user, cashback_amount, appointment_obj, product_id):
        # check if cashback already credited
        if ConsumerTransaction.objects.filter(product_id=product_id, type=ConsumerTransaction.CASHBACK_CREDIT, reference_id=appointment_obj.id).exists():
            return

        consumer_account = cls.objects.select_for_update().get(user=user)
        consumer_account.cashback += cashback_amount
        action = ConsumerTransaction.CASHBACK_CREDIT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = consumer_account.consumer_tx_appointment_data(appointment_obj.user, appointment_obj, product_id, cashback_amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        consumer_account.save()

    @classmethod
    def credit_referral(cls, user, cashback_amount, appointment_obj=None, product_id=None):
        consumer_account = cls.objects.get_or_create(user=user)
        consumer_account = cls.objects.select_for_update().get(user=user)

        consumer_account.cashback += cashback_amount
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
        return consumer_tx_data

    def consumer_tx_appointment_data(self, user, app_obj, product_id, amount, action, tx_type, source=None):
        if source is None:
            source = ConsumerTransaction.WALLET_SOURCE

        consumer_tx_data = dict()
        consumer_tx_data['user'] = user
        if product_id is not None:
            consumer_tx_data['product_id'] = product_id
        if app_obj:
            consumer_tx_data['reference_id'] = app_obj.id
        consumer_tx_data['type'] = tx_type
        consumer_tx_data['action'] = action
        consumer_tx_data['amount'] = amount
        consumer_tx_data['source'] = source
        return consumer_tx_data

    class Meta:
        db_table = "consumer_account"


class ConsumerTransaction(TimeStampedModel):
    CANCELLATION = 0
    PAYMENT = 1
    REFUND = 2
    SALE = 3
    RESCHEDULE_PAYMENT = 4
    CASHBACK_CREDIT = 5
    REFERRAL_CREDIT = 6

    WALLET_SOURCE = 1
    CASHBACK_SOURCE = 2

    SOURCE_TYPE = [(WALLET_SOURCE, "Wallet"), (CASHBACK_SOURCE, "Cashback")]
    action_list = ["Cancellation", "Payment", "Refund", "Sale", "CashbackCredit", "ReferralCredit"]
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



    @classmethod
    def valid_appointment_for_cancellation(cls, app_id, product_id):
        return not cls.objects.filter(type=PgTransaction.CREDIT, reference_id=app_id, product_id=product_id,
                                      action=cls.CANCELLATION).exists()

    class Meta:
        db_table = 'consumer_transaction'


class ConsumerRefund(TimeStampedModel):
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'

    PENDING = 1
    REQUESTED = 5
    COMPLETED = 10
    MAXREFUNDDAYS = 60
    state_type = [(PENDING, "Pending"), (COMPLETED, "Completed"), (REQUESTED, "Requested")]
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    consumer_transaction = models.ForeignKey(ConsumerTransaction, on_delete=models.DO_NOTHING)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pg_transaction = models.ForeignKey(PgTransaction, related_name='pg_refund', blank=True, null=True, on_delete=models.DO_NOTHING)
    refund_state = models.PositiveSmallIntegerField(choices=state_type, default=PENDING)
    refund_initiated_at = models.DateTimeField(blank=True, null=True)

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
                    logger.error("Error in Refund of user with data - " + json.dumps(req_data) + " with exception - " + str(e))

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
    def refund_status_request(cls, ref_id):
        if settings.AUTO_REFUND:
            url = settings.PG_REFUND_STATUS_API_URL
            token = settings.PG_REFUND_AUTH_TOKEN
            headers = {
                "auth": token
            }
            response = requests.get(url=url, params={"refId": ref_id}, headers=headers)
            #print(response.url)
            #print(response.status_code)
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
                        code != PgTransaction.REFUND_UPDATE_FAILURE_STATUS:
                    with transaction.atomic():
                        obj = cls.objects.select_for_update().get(id=ref_id)
                        if obj.refund_state != cls.COMPLETED:
                            obj.refund_state = cls.COMPLETED
                            obj.save()
                            print("status updated for - " + str(obj.id))
                else:
                    pass
                    #logger.error("Invalid ok status or code mismatch - " + str(response.content))

    @classmethod
    def update_refund_status(cls):
        refund_ids = cls.objects.filter(refund_state=cls.REQUESTED).values_list('id', flat=True)
        for ref_id in refund_ids:
            cls.refund_status_request(ref_id)


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
    AUTOMATIC = 1
    MANUAL = 2


    DoctorPayout = Order.DOCTOR_PRODUCT_ID
    LabPayout = Order.LAB_PRODUCT_ID
    InsurancePremium = Order.INSURANCE_PRODUCT_ID
    BookingTypeChoices = [(DoctorPayout,'Doctor Booking'),(LabPayout,'Lab Booking'),(InsurancePremium,'Insurance Purchase')]


    NEFT = "NEFT"
    IMPS = "IMPS"
    IFT = "IFT"
    INTRABANK_IDENTIFIER = "KKBK"
    STATUS_CHOICES = [(PENDING, 'Pending'), (ATTEMPTED, 'ATTEMPTED'), (PAID, 'Paid')]
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
    paid_to = models.ForeignKey(Merchant, on_delete=models.DO_NOTHING, related_name='payouts', null=True)
    utr_no = models.CharField(max_length=500, blank=True, default='')
    pg_status = models.CharField(max_length=500, blank=True, default='')
    type = models.PositiveIntegerField(default=None, choices=TYPE_CHOICES, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey()
    booking_type = models.IntegerField(null=True, blank=True, choices=BookingTypeChoices)

    def save(self, *args, **kwargs):

        first_instance = False
        if not self.id:
            first_instance = True

        if self.id and not self.is_insurance_premium_payout() and hasattr(self,'process_payout') and self.process_payout and self.status==self.PENDING and self.type==self.AUTOMATIC:
            self.type = self.AUTOMATIC
            if not self.content_object:
                self.content_object = self.get_billed_to()
            if not self.paid_to:
                self.paid_to = self.get_merchant()

            try:
                has_txn, order_data, appointment = self.has_transaction()
                if has_txn:
                    if self.status == self.PENDING:
                        self.status = self.ATTEMPTED
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

            appointment = self.lab_appointment.all().first()
            if not appointment:
                appointment = self.opd_appointment.all().first()

            if appointment and appointment.__class__.__name__ == 'LabAppointment':
                transaction.on_commit(lambda: push_appointment_to_matrix.apply_async(({'type': 'LAB_APPOINTMENT', 'appointment_id': appointment.id, 'product_id': 5,
                                                                                       'sub_product_id': 2},), countdown=15))
            elif appointment and appointment.__class__.__name__ == 'OpdAppointment':
                transaction.on_commit(lambda: push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': appointment.id, 'product_id': 5,
                                                                                       'sub_product_id': 2},), countdown=15))

        super().save(*args, **kwargs)

        if first_instance:
            MerchantPayout.objects.filter(id=self.id).update(payout_ref_id=self.id)
            # self.payout_ref_id = self.id
            # self.save()

    # @classmethod
    # def creating_pending_insurance_transactions(cls):
    #     pending = cls.objects.filter(booking_type=cls.InsurancePremium, utr_no__isnull=False)
    #     for p in pending:
    #         if p.utr_no:
    #             p.create_insurance_transaction()

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

            all_payouts = [x for x in all_payouts if not x._removed]
            transfers = [x for x in transfers if not x._removed]
            if len(transfers)==0 and (transferred_amount+self.payable_amount)<=premium_amount:
                return True



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

    def get_insurance_transaction(self):
        from ondoc.insurance.models import UserInsurance, InsuranceTransaction
        if not self.booking_type == self.InsurancePremium:
            raise Exception('Not implemented for non insurance premium payouts')
        user_insurance = self.get_user_insurance()
        existing = user_insurance.transactions.filter(reason=InsuranceTransaction.PREMIUM_PAYOUT)
        return existing

    def get_user_insurance(self):
        ui = self.user_insurance.all()
        if len(ui)>1:
            raise Exception('Multiple user insurance found for a single payout')
        if len(ui)==1:
            return ui.first()

        pms = PayoutMapping.objects.filter(payout=self).first()
        user_insurance = pms.content_object
        return user_insurance

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

    def get_appointment(self):
        if self.lab_appointment.all():
            return self.lab_appointment.all()[0]
        elif self.opd_appointment.all():
            return self.opd_appointment.all()[0]
        elif self.user_insurance.all():
            return self.user_insurance.all()[0]
        return None

    def is_nodal_transfer(self):
        merchant = Merchant.objects.filter(id=settings.DOCPRIME_NODAL2_MERCHANT).first()
        if self.paid_to == merchant:
            return True

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

        trans = PgTransaction.objects.filter(order=user_insurance.order)
        if len(trans)>1:
            raise Exception('multiple transactions found')

        if trans and trans[0].amount == self.payable_amount:
            return trans

        from ondoc.insurance.models import UserInsurance
        uis = UserInsurance.objects.filter(user=user_insurance.user)
        if len(uis)==1:
            trans = PgTransaction.objects.filter(user=user_insurance.user, product_id=Order.INSURANCE_PRODUCT_ID)
            if len(trans)==1 and trans[0].amount == self.payable_amount:
                return trans

        return []

    def is_insurance_premium_payout(self):
        if self.booking_type == Order.INSURANCE_PRODUCT_ID:
            return True

        # if self.get_user_insurance():
        #     return True
        return False

    def get_or_create_insurance_premium_transaction(self):
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
                req_data["merchCode"] = "apolloDummy"


            response = requests.post(url, data=json.dumps(req_data), headers=headers)
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

    def get_billed_to(self):
        if self.content_object:
            return self.content_object
        appt = self.get_appointment()
        if appt and appt.get_billed_to:
            return appt.get_billed_to
        return ''

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

    def update_status_from_pg(self):
        with transaction.atomic():
            # if self.pg_status=='SETTLEMENT_COMPLETED' or self.utr_no or self.type ==self.MANUAL:
            #     return

            order_no = None
            url = settings.SETTLEMENT_DETAILS_API
            if self.is_insurance_premium_payout():
                txn = self.get_insurance_premium_transactions()
                if txn:
                    order_no = txn[0].order_no

            else:
                order_no = self.get_pg_order_no()

            if order_no:
                req_data = {"orderNo":order_no}
                req_data["hash"] = self.create_checksum(req_data)

                headers = {"auth": settings.SETTLEMENT_AUTH,
                           "Content-Type": "application/json"}

                response = requests.post(url, data=json.dumps(req_data), headers=headers)
                if response.status_code == status.HTTP_200_OK:
                    resp_data = response.json()
                    self.status_api_response = resp_data
                    if resp_data.get('ok') == 1 and len(resp_data.get('settleDetails'))>0:
                        details = resp_data.get('settleDetails')
                        for d in details:
                            if d.get('refNo') == str(self.payout_ref_id) or\
                                    (not self.payout_ref_id and d.get('orderNo')==order_no):
                                self.utr_no = d.get('utrNo','')
                                self.pg_status = d.get('txStatus','')
                                if self.utr_no:
                                    self.status = self.PAID
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

    class Meta:
        db_table = "merchant_payout"


class PayoutMapping(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey()
    payout = models.ForeignKey(MerchantPayout, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "payout_mapping"

class UserReferrals(TimeStampedModel):
    SIGNUP_CASHBACK = 50
    COMPLETION_CASHBACK = 50

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
