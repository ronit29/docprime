from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import LabPricingGroup, AvailableLabTest, Lab
from django.db import transaction


class Command(BaseCommand):
    help = 'Create lab pricing groups'

    @transaction.atomic
    def create_lab_pricing_groups(self, labs):
        for lab in labs:
            lab_pricing_group, created = LabPricingGroup.objects.get_or_create(
                group_name="{}-{}".format(lab.name, lab.id),
                pathology_agreed_price_percentage=lab.pathology_agreed_price_percentage,
                pathology_deal_price_percentage=lab.pathology_deal_price_percentage,
                radiology_agreed_price_percentage=lab.radiology_agreed_price_percentage,
                radiology_deal_price_percentage=lab.radiology_deal_price_percentage
            )
            AvailableLabTest.objects.filter(lab=lab).update(lab_pricing_group=lab_pricing_group)
            lab.lab_pricing_group = lab_pricing_group
            lab.save()

    def handle(self, *args, **options):
        lab_ids = AvailableLabTest.objects.all().values_list("lab").distinct()
        labs = Lab.objects.filter(id__in=lab_ids)
        self.create_lab_pricing_groups(labs)
