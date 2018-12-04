from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import  GeocodingResults

def map_lab_geocoding_results():
    all_labs = Lab.objects.filter(is_live=True)

    print("Attempting for lab.", len(all_labs))

    for lab in all_labs:
        if lab.location:
            print(GeocodingResults.get_or_create(latitude=lab.location.y, longitude=lab.location.x, content_object=lab), 'lab_id: ',lab.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_lab_geocoding_results()