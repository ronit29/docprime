from django.core.management.base import BaseCommand
from ondoc.sendemail import api as email_api

class Command(BaseCommand):
    help = 'Send a test mail using email send api'

    def handle(self, *args, **options):
        email_api.send_email('arunchaudhary@policybazaar.com', 'Test Message Subject', 'This is a test message')
        self.stdout.write('Successfully send test email')
