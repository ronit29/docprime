from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship
from ondoc.diagnostic.models import Lab
from django.contrib.contenttypes.models import ContentType

def map_lab_entity_location_relations():

    content_type = ContentType.objects.get(model='lab')
    # if content_type:
    #     id = content_type.id
    #object_ids = Lab.objects.filter(is_live=True).values_list('id', flat=True)

    is_bulk_created = EntityLocationRelationship.lab_entity_loc_rel(content_type=content_type)

    if is_bulk_created:
        print('success')
    else:
        print('failure')

class Command(BaseCommand):
    def handle(self, **options):
        map_lab_entity_location_relations()
