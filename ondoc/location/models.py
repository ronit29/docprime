from django.contrib.gis.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from .service import get_meta_by_latlong
import logging
import json
from decimal import Decimal
from ondoc.doctor import models as doc_models
from ondoc.authentication.models import TimeStampedModel
from django.contrib.gis.geos import Point, GEOSGeometry
from django.template.defaultfilters import slugify
import datetime
from django.contrib.postgres.fields import JSONField
from ondoc.api.v1.utils import RawSql
from ondoc.common.helper import Choices
from django.db.models import Q
import requests
from rest_framework import status
from django.conf import settings
from django.db import transaction
from collections import OrderedDict
import re
from django.contrib.postgres.fields import ArrayField
from django.db.models import Prefetch
from django.db import transaction


logger = logging.getLogger(__name__)


def split_and_append(initial_str, spliter, appender):
    value_chunks = initial_str.split(spliter)
    return appender.join(value_chunks)

class TempURL(TimeStampedModel):

    url = models.CharField(blank=False, null=True, max_length=2000, db_index=True)
    url_type = models.CharField(max_length=24, null=True)
    entity_type = models.CharField(max_length=24, null=True)
    search_slug = models.CharField(max_length=1000, null=True)
    extras = JSONField(null=True)
    breadcrumb = JSONField(null=True)
    entity_id = models.PositiveIntegerField(null=True, default=None)
    is_valid = models.BooleanField(default=True)
    count = models.IntegerField(max_length=30, null=True, default=0)
    sitemap_identifier = models.CharField(max_length=28, null=True)
    sequence = models.PositiveIntegerField(default=0, null=True)
    locality_latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    locality_longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    sublocality_value = models.TextField(default='', null=True)
    locality_value = models.TextField(default='', null=True)
    sublocality_latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8, blank=True)
    sublocality_longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8, blank=True)
    locality_id = models.PositiveIntegerField(default=None,null=True)
    sublocality_id = models.PositiveIntegerField(default=None, null=True)
    specialization = models.TextField(default='', null=True)
    specialization_id = models.PositiveIntegerField(default=None, null=True)
    ipd_procedure = models.TextField(default='', null=True)
    ipd_procedure_id = models.PositiveIntegerField(default=None, null=True)
    locality_location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    sublocality_location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)

    class Meta:
        db_table='temp_url'


class GoogleSearches(TimeStampedModel):
    search_keywords = models.CharField(max_length=200, null=False, blank=False)
    results = JSONField()
    count = models.PositiveIntegerField(default=None, null=True)

    class Meta:
        db_table = 'google_search'


class GoogleSearchEntry(TimeStampedModel):
    place_id = models.TextField()
    place_result = JSONField()
    doctor_details = JSONField()
    place_search = models.ManyToManyField(GoogleSearches, through='GoogleResult',
                                          through_fields=('place_entry','search_results'),
                                          related_name='assoc_search_results',
                                          )

    class Meta:
        db_table = 'google_search_place_entry'


class GoogleResult(TimeStampedModel):
    place_entry = models.ForeignKey(GoogleSearchEntry, on_delete=models.CASCADE, related_name='google_place_details')
    search_results = models.ForeignKey(GoogleSearches, on_delete=models.CASCADE, related_name='google_search_details')

    class Meta:
        db_table = 'google_results'


class GeocodingResults(TimeStampedModel):

    geocodine_cache = None

    value = models.TextField()
    #latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    #longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    latitude = models.CharField(max_length=200, blank=True, null=True)
    longitude = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'geocoding_results'

    @classmethod
    def get_location_dict(cls):

        if not cls.geocodine_cache:
            gr = GeocodingResults.objects.values('latitude', 'longitude')
            results = {}
            for x in gr:
                key = cls.get_key(x.get('latitude'), x.get('longitude'))
                results[key] = True
            cls.geocodine_cache = results


        return cls.geocodine_cache

    @classmethod
    def get_key(cls, latitude, longitude):

        latitude = str(latitude)
        longitude = str(longitude)
        return latitude+'-'+longitude

    @classmethod
    def create_results(cls, *args, **kwargs):

        from .models import GeocodingResults

        latitude = kwargs.get('latitude')
        longitude = kwargs.get('longitude')
        id = kwargs.get('id')
        type = kwargs.get('type')

        key = cls.get_key(latitude, longitude)

        exists = cls.get_location_dict().get(key)

        #saved_json = GeocodingResults.objects.filter(latitude=kwargs.get('latitude'), longitude=kwargs.get('longitude'))

        if not exists:
            saved_json = GeocodingResults.objects.filter(latitude=latitude, longitude=longitude)
            if saved_json:
                cls.geocodine_cache[key]=True
                exists = True

        if not exists:
            cls.geocodine_cache[key]=True

            response = requests.get('https://maps.googleapis.com/maps/api/geocode/json?sensor=false',
                                    params={'latlng': '%s,%s' % (kwargs.get('latitude'), kwargs.get('longitude')),
                                            'key': settings.REVERSE_GEOCODING_API_KEY, 'language': 'en'})

            if response.status_code != status.HTTP_200_OK or not response.ok:
                #logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
                #logger.info("[ERROR] %s", response.reason)
                #print('google api failed for en' + str(response.reason))
                print(response.json())
                print('api failure: ' + type + '-'
                        + str(id)
                        + ', status_code: ' + str(response.status_code)
                        + ', reason: ' + str(response.reason))

            resp_data = response.json()

            if resp_data.get('error_message'):
                print(resp_data)

            if resp_data.get('status', None) == 'OK' and isinstance(resp_data.get('results'), list) and \
                    len(resp_data.get('results')) > 0:
                geo_result = GeocodingResults(value=json.dumps(resp_data), latitude=kwargs.get('latitude'), longitude= kwargs.get('longitude')).save()
            else:
                #print(' google api return invalid addresses ')
                # logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
                # logger.info("[ERROR] %s", response.reason)
                print('data not found: ' + type + '-'
                        + str(id)
                        + ', status_code: ' + str(response.status_code)
                        + ', reason: ' + str(response.reason))

        return ('success: ' + type + '-'
                        + str(id))


class CityInventory(TimeStampedModel):

    city = models.TextField()
    rank = models.PositiveIntegerField(null=True, default=0)

    class Meta:
        db_table = 'seo_cities'


