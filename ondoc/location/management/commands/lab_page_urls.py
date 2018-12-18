from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls, LabPageUrl
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from ondoc.api.v1.utils import RawSql


def map_lab_location_urls():
    query = '''select nextval('entity_url_version_seq') as inc'''
    seq = RawSql(query,[]).fetch_all()
    sequence = seq[0]['inc']

    all_labs = Lab.objects.filter(is_live=True).all().annotate(distance=Distance('location', Point(float(77.0694707),float(28.4502948), srid=4326))).order_by('distance')
    for lab in all_labs:
        print(LabPageUrl.create_lab_page_urls(lab, sequence))
    EntityUrls.objects.filter(sitemap_identifier='LAB_PAGE', sequence__lt=sequence).update(is_valid=False)




class Command(BaseCommand):
    def handle(self, **options):
        map_lab_location_urls()