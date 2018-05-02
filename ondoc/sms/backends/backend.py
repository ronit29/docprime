import requests
from django.conf import settings


class SmsBackend(object):

    def send_message(self, message, phone_no):

        payload = {'sender': 'PANCEA', 'route': '4','authkey':settings.SMS_AUTH_KEY}
        payload['message'] = message
        payload['mobiles'] = '91' + phone_no
        r = requests.get('http://api.msg91.com/api/sendhttp.php', params=payload)
        if r.status_code == requests.codes.ok:
            return True
        return False


class ConsoleSmsBackend(object):

    def send_message(self, message, phone_no):

        print(message)
        return True
