from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.location.models import EntityUrls


def specialization_search_urls():
    print(EntityUrls.create_specialization_search_urls())



class Command(BaseCommand):
    def handle(self, **options):
        specialization_search_urls()
