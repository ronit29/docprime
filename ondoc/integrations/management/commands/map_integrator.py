from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare
from django.conf import settings


def map_integrators():
    obj_id = settings.THYROCARE_NETWORK_ID
    Thyrocare.thyrocare_product_data(obj_id, 'TESTS')
    Thyrocare.thyrocare_profile_data(obj_id, 'PROFILE')


class Command(BaseCommand):
    def handle(self, **options):
        map_integrators()