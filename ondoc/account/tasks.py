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


@task(bind=True)
@transaction.atomic
def refund_status_update(self):
    from ondoc.account.models import ConsumerRefund, PgTransaction
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'
    refund_obj = ConsumerRefund.objects.select_for_update().filter(refund_state=ConsumerRefund.PENDING)
    url = settings.PG_REFUND_STATUS_API_URL
    token = settings.PG_REFUND_AUTH_TOKEN
    headers = {
        "auth": token
    }
    for obj in refund_obj:
        response = requests.get(url=url, params={"refId": obj.id}, headers=headers)
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
            if resp_data.get("ok") and str(resp_data["ok"]) == SUCCESS_OK_STATUS and code is not None and code != PgTransaction.REFUND_FAILURE_STATUS:
                obj.refund_state = ConsumerRefund.COMPLETED
                obj.save()
                print("status updated for - " + str(obj.id))
            else:
                logging.error("Invalid ok status or code mismatch - " + str(response.content))


@task(bind=True, max_retries=6)
@transaction.atomic
def refund_curl_task(self, req_data):
    from .models import ConsumerRefund
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'
    FAILURE_STATUS = 'FAIL'
    ALREADY_REQUESTED_STATUS = 'ALREADY_REQUESTED'
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
                if resp_data.get("ok") is not None and str(resp_data["ok"]) == SUCCESS_OK_STATUS:
                    refund_queryset = ConsumerRefund.objects.select_for_update().filter(pk=req_data["refNo"]).first()
                    if refund_queryset:
                        refund_queryset.refund_state = ConsumerRefund.REQUESTED
                        refund_queryset.save()
                        print("Status Updated")
                elif (resp_data.get("ok") is not None and str(resp_data["ok"]) == FAILURE_OK_STATUS and
                      resp_data.get("status") and str(resp_data["status"]) == ALREADY_REQUESTED_STATUS):
                    print("Already Requested")
                elif (resp_data.get("ok") is None or
                      (str(resp_data["ok"]) == FAILURE_OK_STATUS and
                       (resp_data.get("status") is None or str(resp_data["status"]) == FAILURE_STATUS))):
                    print("Refund Failure")
                    raise Exception("Retry on wrong response - " + str(response.content))
                else:
                    print("Incorrect response")
                    raise Exception("Retry on wrong response - " + str(response.content))
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))
        except Exception as e:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Error in Refund with next retry countdown - " + str(countdown_time) + " of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
            self.retry([req_data], countdown=countdown_time)
