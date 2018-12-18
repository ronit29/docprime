from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import LabTest
from ondoc.location.models import EntityLocationRelationship, EntityUrls



def map_test_search_urls():
    success = EntityUrls.create_test_search_urls()
    if success:
        print("Successfull")
    else:
        print("Failed")

class Command(BaseCommand):
    def handle(self, **options):
        map_test_search_urls()