class EntityAddress(TimeStampedModel):

    class AllowedKeys(Choices):
        LOCALITY = 'LOCALITY'
        SUBLOCALITY = 'SUBLOCALITY'
        ADMINISTRATIVE_AREA_LEVEL_1 = 'ADMINISTRATIVE_AREA_LEVEL_1'
        ADMINISTRATIVE_AREA_LEVEL_2 = 'ADMINISTRATIVE_AREA_LEVEL_2'
        COUNTRY = 'COUNTRY'

    type = models.CharField(max_length=128, blank=True, null=True, choices=AllowedKeys.as_choices())
    value = models.TextField()
    alternative_value = models.TextField(default='', null=True)
    address = models.TextField(max_length=2000, blank=True, null=True)
    components = ArrayField(models.TextField(), null=True)

    type_blueprint = models.CharField(max_length=128, blank=False, null=True)
    postal_code = models.PositiveIntegerField(null=True)
    #parent = models.IntegerField(null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, db_constraint=False)
    centroid = models.PointField(geography=True, srid=4326, blank=True, null=True)
    abs_centroid = models.PointField(geography=True, srid=4326, blank=True, null=True)
    #geocoding = models.ForeignKey(GeocodingResults, null=True, on_delete=models.DO_NOTHING)
    no_of_childs = models.PositiveIntegerField(default=0, null=True)
    child_count = models.PositiveIntegerField(default=None, null=True)
    use_in_url = models.BooleanField(verbose_name='Use in URL', default=False)
    order = models.PositiveIntegerField(default=None, null=True)
    search_slug = models.CharField(max_length=256, blank=True, null=True)
    geocoding = models.ManyToManyField(
        GeocodingResults,
        through='AddressGeoMapping',
        through_fields=('entity_address', 'geocoding_result'),
        related_name='entity_addresses',
    )

    @classmethod
    def unique_components(cls, components):
        if not components:
            return []

        seen, result = set(), []
        for item in components:
            processed = cls.to_aplhanumeric(item.lower())
            if processed not in seen:
                seen.add(processed)
                result.append(item)
        return result

    @classmethod
    def to_aplhanumeric(cls , text):
        pattern = re.compile('[\W_]+')
        return pattern.sub('', text)
    
    @classmethod
    def use_address_in_url(cls, type, name, parent_entity=None):

        if not type:
            return False
        if not cls.is_english(name):
            return False

        if parent_entity and parent_entity.use_in_url and not cls.is_english(parent_entity.alternative_value):
            return False

        use_in_url = True
        if not type.startswith('LOCALITY') and not type.startswith('SUBLOCALITY'):
            use_in_url = False

        if type.startswith('LOCALITY') and parent_entity.use_in_url:
            use_in_url = False

        if type.startswith('SUBLOCALITY') and (not parent_entity or not parent_entity.use_in_url\
            or not parent_entity.type or not parent_entity.type.startswith('LOCALITY')):
            use_in_url = False

        if name in ('[no name]', 'Unnamed Road'):
            use_in_url = False
        # if use_in_url and parent_entity and parent_entity.use_in_url \
        #     and parent_entity.type and parent_entity.type.startswith('SUBLOCALITY'):
        #     use_in_url = False

        return use_in_url

    @classmethod
    def get_search_url_slug(cls, type, name, parent_entity=None):
        if not type:
            return False

        text = None    

        if type.startswith('LOCALITY'):
            text = name
        elif type and parent_entity and parent_entity.type:
            if type.startswith('SUBLOCALITY') and parent_entity.type.startswith('LOCALITY'):
                text = name+' '+parent_entity.alternative_value

        if text:
            return slugify(text)

        return None

    @classmethod
    def is_english(cls, text):
        if not text:
            return False
        try:
            text.encode(encoding='utf-8').decode('ascii')
        except UnicodeDecodeError:
            return False
        else:
            return True


    @classmethod
    def create(cls, geocoding_obj, value):
        mapping_dictionary = {
            'bengaluru': 'Bangalore',
            'bengalooru': 'Bangalore',
            'gurugram': 'Gurgaon',
            'gurugram rural': 'Gurgaon'
        }

        response_list = list()
        longitude = geocoding_obj.longitude
        latitude = geocoding_obj.latitude

        # Take the address component with longest length as it can provide us the most relevant address.
        max_length = 0
        address_component = None
        # result_value.get('results')[00].get('address_components')
        if value.get('results'):
            result_list = value.get('results')
        for result in result_list:
            if len(result.get('address_components', [])) > max_length:
                address_component = result.get('address_components')
                max_length = len(result.get('address_components'))

        if not address_component:
            return response_list

        system_types = ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2', 'LOCALITY', 'SUBLOCALITY',
                     'SUBLOCALITY_LEVEL_1', 'SUBLOCALITY_LEVEL_2', 'SUBLOCALITY_LEVEL_3']

        pin_code = None
        parent_id = None
        parent_entity = None

        order = 1
        address_component.reverse()
        save_location = False

        for component in address_component:

            long_name = component.get('long_name')
            types = [key.upper() for key in component.get('types', [])]
            type_blueprint = ",".join(types)
            use_in_url = False

            if 'POSTAL_CODE' in types:
                pin_code = long_name
                continue

            selected_type = None
            for st in system_types:
                for tp in types:
                    if st==tp:
                        selected_type = st
            if selected_type and selected_type.startswith('SUBLOCALITY'):
                selected_type = 'SUBLOCALITY'

            if (selected_type and selected_type.startswith('SUBLOCALITY')) or (parent_entity and parent_entity.type and
                parent_entity.type.startswith('LOCALITY')):
                save_location = True

            postal_code = None
            if save_location:
                postal_code = pin_code

            saved_data = EntityAddress.objects.filter(type=selected_type, value=long_name, parent=parent_id)
            if len(saved_data) > 0:
                entity_address = saved_data[0]                
                AddressGeoMapping.objects.get_or_create(entity_address=entity_address, geocoding_result=geocoding_obj)
            else:
                point = None
                if save_location:                    
                    point = Point(float(longitude), float(latitude))

                alternative_name = mapping_dictionary.get(long_name.lower(), long_name)
                #address = alternative_name
                components = [alternative_name]

                if parent_entity and parent_entity.components:
                    #components.append(parent_entity.components)
                    components = components + parent_entity.components

                #print(components)
                components = cls.unique_components(components)
                address = ", ".join(components)
                use_in_url = cls.use_address_in_url(selected_type, alternative_name, parent_entity)
                search_slug = None
                if use_in_url:
                    search_slug = cls.get_search_url_slug(selected_type, alternative_name, parent_entity)
                #print(use_in_url)

                entity_address = EntityAddress(type=selected_type, abs_centroid=point, postal_code=postal_code,
                                                   type_blueprint=type_blueprint, value=long_name, parent=parent_entity,
                                                   alternative_value=alternative_name,
                                                   order=order, use_in_url=use_in_url,
                                                   address=address, components = components,
                                                   search_slug = search_slug)
                entity_address.save()
                AddressGeoMapping.objects.get_or_create(entity_address=entity_address, geocoding_result=geocoding_obj)
                #entity_address.geocoding..add(geocoding_obj)
                

            parent_id = entity_address.id
            parent_entity = entity_address
            order += 1


        return "success"



            # if entity_address.type in ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2',
            #                            'LOCALITY', 'SUBLOCALITY']:
            #    ea_list.append(entity_address)
        # if ea_list:
        #     return "success"
        # else:
        #     return "failure"

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        mapping_dictionary = {
            'bengaluru': 'Bangalore',
            'bengalooru': 'Bangalore',
            'gurugram': 'Gurgaon',
            'gurugram rural': 'Gurgaon'
        }

        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
        geocoding_qs = GeocodingResults.objects.filter(latitude=kwargs.get('latitude'), longitude=kwargs.get('longitude'))
        if not kwargs.get('content_object', None):
            raise ValueError('Missing parameter: content_object')

        parent_id = None
        postal_code = None
        ea_list = list()

        for meta in meta_data:
            point = None
            if meta['key'] in cls.AllowedKeys.availabilities():
                if meta['key'].startswith('SUBLOCALITY'):
                    postal_code = meta['postal_code']
                if meta['key'] not in [cls.AllowedKeys.COUNTRY, cls.AllowedKeys.ADMINISTRATIVE_AREA_LEVEL_1,
                                       cls.AllowedKeys.ADMINISTRATIVE_AREA_LEVEL_2]:
                    point = Point(kwargs.get('longitude'), kwargs.get('latitude'))
                saved_data = cls.objects.filter(type=meta['key'], postal_code=postal_code, type_blueprint=meta['type'], value=meta['value'], parent=parent_id)
                if len(saved_data) == 1:
                    entity_address = saved_data[0]
                    parent_id = entity_address.id
                elif len(saved_data) == 0:
                    alternative_name = mapping_dictionary.get(meta['value'].lower()) if mapping_dictionary.get(meta['value'].lower(), None) else meta['value']
                    geocoding_obj = geocoding_qs.first() if geocoding_qs.exists() else None
                    entity_address = cls(type=meta['key'], centroid=point, postal_code=postal_code,
                                         type_blueprint=meta['type'], value=meta['value'], parent=parent_id,
                                         alternative_value=alternative_name, geocoding=geocoding_obj)
                    entity_address.save()
                    parent_id = entity_address.id

            if entity_address.type in ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2', 'LOCALITY', 'SUBLOCALITY']:
                ea_list.append(entity_address)

        return ea_list

    class Meta:
        db_table = 'entity_address'


class AddressGeoMapping(TimeStampedModel):
    entity_address = models.ForeignKey(EntityAddress, on_delete=models.CASCADE, related_name='address_geos')
    geocoding_result = models.ForeignKey(GeocodingResults, on_delete=models.CASCADE, related_name='geo_addresses')
    class Meta:
        db_table = "address_geo_mapping"
        unique_together = (('entity_address', 'geocoding_result', ),)


class EntityLocationRelationship(TimeStampedModel):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    #valid = models.BooleanField(default=True)
    location = models.ForeignKey(EntityAddress, related_name='associated_relations', on_delete=models.CASCADE)
    type = models.CharField(max_length=128, blank=True, null=True, choices=EntityAddress.AllowedKeys.as_choices())
    entity_geo_location = models.PointField(geography=True, srid=4326, blank=True, null=True)

    @classmethod
    def create(cls, *args, **kwargs):
        try:
            entity_location_qs = cls.objects.filter(
                content_type=ContentType.objects.get_for_model(kwargs.get('content_object')),
                object_id=kwargs.get('content_object').id)

            # Deleting all the records in this table for provided hospital or lab. As all will be created
            # again when we will call map_hospital_locations or map_lab_page_urls.

            entity_location_qs.delete()

            ea_list = EntityAddress.get_or_create(**kwargs)
            if len(ea_list) >= 1:
                for ea in ea_list:
                    entity_location_relation = cls(content_object=kwargs.get('content_object'), type=ea.type,
                                                   location=ea, entity_geo_location=kwargs.get('content_object').location)
                    entity_location_relation.save()
            return True
        except Exception as e:
            print(str(e))
            return False

    @transaction.atomic
    def lab_entity_loc_rel(**kwargs):
        #try:
        content_type = kwargs.get('content_type')
        if content_type:
            content_type_id = content_type.id
        #object_ids = kwargs.get('object_ids')
        entity_location_qs = EntityLocationRelationship.objects.filter(content_type=content_type).delete()
        # if entity_location_qs:
        #     entity_location_qs.delete()
        print(str(content_type_id))
        query = '''insert into entity_location_relations(object_id, location_id, content_type_id, type, entity_geo_location, created_at, updated_at) 
                    select l.id as object_id, ea.id as location_id,
                     %s as content_type_id, type,  l.location as entity_geo_location, now(), now()
                    from lab l inner join geocoding_results gs on 
                    st_x(l.location::geometry)::text=gs.longitude and st_y(l.location::geometry)::text=gs.latitude
                     and l.is_live = True 
                     inner join address_geo_mapping agm on agm.geocoding_result_id = gs.id
                     inner join entity_address ea on agm.entity_address_id = ea.id 
                     order by l.id, ea.order '''
        results = RawSql(query, [content_type_id]).execute()
        #results = [EntityLocationRelationship(**result) for result in results]
        #EntityLocationRelationship.objects.bulk_create(results)
        return True
        #except Exception as e:
        #return False

    @transaction.atomic
    def hosp_entity_loc_rel(**kwargs):
        #try:
        content_type = kwargs.get('content_type')
        if content_type:
            content_type_id = content_type.id
        else:
            return False

        #object_ids = kwargs.get('object_ids')
        entity_location_qs = EntityLocationRelationship.objects.filter(content_type=content_type).delete()
        # if entity_location_qs:
        #     entity_location_qs.delete()
        query = '''insert into entity_location_relations(object_id, location_id, content_type_id, type, entity_geo_location, created_at, updated_at) 
                    select h.id as object_id, ea.id as location_id,
                     %s as content_type_id, type,  h.location as entity_geo_location, now(), now()
                    from hospital h inner join geocoding_results gs on 
                    st_x(h.location::geometry)::text=gs.longitude and st_y(h.location::geometry)::text=gs.latitude
                     and h.is_live = True 
                     inner join address_geo_mapping agm on agm.geocoding_result_id = gs.id
                     inner join entity_address ea on agm.entity_address_id = ea.id 
                     order by h.id, ea.order 
'''
        results = RawSql(query, [content_type_id]).execute()
        #results = [EntityLocationRelationship(**result) for result in results]
        #EntityLocationRelationship.objects.bulk_create(results)
        return True
        # except Exception as e:
        #     print(str(e))
        #     return False

    class Meta:
        db_table = 'entity_location_relations'


