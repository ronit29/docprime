from __future__ import absolute_import, unicode_literals

from rest_framework import status
import requests
from celery import task


@task(bind=True, max_retries=6)
def refund_curl_task(self, req_data):
    try:
        token = "gFH8gPXbCWaW8WqUefmFBcyRj0XIw"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        url = "http://pgdev.policybazaar.com/dp/refund/refundRequested"
        response = requests.post(url, data=req_data, headers=headers)
        if response.status_code == status.HTTP_200_OK:
            print("SSSSSSSSSSSSUUUUUUUUUUUUUUUUCCCCCCCCCCCCCCCCCCEEEEEEESSSSSSSSSSSSSSSSSSSS")
            from ondoc.account.models import ConsumerRefund
            refund_queryset = ConsumerRefund.objects.filter(user_id=req_data["user"], consumer_transaction=req_data["orderId"], pg_transaction=req_data["refNo"]).first()
            if refund_queryset:
                refund_queryset.refund_state = ConsumerRefund.COMPLETED
                refund_queryset.save()
        else:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            print(countdown_time)
            self.retry([req_data], countdown=countdown_time)
    except:
        print("EEEEEEEEEEEXXXXXXXXXXXXXXXCCCCCCCCCCEEEEEEEEEEEEPPPPPPPPPPTTTTTTTTTTTTTIIIIIOOOONNNNNNN")
        countdown_time = (2 ** self.request.retries) * 60 * 10
        print(countdown_time)
        self.retry([req_data], countdown=countdown_time)
