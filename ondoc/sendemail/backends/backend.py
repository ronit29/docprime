import json
from django.core.mail.backends.console import EmailBackend as Console
from django.core.mail.backends.smtp import EmailBackend as SMTP
from django.core.mail import send_mail, get_connection
from django.conf import settings
from ondoc.notification.rabbitmq_client import publish_message
# from ondoc.notification.sqs_client import publish_message


class NodeJsEmailBackend(object):

    def send_email(self, subject, message, sender, to):
        payload = {
            "type": "email",
            "data": {
                "email": to,
                "email_subject": subject,
                "content": message
            }
        }
        publish_message(json.dumps(payload))


class ConsoleEmailBackend(NodeJsEmailBackend):

    def send_email(self, subject, message, sender, to):
        if settings.SEND_THROUGH_NODEJS_ENABLED:
            super().send_email(subject, message, sender, to)
            return
        send_mail(subject, message, sender, [to], fail_silently=False, connection=Console())


class SMTPEmailBackend(object):

    def send_email(self, subject, message, sender, to):
        send_mail(subject, message, sender, [to], fail_silently=False, connection=SMTP())

class MailgunEmailBackend(object):

    def send_email(self, subject, message, sender, to):
        connection = get_connection('anymail.backends.mailgun.EmailBackend')
        send_mail(subject, message, sender, [to], fail_silently=False, connection=connection)

class WhiteListedEmailBackend(object):

    def send_email(self, subject, message, sender, to):
        if self.is_email_whitelisted(to):
            connection = get_connection('anymail.backends.mailgun.EmailBackend')
            send_mail(subject, message, sender, [to], fail_silently=False, connection=connection)
        else:
            send_mail(subject, message, sender, [to], fail_silently=False, connection=Console())

    def is_email_whitelisted(self, email):
        if email in settings.EMAIL_WHITELIST:
            return True
        return False
