from django.core.management.base import BaseCommand
from ondoc.procedure.models import IpdProcedure


class Command(BaseCommand):
    def handle(self, **options):
        IpdProcedure.update_ipd_seo_urls()

