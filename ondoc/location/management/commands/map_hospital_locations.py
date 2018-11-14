from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import EntityLocationRelationship
from django.contrib.gis.geos import Point
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db.models.functions import Distance
from ondoc.api.v1.utils import RawSql


def map_hospital_locations():
    content_type = ContentType.objects.get(model='hospital')
    if content_type:
        query = '''select distinct(h.id) from hospital h inner join entity_location_relations elr on h.id = elr.object_id 
        and elr.content_type_id=%d and h.is_live=True and (ST_Distance(h.location, elr.entity_geo_location)>0 
        or elr.entity_geo_location is null) order by h.id''' % content_type.id
        result = RawSql(query).fetch_all()

        all_hospitals_id = list(map(lambda h: h.get('id', 0), result))
        all_hospitals = Hospital.objects.filter(id__in=all_hospitals_id)

        print("Attempting for hospital. ", len(all_hospitals))

        for hospital in all_hospitals:
            if hospital.location:
                success = EntityLocationRelationship.create(latitude=hospital.location.y, longitude=hospital.location.x, content_object=hospital)
                if success:
                    print("Successfull for hospital id ", hospital.id)
                else:
                    print("Failed for hospital id ", hospital.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_locations()