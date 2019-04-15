from django.core.management.base import BaseCommand
from ondoc.location.services.hospital_urls import HospitalURL


class Command(BaseCommand):
    def handle(self, **options):
        url_creator = HospitalURL()
        url_creator.create()
