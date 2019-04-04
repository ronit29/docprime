from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare


def get_test_parameter():
    Thyrocare.get_test_parameter()


class Command(BaseCommand):
    def handle(self, **options):
        get_test_parameter()
