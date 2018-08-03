from __future__ import absolute_import, unicode_literals

from rest_framework import status
from celery import task
import requests
import json
import logging

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=6)
def refund_curl_task(self, req_data):
    print(req_data)
    try:
        token = "gFH8gPXbCWaW8WqUefmFBcyRj0XIw"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        url = "http://pgdev.policybazaar.com/dp/refund/refundRequested"
        response = requests.post(url, data=req_data, headers=headers)
        response.raise_for_status()
        if response.status_code == status.HTTP_200_OK:
            from .models import ConsumerRefund
            refund_queryset = ConsumerRefund.objects.filter(user_id=req_data["user"], consumer_transaction_id=req_data["orderId"], pg_transaction_id=req_data["refNo"]).first()
            if refund_queryset:
                refund_queryset.refund_state = ConsumerRefund.COMPLETED
                refund_queryset.save()
                print("Status Updated")
        else:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            print(countdown_time)
            self.retry([req_data], countdown=countdown_time)
    except Exception as e:
        countdown_time = (2 ** self.request.retries) * 60 * 10
        logging.error("Error in Refund with next retry countdown - " + str(countdown_time) + " of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
        self.retry([req_data], countdown=countdown_time)
