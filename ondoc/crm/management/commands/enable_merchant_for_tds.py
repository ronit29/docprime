from django.core.management.base import BaseCommand
from ondoc.account.models import Merchant


def enable_merchant_for_tds():
    pan_card_characters = ['C', 'F', 'A', 'T', 'B', 'L', 'J', 'G']
    merchants = Merchant.objects.all()
    for merchant in merchants:
        pan_number = merchant.pan_number
        if pan_number:
            pan_character = list(pan_number)[3]
            if pan_character in pan_card_characters:
                merchant.enable_for_tds_deduction = True
                merchant.save()


class Command(BaseCommand):
    def handle(self, **options):
        enable_merchant_for_tds()











