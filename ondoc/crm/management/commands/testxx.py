from django.core.management.base import BaseCommand

from ondoc.insurance.models import UserInsurance
from django.db import transaction

class Command(BaseCommand):

    help = 'Create payouts for appointments'

    #@transaction.atomic
    def handle(self, *args, **options):
        print('hello')
        UserInsurance.transfer_to_nodal_if_required()
        #return
        #UserInsurance.all_premiums_which_need_transfer()
        # ui = UserInsurance.objects.filter(id__in=[3000001144,3000001145,3000001146,3000001147,3000001148,3000001149,3000001151,3000001153,3000001155,3000001157,3000001158,3000001114,3000001115,3000001116,3000001117,3000001119,3000001120,3000001121,3000001124,3000001126,3000001127,3000001128,3000001129,3000001130,3000001131,3000001132,3000001133,3000001134,3000001135,3000001136,3000001137,3000001138,3000001139,3000001141,3000001142,3000001143,3000001160,3000001161,3000001162])
        # for u in ui:
        #     print(str(u.id))
        #     u.process_payout()