class EntityUrls(TimeStampedModel):
    class SitemapIdentifier(Choices):
        SPECIALIZATION_LOCALITY_CITY = 'SPECIALIZATION_LOCALITY_CITY'
        SPECIALIZATION_CITY = 'SPECIALIZATION_CITY'
        DOCTORS_LOCALITY_CITY = 'DOCTORS_LOCALITY_CITY'
        DOCTORS_CITY = 'DOCTORS_CITY'
        DOCTOR_PAGE = 'DOCTOR_PAGE'
        LAB_TEST = 'LAB_TEST'

        LAB_LOCALITY_CITY = 'LAB_LOCALITY_CITY'
        LAB_CITY = 'LAB_CITY'
        LAB_PAGE = 'LAB_PAGE'

    class UrlType(Choices):
        PAGEURL = 'PAGEURL'
        SEARCHURL = 'SEARCHURL'

    url = models.CharField(blank=False, null=True, max_length=2000, db_index=True)
    url_type = models.CharField(max_length=24, choices=UrlType.as_choices(), null=True)
    entity_type = models.CharField(max_length=24, null=True)
    extras = JSONField(null=True)
    breadcrumb = JSONField(null=True)
    entity_id = models.PositiveIntegerField(null=True, default=None)
    is_valid = models.BooleanField(default=True)
    count = models.IntegerField(max_length=30, null=True, default=0)
    sitemap_identifier = models.CharField(max_length=28, null=True, choices=SitemapIdentifier.as_choices())
    sequence = models.PositiveIntegerField(default=0)
    locality_latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    locality_longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    sublocality_value = models.TextField(default='', null=True)
    locality_value = models.TextField(default='', null=True)
    sublocality_latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8, blank=True)
    sublocality_longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8, blank=True)
    locality_id = models.PositiveIntegerField(default=None,null=True)
    sublocality_id = models.PositiveIntegerField(default=None, null=True)
    specialization = models.TextField(default='', null=True)
    specialization_id = models.PositiveIntegerField(default=None, null=True)
    ipd_procedure = models.TextField(default='', null=True)
    ipd_procedure_id = models.PositiveIntegerField(default=None, null=True)
    locality_location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    sublocality_location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)

    def __str__(self):
        return self.url


    @property
    def additional_info(self):
        return self.extras

    @classmethod
    def create_test_search_urls(cls):

        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query, []).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier in ('LAB_TEST')'''

        query = '''insert into entity_urls( sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, 
                       updated_at, sequence, extras, entity_id)

                    select   x.sitemap_identifier as sitemap_identifier, x.url as url, 
                    x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid as id_valid, 
                    x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence, x.extras as extras,
                    x.entity_id as entity_id
                    from
                    (
                    select getslug(concat(name, '-lbtst'))as url,  True as is_valid ,0 as count, id as entity_id, 'PAGEURL' as url_type, 'Test' as entity_type,
                    'LAB_TEST' as sitemap_identifier, NOW() as created_at, NOW() as updated_at, %d as sequence, json_build_object('test',name) as extras
                    from
                    (
                    select id, name from lab_test
                    )as data
                    ) as x''' % (sequence)
        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute(update_query)
                cursor.execute(query)
            except Exception as e:
                print(str(e))
                return False

        return True

    def create_doctor_specialization_entity_urls():
        query = '''insert into entity_urls(specialization_id, specialization, sequence,extras, sitemap_identifier, url, count, entity_type, 
                        url_type,  created_at, 
                        updated_at,  sublocality_latitude, sublocality_longitude, locality_latitude, 
                        locality_longitude, locality_id, sublocality_id,
                        locality_value, sublocality_value, is_valid, locality_location, sublocality_location, location)

                        select a.specialization_id, a.specialization, a.sequence, a.extras, a.sitemap_identifier,
                         getslug(a.url) as url, a.count, a.entity_type,
                         a.url_type, now() as created_at, now() as updated_at,
                         a.sublocality_latitude, a.sublocality_longitude, a.locality_latitude, a.locality_longitude,
                         a.locality_id, a.sublocality_id, a.locality_value, a.sublocality_value, a.is_valid, 
                         a.locality_location, a.sublocality_location, a.location
                        from ( select  sdu.*, ea.child_count, ROW_NUMBER() over 
                        (partition by sdu.url order by ea.child_count desc, sdu.count desc ) as row_number
                        from seo_doctor_specialization_search sdu inner join entity_address ea on 
                        case when sdu.sublocality_id is not null then sdu.sublocality_id else sdu.locality_id end = ea.id ) a
                        where row_number=1 '''

        sequence_query = '''select sequence from seo_doctor_specialization_search limit 1 '''

        sequence = RawSql(sequence_query, []).fetch_all()

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier 
                                  in ('SPECIALIZATION_LOCALITY_CITY', 'SPECIALIZATION_CITY') and sequence< %d''' % \
                       sequence[0].get(
                           'sequence')

        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute(query)
                cursor.execute(update_query)
            except Exception as e:
                print(str(e))
                return False

        return True

    def create_doctor_search_urls_temp_table():
        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query, []).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

        create_temp_table_query = '''create table seo_doctor_search_urls as
                    select max(ST_Distance(ea.centroid,h.location)) as distance,
                    ea.alternative_value, ea.search_slug, null::json as extras , null::geography as sublocality_location,  
                    null::geography as locality_location, null::geography as location,
                    case when ea.type = 'SUBLOCALITY' then 
                    getslug(concat('doctors-in-', ea.search_slug, '-sptlitcit'))
                    else getslug(concat('doctors-in-', ea.search_slug, '-sptcit'))
                    end as url, ea.type, count(distinct d.id) as count,
                    case when ea.type = 'SUBLOCALITY' then 
                    ea.id 
                    end as sublocality_id,
                    case when ea.type = 'LOCALITY' then ea.id 
                    when ea.type = 'SUBLOCALITY' then max(eaparent.id)
                    end as locality_id,
                    case when ea.type = 'SUBLOCALITY' then 
                    st_x(ea.centroid::geometry) end as sublocality_longitude,
                    case when ea.type = 'SUBLOCALITY' then 
                    st_y(ea.centroid::geometry) end as sublocality_latitude,
                    case when ea.type = 'LOCALITY' then st_x(ea.centroid::geometry)
                    when ea.type = 'SUBLOCALITY' then max(st_x(eaparent.centroid::geometry))
                    end as locality_longitude,
                    case when ea.type = 'LOCALITY' then st_y(ea.centroid::geometry)
                    when ea.type = 'SUBLOCALITY' then max(st_y(eaparent.centroid::geometry)) 
                    end as locality_latitude,
                    case when ea.type = 'SUBLOCALITY' then ea.alternative_value end as sublocality_value,
                    case when ea.type = 'LOCALITY' then ea.alternative_value 
                    when  ea.type = 'SUBLOCALITY' then max(eaparent.alternative_value) end as locality_value,
                    case when ea.type = 'LOCALITY' then 'DOCTORS_CITY'
                    else 'DOCTORS_LOCALITY_CITY' end as sitemap_identifier,
                    %d as sequence,
                    'Doctor' as entity_type,
                    'SEARCHURL' url_type,
                    True as is_valid
                    from hospital h inner join entity_address ea on ((ea.type = 'LOCALITY' and ST_DWithin(ea.centroid,h.location,15000)) OR 
                    (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))) and h.is_live=true
                    and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true inner join doctor_clinic dc on dc.hospital_id = h.id
                    and dc.enabled=true 
                    inner join doctor d on dc.doctor_id= d.id
                    and d.is_live=true left join entity_address eaparent on ea.parent_id=eaparent.id and eaparent.use_in_url=true
                    group by ea.id having count(distinct d.id) >= 3''' % sequence
        create_temp_table = RawSql(create_temp_table_query, []).execute()

        update_extras_query = '''update  seo_doctor_search_urls 
                        set extras = case when type='LOCALITY' then
                        json_build_object('location_json',json_build_object('locality_id',locality_id,'locality_value',locality_value, 
                        'locality_latitude',locality_latitude,'locality_longitude',locality_longitude))

                        else json_build_object('location_json',
                        json_build_object('sublocality_id', sublocality_id,'sublocality_value', sublocality_value,
                        'locality_id', locality_id, 'locality_value', locality_value,'breadcrum_url',getslug('doctors-in-' || locality_value ||'-sptcit'),
                        'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 'locality_latitude',locality_latitude,
                        'locality_longitude',locality_longitude))  end'''
        update_extras = RawSql(update_extras_query, []).execute()

        update_locality_loc_query = '''update seo_doctor_search_urls set locality_location = st_setsrid(st_point(locality_longitude, locality_latitude),4326)::geography where 
        		            locality_latitude is not null and locality_longitude is not null'''

        update_locality_loc = RawSql(update_locality_loc_query, []).execute()

        update_sublocality_loc_query = '''update seo_doctor_search_urls set sublocality_location = st_setsrid(st_point(sublocality_longitude, sublocality_latitude),4326)::geography where 
                                 sublocality_latitude is not null and sublocality_longitude is not null'''

        update_sublocality_loc = RawSql(update_sublocality_loc_query, []).execute()

        update_location_query = '''update seo_doctor_search_urls set location = case when 
                    sublocality_location is not null then sublocality_location  else locality_location end'''
        update_location = RawSql(update_location_query, []).execute()

        return 'success'

    def create_doctor_spec_urls_temp_table():
        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query, []).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

        create_temp_table_query = '''create table seo_doctor_specialization_search as
                    select  max(ST_Distance(ea.centroid,h.location)) as distance, 
                    ps.id as specialization_id, ps.name as specialization, ea.alternative_value,
                    ea.search_slug, null as url, null::json as extras, null::geography as locality_location, 
                    null::geography as sublocality_location, null::geography as location,
                    ea.type, count(distinct d.id) as count,
                    case when ea.type = 'SUBLOCALITY' then 
                    ea.id 
                    end as sublocality_id,
                    case when ea.type = 'LOCALITY' then ea.id 
                    when ea.type = 'SUBLOCALITY' then max(eaparent.id)
                    end as locality_id,
                    case when ea.type = 'SUBLOCALITY' then 
                    st_x(ea.centroid::geometry) end as sublocality_longitude,
                    case when ea.type = 'SUBLOCALITY' then 
                    st_y(ea.centroid::geometry) end as sublocality_latitude,
                    case when ea.type = 'LOCALITY' then st_x(ea.centroid::geometry)
                    when ea.type = 'SUBLOCALITY' then max(st_x(eaparent.centroid::geometry))
                    end as locality_longitude,
                    case when ea.type = 'LOCALITY' then st_y(ea.centroid::geometry)
                    when ea.type = 'SUBLOCALITY' then max(st_y(eaparent.centroid::geometry))
                    end as locality_latitude,
                    case when ea.type = 'SUBLOCALITY' then ea.alternative_value end as sublocality_value,
                    case when ea.type = 'LOCALITY' then ea.alternative_value 
                     when  ea.type = 'SUBLOCALITY' then max(eaparent.alternative_value) end as locality_value,
                    case when ea.type = 'LOCALITY' then 'SPECIALIZATION_CITY'
                    else 'SPECIALIZATION_LOCALITY_CITY' end as sitemap_identifier,
                    %d as sequence,
                    'Doctor' as entity_type,
                    'SEARCHURL' url_type,
                    True as is_valid
                    from hospital h inner join entity_address ea on ((ea.type = 'LOCALITY' and 
                    ST_DWithin(ea.centroid,h.location,15000)) OR 
                    (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))) and h.is_live=true
                    and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true inner join doctor_clinic dc on dc.hospital_id = h.id
                    and dc.enabled=true
                    inner join doctor d on dc.doctor_id= d.id
                    inner join doctor_practice_specialization dps on dps.doctor_id = d.id and d.is_live=true
                    inner join practice_specialization ps on ps.id = dps.specialization_id 
                    left join entity_address eaparent on ea.parent_id=eaparent.id and eaparent.use_in_url=true
                    group by ps.id, ea.id having count(distinct d.id) >= 3 
                ''' % sequence

        create_temp_table = RawSql(create_temp_table_query, []).execute()

        update_urls_query = '''update seo_doctor_specialization_search set url = case when type = 'SUBLOCALITY' then 
                    getslug(concat(specialization,'-in-', search_slug, '-sptlitcit'))
                    else getslug(concat(specialization,'-in-', search_slug, '-sptcit'))
                    end'''
        update_urls = RawSql(update_urls_query, []).execute()

        update_extras_query = '''update  seo_doctor_specialization_search 
                          set extras = case when type='LOCALITY' then
                           json_build_object('specialization_id', specialization_id, 'location_json',
                           json_build_object('locality_id', locality_id, 'locality_value', locality_value, 'locality_latitude', 
                           locality_latitude,'locality_longitude', locality_longitude), 'specialization', specialization)

                          else  json_build_object('specialization_id', specialization_id,'location_json',
                          json_build_object('sublocality_id',sublocality_id,'sublocality_value',sublocality_value,
                           'locality_id', locality_id, 'locality_value', locality_value,
                           'breadcrum_url',getslug(specialization || '-in-' || locality_value ||'-sptcit'),
                          'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 
                          'locality_latitude',locality_latitude,'locality_longitude',locality_longitude),'specialization', specialization) end'''
        update_extras = RawSql(update_extras_query, []).execute()

        update_locality_loc_query = '''update seo_doctor_specialization_search set locality_location = st_setsrid(st_point(locality_longitude, locality_latitude),4326)::geography where 
                locality_latitude is not null and locality_longitude is not null'''

        update_locality_loc = RawSql(update_locality_loc_query, []).execute()

        update_sublocality_loc_query = '''update seo_doctor_specialization_search set sublocality_location = st_setsrid(st_point(sublocality_longitude, sublocality_latitude),4326)::geography where 
                 sublocality_latitude is not null and sublocality_longitude is not null'''

        update_sublocality_loc = RawSql(update_sublocality_loc_query, []).execute()

        update_location_query = '''update seo_doctor_specialization_search set location = case when 
                           sublocality_location is not null then sublocality_location  else locality_location end'''
        update_location = RawSql(update_location_query, []).execute()

        return 'success'

    @classmethod
    def create_doctor_search_urls(cls):

        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query, []).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0


        # Mark all existing urls as is_valid=False.

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier in ('SPECIALIZATION_CITY', 'SPECIALIZATION_LOCALITY_CITY', 'DOCTORS_LOCALITY_CITY', 'DOCTORS_CITY')'''


        # Query for specialization in location and insertion .

        # select
        # case when x.sitemap_identifier = 'SPECIALIZATION_CITY' then json_build_object('location_json',
        #     json_build_object('locality_id', x.locality_id, 'locality_value', x.locality_value, 'locality_latitude',
        #     x.locality_latitude, 'locality_longitude', x.locality_longitude))
        #
        # when x.sitemap_identifier = 'SPECIALIZATION_LOCALITY_CITY' then json_build_object('location_json',
        #     json_build_object('sublocality_id', x.sublocality_id, 'sublocality_value',
        #     x.sublocality_value, 'locality_id', x.locality_id, 'locality_value', x.locality_value, 'breadcrum_url',
        #     getslug(x.specialization_name||'-in-'||x.locality_value||'-sptcit'), 'sublocality_latitude', x.sublocality_latitude,
        #     'sublocality_longitude', x.sublocality_longitude, 'locality_latitude', x.locality_latitude, 'locality_longitude',
        #     x.locality_longitude))

        query = '''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, 
            updated_at, sequence, sublocality_latitude, sublocality_longitude, locality_latitude, locality_longitude, locality_id, sublocality_id,
            locality_value, sublocality_value, specialization, specialization_id)
            
            select x.extras as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
            x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, 
            x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence,
            x.sublocality_latitude as sublocality_latitude, x.sublocality_longitude as sublocality_longitude, x.locality_latitude as locality_latitude,
            x.locality_longitude as locality_longitude, x.locality_id as locality_id, x.sublocality_id as sublocality_id,
            x.locality_value as locality_value, x.sublocality_value as sublocality_value, x.specialization_name as specialization,
            x.specialization_id as specialization_id
            from
            (
            select data.*, row_number() over(partition by data.url order by count desc) as rnum from 
            (
            select 
            
            case when y.type='LOCALITY' then json_build_object('specialization_id', specialization_id,'location_json',
            json_build_object('locality_id',location_id,'locality_value',location_name, 'locality_latitude',latitude,
            'locality_longitude',longitude),'specialization',specialization_name)

            when y.type='SUBLOCALITY' then json_build_object('specialization_id', specialization_id,'location_json',
            json_build_object('sublocality_id',location_id,'sublocality_value',location_name,
             'locality_id', ea.id, 'locality_value', ea.alternative_value,'breadcrum_url',getslug(specialization_name || '-in-' || ea.alternative_value
              ||'-sptcit'),
            'sublocality_latitude',latitude, 'sublocality_longitude',longitude, 'locality_latitude',st_y(ea.centroid::geometry),
             'locality_longitude',st_x(ea.centroid::geometry)),'specialization', specialization_name)
             end as extras,
                        
            case when y.type='LOCALITY' then 'SPECIALIZATION_CITY'
            when y.type='SUBLOCALITY' then 'SPECIALIZATION_LOCALITY_CITY'
            end as sitemap_identifier,
            
            case when y.type='LOCALITY' then latitude
            when y.type='SUBLOCALITY' then st_y(ea.centroid::geometry)
            end as locality_latitude,
                    
            case when y.type='SUBLOCALITY' then latitude
            end as sublocality_latitude,
                    
            case when y.type='SUBLOCALITY' then longitude
            end as sublocality_longitude,
                    
            case when y.type='LOCALITY' then longitude
            when y.type='SUBLOCALITY' then st_x(ea.centroid::geometry)
            end as locality_longitude,
                    
            case when y.type='LOCALITY' then location_name
            when y.type='SUBLOCALITY' then ea.alternative_value
            end as locality_value,
            
                    
            case when y.type='SUBLOCALITY' then location_name
            end as sublocality_value,
                    
            case when y.type='LOCALITY' then location_id
            when y.type='SUBLOCALITY' then ea.id
            end as locality_id,
                    
            case when y.type='SUBLOCALITY' then location_id
            end as sublocality_id,
            
            'Doctor' as entity_type,
            'SEARCHURL' as url_type,
            True as is_valid,
            NOW() as created_at,
            NOW() as updated_at,
            %d as sequence,
           
            
            y.*, ea.id as parent_id, ea.alternative_value as parent_name,
            st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
            case when y.type='LOCALITY' then getslug(specialization_name || '-in-' ||location_name||'-sptcit')
            when y.type='SUBLOCALITY' then getslug(specialization_name || '-in-' ||location_name||'-'||ea.alternative_value ||'-sptlitcit')
            end as url
            from
            (select * from 
            (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent_id,ps.id specialization_id,ps.name specialization_name,
            st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
            ,count(*) count from entity_address ea
            inner join hospital h on h.is_live=true
            and (
            (type_blueprint='LOCALITY' and ST_DWithin(ea.centroid,h.location,15000)) or
            (type_blueprint='SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))
            )
            inner join doctor_clinic dc on dc.hospital_id = h.id
            inner join doctor d on dc.doctor_id = d.id and d.is_live=true
            inner join doctor_practice_specialization dps on dps.doctor_id = d.id
            inner join practice_specialization ps on ps.id = dps.specialization_id
            where type_blueprint in ('LOCALITY','SUBLOCALITY')
            group by ea.id,ps.id)x where count>=3)y
            left join entity_address ea on y.parent_id=ea.id 
            ) as data												 
            )x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)

        # Query for doctors in location and insertion .

        # case when y.type = 'LOCALITY' then json_build_object('location_json',
        # json_build_object('locality_id', location_id, 'locality_value', location_name,'locality_latitude', latitude,
        # 'locality_longitude', longitude), 'location_id', location_id)
        #
        # when y.type = 'SUBLOCALITY' then json_build_object('location_json',
        # json_build_object('sublocality_id', location_id, 'sublocality_value', location_name, 'locality_id', ea.id,
        # 'locality_value', ea.alternative_value, 'breadcrum_url',
        # getslug('doctors' | | '-in-' | | ea.alternative_value | | '-sptcit'), 'sublocality_latitude', latitude,
        # 'sublocality_longitude', longitude, 'locality_latitude', st_y(ea.centroid::geometry),
        # 'locality_longitude', st_x(ea.centroid::geometry)), 'location_id', location_id)
        #
        # end as extras,

        query1 = '''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, 
            updated_at, sequence, sublocality_latitude, sublocality_longitude, locality_latitude, locality_longitude, locality_id, sublocality_id,
            locality_value, sublocality_value, specialization)
            
            select
            case when x.sitemap_identifier = 'DOCTORS_CITY' then json_build_object('location_json',
                json_build_object('locality_id', x.locality_id, 'locality_value', x.locality_value, 'locality_latitude', 
                x.locality_latitude, 'locality_longitude', x.locality_longitude))
                
            when x.sitemap_identifier = 'DOCTORS_LOCALITY_CITY' then json_build_object('location_json',
                json_build_object('sublocality_id', x.sublocality_id, 'sublocality_value',
                x.sublocality_value, 'locality_id', x.locality_id, 'locality_value', x.locality_value, 'breadcrum_url',
                getslug('doctors' || '-in-' || x.locality_value ||'-sptcit'), 'sublocality_latitude', x.sublocality_latitude, 
                'sublocality_longitude', x.sublocality_longitude, 'locality_latitude', x.locality_latitude, 'locality_longitude', 
                x.locality_longitude)) 
             
            end as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
            x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, 
            x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence,
            x.sublocality_latitude as sublocality_latitude, x.sublocality_longitude as sublocality_longitude, x.locality_latitude as locality_latitude,
            x.locality_longitude as locality_longitude, x.locality_id as locality_id, x.sublocality_id as sublocality_id,
            x.locality_value as locality_value, x.sublocality_value as sublocality_value, x.specialization as specialization
            
            from 
            (
            select data.*, row_number() over(partition by data.url order by count desc) as rnum from
            (
            select
            
            case when y.type='LOCALITY' then 'DOCTORS_CITY'
            when y.type='SUBLOCALITY' then 'DOCTORS_LOCALITY_CITY'
            end as sitemap_identifier,
            
            case when y.type='LOCALITY' then latitude
            when y.type='SUBLOCALITY' then st_y(ea.centroid::geometry)
            end as locality_latitude,
                    
            case when y.type='SUBLOCALITY' then latitude
            end as sublocality_latitude,
                    
            case when y.type='SUBLOCALITY' then longitude
            end as sublocality_longitude,
                    
            case when y.type='LOCALITY' then longitude
            when y.type='SUBLOCALITY' then st_x(ea.centroid::geometry)
            end as locality_longitude,
                    
            case when y.type='LOCALITY' then location_name
            when y.type='SUBLOCALITY' then ea.alternative_value
            end as locality_value,
                    
            case when y.type='SUBLOCALITY' then location_name
            end as sublocality_value,
                    
            case when y.type='LOCALITY' then location_id
            when y.type='SUBLOCALITY' then ea.id
            end as locality_id,
                    
            case when y.type='SUBLOCALITY' then location_id
            end as sublocality_id,

            'Doctor' as entity_type,
            'SEARCHURL' as url_type,
            True as is_valid,
            NOW() as created_at,
            NOW() as updated_at,
            %d as sequence,
            '' as specialization,
            

            y.*, ea.id as parent_id, ea.alternative_value as parent_name,
            st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
            case when y.type='LOCALITY' then 'doctors' || '-in-' ||location_name||'-sptcit'
            when y.type='SUBLOCALITY' then 'doctors' || '-in-' ||location_name||'-'||ea.alternative_value ||'-sptlitcit'
            end as url
            from
            (select * from
            (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent_id,
            st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
            ,count(*) count from entity_address ea
            inner join hospital h on h.is_live=true
            and (
            (type_blueprint='LOCALITY' and ST_DWithin(ea.centroid,h.location,15000)) or
            (type_blueprint='SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))
            )
            inner join doctor_clinic dc on dc.hospital_id = h.id
            inner join doctor d on dc.doctor_id = d.id and d.is_live=true
            where type_blueprint in ('LOCALITY','SUBLOCALITY')
            group by ea.id)x where count>=3)y
            left join entity_address ea on y.parent_id=ea.id
            ) as data
            )x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)

        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute(update_query)
                cursor.execute(query)
                cursor.execute(query1)
            except Exception as e:
                print(str(e))
                return False

        return True

    @classmethod
    def create_lab_search_urls(cls):
        from ondoc.diagnostic.models import Lab

        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query,[]).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

        # Mark all existing urls as is_valid=False.

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier in ('LAB_LOCALITY_CITY', 'LAB_CITY');'''

        query =  '''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, 
                       updated_at, sequence, sublocality_latitude, sublocality_longitude, locality_latitude, locality_longitude, locality_id, sublocality_id,
                       locality_value, sublocality_value, specialization)
                       
                       select 
                       case when x.sitemap_identifier = 'LAB_CITY' then json_build_object('location_json',
                              json_build_object('locality_id', x.locality_id, 'locality_value', x.locality_value, 'locality_latitude', 
                              x.locality_latitude, 'locality_longitude', x.locality_longitude))
                
                       when x.sitemap_identifier = 'LAB_LOCALITY_CITY' then json_build_object('location_json',
                              json_build_object('sublocality_id', x.sublocality_id, 'sublocality_value',
                              x.sublocality_value, 'locality_id', x.locality_id, 'locality_value', x.locality_value, 'breadcrum_url',
                              getslug('labs' || '-in-' || x.locality_value || '-lbcit'), 'sublocality_latitude', x.sublocality_latitude, 
                              'sublocality_longitude', x.sublocality_longitude, 'locality_latitude', x.locality_latitude, 'locality_longitude', 
                              x.locality_longitude))
                        
                       end as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
                       x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, 
                       x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence,
                       x.sublocality_latitude as sublocality_latitude, x.sublocality_longitude as sublocality_longitude, x.locality_latitude as locality_latitude,
                       x.locality_longitude as locality_longitude, x.locality_id as locality_id, x.sublocality_id as sublocality_id,
                       x.locality_value as locality_value, x.sublocality_value as sublocality_value, x.specialization as specialization
                      
                       from 
                       (select data.*, row_number() over(partition by data.url order by count desc) as rnum
                       from 
                       (
                       select

                       case when y.type='LOCALITY' then 'LAB_CITY'
                       when y.type='SUBLOCALITY' then 'LAB_LOCALITY_CITY'
                       end as sitemap_identifier,

                       case when y.type='LOCALITY' then latitude
                       when y.type='SUBLOCALITY' then st_y(ea.centroid::geometry)
                       end as locality_latitude,

                       case when y.type='SUBLOCALITY' then latitude
                       end as sublocality_latitude,

                       case when y.type='SUBLOCALITY' then longitude
                       end as sublocality_longitude,

                       case when y.type='LOCALITY' then longitude
                       when y.type='SUBLOCALITY' then st_x(ea.centroid::geometry)
                       end as locality_longitude,

                       case when y.type='LOCALITY' then location_name
                       when y.type='SUBLOCALITY' then ea.alternative_value
                       end as locality_value,

                       case when y.type='SUBLOCALITY' then location_name
                       end as sublocality_value,

                       case when y.type='LOCALITY' then location_id
                       when y.type='SUBLOCALITY' then ea.id
                       end as locality_id,

                       case when y.type='SUBLOCALITY' then location_id
                       end as sublocality_id,

                       'Lab' as entity_type,
                       'SEARCHURL' as url_type,
                       True as is_valid,
                       NOW() as created_at,
                       NOW() as updated_at,
                       %d as sequence,
                       '' as specialization,
                       

                       y.*, ea.id as parent_id, ea.alternative_value as parent_name,
                       st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
                       case when y.type='LOCALITY' then 'labs' || '-in-' ||location_name||'-lbcit'
                       when y.type='SUBLOCALITY' then 'labs' || '-in-' ||location_name||'-'||ea.alternative_value ||'-lblitcit'
                       end as url
                       from
                       (select * from 
                       (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent_id,
                       st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
                       ,count(*) count from entity_address ea
                       inner join lab l on l.is_live=true 
                       and (
                       (type_blueprint='LOCALITY' and ST_DWithin(ea.centroid,l.location,15000)) or
                       (type_blueprint='SUBLOCALITY' and ST_DWithin(ea.centroid,l.location,5000))
                       )
                       where type_blueprint in ('LOCALITY','SUBLOCALITY')
                       group by ea.id)x where count>=3)y
                       left join entity_address ea on y.parent_id=ea.id 
                       ) as data 
                       ) x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' 
                       ''' % (sequence)

        # query ='''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, updated_at, sequence)
        #     select x.extras as extras, x.sitemap_identifier as sitemap_identifier, x.url as url,
        #     x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence
        #     from
        #     (select data.*, row_number() over(partition by data.url order by count desc) as rnum
        #     from
        #     (
        #     select
        #     case when y.type='LOCALITY' then json_build_object('location_json',
        #     json_build_object('locality_id',location_id,'locality_value',location_name, 'locality_latitude',latitude,
        #     'locality_longitude',longitude))
        #
        #     when y.type='SUBLOCALITY' then json_build_object('location_json',
        #     json_build_object('sublocality_id',location_id,'sublocality_value',location_name,
        #      'locality_id', ea.id, 'locality_value', ea.alternative_value,'breadcrum_url',getslug('labs' || '-in-' || ea.alternative_value ||'-lbcit'),
        #     'sublocality_latitude',latitude, 'sublocality_longitude',longitude, 'locality_latitude',st_y(ea.centroid::geometry),
        #      'locality_longitude',st_x(ea.centroid::geometry)))
        #
        #     end as extras,
        #
        #     case when y.type='LOCALITY' then 'LAB_CITY'
        #     when y.type='SUBLOCALITY' then 'LAB_LOCALITY_CITY'
        #     end as sitemap_identifier,
        #
        #     'Lab' as entity_type,
        #     'SEARCHURL' as url_type,
        #     True as is_valid,
        #     NOW() as created_at,
        #     NOW() as updated_at,
        #     %d as sequence,
        #
        #     y.*, ea.id as parent_id, ea.alternative_value as parent_name,
        #     st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
        #     case when y.type='LOCALITY' then getslug('labs' || '-in-' ||location_name||'-lbcit')
        #     when y.type='SUBLOCALITY' then getslug('labs' || '-in-' ||location_name||'-'||ea.alternative_value ||'-lblitcit')
        #     end as url
        #     from
        #     (select * from
        #     (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent,
        #     st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
        #     ,count(*) count from entity_address ea
        #     inner join lab l on l.is_live=true
        #     and (
        #     (type_blueprint='LOCALITY' and st_distance(ea.centroid,l.location)<15000) or
        #     (type_blueprint='SUBLOCALITY' and st_distance(ea.centroid,l.location)<5000)
        #     )
        #     where type_blueprint in ('LOCALITY','SUBLOCALITY')
        #     group by ea.id)x where count>=3)y
        #     left join entity_address ea on y.parent=ea.id
        #     ) as data
        #     ) x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)

        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute(update_query)
                cursor.execute(query)

            except Exception as e:
                print(str(e))
                return False

        return True

    @classmethod
    def create_page_url(cls, entity_object, sequence):

        try:

            if entity_object.__class__.__name__.upper() == 'DOCTOR':
                sitemap_identifier = cls.SitemapIdentifier.DOCTOR_PAGE
                forname = 'doctors'
                identifier = 'spt'
            else:
                sitemap_identifier = cls.SitemapIdentifier.LAB_PAGE
                forname = 'labs'
                identifier = 'lb'
            entity_helper = entity_as_mapping[entity_object.__class__.__name__.upper()]
            entity_helper_obj = entity_helper()
            url_dict = entity_helper_obj.create_return_personal_urls(entity_object)

            if isinstance(url_dict, dict):
                if url_dict.get('page_urls'):
                    page_url_dict = url_dict['page_urls']
                    url = page_url_dict.get('urls')
                    specialization = page_url_dict.get('specialization_name', '')
                    specialization_id = page_url_dict.get('specialization_id', None)
                    seo_parameters = page_url_dict.get('seo_parameters')
                    if seo_parameters:
                        locality_id = seo_parameters.get('locality_id')
                        if not locality_id:
                            locality_id = None
                        sublocality_id = seo_parameters.get('sublocality_id')
                        if not sublocality_id:
                            sublocality_id = None
                        locality_value = seo_parameters.get('locality_value')
                        sublocality_value = seo_parameters.get('sublocality_value')
                        locality_latitude = seo_parameters.get('locality_latitude')
                        locality_longitude = seo_parameters.get('locality_longitude')
                        sublocality_latitude = seo_parameters.get('sublocality_latitude')
                        if not sublocality_latitude:
                            sublocality_latitude = None
                        sublocality_longitude = seo_parameters.get('sublocality_longitude')
                        if not sublocality_longitude:
                            sublocality_longitude = None

                    if not url:
                        return

                    # build urls for bread crums
                    breadcrums = list()
                    location_id = page_url_dict.get('location_id')
                    address_obj = EntityAddress.objects.get(id=location_id)

                    # locality_value = address_obj.value
                    # sublocality_value = ''

                    if address_obj.type_blueprint == EntityAddress.AllowedKeys.SUBLOCALITY:
                        # address_obj_parent = EntityAddress.objects.get(id=address_obj.parent)
                        # locality_value = address_obj_parent.alternative_value
                        # sublocality_value = address_obj.alternative_value
                        if locality_id:
                            bread_url = slugify('{prefix}-in-{locality}-{identifier}cit'
                                                .format(identifier=identifier, prefix=forname,
                                                        locality=locality_value))

                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': locality_value, 'url': bread_url})

                            bread_url = slugify('{prefix}-in-{sublocality}-{locality}-{identifier}litcit'.
                                                format(prefix=forname, sublocality=address_obj.alternative_value,
                                                       locality=locality_value, identifier=identifier))

                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': address_obj.alternative_value, 'url': bread_url})

                    extra = {'related_entity_id': entity_object.id, 'location_id': page_url_dict.get('location_id'),
                             'breadcrums': breadcrums, 'locality_value': locality_value, 'sublocality_value': sublocality_value}

                    entity_url_objs = cls.objects.filter(entity_id=entity_object.id, entity_type=entity_object.__class__.__name__, url_type='PAGEURL', is_valid=True)
                    if not entity_url_objs.exists():
                        entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                             url_type=cls.UrlType.PAGEURL, entity_id=entity_object.id,
                                             extras=extra, sitemap_identifier=sitemap_identifier, sequence=sequence,
                                             specialization=specialization, locality_value=locality_value,
                                             sublocality_value=sublocality_value, locality_id=locality_id,
                                             sublocality_id=sublocality_id, locality_longitude=locality_longitude,
                                             locality_latitude=locality_latitude, sublocality_longitude=sublocality_longitude,
                                             sublocality_latitude=sublocality_latitude, specialization_id=specialization_id)
                        entity_url_obj.save()
                    else:
                        entity_url_obj = entity_url_objs.first()
                        if entity_url_obj.url != url:
                            entity_url_obj.is_valid = False
                            entity_url_obj.save()

                            entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                                 url_type=cls.UrlType.PAGEURL, extras=extra,
                                                 entity_id=entity_object.id,sitemap_identifier=sitemap_identifier,
                                                 sequence=sequence, specialization=specialization, locality_value=locality_value,
                                                 sublocality_value=sublocality_value, locality_id=locality_id,
                                                 sublocality_id=sublocality_id, specialization_id=specialization_id)
                            entity_url_obj.save()
                        else:
                            entity_url_obj.extras = extra
                            entity_url_obj.save()
            return True

        except Exception as e:
            print(str(e))
            return False

    class Meta:
        db_table = 'entity_urls'
        indexes = [
            models.Index(fields=['locality_value']),
            models.Index(fields=['url']),
            models.Index(fields=['locality_value', 'sitemap_identifier',]),
            models.Index(fields=['specialization_id', 'sitemap_identifier',]),
            models.Index(fields=['specialization_id', 'locality_id','sublocality_id']),
            models.Index(fields=['locality_id','sublocality_id']),
        ]



