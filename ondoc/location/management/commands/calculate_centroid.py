from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, LineString, Polygon
from ondoc.location.models import EntityAddress


def new_calculate_centroid(ea):
    if ea:
        childs = EntityAddress.objects.filter(parent=ea.id)

        if len(childs) == 0:
            if ea.centroid:
                return ea.centroid
            if not ea.centroid:
                return None

        ea.no_of_childs = len(childs)
        points = []
        for x in childs:
            point = new_calculate_centroid(x)
            if point:
                points.append(point)

        calculated_centroid = None
        if len(points) == 1:
            calculated_centroid = points[0]
        elif len(points) == 2:
            p = LineString(points)
            geo_poly = GEOSGeometry(p)
            calculated_centroid = geo_poly.centroid
        elif len(points) > 2:
            points.append(points[0])
            p = Polygon(points)
            if p.area == 0:
                p = LineString(points)
            geo_poly = GEOSGeometry(p)
            calculated_centroid = geo_poly.centroid
        ea.centroid = calculated_centroid
        ea.save()
        return calculated_centroid

# def calculate_centroid():
#     try:
#         entity_addr_queryset = EntityAddress.objects.filter(type__in=[EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY])
#         for address in entity_addr_queryset:
#             point_list = list()
#             entity_location_relationships_qs = address.associated_relations.filter(valid=True).values('object_id', 'content_type')
#             for entity_loc_relation in entity_location_relationships_qs:
#                 ct = ContentType.objects.get_for_id(entity_loc_relation['content_type'])
#                 obj = ct.get_object_for_this_type(pk=entity_loc_relation['object_id'])
#
#                 point_list.append(GEOSGeometry('POINT(%s %s)' % (obj.location.x, obj.location.y)))
#
#             if len(point_list) > 3:
#                 point_list.append(point_list[0])
#                 p = Polygon(point_list)
#                 geo_poly = GEOSGeometry(p)
#                 print("Before ", address.centroid)
#                 address.centroid = geo_poly.centroid
#                 address.save()
#                 print("After ", address.centroid)
#                 print('Successfull for location ', address.value)
#             else:
#                 print('Not sufficient point for location ', address.value)
#
#     except Exception as e:
#         print(str(e))


class Command(BaseCommand):
    def handle(self, **options):
        # ea_id = 4729
        countries = EntityAddress.objects.filter(type_blueprint='COUNTRY')
        if countries:
            for country in countries:
                new_calculate_centroid(country)
        else:
            print('error: object not found')

