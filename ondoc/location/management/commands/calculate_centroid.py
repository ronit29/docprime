from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.contrib.contenttypes.models import ContentType
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls, EntityAddress
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance


def calculate_centroid():
    try:
        entity_addr_queryset = EntityAddress.objectEntityLos.filter(type__in=[EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY])
        for address in entity_addr_queryset:
            point_list = list()
            entity_location_relationships_qs = address.associated_relations.filter(valid=True).values('object_id', 'content_type')
            for entity_loc_relation in entity_location_relationships_qs:
                ct = ContentType.objects.get_for_id(entity_loc_relation['content_type'])
                obj = ct.get_object_for_this_type(pk=entity_loc_relation['object_id'])

                point_list.append(GEOSGeometry('POINT(%s %s)' % (obj.location.x, obj.location.y)))

            if len(point_list) > 3:
                point_list.append(point_list[0])
                p = Polygon(point_list)
                geo_poly = GEOSGeometry(p)
                print("Before ", address.centroid)
                address.centroid = geo_poly.centroid
                address.save()
                print("After ", address.centroid)
                print('Successfull for location ', address.value)
            else:
                print('Not sufficient point for location ', address.value)

    except Exception as e:
        print(str(e))


class Command(BaseCommand):
    def handle(self, **options):
        calculate_centroid()
