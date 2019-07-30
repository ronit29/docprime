from django.core.management.base import BaseCommand
# from ondoc.doctor.models import Doctor
# from ondoc.location.models import EntityUrls
from ondoc.location.services.doctor_urls import DoctorURL

# def doctor_search_urls_temp_table():
#     success = EntityUrls.doctor_search_urls()
#     if success:
#         print("Successfull")
#     else:
#         print("Failed")


def doctor_urls():
    url_creator = DoctorURL()
    url_creator.create()


class Command(BaseCommand):
    def handle(self, **options):
        doctor_urls()
        #doctor_search_urls_temp_table()
