from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from ondoc.api.v1.utils import RawSql


def map_lab_location_urls():
    all_labs = Lab.objects.filter(is_live=True).all().annotate(distance=Distance('location', Point(float(77.0694707),float(28.4502948), srid=4326))).order_by('distance')[:5000]
    for lab in all_labs:
        if lab.location:
            success = EntityLocationRelationship.create(latitude=lab.location.y, longitude=lab.location.x, content_object=lab)
            if success:
                print("Successfull for labid ", lab.id)
            else:
                print("Failed for labid ", lab.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_lab_location_urls()
