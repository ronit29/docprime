from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare
from ondoc.integrations.models import IntegratorMapping
from ondoc.diagnostic.models import AvailableLabTest, LabNetwork
from decimal import Decimal


def map_integrator_prices():
    integrator_mappings = IntegratorMapping.objects.filter(test__isnull=False, is_active=True)
    for integrator_mapping in integrator_mappings:
        lab_network_id = integrator_mapping.object_id
        lab_network_obj = LabNetwork.objects.filter(id=lab_network_id).first()
        if lab_network_obj:
            labs_under_network = lab_network_obj.lab.all()
            for lab in labs_under_network:
                pricing_group = lab.lab_pricing_group

                available_lab_test = AvailableLabTest.objects.filter(lab_pricing_group=pricing_group, test=integrator_mapping.test).first()
                integrator_test_price = integrator_mapping.integrator_product_data.get('rate', {}).get('b2c')
                if available_lab_test:
                    available_lab_test.supplier_price = Decimal(integrator_test_price)
                    available_lab_test.supplier_name =integrator_mapping.integrator_class_name
                    available_lab_test.save()


class Command(BaseCommand):
    def handle(self, **options):
        map_integrator_prices()