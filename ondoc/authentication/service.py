import requests
import json
from django.utils import timezone
import time

def getTimeDifferenceInMinutes(end):
    d1_ts = time.mktime(timezone.now().timetuple())
    d2_ts = time.mktime(end.timetuple())
    return (int(d1_ts-d2_ts) / 60)


def sendOTP(number, otp):
    headers = {'content-type': 'application/json'}
    post_data = {
        "CommunicationDetails": {
            "Conversations": [
                {
                    "ToReceipent": [
                        str(number)
                    ],
                    "Body": "OTP For Login - " + str(otp)
                }
            ],
            "CommunicationType": 2
        }
    }

    r = requests.post("http://qamatrixapi.policybazaar.com/Communication/Communication.svc/Send", data=json.dumps(post_data), headers=headers)

    if r.status_code is 200:
        response_data = json.loads(r.text)
        if response_data['SendResult']['Response'] == 'Success':
            return True

    raise Exception('OTP Send Failed')