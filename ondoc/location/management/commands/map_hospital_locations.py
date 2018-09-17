from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import EntityLocationRelationship
from django.contrib.gis.geos import Point

from django.contrib.gis.db.models.functions import Distance


def map_hospital_locations():
    all_hospitals = Hospital.objects.all().annotate(distance=Distance('location', Point(float(77.0694707),float(28.4502948), srid=4326))).order_by('distance')[:50]
    for hospital in all_hospitals:
        if hospital.data_status == 3:
            success = EntityLocationRelationship.create(latitude=hospital.location.y, longitude=hospital.location.x, content_object=hospital)
            if not success:
                break


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_locations()