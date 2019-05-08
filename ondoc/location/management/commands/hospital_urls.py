from django.core.management.base import BaseCommand
from ondoc.location.services.hospital_urls import HospitalURL


def hospital_urls():
    url_creator = HospitalURL()
    url_creator.create()


class Command(BaseCommand):
    def handle(self, **options):
        hospital_urls()
