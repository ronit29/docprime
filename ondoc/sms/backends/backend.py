import json
import requests
from django.conf import settings
from ondoc.authentication.models import OtpVerifications
from random import randint
from ondoc.notification.rabbitmq_client import publish_message
# from ondoc.notification.sqs_client import publish_message
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from ondoc.notification.models import WhtsappNotification, NotificationAction


class NodeJsSmsBackend(object):

    def send(self, message, phone_no, retry_send=False, otp=None, via_sms=True, via_whatsapp=False):
        from requests.utils import quote

        if via_sms:
            payload = {
                "type": "sms",
                "data": {
                    "phone_number": phone_no,
                    "content": quote(message),
                    "retry": retry_send
                }
            }
            publish_message(json.dumps(payload))

        if otp and phone_no and via_whatsapp:
            whatsapp_message = {"media": {},
                                "message": "",
                                "template": {
                                    "name": "docprime_otp_verification",
                                    "params": [otp]
                                },
                                "message_type": "HSM",
                                "phone_number": phone_no
                                }

            whatsapp_noti = WhtsappNotification.objects.create(
                phone_number=phone_no,
                notification_type=NotificationAction.LOGIN_OTP,
                template_name='docprime_otp_verification',
                payload=whatsapp_message
            )

            whatsapp_payload = {
                "data": whatsapp_noti.payload,
                "type": "social_message"
            }

            publish_message(json.dumps(whatsapp_payload))


class BaseSmsBackend(NodeJsSmsBackend):

    def send(self, message, phone_no, retry_send=False, otp=None, via_sms=True, via_whatsapp=False):
        from requests.utils import quote
        if settings.SEND_THROUGH_NODEJS_ENABLED:
            super().send(message, phone_no, retry_send, otp, via_sms, via_whatsapp)
            return True
        payload = {'sender': 'DOCPRM', 'route': '4','authkey':settings.SMS_AUTH_KEY}
        payload['message'] = quote(message)
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

    def send_otp(self, message, phone_no, retry_send=False, **kwargs):
        call_source = kwargs.get('call_source')
        via_sms = kwargs.get('via_sms', True)
        via_whatsapp = kwargs.get('via_whatsapp', False)
        data = create_otp(phone_no, message, call_source=call_source)
        message = data['message']
        otp = data['otp']
        return self.send(message, phone_no, retry_send, otp, via_sms, via_whatsapp)

class ConsoleSmsBackend(BaseSmsBackend):

    def send_message(self, message, phone_no):

        self.print(message)
        return True

    def send_otp(self, message, phone_no, retry_send=False, **kwargs):

        call_source = kwargs.get('call_source')
        data = create_otp(phone_no, message, call_source=call_source)
        message = data['message']
        otp = data['otp']
        self.print(message)
        return True

class WhitelistedSmsBackend(BaseSmsBackend):

    def send_message(self, message, phone_no):

        if self.is_number_whitelisted(phone_no):
            return self.send(message, phone_no)
        else:
            return self.print(message)

    def send_otp(self, message, phone_no, retry_send=False, **kwargs):

        via_sms = kwargs.get('via_sms', True)
        via_whatsapp = kwargs.get('via_whatsapp', False)
        call_source = kwargs.get('call_source')
        data = create_otp(phone_no, message, call_source=call_source)
        message = data['message']
        otp = data['otp']
        if self.is_number_whitelisted(phone_no):
            return self.send(message, phone_no, retry_send, otp, via_sms, via_whatsapp)
        else:
            return self.print(message)

    def is_number_whitelisted(self, number):
        if str(number) in settings.NUMBER_WHITELIST:
            return True
        return False


def create_otp(phone_no, message, **kwargs):
    call_source = kwargs.get('call_source')
    otpEntry = (OtpVerifications.objects.filter(phone_number=phone_no, is_expired=False,
                                                created_at__gte=timezone.now() - relativedelta(
                                                    minutes=OtpVerifications.OTP_EXPIRY_TIME)).first())
    if otpEntry:
        otp = otpEntry.code
    else:
        OtpVerifications.objects.filter(phone_number=phone_no).update(is_expired=True)
        otp = randint(100000,999999)
        otpEntry = OtpVerifications(phone_number=phone_no, code=otp, country_code="+91", otp_request_source=call_source)
        otpEntry.save()
    message = message.format(str(otp))
    data = {}
    data['message'] = message
    data['otp'] = otp
    return data
