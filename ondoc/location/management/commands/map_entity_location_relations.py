from django.core.management.base import BaseCommand

from ondoc.doctor.models import Hospital
from ondoc.location.models import EntityAddress, EntityLocationRelationship
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import RawSql


def map_entity_location_relations():

    content_type = ContentType.objects.get(model='hospital')
    if content_type:
        id = content_type.id

    query = '''select h.id as object_id, ea.id as location_id, %s as content_type_id, type, h.location as entity_geo_location from entity_address ea
                inner join geocoding_results gs on ea.geocoding_id = gs.id inner join hospital h on 
                h.location = st_setsrid(st_point(gs.longitude, gs.latitude), 4326)::geography where h.is_live = True'''
    hosp_results = RawSql(query,[id]).fetch_all()
    hosp_results = [EntityLocationRelationship(**result) for result in hosp_results]
    EntityLocationRelationship.objects.bulk_create(hosp_results)

    content_type = ContentType.objects.get(model='lab')
    if content_type:
        id = content_type.id

    query = '''select l.id as object_id, ea.id as location_id, %s as content_type_id, type, l.location as entity_geo_location from entity_address ea
                inner join geocoding_results gs on ea.geocoding_id = gs.id inner join lab l on 
                l.location = st_setsrid(st_point(gs.longitude, gs.latitude), 4326)::geography where l.is_live=True'''
    lab_results = RawSql(query,[id]).fetch_all()
    lab_results = [EntityLocationRelationship(**result) for result in lab_results]
    EntityLocationRelationship.objects.bulk_create(lab_results)
    print('success')


class Command(BaseCommand):
    def handle(self, **options):
        map_entity_location_relations()