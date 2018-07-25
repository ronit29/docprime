from __future__ import absolute_import, unicode_literals

import requests
from celery import Celery, shared_task, task


@task(bind=True)
def refund_curl_task(self, req_data):
    try:
        token = "gFH8gPXbCWaW8WqUefmFBcyRj0XIw"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        url = "http://pgdev.policybazaar.com/dp/refund/refundRequested"
        response = requests.post(url, data=req_data, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            # Update transaction status
            pass
        else:
            self.retry(req_data={"hello": 1})
        print("\n\n\n")
        print(response.status_code)
        print("\n\n\n")
    except:
        self.retry(countdown=60)
