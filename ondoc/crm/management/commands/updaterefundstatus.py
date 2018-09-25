from django.core.management.base import BaseCommand
from ondoc.account.models import ConsumerRefund


class Command(BaseCommand):
    help = 'Update Consumer refund status'

    def handle(self, *args, **options):
        ConsumerRefund.update_refund_status()
