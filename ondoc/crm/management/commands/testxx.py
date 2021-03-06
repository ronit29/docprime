from django.core.management.base import BaseCommand

from ondoc.insurance.models import UserInsurance
from ondoc.account.models import MerchantPayout, PayoutMapping
from django.db import transaction
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):

    help = 'Create payouts for appointments'
    def handle(self, *args, **options):
        #insurance_ids = [3000001027,3000000488,3000000861,3000000690,3000000864,3000000554,3000001039,3000000574,3000000388,3000000650,3000000596,3000000765,3000000479,3000000597,3000000503,3000000507,3000000476,3000000669,3000000431,3000000892,3000000502,3000000567,3000000589,3000000553,3000000526,3000001156,3000000520,3000001123,3000001176,3000001065,3000000887,3000000883,3000001150,3000000966,3000000968,3000001015,3000000426,3000000988,3000000938,3000001019,3000001183,3000001140,3000000575,3000000496,3000000600,3000000987,3000001118,3000001125,3000000927,3000001152,3000001069,3000000617,3000000986,3000000976,3000001053,3000000838,3000000693,3000000449,3000000677,3000000639,3000000735,3000000582,3000000540,3000000585,3000000427,3000000652,3000000429,3000000543,3000000401,3000000719,3000000728,3000001170,3000000410,3000000996,3000001159,3000000560,3000000481,3000001008,3000000950,3000000545,3000000801,3000000586,3000000630,3000000732,3000000668,3000001048,3000000971,3000000773,3000000458,3000000428,3000000718,3000000480,3000000566,3000000664,3000000451,3000000675,3000000402,3000000425,3000000550,3000000475,3000001154,3000000868,3000001003,3000000681,3000000893,3000000614,3000000671]

        uis = UserInsurance.objects.filter(premium_transferred=False).order_by('id')
        for ui in uis:
            print(str(ui.id))
            ui.process_payout()
        return

        insurance_ids = [3000001183,3000001176]
        uis = UserInsurance.objects.filter(id__in=insurance_ids).order_by('id')
        for ui in uis:
            print('processing for '+str(ui.id))
            pms = PayoutMapping.objects.filter(object_id=ui.id, content_type_id=\
                ContentType.objects.get_for_model(ui).id).\
                exclude(payout__paid_to_id=settings.DOCPRIME_NODAL2_MERCHANT)
            for pm in pms:
                status = pm.payout.should_create_insurance_transaction()
                if status:
                    print('process money')
                    with transaction.atomic():
                        pm.payout.create_insurance_transaction()
                else:
                    print('dont process money')
        # print('hello')
        # mps = MerchantPayout.objects.filter(id__in=[1020956,1020957])
        # for mp in mps:
        #     mp.should_create_insurance_transaction()
        #return
        #UserInsurance.all_premiums_which_need_transfer()
        # ui = UserInsurance.objects.filter(id__in=[3000001144,3000001145,3000001146,3000001147,3000001148,3000001149,3000001151,3000001153,3000001155,3000001157,3000001158,3000001114,3000001115,3000001116,3000001117,3000001119,3000001120,3000001121,3000001124,3000001126,3000001127,3000001128,3000001129,3000001130,3000001131,3000001132,3000001133,3000001134,3000001135,3000001136,3000001137,3000001138,3000001139,3000001141,3000001142,3000001143,3000001160,3000001161,3000001162])
        # for u in ui:
        #     print(str(u.id))
        #     u.process_payout()