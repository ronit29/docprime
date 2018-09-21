from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def map_doctor_search_urls():
    success = EntityUrls.create_doctor_search_urls()
    if success:
        print("Successfull")
    else:
        print("Failed")


class Command(BaseCommand):
    def handle(self, **options):
        map_doctor_search_urls()
