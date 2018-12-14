from django.core.management.base import BaseCommand
from ondoc.location.models import GeocodingResults, EntityAddress
import json


def map_entity_address():
    geocoding_data = GeocodingResults.objects.all()
    for data in geocoding_data:
        value = None
        value = json.loads(data.value)
        print(EntityAddress.create(data, value))


class Command(BaseCommand):
    def handle(self, **options):
        map_entity_address()