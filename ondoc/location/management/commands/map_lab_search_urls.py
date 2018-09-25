from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance


def map_lab_search_urls():
    success = EntityUrls.create_lab_search_urls()
    if success:
        print("Successfull")
    else:
        print("Failed")

class Command(BaseCommand):
    def handle(self, **options):
        map_lab_search_urls()
