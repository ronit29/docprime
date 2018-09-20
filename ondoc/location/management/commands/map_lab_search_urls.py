from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance


def map_lab_search_urls():
    all_labs = Lab.objects.filter(is_live=True).all().annotate(distance=Distance('location', Point(float(77.0694707),float(28.4502948), srid=4326))).order_by('distance')[:50]
    for lab in all_labs:
        success = EntityUrls.create_search_urls(lab)
        if success:
            print("Successfull for ", lab.id)
        else:
            print("Failed for ", lab.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_lab_search_urls()
