from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def doctor_spec_urls_temp_table():
    success = EntityUrls.create_doctor_spec_urls_temp_table()
    if success:
        print("Successfull")
    else:
        print("Failed")


class Command(BaseCommand):
    def handle(self, **options):
        doctor_spec_urls_temp_table()
