from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import EntityLocationRelationship


def map_hospital_locations():
    pass
    # all_hospitals = Hospital.objects.all()
    # for hospital in all_hospitals:
    #     if hospital.data_status == 3:
    #         success = EntityLocationRelationship.create(latitude=hospital.location.y, longitude=hospital.location.x, content_object=hospital)
    #         if not success:
    #             break


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_locations()