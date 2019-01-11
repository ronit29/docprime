from django.core.management.base import BaseCommand
from ondoc.location.services import service


def google_search_results():
    obj = service.SearchedDoctorData
    print(obj.find_doctor_data())


class Command(BaseCommand):
    def handle(self, **options):
        google_search_results()