class EntityUrlsHelper(object):

    def _create_return_personal_urls(self, entity_object):
        raise NotImplemented()

    def create_return_personal_urls(self, entity_object):
        urls = self._create_return_personal_urls(entity_object)
        return urls

    def build_url(self, prefix, location):
        import re
        url = ''
        locality_value = None
        sublocality_value = None
        locality_id = None
        sublocality_id = None
        locality_latitude = None
        locality_longitude = None
        sublocality_latitude = None
        sublocality_longitude = None
        seo = dict()

        if location.type == 'LOCALITY':
            ea = EntityAddress.objects.get(id=location.location_id, type=location.type)
            locality_id = location.location_id
            locality_value = ea.alternative_value
            locality_latitude = ea.centroid.y
            locality_longitude = ea.centroid.x
            url = "{prefix}-in-{locality}".format(prefix=prefix, locality=ea.alternative_value)
        elif location.type == 'SUBLOCALITY':
            ea_sublocality = EntityAddress.objects.get(id=location.location_id, type=location.type)
            sublocality_id = location.location_id
            sublocality_latitude = ea_sublocality.centroid.y
            sublocality_longitude = ea_sublocality.centroid.x
            ea_locality = EntityAddress.objects.get(id=ea_sublocality.parent_id, type='LOCALITY')
            locality_id = ea_sublocality.parent_id
            locality_latitude = ea_locality.centroid.y
            locality_longitude = ea_locality.centroid.x
            locality_value = ea_locality.alternative_value
            sublocality_value = ea_sublocality.alternative_value
            url = "{prefix}-in-{sublocality}-{locality}"\
                .format(prefix=prefix, sublocality=ea_sublocality.alternative_value, locality=ea_locality.alternative_value)

        url = slugify(url)

        if not url and not re.match("^[A-Za-z0-9_-]*$", url):
            return None

        seo['parameters'] = { 'url': url,
                                'locality_id': locality_id,
                                'locality_value': locality_value,
                                'sublocality_id': sublocality_id,
                                'sublocality_value': sublocality_value,
                                'locality_latitude': locality_latitude,
                                'locality_longitude': locality_longitude,
                                'sublocality_latitude': sublocality_latitude,
                                'sublocality_longitude': sublocality_longitude
        }

        print(seo)

        return seo


