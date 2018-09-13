from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def map_doctor_urls():
    all_doctors = Doctor.objects.all()
    for doctor in all_doctors:
        if doctor.data_status == 3:
            success = EntityUrls.create(doctor)
            print("success is", success)
            if not success:
                break


class Command(BaseCommand):
    def handle(self, **options):
        map_doctor_urls()
