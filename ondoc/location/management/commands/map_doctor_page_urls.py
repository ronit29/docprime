from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def map_doctor_urls():
    all_doctors = Doctor.objects.filter(is_live=True).all()
    for doctor in all_doctors:
        success = EntityUrls.create_page_url(doctor)
        print("success is", success)
        if not success:
            print("Failed for id", doctor.id)



class Command(BaseCommand):
    def handle(self, **options):
        map_doctor_urls()
