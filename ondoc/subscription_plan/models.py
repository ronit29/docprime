import datetime

from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.db.models import Count
from django.utils import timezone
import logging
from ondoc.account.models import ConsumerAccount, Order, MoneyPool
from ondoc.api.v1.utils import payment_details
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import User
from ondoc.diagnostic.models import LabNetwork, Lab, LabTest, LabAppointment

# Create your models here.

logger = logging.getLogger(__name__)


class Plan(auth_model.TimeStampedModel):
    name = models.CharField(max_length=50)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2)
    unlimited_online_consultation = models.BooleanField(default=True)
    priority_queue = models.BooleanField(default=True)
    features = models.ManyToManyField('PlanFeature', through='PlanFeatureMapping', through_fields=('plan', 'feature'),
                                      related_name='plans_included_in')
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan"

    def __str__(self):
        return self.name


class PlanFeature(auth_model.TimeStampedModel):
    name = models.CharField(max_length=150, default='')
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE, null=True, blank=True)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, null=True, blank=True)
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan_feature"

    def __str__(self):
        output = ''
        if self.name:
            output = self.name
            return output
        if self.network:
            output += self.network.name
        if self.lab:
            output += self.lab.name
        if self.test:
            output += self.test.name
        return output


class PlanFeatureMapping(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="feature_mappings")
    feature = models.ForeignKey(PlanFeature, on_delete=models.CASCADE, related_name="plan_mappings")
    count = models.PositiveIntegerField(verbose_name="Times per year?")
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = (('plan', 'feature'),)


