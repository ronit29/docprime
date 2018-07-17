from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel, User
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from django.db import transaction

# Create your models here.


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
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        appointment_obj = None
        if self.action == Order.OPD_APPOINTMENT_CREATE:
            if consumer_account.balance >= appointment_data["effective_price"]:
                appointment_obj = OpdAppointment.create_appointment(appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                self.update_order(order_dict)
                appointment_amount = appointment_obj.effective_price
                self.debit_payment(consumer_account, pg_data, appointment_obj, appointment_amount)
        elif self.action == Order.LAB_APPOINTMENT_CREATE:
            if consumer_account.balance >= appointment_data["effective_price"]:
                appointment_obj = LabAppointment.create_appointment(appointment_data)
                order_dict = {
                    "reference_id": appointment_obj.id,
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                self.update_order(order_dict)
                appointment_amount = appointment_obj.effective_price
                self.debit_payment(consumer_account, pg_data, appointment_obj, appointment_amount)
        elif self.action == Order.OPD_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = OpdAppointment.objects.get(pk=self.reference_id)
            if consumer_account.balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                debit_amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                self.update_order(order_dict)
                self.debit_payment(consumer_account, pg_data, appointment_obj, debit_amount)
        elif self.action == Order.LAB_APPOINTMENT_RESCHEDULE:
            new_appointment_data = appointment_data
            appointment_obj = LabAppointment.objects.get(pk=self.reference_id)
            if consumer_account.balance + appointment_obj.effective_price >= new_appointment_data["effective_price"]:
                debit_amount = new_appointment_data["effective_price"] - appointment_obj.effective_price
                appointment_obj.action_rescheduled_patient(new_appointment_data)
                order_dict = {
                    "payment_status": Order.PAYMENT_ACCEPTED
                }
                self.update_order(order_dict)
                self.debit_payment(consumer_account, pg_data, appointment_obj, debit_amount)
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

    class Meta:
        db_table = "order"


class PgTransaction(TimeStampedModel):
    DOCTOR_APPOINTMENT = 1
    LAB_APPOINTMENT = 2
    CREDIT = 0
    DEBIT = 1
    TYPE_CHOICES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
    order_id = models.PositiveIntegerField()
    order_no = models.PositiveIntegerField(blank=True, null=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    payment_mode = models.CharField(max_length=50)
    response_code = models.CharField(max_length=50)
    bank_id = models.CharField(max_length=50)
    transaction_date = models.CharField(max_length=80)
    bank_name = models.CharField(max_length=100)
    currency = models.CharField(max_length=15)
    status_code = models.IntegerField()
    pg_name = models.CharField(max_length=100)
    status_type = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, unique=True)
    pb_gateway_name = models.CharField(max_length=100)

    class Meta:
        db_table = "pg_transaction"


class ConsumerAccount(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def credit_payment(self, data, amount):
        self.balance += amount
        action = ConsumerTransaction.PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.form_consumer_tx_data(data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def credit_cancellation(self, data, amount):
        self.balance += amount
        action = ConsumerTransaction.CANCELLATION
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.form_consumer_tx_data(data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def debit_refund(self, data):
        amount = self.balance
        self.balance = 0
        action = ConsumerTransaction.REFUND
        tx_type = PgTransaction.DEBIT
        consumer_tx_data = self.form_consumer_tx_data(data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def debit_schedule(self, data, amount):
        self.balance -= amount
        action = ConsumerTransaction.SALE
        tx_type = PgTransaction.DEBIT
        consumer_tx_data = self.form_consumer_tx_data(data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def credit_schedule(self, data, amount):
        self.balance += amount
        action = ConsumerTransaction.RESCHEDULE_PAYMENT
        tx_type = PgTransaction.CREDIT
        consumer_tx_data = self.form_consumer_tx_data(data, amount, action, tx_type)
        ConsumerTransaction.objects.create(**consumer_tx_data)
        self.save()

    def form_consumer_tx_data(self, data, amount, action, tx_type):
        consumer_tx_data = dict()
        consumer_tx_data['user'] = data['user']
        consumer_tx_data['product_id'] = data['product_id']
        consumer_tx_data['reference_id'] = data.get('reference_id')
        consumer_tx_data['transaction_id'] = data.get('transaction_id')
        consumer_tx_data['order_id'] = data.get('order_id')
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
    product_id = models.SmallIntegerField(choices=Order.PRODUCT_IDS)
    reference_id = models.IntegerField(blank=True, null=True)
    order_id = models.IntegerField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    # pg_transaction = models.ForeignKey(PgTransaction, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.SmallIntegerField(choices=PgTransaction.TYPE_CHOICES)
    action = models.SmallIntegerField(choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'consumer_transaction'


class Invoice(TimeStampedModel):
    PRODUCT_IDS = Order.PRODUCT_IDS
    reference_id = models.PositiveIntegerField()
    product_id = models.SmallIntegerField(choices=PRODUCT_IDS)
    file = models.FileField(upload_to='invoices', null=True, blank=True)