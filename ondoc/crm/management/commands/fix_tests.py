from ondoc.diagnostic.models import AvailableLabTest, LabTest
from django.db import transaction

class Command(BaseCommand):
    help = 'Fix test mapping'

    def handle(self, *args, **options):
        data= [(11542,11817),(11556,12235),(11557,12029),(11720,11719),(11727,11817),(11729,11719),(11738,11554),(11750,11896),(11781,12232),(11784,11868),(11786,12099),(11789,11863),(11792,11748),(11798,11547),(11803,12029),(11804,11933),(11823,12027),(11829,11719),(11836,12192),(11839,12181),(11842,11751),(11843,11752),(11846,12001),(11859,12148),(11866,11544),(11872,11586),(11878,12005),(11881,11819),(11890,11891),(11893,11892),(11894,11752),(11897,12021),(11899,11754),(11901,11748),(11918,11805),(11919,11807),(11925,11749),(11931,12178),(11932,11552),(11935,11721),(11936,11863),(11938,11805),(11939,12029),(11940,12032),(11941,12032),(11942,12029),(11994,11870),(12003,12013),(12012,11855),(12016,11863),(12026,11898),(12028,11550),(12036,11852),(12043,11554),(12047,12051),(12065,11826),(12086,12146),(12092,12096),(12093,12097),(12094,12096),(12095,12097),(12098,11951),(12120,12119),(12121,11558),(12149,12077),(12155,12044),(12180,12192),(12186,12029),(12188,12029),(12191,11791),(12234,11545),(12247,11545),(12248,11543)]
        with transaction.atomic():

            for x in data:
                original = x[0]
                new = x[1]
                existing_entries = AvailableLabTest.objects.filter(test_id=original)
                for ee in existing_entries:
                    duplicate = AvailableLabTest.objects.filter(test_id=new,\
                     lab_pricing_group_id=ee.lab_pricing_group_id).first()
                    if not duplicate:
                        new_entry = AvailableLabTest()
                        new_entry.mrp = ee.mrp
                        new_entry.computed_agreed_price = ee.computed_agreed_price
                        new_entry.computed_deal_price = ee.computed_deal_price
                        new_entry.test_id = new
                        new_entry.custom_deal_price = ee.custom_deal_price
                        new_entry.custom_agreed_price = ee.custom_agreed_price
                        new_entry.enabled = ee.enabled
                        new_entry.lab_pricing_group_id = ee.lab_pricing_group_id
                        #new_entry.save()

                    ee.enabled = False
                    #ee.save()    

            old_ids =  [x[0] for x in data]
            #LabTest.filter(id__in=old_ids).update(enabled=False)
