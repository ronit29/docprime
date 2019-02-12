from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel, User, UserProfile, Merchant
from ondoc.account.tasks import refund_curl_task
from ondoc.notification.models import AppNotification, NotificationAction
from ondoc.notification.tasks import process_payout
# from ondoc.diagnostic.models import LabAppointment
from django.db import transaction
from django.db.models import Sum, Q, F, Max
from datetime import datetime, timedelta
from django.utils import timezone
from ondoc.api.v1.utils import refund_curl_request, form_pg_refund_data, opdappointment_transform, \
    labappointment_transform, payment_details
from django.conf import settings
from rest_framework import status
import hashlib
import copy
import json
import logging
import requests
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
                      )
    DOCTOR_PRODUCT_ID = 1
    LAB_PRODUCT_ID = 2
    PRODUCT_IDS = [(DOCTOR_PRODUCT_ID, "Doctor Appointment"), (LAB_PRODUCT_ID, "LAB_PRODUCT_ID")]
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS, blank=True, null=True)
    reference_id = models.IntegerField(blank=True, null=True)
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

    def __str__(self):
        return "{}".format(self.id)

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

    @transaction.atomic
    def process_order(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.api.v1.doctor.serializers import OpdAppTransactionModelSerializer
        from ondoc.api.v1.diagnostic.serializers import LabAppTransactionModelSerializer

        # Initial validations for appointment data
        appointment_data = self.action_data
        # Check if payment is required at all, only when payment is required we debit consumer's account
        payment_not_required = False
        if self.product_id == self.DOCTOR_PRODUCT_ID:
            serializer = OpdAppTransactionModelSerializer(data=appointment_data)
            serializer.is_valid(raise_exception=True)
            appointment_data = serializer.validated_data
            if appointment_data['payment_type'] == OpdAppointment.COD:
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

        consumer_account = ConsumerAccount.objects.get_or_create(user=appointment_data['user'])
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=appointment_data['user'])

        appointment_obj = None
        order_dict = dict()
        amount = None
        total_balance = consumer_account.get_total_balance()

        if self.action == Order.OPD_APPOINTMENT_CREATE:
            if total_balance >= appointment_data["effective_price"] or payment_not_required:
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

        if order_dict:
            self.update_order(order_dict)

        wallet_amount = cashback_amount = 0
        # If payment is required and appointment is created successfully, debit consumer's account
        if appointment_obj and not payment_not_required:
            # debit consumer account and update appointment with price breakup
            wallet_amount, cashback_amount = consumer_account.debit_schedule(appointment_obj, self.product_id, amount)
            appointment_obj.price_data = {"wallet_amount": int(wallet_amount), "cashback_amount": int(cashback_amount)}
            appointment_obj.save()

        return appointment_obj, wallet_amount, cashback_amount

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

        if self.orders.exists():
            completed_order = self.orders.filter(reference_id__isnull=False).first()
            return completed_order.getAppointment() if completed_order else None

        if not self.reference_id:
            return None

        if self.product_id == self.LAB_PRODUCT_ID:
            return LabAppointment.objects.filter(id=self.reference_id).first()
        elif self.product_id == self.DOCTOR_PRODUCT_ID:
            return OpdAppointment.objects.filter(id=self.reference_id).first()
        return None

    def get_total_price(self):
        if self.parent:
            raise Exception("Cannot calculate price on a child order")

        return ( self.amount or 0 ) + ( self.wallet_amount or 0 )

    def getTransactions(self):
        # if trying to get txn on a child order, recurse for its parent instead
        if self.parent:
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
                product_id=1 # remove later
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
                product_id=1  # remove later
            )

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
                order = cls.Order.objects.create(
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
    def process_pg_order(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        orders_to_process = []
        if self.orders.exists():
            orders_to_process = self.orders.all()
        else:
            orders_to_process = [self]

        total_cashback_used = total_wallet_used = 0
        opd_appointment_ids = []
        lab_appointment_ids = []

        for order in orders_to_process:
            try:
                curr_app, curr_wallet, curr_cashback = order.process_order()

                # appointment was not created - due to insufficient balance, do not process
                if not curr_app:
                    continue
                if order.product_id == Order.DOCTOR_PRODUCT_ID:
                    opd_appointment_ids.append(curr_app.id)
                elif order.product_id == Order.LAB_PRODUCT_ID:
                    lab_appointment_ids.append(curr_app.id)

                total_cashback_used += curr_cashback
                total_wallet_used += curr_wallet

                # mark cart item delete after order process
                if order.cart:
                    order.cart.mark_delete()
            except Exception as e:
                logger.error(str(e))

        if not opd_appointment_ids and not lab_appointment_ids:
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

        resp = { "opd" : opd_appointment_ids , "lab" : lab_appointment_ids, "type" : "all", "id" : None }
        # Handle backward compatibility, in case of single booking, return the booking id
        if (len(opd_appointment_ids) + len(lab_appointment_ids)) == 1:
            resp["type"] = "doctor" if len(opd_appointment_ids) > 0 else "lab"
            resp["id"] = opd_appointment_ids[0] if len(opd_appointment_ids) > 0 else lab_appointment_ids[0]

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
        if order_obj.payment_status != Order.PAYMENT_ACCEPTED:
            order_obj.payment_status = status
            order_obj.save()
        return order_obj

    class Meta:
        db_table = "order"


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
        if product_id == Order.DOCTOR_PRODUCT_ID:
            client_key = settings.PG_CLIENT_KEY_P1
            secret_key = settings.PG_SECRET_KEY_P1
        elif product_id == Order.LAB_PRODUCT_ID:
            client_key = settings.PG_CLIENT_KEY_P2
            secret_key = settings.PG_SECRET_KEY_P2
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

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
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

    class Meta:
        db_table = "dummy_transaction"


class MoneyPool(TimeStampedModel):
    wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    logs = JSONField(default=[])

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
    reference_id = models.IntegerField(blank=True, null=True)
    order_id = models.IntegerField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    # pg_transaction = models.ForeignKey(PgTransaction, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.SmallIntegerField(choices=PgTransaction.TYPE_CHOICES)
    action = models.SmallIntegerField(choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.SmallIntegerField(choices=SOURCE_TYPE, blank=True, null=True)

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
    file = models.FileField(upload_to='invoices', null=True, blank=True)


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
    STATUS_CHOICES = [(PENDING, 'Pending'), (ATTEMPTED, 'ATTEMPTED'), (PAID, 'Paid')]
    TYPE_CHOICES = [(AUTOMATIC, 'Automatic'), (MANUAL, 'Manual')]
    payout_ref_id = models.IntegerField(null=True, unique=True)
    charged_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_approved = models.BooleanField(default=False)
    status = models.PositiveIntegerField(default=PENDING, choices=STATUS_CHOICES)
    payout_time = models.DateTimeField(null=True, blank=True)
    api_response = JSONField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    paid_to = models.ForeignKey(Merchant, on_delete=models.DO_NOTHING, related_name='payouts', null=True)
    utr_no = models.CharField(max_length=500, blank=True, default='')
    type = models.PositiveIntegerField(default=None, choices=TYPE_CHOICES, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey()

    def save(self, *args, **kwargs):
        first_instance = False
        if not self.id:
            first_instance = True

        if self.id and hasattr(self,'process_payout') and self.process_payout and self.status==self.PENDING and self.type==self.AUTOMATIC:
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

        super().save(*args, **kwargs)

        if first_instance:
            self.payout_ref_id = self.id
            self.save()

    def get_appointment(self):
        if self.lab_appointment.all():
            return self.lab_appointment.all()[0]
        elif self.opd_appointment.all():
            return self.opd_appointment.all()[0]
        return None

    def get_billed_to(self):
        if self.content_object:
            return self.content_object
        appt = self.get_appointment()
        if appt and appt.get_billed_to:
            return appt.get_billed_to
        return ''


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

    class Meta:
        db_table = "merchant_payout"


class UserReferrals(TimeStampedModel):
    SIGNUP_CASHBACK = 50
    COMPLETION_CASHBACK = 50

    code = models.CharField(max_length=10, unique=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, unique=True)

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

