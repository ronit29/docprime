from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship
from ondoc.doctor.models import Hospital
from django.contrib.contenttypes.models import ContentType

def map_hosp_entity_location_relations():
    content_type = ContentType.objects.get(model='hospital')
    # if content_type:
    #     id = content_type.id
    #object_ids = Hospital.objects.filter(is_live=True).values_list('id', flat=True)

    is_bulk_created = EntityLocationRelationship.hosp_entity_loc_rel(content_type=content_type)

    if is_bulk_created:
        print('success')
    else:
        print('failure')


class Command(BaseCommand):
    def handle(self, **options):
        map_hosp_entity_location_relations()
