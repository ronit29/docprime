from django.core.management.base import BaseCommand
from ondoc.doctor.models import  GoogleDetailing
from ondoc.doctor.service import get_doctor_detail_from_google, get_clinic_detail_from_google


def google_doctor_parser():
    for doctor in GoogleDetailing.objects.all().order_by('id'):
        success = get_doctor_detail_from_google(doctor)
        if success:
            print("Successfull for id ", doctor.id)
        else:
            print("Failed for id ", doctor.id)

        success = get_clinic_detail_from_google(doctor)
        if success:
            print("Successfull for id ", doctor.id)
        else:
            print("Failed for id ", doctor.id)


class Command(BaseCommand):
    def handle(self, **options):
        google_doctor_parser()
