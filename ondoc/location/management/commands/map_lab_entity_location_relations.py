from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship
from ondoc.diagnostic.models import Lab
from django.contrib.contenttypes.models import ContentType

def map_lab_entity_location_relations():

    content_type = ContentType.objects.get(model='lab')
    if content_type:
        id = content_type.id
    object_ids = Lab.objects.filter(is_live=True).values_list('id', flat=True)

    is_bulk_created = EntityLocationRelationship.lab_entity_loc_rel(content_type=content_type, object_ids=object_ids)

    if is_bulk_created:
        print('success')
    else:
        print('failure')

    # content_type = ContentType.objects.get(model='lab')
    # if content_type:
    #     id = content_type.id
    #
    # entity_location_qs = EntityLocationRelationship.objects.filter(
    #     content_type=content_type,
    #     object_id__in=Lab.objects.filter(is_live=True).values_list('id', flat=True))
    # if entity_location_qs:
    #     entity_location_qs.delete()
    #
    # query = '''select l.id as object_id, ea.id as location_id, %s as content_type_id, type, l.location as entity_geo_location from entity_address ea
    #             inner join geocoding_results gs on ea.geocoding_id = gs.id inner join lab l on
    #             l.location = st_setsrid(st_point(gs.longitude, gs.latitude), 4326)::geography where l.is_live=True'''
    # lab_results = RawSql(query,[id]).fetch_all()
    # lab_results = [EntityLocationRelationship(**result) for result in lab_results]
    # EntityLocationRelationship.objects.bulk_create(lab_results)

class Command(BaseCommand):
    def handle(self, **options):
        map_lab_entity_location_relations()
