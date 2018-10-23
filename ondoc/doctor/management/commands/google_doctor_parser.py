from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorPlaceSheet
from ondoc.doctor.service import get_doctor_detail_from_google

def google_doctor_parser():
    for doctor in DoctorPlaceSheet.objects.all():
        success = get_doctor_detail_from_google(doctor)
        if success:
            print("Successfull")
        else:
            print("Failed")

class Command(BaseCommand):
    def handle(self, **options):
        google_doctor_parser()
