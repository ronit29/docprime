from __future__ import absolute_import, unicode_literals

from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import logging

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=6)
def refund_curl_task(self, req_data):
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
            response = requests.post(url, data=req_data, headers=headers)
            # response.raise_for_status()
            if response.status_code == status.HTTP_200_OK:
                from .models import ConsumerRefund
                resp_data = response.json()
                if resp_data.get("ok") and str(resp_data["ok"]) == str(1):
                    refund_queryset = ConsumerRefund.objects.filter(pk=req_data["refNo"]).first()
                    if refund_queryset:
                        refund_queryset.refund_state = ConsumerRefund.COMPLETED
                        refund_queryset.save()
                        print("Status Updated")
                else:
                    countdown_time = (2 ** self.request.retries) * 60 * 10
                    logging.error("Refund Failure with response - " + str(response.content))
                    print(countdown_time)
                    self.retry([req_data], countdown=countdown_time)
            else:
                countdown_time = (2 ** self.request.retries) * 60 * 10
                logging.error("Refund Failure with response - " + str(response.content))
                print(countdown_time)
                self.retry([req_data], countdown=countdown_time)
        except Exception as e:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Error in Refund with next retry countdown - " + str(countdown_time) + " of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
            self.retry([req_data], countdown=countdown_time)
