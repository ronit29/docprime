from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel, User, UserProfile
from ondoc.account.tasks import refund_curl_task
# from ondoc.diagnostic.models import LabAppointment
from django.db import transaction
from django.db.models import Sum, Q, F, Max
from datetime import datetime, timedelta
from django.utils import timezone
from ondoc.api.v1.utils import refund_curl_request
from django.conf import settings
from rest_framework import status
import hashlib
import copy
import json
import logging
import requests

logger = logging.getLogger(__name__)


class Order(TimeStampedModel):
    OPD_APPOINTMENT_RESCHEDULE = 1
    OPD_APPOINTMENT_CREATE = 2
    LAB_APPOINTMENT_RESCHEDULE = 3
    LAB_APPOINTMENT_CREATE = 4
    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, "Payment Accepted"),
        (PAYMENT_PENDING, "Payment Pending"),
    )
    ACTION_CHOICES = (("", "Select"), (OPD_APPOINTMENT_RESCHEDULE, 'Opd Reschedule'),
                      (OPD_APPOINTMENT_CREATE, "Opd Create"),
                      (LAB_APPOINTMENT_CREATE, "Lab Create"),
                      (LAB_APPOINTMENT_RESCHEDULE, "Lab Reschedule"),
                      )
    DOCTOR_PRODUCT_ID = 1
    LAB_PRODUCT_ID = 2
    PRODUCT_IDS = [(DOCTOR_PRODUCT_ID, "Doctor Appointment"), (LAB_PRODUCT_ID, "LAB_PRODUCT_ID")]
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS)
    reference_id = models.PositiveSmallIntegerField(blank=True, null=True)
    action = models.PositiveSmallIntegerField(blank=True, null=True, choices=ACTION_CHOICES)
    action_data = JSONField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    error_status = models.CharField(max_length=250, verbose_name="Error", blank=True, null=True)
    is_viewable = models.BooleanField(verbose_name='Is Viewable', default=True)

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
    def process_order(self, consumer_account, pg_data, appointment_data):
        # New code for processing order
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        appointment_obj = None
        order_dict = dict()
        amount = None
        if self.action == Order.OPD_APPOINTMENT_CREATE:
            if consumer_account.balance >= appointment_data["effective_price"]:
                appointment_obj = OpdAppointment.create_appointment(appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price
        elif self.action == Order.LAB_APPOINTMENT_CREATE:
            if consumer_account.balance >= appointment_data["effective_price"]:
                appointment_obj = LabAppointment.create_appointment(appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = appointment_obj.effective_price
        elif self.action == Order.OPD_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = OpdAppointment.objects.get(pk=self.reference_id)
            if consumer_account.balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
        elif self.action == Order.LAB_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = LabAppointment.objects.get(pk=self.reference_id)
            if consumer_account.balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
        if order_dict:
            self.update_order(order_dict)
        if appointment_obj:
            consumer_account.debit_schedule(appointment_obj, pg_data.get("product_id"), amount)
        return appointment_obj

    def update_order(self, data):
        self.reference_id = data.get("reference_id", self.reference_id)
        self.payment_status = data.get("payment_status", self.payment_status)
        self.save()

    def debit_payment(self, consumer_account, pg_data, app_obj, amount):
        debit_data = {
            "user": pg_data.get("user"),
            "product_id": pg_data.get("product_id"),
            "transaction_id": pg_data.get("transaction_id"),
            "reference_id": app_obj.id
        }
        consumer_account.debit_schedule(debit_data, amount)

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
    order_id = models.PositiveIntegerField()
    order_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=50, null=True, blank=True)
    response_code = models.CharField(max_length=50)
    bank_id = models.CharField(max_length=50)
    transaction_date = models.DateTimeField(auto_now=True)
    bank_name = models.CharField(max_length=100)
    currency = models.CharField(max_length=15)
    status_code = models.IntegerField()
    pg_name = models.CharField(max_length=100)
    status_type = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, unique=True)
    pb_gateway_name = models.CharField(max_length=100)

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

    @staticmethod
    def form_pg_refund_data(refund_objs):
        pg_data = list()
        for data in refund_objs:
            if data.pg_transaction:
                params = {
                    "user": str(data.user.id),
                    "orderNo": str(data.pg_transaction.order_no),
                    "orderId": str(data.pg_transaction.order_id),
                    "refundAmount": str(data.refund_amount),
                    "refNo": str(data.id),
                }
                secret_key = settings.PG_SECRET_KEY_REFUND
                client_key = settings.PG_CLIENT_KEY_REFUND
                params["checkSum"] = PgTransaction.create_pg_hash(params, secret_key, client_key)
                pg_data.append(params)
        return pg_data

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


class ConsumerAccount(TimeStampedModel):
    user = models.OneToOneField(User, blank=True, null=True, on_delete=models.SET_NULL)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def credit_payment(self, pg_data, amount):
        self.balance += amount
        action = ConsumerTransaction.PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.consumer_tx_pg_data(pg_data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def credit_cancellation(self, appointment_obj, product_id, amount):
        self.balance += amount
        action = ConsumerTransaction.CANCELLATION
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj, product_id, amount, action, tx_type)
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
        self.balance -= amount
        action = ConsumerTransaction.SALE
        tx_type = PgTransaction.DEBIT

        consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj, product_id, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def credit_schedule(self, appointment_obj, product_id, amount):
        self.balance += amount
        action = ConsumerTransaction.RESCHEDULE_PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.consumer_tx_appointment_data(appointment_obj, product_id, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

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

    def consumer_tx_appointment_data(self, app_obj, product_id, amount, action, tx_type):
        consumer_tx_data = dict()
        consumer_tx_data['user'] = app_obj.user
        consumer_tx_data['product_id'] = product_id
        consumer_tx_data['reference_id'] = app_obj.id
        # consumer_tx_data['transaction_id'] = data.get('transaction_id')
        # consumer_tx_data['order_id'] = data.get('order_id')
        consumer_tx_data['type'] = tx_type
        consumer_tx_data['action'] = action
        consumer_tx_data['amount'] = amount
        return consumer_tx_data

    class Meta:
        db_table = "consumer_account"


class ConsumerTransaction(TimeStampedModel):
    CANCELLATION = 0
    PAYMENT = 1
    REFUND = 2
    SALE = 3
    RESCHEDULE_PAYMENT = 4
    action_list = ["Cancellation", "Payment", "Refund", "Sale"]
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

    @classmethod
    def valid_appointment_for_cancellation(cls, app_id, product_id):
        return not cls.objects.filter(type=PgTransaction.CREDIT, reference_id=app_id, product_id=product_id,
                                      action=cls.CANCELLATION).exists()

    class Meta:
        db_table = 'consumer_transaction'


class ConsumerRefund(TimeStampedModel):
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
            pg_data = PgTransaction.form_pg_refund_data(consumer_refund_objs)
            # transaction.on_commit(lambda: refund_curl_request(pg_data))
        except Exception as e:
            logger.error("Error in refund celery - " + str(e))

    class Meta:
        db_table = "consumer_refund"

    @classmethod
    def schedule_refund_task(cls, consumer_refund_objs):
        pg_data = PgTransaction.form_pg_refund_data(consumer_refund_objs)
        refund_curl_request(pg_data)

    def schedule_refund(self):
        pg_data = PgTransaction.form_pg_refund_data([self, ])
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
                refund_queryset.save()
                print("Status Updated")


class Invoice(TimeStampedModel):
    PRODUCT_IDS = Order.PRODUCT_IDS
    reference_id = models.PositiveIntegerField()
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS)
    file = models.FileField(upload_to='invoices', null=True, blank=True)
