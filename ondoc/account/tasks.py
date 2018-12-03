from __future__ import absolute_import, unicode_literals

from boto3.resources import params
from django.db import transaction
from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import logging

logger = logging.getLogger(__name__)


@task()
def consumer_refund_update():
    from ondoc.api.v1.utils import consumers_balance_refund
    from ondoc.account.models import ConsumerRefund
    consumers_balance_refund()
    ConsumerRefund.request_pending_refunds()
    ConsumerRefund.update_refund_status()


@task(bind=True)
def refund_status_update(self):
    from ondoc.account.models import ConsumerRefund, PgTransaction
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'
    if settings.AUTO_REFUND:
        refund_ids = ConsumerRefund.objects.filter(refund_state=ConsumerRefund.REQUESTED).values_list('id', flat=True)
        url = settings.PG_REFUND_STATUS_API_URL
        token = settings.PG_REFUND_AUTH_TOKEN
        headers = {
            "auth": token
        }
        for ref_id in refund_ids:
            response = requests.get(url=url, params={"refId": ref_id}, headers=headers)
            print(response.url)
            print(response.status_code)
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
                if resp_data.get("ok") and str(resp_data["ok"]) == SUCCESS_OK_STATUS and code is not None and code != PgTransaction.REFUND_UPDATE_FAILURE_STATUS:
                    with transaction.atomic():
                        obj = ConsumerRefund.objects.select_for_update().get(id=ref_id)
                        if obj.refund_state != ConsumerRefund.COMPLETED:
                            obj.refund_state = ConsumerRefund.COMPLETED
                            obj.save()
                            print("status updated for - " + str(obj.id))
                else:
                    logger.error("Invalid ok status or code mismatch - " + str(response.content))


@task(bind=True, max_retries=6)
def refund_curl_task(self, req_data):
    from .models import ConsumerRefund, PgTransaction
    if settings.AUTO_REFUND:
        print(req_data)
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
                logger.error("Response content - " + str(response.content) + " with request data - " + json.dumps(req_data))
                if resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS:
                    ConsumerRefund.update_refund_status_on_resp(req_data["refNo"])
                elif (resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                      resp_data.get("status") is not None and str(resp_data["status"]) == PgTransaction.PG_REFUND_ALREADY_REQUESTED_STATUS):
                    ConsumerRefund.update_refund_status_on_resp(req_data["refNo"])
                    print("Already Requested")
                elif (resp_data.get("ok") is None or
                      (str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                       (resp_data.get("status") is None or str(resp_data["status"]) == PgTransaction.PG_REFUND_FAILURE_STATUS))):
                    print("Refund Failure")
                    raise Exception("Retry on wrong response - " + str(response.content))
                else:
                    print("Incorrect response")
                    raise Exception("Retry on wrong response - " + str(response.content))
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))
        except Exception as e:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            logger.error("Error in Refund with next retry countdown - " + str(countdown_time) + " of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
            self.retry([req_data], countdown=countdown_time)


@task()
def set_order_dummy_transaction(order_id, user_id):
    from .models import Order, DummyTransactions
    from ondoc.account.models import User
    try:
        order_row = Order.objects.filter(id=order_id).first()
        user = User.objects.filter(id=user_id).first()
        if order_row and user:
            token = settings.PG_DUMMY_TRANSACTION_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_DUMMY_TRANSACTION_URL

            req_data = {
                "customerId": user_id,
                "mobile": user.phone_number,
                "email": user.email or "dummyemail@docprime.com",
                "productId": order_row.product_id,
                "orderId": order_id,
                "name": "DocPrime Dummy",
                "txAmount": 0,
                "couponCode": "dummy",
                "couponAmt": 0,
                "paymentMode": "DC",
                "AppointmentId": order_row.reference_id,
                "buCallbackSuccessUrl": "",
                "buCallbackFailureUrl": ""
            }

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                if resp_data.get("ok") is not None and resp_data.get("ok") == 1:
                    tx_data = {}
                    tx_data['user'] = user
                    tx_data['product_id'] = order_row.product_id
                    tx_data['order_no'] = resp_data.get('orderNo')
                    tx_data['order_id'] = order_row.id
                    tx_data['reference_id'] = order_row.reference_id
                    tx_data['type'] = DummyTransactions.CREDIT
                    tx_data['amount'] = 0
                    tx_data['payment_mode'] = "DC"
                    tx_data['transaction_id'] = resp_data.get('orderNo')

                    # tx_data['response_code'] = response.get('responseCode')
                    # tx_data['bank_id'] = response.get('bankTxId')
                    # transaction_time = parse(response.get("txDate"))
                    # tx_data['transaction_date'] = transaction_time
                    # tx_data['bank_name'] = response.get('bankName')
                    # tx_data['currency'] = response.get('currency')
                    # tx_data['status_code'] = response.get('statusCode')
                    # tx_data['pg_name'] = response.get('pgGatewayName')
                    # tx_data['status_type'] = response.get('txStatus')
                    # tx_data['pb_gateway_name'] = response.get('pbGatewayName')

                    DummyTransactions.objects.create(**tx_data)
                    print("SAVED DUMMY TRANSACTION")
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))

    except Exception as e:
        logger.error("Error in Setting Dummy Transaction of user with data - " + json.dumps(req_data) + " with exception - " + str(e))