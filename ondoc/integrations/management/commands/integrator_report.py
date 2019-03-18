from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare
from django.conf import settings


def integrator_reports():
    Thyrocare.get_generated_report()


class Command(BaseCommand):
    def handle(self, **options):
        integrator_reports()