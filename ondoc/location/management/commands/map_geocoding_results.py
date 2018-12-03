from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, GeocodingResults

def map_geocoding_results():
    all_hospitals = Hospital.objects.filter(is_live=True)
    all_labs = Lab.objects.filter(is_live=True)

    print("Attempting for hospital. ", len(all_hospitals))
    print("Attempting for lab.", len(all_labs))

    for hospital in all_hospitals:
        if hospital.location:
            print(GeocodingResults.get_or_create(latitude=hospital.location.y, longitude=hospital.location.x, content_object=hospital), 'hospital_id: ', hospital.id)
            # if success:
            #     print("Successfull for hospital id ", hospital.id)
            # else:
            #     print("Failed for hospital id ", hospital.id)


    for lab in all_labs:
        if lab.location:
            print(GeocodingResults.get_or_create(latitude=lab.location.y, longitude=lab.location.x, content_object=lab), 'lab_id: ',lab.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_geocoding_results()