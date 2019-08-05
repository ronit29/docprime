from django.db import models, transaction
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.account import models as acc_models
from ondoc.api.v1 import utils as v1_utils
from ondoc.coupon import models as coupon_models
# Create your models here.


class EConsultation(auth_models.TimeStampedModel, auth_models.CreatedByModel):

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )

    doctor = models.ForeignKey(doc_models.Doctor, on_delete=models.SET_NULL, null=True)
    offline_patient = models.ForeignKey(doc_models.OfflinePatients, on_delete=models.SET_NULL, null=True)
    online_patient = models.ForeignKey(auth_models.UserProfile, on_delete=models.SET_NULL, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2)
    validity = models.PositiveIntegerField(null=True, blank=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    link = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return str(self.id)

    @classmethod
    @transaction.atomic()
    def create_order(cls, request, data):
        user = request.user
        resp = {}
        # balance = 0
        # cashback_balance = 0
        process_immediately = False
        consumer_account = acc_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = acc_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance
        cashback_balance = consumer_account.cashback
        total_balance = balance + cashback_balance
        deal_price = data['price']
        coupon_discount, coupon_cashback, coupon_list, random_coupon_list = coupon_models.Coupon.get_total_deduction(data, deal_price)
        payable_amount = max(0, deal_price - coupon_discount - coupon_cashback)

        product_id = acc_models.Order.SUBSCRIPTION_PLAN_PRODUCT_ID
        if total_balance >= payable_amount:
            # cashback_amount = min(cashback_balance, payable_amount)
            cashback_amount = 0
            wallet_amount = max(0, payable_amount - cashback_amount)
            pg_order = acc_models.Order.objects.create(
                amount=0,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=acc_models.Order.PAYMENT_PENDING,
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

            pg_order = acc_models.Order.objects.create(
                amount=amount_from_pg,
                wallet_amount=wallet_amount,
                cashback_amount=cashback_amount,
                payment_status=acc_models.Order.PAYMENT_PENDING,
                user=user,
                product_id=product_id,
                # visitor_info=visitor_info
            )

        action = acc_models.Order.SUBSCRIPTION_PLAN_BUY
        # Snapshot of plan and its features
        # if_subscription_plan_contains_anything_except_test
        extra_details = {"id": plan.id,
                         "name": plan.name,
                         "mrp": str(plan.mrp),
                         "deal_price": str(plan.deal_price),
                         "payable_amount": str(payable_amount),
                         "unlimited_online_consultation": plan.unlimited_online_consultation,
                         "priority_queue": plan.priority_queue,
                         "features": [{"id": feature_mapping.feature.id, "name": feature_mapping.feature.name,
                                       "count": feature_mapping.count, "test":
                                           feature_mapping.feature.test.id,
                                       "test_name": feature_mapping.feature.test.name} for feature_mapping in
                                      plan.feature_mappings.filter(enabled=True)]}

        action_data = {"user": user.id, "plan": plan.id, "extra_details": extra_details, "coupon": coupon_list,
                       "coupon_data": {"random_coupon_list": random_coupon_list}}
        child_order = acc_models.Order.objects.create(
            product_id=product_id,
            action=action,
            action_data=action_data,
            payment_status=acc_models.Order.PAYMENT_PENDING,
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
            resp['data'], resp["payment_required"] = v1_utils.payment_details(request, pg_order)
        return resp


    class Meta:
        db_table = "e_consultation"
