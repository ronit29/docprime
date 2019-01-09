from django.core.management.base import BaseCommand

from ondoc.account.models import MerchantPayout, Order
from django.db import transaction


class Command(BaseCommand):

    help = 'Map completed payouts with transactions'

    def get_payout_transaction(self, payout_data):
        appointment = payout_data.get_appointment()
        if not appointment:
            return None
        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()
        if not order_data:
            return None
        all_txn = order_data.getTransactions()
        if all_txn and all_txn[0]:
            return all_txn[0].id

    @transaction.atomic
    def handle(self, *args, **options):
        completed_payouts = MerchantPayout.objects.filter(status=MerchantPayout.PAID)

        if not completed_payouts.exists():
            print("No payout to process")
            return

        for payout in completed_payouts:
            if not payout.payout_ref_id:
                txn_id = self.get_payout_transaction(payout)
                if txn_id:
                    try:
                        payout.payout_ref_id = txn_id
                        payout.save()
                        print("Successfuly mapped payout id with txn for payout - " + str(payout.id))
                    except Exception as e:
                        print("Error saving payout with new txn id - " + str(e))
                else:
                    print("No txn found for payout - " + str(payout.id))
            else:
                print("Reference id already mapped for payout - " + str(payout.id))


