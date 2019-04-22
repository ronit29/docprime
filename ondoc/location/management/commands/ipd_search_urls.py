from django.core.management.base import BaseCommand
from ondoc.location.services.doctor_urls import IpdProcedure


class Command(BaseCommand):
    def handle(self, **options):
        ipd_procedure = IpdProcedure()
        ipd_procedure.create()
