from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from ondoc.api.v1.utils import RawSql


def map_lab_location_urls():
    content_type = ContentType.objects.get(model='lab')
    if content_type:
        query = '''select distinct(l.id) from lab l inner join entity_location_relations elr on l.id = elr.object_id 
        and elr.content_type_id=%s and l.is_live=True and (ST_Distance(l.location, elr.entity_geo_location)>0 
        or elr.entity_geo_location is null) order by l.id'''

        result = RawSql(query, [content_type.id]).fetch_all()

        all_labs_id = list(map(lambda h: h.get('id', 0), result))
        all_labs = Lab.objects.filter(id__in=all_labs_id)

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