class UserPlanMapping(auth_model.TimeStampedModel):
    CANCELLED = 2
    BOOKED = 1

    STATUS_CHOICES = [(CANCELLED, 'Cancelled'),
                      (BOOKED, 'Booked')]

    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, related_name="subscribed_user_mapping")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="plan_mapping", unique=True)
    is_active = models.BooleanField(default=True)
    expire_at = models.DateTimeField(null=True)
    extra_details = JSONField(blank=True, null=True)  # Snapshot of the plan when bought
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True)
    status = models.PositiveSmallIntegerField(default=BOOKED, choices=STATUS_CHOICES)

    class Meta:
        db_table = "subscription_plan_user"

    def cancel(self):
        if not self.is_cancellable():
            raise Exception("Plan already used, cannot cancel")
            return

        # Taking Lock first
        ConsumerAccount.objects.get_or_create(user=self.user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)

        old_instance = UserPlanMapping.objects.get(pk=self.id)
        if old_instance.status == self.BOOKED and old_instance.is_active:
            self.status = self.CANCELLED
            self.is_active = False
            self.save()
            wallet_refund, cashback_refund = self.get_cancellation_breakup()
            consumer_account.credit_cancellation(self, Order.SUBSCRIPTION_PLAN_PRODUCT_ID, wallet_refund, cashback_refund)

    def get_cancellation_breakup(self):
        wallet_refund = cashback_refund = 0
        if self.money_pool:
            wallet_refund, cashback_refund = self.money_pool.get_refund_breakup(self.bought_at_price())
        return wallet_refund, cashback_refund

    def bought_at_price(self):
        price = self.extra_details['deal_price']
        return int(float(price))

    def is_cancellable(self):
        return self.appointment_using.all().count() != 0

    def save(self, *args, **kwargs):
        if not self.expire_at:
            self.expire_at = timezone.now() + datetime.timedelta(days=365)
            super().save(*args, **kwargs)
        super().save(*args, **kwargs)

    @classmethod
    @transaction.atomic()
    def create_order(cls, request, data):
        user = request.user
        resp = {}
        # balance = 0
        # cashback_balance = 0
        plan = data.get('plan')
        # amount_to_be_paid = plan.deal_price
        process_immediately = False
        consumer_account = ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance
        # cashback_balance = consumer_account.cashback
        # total_balance = balance + cashback_balance
        total_balance = balance
        payable_amount = plan.deal_price
        product_id = Order.SUBSCRIPTION_PLAN_PRODUCT_ID
        if total_balance >= payable_amount:
            # cashback_amount = min(cashback_balance, payable_amount)
            cashback_amount = 0
            wallet_amount = max(0, payable_amount - cashback_amount)
            pg_order = Order.objects.create(
                amount=0,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=Order.PAYMENT_PENDING,
                user=user,
                product_id=product_id,
                # visitor_info=visitor_info
            )
            process_immediately = True
        else:
            amount_from_pg = max(0, payable_amount - total_balance)
            required_amount = payable_amount
            # cashback_amount = min(required_amount, cashback_balance)
            cashback_amount = 0
            wallet_amount = 0
            if cashback_amount < required_amount:
                wallet_amount = min(balance, required_amount - cashback_amount)

            pg_order = Order.objects.create(
                amount=amount_from_pg,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=Order.PAYMENT_PENDING,
                user=user,
                product_id=product_id,
                # visitor_info=visitor_info
            )

        action = Order.SUBSCRIPTION_PLAN_BUY
        # Snapshot of plan and its features
        # if_subscription_plan_contains_anything_except_test
        extra_details = {"id": plan.id,
                         "name": plan.name,
                         "mrp": str(plan.mrp),
                         "deal_price": str(plan.deal_price),
                         "unlimited_online_consultation": plan.unlimited_online_consultation,
                         "priority_queue": plan.priority_queue,
                         "features": [{"id": feature_mapping.feature.id, "name": feature_mapping.feature.name,
                                       "count": feature_mapping.count, "test":
                                           feature_mapping.feature.test.id,
                                       "test_name": feature_mapping.feature.test.name} for feature_mapping in
                                      plan.feature_mappings.filter(enabled=True)]}

        action_data = {"user": user.id, "plan": plan.id, "extra_details": extra_details}
        child_order = Order.objects.create(
            product_id=product_id,
            action=action,
            action_data=action_data,
            payment_status=Order.PAYMENT_PENDING,
            parent=pg_order,
            user=user
        )
        if process_immediately:
            appointment_ids = pg_order.process_pg_order()
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {
                "orderId": pg_order.id,
                "type": appointment_ids.get("type", "all"),
                "id": appointment_ids.get("id", None)
            }
            resp["appointments"] = appointment_ids
        else:
            resp["status"] = 1
            resp['data'], resp["payment_required"] = payment_details(request, pg_order)
        return resp

    @staticmethod
    def get_active_plans(user):
        return user.plan_mapping.filter(is_active=True, expire_at__gt=timezone.now())

    @classmethod
    def get_free_tests(cls, request, cart_item_id=None):
        user = request.user
        from django.db.models import F
        from ondoc.cart.models import Cart
        active_plan_mapping = cls.get_active_plans(user).first()
        if not active_plan_mapping:
            return []
        plan_test_count = active_plan_mapping.plan.feature_mappings.filter(enabled=True).values('count', test_id=F('feature__test_id'))
        used_test_count = list(LabAppointment.objects.exclude(status=LabAppointment.CANCELLED).filter(user=user,
                                                                                                 user_plan_used=active_plan_mapping).values(
            test_id=F('test_mappings__test__id')).values_list('test_id', flat=True))
        used_test_count_dict = cls.get_frequency_test(used_test_count)
        plan_test_count_dict = {x['test_id']: x['count'] for x in plan_test_count}
        # TODO : SHASHANK_SINGH consider valid cart items only
        cart_queryset = Cart.objects.all()
        if cart_item_id:
            cart_queryset = cart_queryset.exclude(id=cart_item_id)
        all_cart_objs = cart_queryset.filter(data__included_in_user_plan=True, deleted_at__isnull=True,
                                             product_id=Order.LAB_PRODUCT_ID, user=user)
        all_tests_in_carts = []
        for cart_obj in all_cart_objs:
            all_tests_in_carts.extend(cart_obj.data.get('test_ids', []) if cart_obj.data else [])
        used_in_cart_test_count_dict = cls.get_frequency_test(all_tests_in_carts)
        result = {}
        for temp_test in plan_test_count_dict:
            count_left = plan_test_count_dict[temp_test] - used_test_count_dict.get(temp_test, 0) - used_in_cart_test_count_dict.get(temp_test, 0)
            result[temp_test] = count_left if count_left >= 0 else 0

        # used_test_count = LabAppointment.objects.exclude(status=LabAppointment.CANCELLED).filter(user=user).annotate(
        #     booked_test=F('test_mappings__test')).values('booked_test').filter(booked_test__isnull=False).annotate(
        #     count=Count('booked_test'))
        return [x for x in result if result[x] > 0]
        # return result

    @staticmethod
    def get_frequency_test(test_booked):
        test_booked = sorted(test_booked)
        from itertools import groupby
        return {key: len(list(group)) for key, group in groupby(test_booked)}
