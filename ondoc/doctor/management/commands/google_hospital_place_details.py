from django.core.management.base import BaseCommand
from ondoc.doctor.models import HospitalPlaceDetails


def google_hospital_place_details():
    HospitalPlaceDetails.update_place_details()


class Command(BaseCommand):
    def handle(self, **options):
        google_hospital_place_details()