class EntityHelperAsDoctor(EntityUrlsHelper):

    def _create_return_personal_urls(self, entity_object):
        urls = dict()
        search_urls = list()
        doctor_page_url = ''

        # Finding all the doctor specialization for appending in to the url.
        doctor_specializations = doc_models.DoctorPracticeSpecialization.objects.filter(doctor=entity_object).all()
        specializations = [doctor_specialization.specialization for doctor_specialization in doctor_specializations]

        # Finding all the hospitals and appending along with the specializations.
        doctor_realted_hospitals = entity_object.hospitals.all().filter(is_live=True)

        hospital_for_doctor_page = None

        if doctor_realted_hospitals.filter(is_live=True, hospital_type=1).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(is_live=True, hospital_type=1).first()
        elif doctor_realted_hospitals.filter(is_live=True, hospital_type=2).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(is_live=True, hospital_type=2).first()
        elif doctor_realted_hospitals.filter(is_live=True, hospital_type=3).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(is_live=True, hospital_type=3).first()
        else:
            hospital_for_doctor_page = doctor_realted_hospitals.filter(is_live=True).first()

        if hospital_for_doctor_page:

            query_set_for_personal_url = hospital_for_doctor_page.entity.all().filter(type="SUBLOCALITY", valid=True)
            if not query_set_for_personal_url.exists():
                query_set_for_personal_url = hospital_for_doctor_page.entity.all().filter(type="LOCALITY", valid=True)

            if query_set_for_personal_url.exists():
                specialization_name = [specialization.name for specialization in specializations]
                doctor_page_seo_parameters = self.build_url("dr-%s-%s" %(entity_object.name, "-".join(specialization_name)),
                                                 query_set_for_personal_url.first())

                if doctor_page_seo_parameters:
                    if doctor_page_seo_parameters.get('parameters').get('url'):
                        doctor_page_url = "%s-%s" % (doctor_page_seo_parameters.get('parameters').get('url'), 'dpp')

                urls['page_urls'] = {
                    'urls': doctor_page_url.lower(),
                    'location_id': query_set_for_personal_url.first().location.id,
                    'specialization_name': specialization_name[0] if len(specialization_name) > 0 else '',
                    'specialization_id': specializations[0].id if len(specializations) > 0 else None,
                    'seo_parameters': doctor_page_seo_parameters.get('parameters')
                }

        print(urls)
        return urls


