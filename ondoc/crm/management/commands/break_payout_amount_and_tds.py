from django.core.management.base import BaseCommand
from ondoc.account.models import MerchantPayout
from ondoc.authentication.models import MerchantTdsDeduction


def break_payout_amount_and_tds():
    all_deductions = MerchantTdsDeduction.objects.all()
    for deduction in all_deductions:
        payout_obj = MerchantPayout.objects.filter(id=deduction.merchant_payout_id).first()
        if payout_obj:
            tds_amount = deduction.tds_deducted
            payout_amount = payout_obj.payable_amount
            original_payable_amount = payout_amount - tds_amount
            payout_obj.payable_amount = original_payable_amount
            payout_obj.tds_amount = tds_amount
            payout_obj.save()


class Command(BaseCommand):

    def handle(self, **options):
        break_payout_amount_and_tds()

