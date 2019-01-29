from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare


def map_integrators():
    obj_id = 1
    Thyrocare.thyrocare_product_data(obj_id, 'TESTS')
    Thyrocare.thyrocare_profile_data(obj_id, 'PROFILE')


class Command(BaseCommand):
    def handle(self, **options):
        map_integrators()