class EntityHelperAsLab(EntityUrlsHelper):

    def _create_return_personal_urls(self, entity_object):
        urls = dict()
        specialization_name = None


        query_set_for_personal_url = entity_object.entity.all().filter(type="SUBLOCALITY", valid=True)
        if not query_set_for_personal_url.exists():
            query_set_for_personal_url = entity_object.entity.all().filter(type="LOCALITY", valid=True)

        if query_set_for_personal_url.exists():
            lab_page_seo_parameters = self.build_url("%s" % entity_object.name, query_set_for_personal_url.first())
            if lab_page_seo_parameters:
                if lab_page_seo_parameters.get('parameters'):
                    lab_page_url = "%s-%s" % (lab_page_seo_parameters.get('parameters').get('url'), 'lpp')

                urls['page_urls'] = {
                    'urls': lab_page_url.lower(),
                    'location_id': query_set_for_personal_url.first().location.id,
                    'specialization_name': specialization_name,
                    'seo_parameters': lab_page_seo_parameters.get('parameters')
                }

        print(urls)
        return urls


entity_as_mapping = {
    'DOCTOR': EntityHelperAsDoctor,
    'LAB': EntityHelperAsLab
}


class LabPageUrl(object):
    sitemap_identifier = EntityUrls.SitemapIdentifier.LAB_PAGE
    forname = 'labs'
    identifier = 'lb'

    def __init__(self, lab, sequence):
        self.lab = lab
        self.locality = None
        self.sequence = sequence

        self.sublocality = None
        self.sublocality_id = None
        self.sublocality_longitude = None
        self.sublocality_latitude = None

    def initialize(self):
        if self.lab:
            sublocality = self.lab.entity.filter(type="SUBLOCALITY", valid=True).first()
            if sublocality:
                self.sublocality = sublocality.location.alternative_value
                self.sublocality_id = sublocality.location.id
                self.sublocality_longitude = sublocality.location.centroid.x
                self.sublocality_latitude = sublocality.location.centroid.y

            locality = self.lab.entity.filter(type="LOCALITY", valid=True).first()
            if locality:
                self.locality = locality.location.alternative_value
                self.locality_id = locality.location.id
                self.locality_longitude = locality.location.centroid.x
                self.locality_latitude = locality.location.centroid.y

    def create(self):
        self.initialize()
        if self.lab and self.locality:

            url = "%s" % self.lab.name
            if self.locality and self.sublocality:
                url = url + "-in-%s-%s-lpp" % (self.sublocality, self.locality)
            elif self.locality:
                url = url + "-in-%s-lpp" % self.locality

            url = slugify(url)

            data = {}
            data['url'] = url
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Lab'
            data['entity_id'] = self.lab.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.LAB_PAGE
            data['locality_id'] = self.locality_id
            data['locality_value'] = self.locality
            data['locality_latitude'] = self.locality_latitude
            data['locality_longitude'] = self.locality_longitude

            if self.locality_latitude and self.locality_longitude:
                data['locality_location'] = Point(self.locality_longitude, self.locality_latitude)

            if self.sublocality_latitude and self.sublocality_longitude:
                data['sublocality_location'] = Point(self.sublocality_longitude, self.sublocality_latitude)

            data['sublocality_id'] = self.sublocality_id
            data['sublocality_value'] = self.sublocality
            data['sublocality_latitude'] = self.sublocality_latitude
            data['sublocality_longitude'] = self.sublocality_longitude
            data['location'] = self.lab.location

            extras = {}
            extras['related_entity_id'] = self.lab.id
            extras['location_id'] = self.sublocality_id if self.sublocality_id else self.locality_id
            extras['locality_value'] = self.locality if self.locality else ''
            extras['sublocality_value'] = self.sublocality if self.sublocality else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            data['sequence'] = self.sequence


            EntityUrls.objects.filter(entity_id=self.lab.id, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).filter(~Q(url = url)).update(is_valid=False)
            EntityUrls.objects.filter(entity_id=self.lab.id, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE, url=url).delete()
            EntityUrls.objects.create(**data)

    def create_lab_page_urls(lab, sequence):
        sequence = sequence
        locality_value = None
        locality_id = None
        locality_latitude = None
        locality_longitude = None
        sublocality_value = None
        sublocality_id = None
        sublocality_longitude = None
        sublocality_latitude = None
        sublocality = None
        locality = None

        if lab:
            if lab.is_live:
                entity_location_relation = lab.entity.all()
                for obj in entity_location_relation:
                    if obj.location.use_in_url:
                        if obj.location.type == 'SUBLOCALITY':
                            sublocality = obj.location
                            break
                if sublocality:
                    sublocality_value = sublocality.alternative_value
                    sublocality_id = sublocality.id
                    if sublocality.centroid:
                        sublocality_longitude = sublocality.centroid.x
                        sublocality_latitude = sublocality.centroid.y
                    locality = EntityAddress.objects.filter(id=sublocality.parent_id).first()
                    if locality:
                        locality_value = locality.alternative_value
                        locality_id = locality.id
                        if locality.centroid:
                            locality_longitude = locality.centroid.x
                            locality_latitude = locality.centroid.y
                if lab:

                    if locality and sublocality:
                        url = lab.name + "-in-%s-%s" % (sublocality_value, locality_value)
                    # elif locality:
                    #     url = lab.name + "-in-%s" % locality_value
                    else:
                       url = lab.name

                    url = slugify(url)

                    data = {}
                    data['is_valid'] = True
                    data['url_type'] = EntityUrls.UrlType.PAGEURL
                    data['entity_type'] = 'Lab'
                    data['entity_id'] = lab.id
                    data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.LAB_PAGE
                    data['locality_id'] = locality_id
                    data['locality_value'] = locality_value
                    data['locality_latitude'] = locality_latitude
                    data['locality_longitude'] = locality_longitude

                    if locality_latitude and locality_longitude:
                        data['locality_location'] = Point(locality_longitude, locality_latitude)

                    if sublocality_latitude and sublocality_longitude:
                        data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

                    data['sublocality_id'] = sublocality_id
                    data['sublocality_value'] = sublocality_value
                    data['sublocality_latitude'] = sublocality_latitude
                    data['sublocality_longitude'] = sublocality_longitude
                    data['location'] = lab.location

                    extras = {}
                    extras['related_entity_id'] = lab.id
                    extras['location_id'] = sublocality_id if sublocality_id else locality_id
                    extras['locality_value'] = locality_value if locality else ''
                    extras['sublocality_value'] = sublocality_value if sublocality else ''
                    extras['breadcrums'] = []
                    data['extras'] = extras
                    data['sequence'] = sequence

                    new_url = url

                    dup_url = EntityUrls.objects.filter(url=new_url+'-lpp',
                                                        sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE
                                                        ).filter(~Q(entity_id=lab.id)).first()
                    if dup_url:
                        new_url = new_url + '-' + str(lab.id)
                    new_url = new_url + '-lpp'

                    EntityUrls.objects.filter(entity_id=lab.id,
                                              sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE,
                                              is_valid=True).filter(
                        ~Q(url=new_url)).update(is_valid=False)

                    EntityUrls.objects.filter(entity_id=lab.id,
                                              sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE,
                                              url=new_url).delete()
                    data['url'] = new_url
                    EntityUrls.objects.create(**data)
                    return ("success: " + str(lab.id))


