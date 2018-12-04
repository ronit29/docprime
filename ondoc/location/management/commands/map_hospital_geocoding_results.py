from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import  GeocodingResults

def map_hospital_geocoding_results():
    all_hospitals = Hospital.objects.filter(is_live=True)

    print("Attempting for hospital. ", len(all_hospitals))

    for hospital in all_hospitals:
        if hospital.location:
            print(GeocodingResults.get_or_create(latitude=hospital.location.y, longitude=hospital.location.x, content_object=hospital), 'hospital_id: ', hospital.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_geocoding_results()