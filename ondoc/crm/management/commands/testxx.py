from django.core.management.base import BaseCommand

from ondoc.insurance.models import UserInsurance
from django.db import transaction

class Command(BaseCommand):

    help = 'Create payouts for appointments'

    @transaction.atomic
    def handle(self, *args, **options):
        print('hello')
        #return
        ui = UserInsurance.objects.filter(id=3000000838).first()
        ui.process_payout()