class DoctorPageURL(object):
    identifier = 'spt'
    sitemap_identifier = EntityUrls.SitemapIdentifier.DOCTOR_PAGE

    def __init__(self, doctor, sequence):
        self.doctor = doctor
        self.locality = None
        self.specializations = []
        self.sequence = sequence

        self.sublocality = None
        self.sublocality_id = None
        self.sublocality_longitude = None
        self.sublocality_latitude = None

    def init_preferred_hospital(self):

        hospital = None
        doctor_hospitals = self.doctor.hospitals.filter(is_live=True)

        hospital = doctor_hospitals.filter(hospital_type=1).order_by('id').first()
        if not hospital:
            hospital = doctor_hospitals.filter(hospital_type=2).order_by('id').first()
        if not hospital:
            hospital = doctor_hospitals.filter(hospital_type=3).order_by('id').first()
        if not hospital:
            hospital = doctor_hospitals.order_by('id').first()


        self.hospital = hospital

    def initialize(self):

        self.init_preferred_hospital()
        if self.hospital:
            doctor_specializations = doc_models.DoctorPracticeSpecialization.objects.filter(doctor=self.doctor).order_by('specialization_id')
            self.specializations = [doctor_specialization.specialization for doctor_specialization in doctor_specializations]

            sublocality = self.hospital.entity.filter(type="SUBLOCALITY", valid=True).first()
            if sublocality:
                self.sublocality = sublocality.location.alternative_value
                self.sublocality_id = sublocality.location.id
                self.sublocality_longitude = sublocality.location.centroid.x
                self.sublocality_latitude = sublocality.location.centroid.y

            locality = self.hospital.entity.filter(type="LOCALITY", valid=True).first()
            if locality:
                self.locality = locality.location.alternative_value
                self.locality_id = locality.location.id
                self.locality_longitude = locality.location.centroid.x
                self.locality_latitude = locality.location.centroid.y

    def create(self):

        self.initialize()
        url = None

        if self.hospital and self.locality and self.specializations and len(self.specializations)>0:

            specialization_name = [specialization.name for specialization in self.specializations]

            url = "dr-%s-%s" %(self.doctor.name, "-".join(specialization_name))
            if self.locality and self.sublocality:
                url = url+"-in-%s-%s-dpp" %(self.sublocality, self.locality)
            elif self.locality:
                url = url+"-in-%s-dpp" %(self.locality)

            url = slugify(url)

            data = {}
            data['url'] = url
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Doctor'
            data['entity_id'] = self.doctor.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            data['locality_id'] = self.locality_id
            data['locality_value'] = self.locality
            data['locality_latitude'] = self.locality_latitude
            data['locality_longitude'] = self.locality_longitude

            if self.locality_latitude and self.locality_longitude:
                data['locality_location'] =  Point(self.locality_longitude, self.locality_latitude)

            if self.sublocality_latitude and self.sublocality_longitude:
                data['sublocality_location'] =  Point(self.sublocality_longitude, self.sublocality_latitude)

            data['sublocality_id'] = self.sublocality_id
            data['sublocality_value'] = self.sublocality
            data['sublocality_latitude'] = self.sublocality_latitude
            data['sublocality_longitude'] = self.sublocality_longitude
            data['location'] = self.hospital.location
            data['specialization'] = self.specializations[0].name
            data['specialization_id'] = self.specializations[0].id

            extras = {}
            extras['related_entity_id'] = self.doctor.id
            extras['location_id'] = self.sublocality_id if self.sublocality_id else self.locality_id
            extras['locality_value'] = self.locality if self.locality else ''
            extras['sublocality_value'] = self.sublocality if self.sublocality else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            data['sequence'] = self.sequence


            EntityUrls.objects.filter(entity_id=self.doctor.id, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).filter(~Q(url = url)).update(is_valid=False)
            EntityUrls.objects.filter(entity_id=self.doctor.id, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE, url=url).delete()
            EntityUrls.objects.create(**data)


    def create_doctor_page_urls():

        from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization, Hospital, PracticeSpecialization

        query = '''select nextval('entity_url_version_seq') as inc'''
        seq = RawSql(query,[]).fetch_all()

        sequence = seq[0]['inc']

        cache = PageUrlCache(EntityUrls.SitemapIdentifier.DOCTOR_PAGE)
        #to_disable = []
        to_delete = []
        to_create = []

        doc_obj =Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization',
                                    (Prefetch('hospitals', queryset=Hospital.objects.filter(is_live=True).order_by('hospital_type', 'id')))
                                    ).prefetch_related('hospitals__entity','hospitals__entity__location','hospitals__entity__location__parent').filter(is_live=True, is_test_doctor=False).order_by('id')


        for doctor in doc_obj:
            #status = DoctorPageURL.create_doctor_page_urls(doctor,sequence)

            locality_value = None
            locality_id = None
            locality_latitude = None
            locality_longitude = None
            sublocality_value = None
            sublocality_id = None
            sublocality_longitude = None
            sublocality_latitude = None
            sequence = sequence
            doc_sublocality = None
            doc_locality = None
            hospital = None

            practice_specializations = doctor.doctorpracticespecializations.all()
            sp_dict = dict()
            for sp in practice_specializations:
                sp_dict[sp.specialization_id] = sp.specialization.name
            sp_dict = OrderedDict(sorted(sp_dict.items()))
            specializations = list(sp_dict.values())
            specialization_ids = list(sp_dict.keys())

            all_hospitals = doctor.hospitals.all()
            for hosp in all_hospitals:
                if hosp.is_live:
                    hospital = hosp
                break


            #print('attempting for doctor '+str(doctor.id))
            # if doctor.hospitals.all():
            #     hospital = doctor.hospitals.all()[0]
            #     if hospital.is_live:
                    # doc_sublocality = hospital.entity.filter(type="SUBLOCALITY").first()
            if not hospital:
                print('hospital not found')

            if hospital:
                entity_location_relation = hospital.entity.all()
                print('mapped entities for hospital'+str(hospital.id)+'='+str(len(entity_location_relation)))
                for obj in entity_location_relation:
                    #print('location mapped')

                    if not doc_sublocality and obj.location.use_in_url:
                        if obj.location.type =='SUBLOCALITY':
                            doc_sublocality = obj.location
                            #print('sublocality found')

                    # if not doc_locality and obj.location.use_in_url:
                    #     if obj.location.type =='LOCALITY':
                    #         doc_locality = obj.location

                    # if obj.location.type =='SUBLOCALITY':
                    #
                    #     doc_sublocality = EntityAddress.objects.filter(id=obj.location.id)
                    #     if doc_sublocality:
                    #         doc_sublocality = doc_sublocality[0]
                if doc_sublocality:
                    sublocality_value = doc_sublocality.alternative_value
                    sublocality_id = doc_sublocality.id
                    if doc_sublocality.centroid:
                        sublocality_longitude = doc_sublocality.centroid.x
                        sublocality_latitude = doc_sublocality.centroid.y
                    # doc_sublocality = hospital.entity.filter(type="LOCALITY", valid=True).first()

                    #doc_locality = EntityAddress.objects.filter(id=doc_sublocality.parent).first()
                    doc_locality = doc_sublocality.parent
                    if doc_locality:
                        #doc_locality = doc_locality[0]
                        locality_value = doc_locality.alternative_value
                        locality_id = doc_locality.id
                        if doc_locality.centroid:
                            locality_longitude = doc_locality.centroid.x
                            locality_latitude = doc_locality.centroid.y
                    #doc_locality = EntityAddress.objects.filter(id=doc_sublocality.location.parent).first()
                    # locality_value = doc_locality.alternative_value
                    # locality_id = doc_locality.id
                    # if doc_locality.centroid:
                    #     locality_longitude = doc_locality.centroid.x
                    #     locality_latitude = doc_locality.centroid.y

                    # doc_locality = hospital.entity.filter(type="LOCALITY", valid=True).first()
                    #doc_locality = hospital.entity.filter(type="LOCALITY", valid=True, location__centroid__isnull=False).first()

            if not doc_locality or not doc_sublocality:
                print('failed')

            if specializations:
                url = "dr-%s-%s" % (doctor.name, "-".join(specializations))
            else:
                url = "dr-%s" % (doctor.name)

            if doc_locality and doc_sublocality:
                url = url + "-in-%s-%s" % (sublocality_value, locality_value)
            # elif doc_locality:
            #     url = url + "-in-%s" % (locality_value)
            else:
                url = url

            url = slugify(url)
            data = {}
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Doctor'
            data['entity_id'] = doctor.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            #if doc_locality
            data['locality_id'] = locality_id
            data['locality_value'] = locality_value
            data['locality_latitude'] = locality_latitude
            data['locality_longitude'] = locality_longitude

            if locality_latitude and locality_longitude:
                data['locality_location'] = Point(locality_longitude, locality_latitude)

            if sublocality_latitude and sublocality_longitude:
                data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

            #if doc_sublocality:
            data['sublocality_id'] = sublocality_id
            data['sublocality_value'] = sublocality_value
            data['sublocality_latitude'] = sublocality_latitude
            data['sublocality_longitude'] = sublocality_longitude

            if hospital:
                data['location'] = hospital.location

            # if specializations and specialization_ids:
            #     data['specialization'] = specializations[0]
            #     data['specialization_id'] = specialization_ids[0]

            extras = {}
            extras['related_entity_id'] = doctor.id
            #if sublocality_id or locality_id:
            extras['location_id'] = sublocality_id if sublocality_id else locality_id
            extras['locality_value'] = locality_value if doc_locality else ''
            extras['sublocality_value'] = sublocality_value if doc_sublocality else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            data['sequence'] = sequence

            new_url = url
            # counter = 0
            #
            # while True:
            #     if counter>0:
            #         # new_url = url+'-'+'-'+''.join([random.choice(string.digits) for n in range(10)])
            #         new_url = url + '-' + str(counter)
            #     dup_url = EntityUrls.objects.filter(url=new_url, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).filter(~Q(entity_id=doctor.id)).first()
            #     if not dup_url:
            #         break
            #     counter = counter + 1

            is_duplicate = cache.is_duplicate(new_url + '-dpp', doctor.id)
            # dup_url = EntityUrls.objects.filter(url=new_url + '-dpp',
            #                                     sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            #                                     ).filter(~Q(entity_id=doctor.id)).first()
            if is_duplicate:
                new_url = new_url + '-' + str(doctor.id)

            new_url = new_url + '-dpp'

            # EntityUrls.objects.filter(entity_id=doctor.id,
            #                           sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).filter(
            #     ~Q(url=new_url)).update(is_valid=False)

            to_delete.extend(cache.get_deletions(new_url, doctor.id))
            # EntityUrls.objects.filter(entity_id=doctor.id, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE,
            #                           url=new_url).delete()

            data['url'] = new_url
            to_create.append(EntityUrls(**data))
            #EntityUrls.objects.create(**data)

        with transaction.atomic():

            EntityUrls.objects.filter(id__in=to_delete).delete()
            #EntityUrls.filter(id__in=to_delete).delete()
            EntityUrls.objects.bulk_create(to_create)
            EntityUrls.objects.filter(sitemap_identifier='DOCTOR_PAGE', sequence__lt=sequence).update(is_valid=False)    
            return ("success: " + str(doctor.id))


class DefaultRating(TimeStampedModel):
    ratings = models.FloatField(null=True)
    reviews = models.PositiveIntegerField(null=True)
    url = models.TextField()

    class Meta:
        db_table = 'default_rating'
        indexes = [
            models.Index(fields=['url']),
        ]


class CityLatLong(TimeStampedModel):
    city = models.TextField()
    latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)

    class Meta:
        db_table = 'city_lat_long'