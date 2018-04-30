import requests
import json

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