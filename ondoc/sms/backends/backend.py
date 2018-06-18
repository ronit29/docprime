import requests
from django.conf import settings
from ondoc.authentication.models import OtpVerifications
from random import randint

class SmsBackend(object):

    def send_message(self, message, phone_no):

        payload = {'sender': 'PANCEA', 'route': '4','authkey':settings.SMS_AUTH_KEY}
        payload['message'] = message
        payload['mobiles'] = '91' + str(phone_no)
        r = requests.get('http://api.msg91.com/api/sendhttp.php', params=payload)
        if r.status_code == requests.codes.ok:
            return True
        return False

    def send_otp(self, message, phone_no):

        message = create_otp(phone_no, message)

        #'hanning{0}.pdf'.format(num)

        payload = {'sender': 'PANCEA', 'route': '4','authkey':settings.SMS_AUTH_KEY}
        payload['message'] = 'Otp is '+message
        payload['mobiles'] = '91' + str(phone_no)
        r = requests.get('http://api.msg91.com/api/sendhttp.php', params=payload)
        if r.status_code == requests.codes.ok:
            return True
        return False


class ConsoleSmsBackend(object):

    def send_message(self, message, phone_no):

        print(message)
        return True

    def send_otp(self, message, phone_no):

        message = create_otp(phone_no, message)
        print(message)
        return True

def create_otp(phone_no, message):
    otp = randint(100000,999999)
    otpEntry = OtpVerifications(phone_number=phone_no, code=otp, country_code="+91")
    otpEntry.save()
    print(str(otp))
    message = message.format(str(otp))
    return message
