from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, LineString, Polygon
from ondoc.location.models import EntityAddress
from ondoc.api.v1.utils import RawSql

def new_calculate_centroid(ea):

    if ea.centroid:
        return ea.centroid

    childs = EntityAddress.objects.filter(parent=ea.id)
    ea.no_of_childs = len(childs)

    if len(childs) == 0:
        if ea.abs_centroid:
            ea.centroid = ea.abs_centroid
            ea.save()
            return ea.centroid
        elif not ea.abs_centroid:
            ea.save()
            return None

    points = []
    for child in childs:
        point = new_calculate_centroid(child)
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


# class Command(BaseCommand):
#     def handle(self, **options):
#         EntityAddress.objects.all().update(centroid=None)
#         ea_objs = EntityAddress.objects.all().order_by('-order')
#         if ea_objs:
#             for ea_obj in ea_objs:
#                 try:
#                     new_calculate_centroid(ea_obj)
#                     print('success: ' + str(ea_obj.value) + '(' + str(ea_obj.id) + ')')
#                 except Exception as e:
#                     print(str(e))
#         else:
#             print('error: objects not found')

class Command(BaseCommand):

    def handle(self, **options):

        RawSql("update entity_address set centroid=null", []).execute()

        max_order = RawSql('select max("order") from entity_address', []).fetch_all()
        if max_order:
           max_order = max_order[0]['max']
           print(max_order)
        else:
            print("error")
            return 

        #for all addresses with no child
        RawSql("update entity_address set centroid=abs_centroid, child_count=1 where id not in (select parent_id from \
            entity_address where parent_id is not null)", []).execute()

        current_order = max_order
        while current_order >=1:
            print("running for "+str(current_order))

            RawSql("update entity_address ea set centroid = (select ST_Centroid(ST_Union(centroid::geometry)) "
                   "from entity_address where parent_id=ea.id and centroid is not null), "
                   "child_count = (select sum(child_count)+1 from entity_address where parent_id=ea.id) " \
                    "where ea.order=%s and (select count(*) from entity_address where parent_id=ea.id and " \
                    "centroid is not null)>0",[current_order]).execute()

            current_order -= 1

        RawSql('''update entity_address e set centroid = ( select
                st_setsrid(st_point(cl.longitude, cl.latitude),4326)::geography as city_centroid
                from  city_lat_long cl where lower(e.alternative_value)  = lower(cl.city) ) where e.id in (select ea.id 
                        from entity_address ea inner join city_lat_long cll 
                    on lower(ea.alternative_value)  = lower(cll.city) and ea.type = 'LOCALITY' )''', []).execute()

