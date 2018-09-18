from django.core.management.base import BaseCommand
from ondoc.account.models import ConsumerRefund


class Command(BaseCommand):
    help = 'Consumer refund with Pending status'

    def handle(self, *args, **options):
        ConsumerRefund.request_pending_refunds()
