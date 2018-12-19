from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def doctor_specialization_entity_urls():
    success = EntityUrls.create_doctor_specialization_entity_urls()
    if success:
        print("Successfull")
    else:
        print("Failed")


class Command(BaseCommand):
    def handle(self, **options):
        doctor_specialization_entity_urls()
