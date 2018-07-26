import requests
from django.conf import settings
from ondoc.authentication.models import OtpVerifications
from random import randint

class BaseSmsBackend(object):

    def send(self, message, phone_no):
        payload = {'sender': 'PANCEA', 'route': '4','authkey':settings.SMS_AUTH_KEY}
        payload['message'] = message
        payload['mobiles'] = '91' + str(phone_no)
        r = requests.get('http://api.msg91.com/api/sendhttp.php', params=payload)
        if r.status_code == requests.codes.ok:
            return True
        return False

    def print(self, message):
        print(message)
        return True


class SmsBackend(BaseSmsBackend):

    def send_message(self, message, phone_no):
        return self.send(message, phone_no)

    def send_otp(self, message, phone_no):

        message = create_otp(phone_no, message)
        return self.send(message, phone_no)

class ConsoleSmsBackend(BaseSmsBackend):

    def send_message(self, message, phone_no):

        self.print(message)
        return True

    def send_otp(self, message, phone_no):

        message = create_otp(phone_no, message)
        self.print(message)
        return True

class WhitelistedSmsBackend(BaseSmsBackend):

    def send_message(self, message, phone_no):

        if self.is_number_whitelisted(phone_no):
            return self.send(message, phone_no)
        else:
            return self.print(message)

    def send_otp(self, message, phone_no):

        message = create_otp(phone_no, message)
        if self.is_number_whitelisted(phone_no):
            return self.send(message, phone_no)
        else:
            return self.print(message)

    def is_number_whitelisted(self, number):
        if str(number) in settings.NUMBER_WHITELIST:
            return True
        return False

def create_otp(phone_no, message):
    otp = randint(100000,999999)
    otpEntry = OtpVerifications(phone_number=phone_no, code=otp, country_code="+91")
    otpEntry.save()
    message = message.format(str(otp))
    return message
