from django.contrib.gis.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging

from .service import get_meta_by_latlong
import logging
logger = logging.getLogger(__name__)
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

def split_and_append(initial_str, spliter, appender):
    value_chunks = initial_str.split(spliter)
    return appender.join(value_chunks)


class GeoIpResults(TimeStampedModel):

    value = models.TextField()
    latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)

    class Meta:
        db_table = 'geo_ip_results'


class EntityAddress(TimeStampedModel):

    class AllowedKeys(Choices):
        LOCALITY = 'LOCALITY'
        SUBLOCALITY = 'SUBLOCALITY'
        ADMINISTRATIVE_AREA_LEVEL_1 = 'ADMINISTRATIVE_AREA_LEVEL_1'
        ADMINISTRATIVE_AREA_LEVEL_2 = 'ADMINISTRATIVE_AREA_LEVEL_2'
        COUNTRY = 'COUNTRY'

    type = models.CharField(max_length=128, blank=False, null=False, choices=AllowedKeys.as_choices())
    value = models.TextField()
    alternative_value = models.TextField(default='', null=True)
    type_blueprint = models.CharField(max_length=128, blank=False, null=True)
    postal_code = models.PositiveIntegerField(null=True)
    parent = models.IntegerField(null=True)
    centroid = models.PointField(geography=True, srid=4326, blank=True, null=True)

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        mapping_dictionary = {
            'bengaluru': 'Bangalore',
            'bengalooru': 'Bangalore',
            'gurugram': 'Gurgaon',
            'gurugram rural': 'Gurgaon'
        }

        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
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
                    entity_address = cls(type=meta['key'], centroid=point, postal_code=postal_code,
                                         type_blueprint=meta['type'], value=meta['value'], parent=parent_id,
                                         alternative_value=alternative_name)
                    entity_address.save()
                    parent_id = entity_address.id

            if entity_address.type in ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2', 'LOCALITY', 'SUBLOCALITY']:
                ea_list.append(entity_address)

        return ea_list

    class Meta:
        db_table = 'entity_address'


class EntityLocationRelationship(TimeStampedModel):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    valid = models.BooleanField(default=True)
    location = models.ForeignKey(EntityAddress, related_name='associated_relations', on_delete=models.CASCADE)
    type = models.CharField(max_length=128, blank=False, null=False, choices=EntityAddress.AllowedKeys.as_choices())

    @classmethod
    def create(cls, *args, **kwargs):
        try:
            ea_list = EntityAddress.get_or_create(**kwargs)
            if len(ea_list) >= 1:
                entity_location_qs = cls.objects.filter(
                    content_type=ContentType.objects.get_for_model(kwargs.get('content_object')),
                    object_id=kwargs.get('content_object').id)
                if entity_location_qs.exists():
                    entity_location_qs.update(valid=False)
                else:
                    for ea in ea_list:
                        entity_location_relation = cls(content_object=kwargs.get('content_object'), type=ea.type, location=ea)
                        entity_location_relation.save()
            return True
        except Exception as e:
            print(str(e))
            return False

    class Meta:
        db_table = 'entity_location_relations'


class EntityUrls(TimeStampedModel):
    class SitemapIdentifier(Choices):
        SPECIALIZATION_LOCALITY_CITY = 'SPECIALIZATION_LOCALITY_CITY'
        SPECIALIZATION_CITY = 'SPECIALIZATION_CITY'
        DOCTORS_LOCALITY_CITY = 'DOCTORS_LOCALITY_CITY'
        DOCTORS_CITY = 'DOCTORS_CITY'
        DOCTOR_PAGE = 'DOCTOR_PAGE'

        LAB_LOCALITY_CITY = 'LAB_LOCALITY_CITY'
        LAB_CITY = 'LAB_CITY'
        LAB_PAGE = 'LAB_PAGE'

    class UrlType(Choices):
        PAGEURL = 'PAGEURL'
        SEARCHURL = 'SEARCHURL'

    url = models.CharField(blank=False, null=True, max_length=500, db_index=True)
    url_type = models.CharField(max_length=24, choices=UrlType.as_choices(), null=True)
    entity_type = models.CharField(max_length=24, null=True)
    extras = JSONField()
    entity_id = models.PositiveIntegerField(null=True, default=None)
    is_valid = models.BooleanField(default=True)
    count = models.IntegerField(max_length=30, null=True, default=0)
    sitemap_identifier = models.CharField(max_length=28, null=True, choices=SitemapIdentifier.as_choices())
    sequence = models.PositiveIntegerField(default=0)

    @property
    def additional_info(self):
        return self.extras

    @classmethod
    def create_doctor_search_urls(cls):

        from ondoc.api.v1.utils import RawSql
        query = '''select nextval('entity_url_version_seq') as inc;'''

        seq = RawSql(query).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

        # Query for specialization in location and insertion .


        query = '''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, updated_at, sequence)
            select x.extras as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
            x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence
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
            (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent,ps.id specialization_id,ps.name specialization_name,
            st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
            ,count(*) count from entity_address ea
            inner join hospital h on h.is_live=true
            and (
            (type_blueprint='LOCALITY' and st_distance(ea.centroid,h.location)<15000) or
            (type_blueprint='SUBLOCALITY' and st_distance(ea.centroid,h.location)<5000)
            )
            inner join doctor_clinic dc on dc.hospital_id = h.id
            inner join doctor d on dc.doctor_id = d.id and d.is_live=true
            inner join doctor_practice_specialization dps on dps.doctor_id = d.id
            inner join practice_specialization ps on ps.id = dps.specialization_id
            where type_blueprint in ('LOCALITY','SUBLOCALITY')
            group by ea.id,ps.id)x where count>=3)y
            left join entity_address ea on y.parent=ea.id 
            ) as data												 
            )x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)

        # Query for doctors in location and insertion .

        query1 = '''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, updated_at, sequence)
            select x.extras as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
            x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, x.created_at as created_at, x.updated_at as updated, x.sequence as sequenceat from 
            (
            select data.*, row_number() over(partition by data.url order by count desc) as rnum from 
            (
            select 
            case when y.type='LOCALITY' then json_build_object('location_json',
            json_build_object('locality_id',location_id,'locality_value',location_name, 'locality_latitude',latitude, 
            'locality_longitude',longitude),'location_id',location_id)
            
            when y.type='SUBLOCALITY' then json_build_object('location_json',
            json_build_object('sublocality_id',location_id,'sublocality_value',location_name,
             'locality_id', ea.id, 'locality_value', ea.alternative_value,'breadcrum_url',getslug('doctors' || '-in-' || ea.alternative_value ||'-sptcit'),
            'sublocality_latitude',latitude, 'sublocality_longitude',longitude, 'locality_latitude',st_y(ea.centroid::geometry),
             'locality_longitude',st_x(ea.centroid::geometry)),'location_id',location_id)
             
            end as extras,
            
            case when y.type='LOCALITY' then 'DOCTORS_CITY'
            when y.type='SUBLOCALITY' then 'DOCTORS_LOCALITY_CITY'
            end as sitemap_identifier,
            
            'Doctor' as entity_type,
            'SEARCHURL' as url_type,
            True as is_valid,
            NOW() as created_at,
            NOW() as updated_at,
            %d as sequence,
            
            y.*, ea.id as parent_id, ea.alternative_value as parent_name,
            st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
            case when y.type='LOCALITY' then getslug('doctors' || '-in-' ||location_name||'-sptcit')
            when y.type='SUBLOCALITY' then getslug('doctors' || '-in-' ||location_name||'-'||ea.alternative_value ||'-sptlitcit')
            end as url
            from
            (select * from 
            (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent,
            st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
            ,count(*) count from entity_address ea
            inner join hospital h on h.is_live=true 
            and (
            (type_blueprint='LOCALITY' and st_distance(ea.centroid,h.location)<15000) or
            (type_blueprint='SUBLOCALITY' and st_distance(ea.centroid,h.location)<5000)
            )
            inner join doctor_clinic dc on dc.hospital_id = h.id
            inner join doctor d on dc.doctor_id = d.id and d.is_live=true
            where type_blueprint in ('LOCALITY','SUBLOCALITY')
            group by ea.id)x where count>=3)y
            left join entity_address ea on y.parent=ea.id 
            ) as data
            )x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)


        # seq = RawSql(query).fetch_all()
        from django.db import connection
        with connection.cursor() as cursor:
            try:
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

        seq = RawSql(query).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

         # Query for lab in location and insertion .


        query ='''insert into entity_urls(extras, sitemap_identifier, url, count, entity_type, url_type, is_valid, created_at, updated_at, sequence)
            select x.extras as extras, x.sitemap_identifier as sitemap_identifier, x.url as url, 
            x.count as count, x.entity_type as entity_type, x.url_type as url_type , x.is_valid, x.created_at as created_at, x.updated_at as updated_at, x.sequence as sequence
            from 
            (select data.*, row_number() over(partition by data.url order by count desc) as rnum
            from 
            (
            select 
            case when y.type='LOCALITY' then json_build_object('location_json',
            json_build_object('locality_id',location_id,'locality_value',location_name, 'locality_latitude',latitude, 
            'locality_longitude',longitude))
            
            when y.type='SUBLOCALITY' then json_build_object('location_json',
            json_build_object('sublocality_id',location_id,'sublocality_value',location_name,
             'locality_id', ea.id, 'locality_value', ea.alternative_value,'breadcrum_url',getslug('labs' || '-in-' || ea.alternative_value ||'-lbcit'),
            'sublocality_latitude',latitude, 'sublocality_longitude',longitude, 'locality_latitude',st_y(ea.centroid::geometry),
             'locality_longitude',st_x(ea.centroid::geometry)))
             
            end as extras,
            
            case when y.type='LOCALITY' then 'LAB_CITY'
            when y.type='SUBLOCALITY' then 'LAB_LOCALITY_CITY'
            end as sitemap_identifier,
            
            'Lab' as entity_type,
            'SEARCHURL' as url_type,
            True as is_valid,
            NOW() as created_at,
            NOW() as updated_at,
            %d as sequence,
            
            y.*, ea.id as parent_id, ea.alternative_value as parent_name,
            st_x(ea.centroid::geometry) as parent_longitude, st_y(ea.centroid::geometry) as parent_latitude,
            case when y.type='LOCALITY' then getslug('labs' || '-in-' ||location_name||'-lbcit')
            when y.type='SUBLOCALITY' then getslug('labs' || '-in-' ||location_name||'-'||ea.alternative_value ||'-lblitcit')
            end as url
            from
            (select * from 
            (select ea.id location_id,ea.alternative_value location_name, ea.type,ea.parent,
            st_x(centroid::geometry) as longitude, st_y(centroid::geometry) as latitude
            ,count(*) count from entity_address ea
            inner join lab l on l.is_live=true 
            and (
            (type_blueprint='LOCALITY' and st_distance(ea.centroid,l.location)<15000) or
            (type_blueprint='SUBLOCALITY' and st_distance(ea.centroid,l.location)<5000)
            )
            where type_blueprint in ('LOCALITY','SUBLOCALITY')
            group by ea.id)x where count>=3)y
            left join entity_address ea on y.parent=ea.id 
            ) as data 
            ) x where rnum=1 and x.url ~* 'y*?(^[A-Za-z0-9-]+$)' ''' % (sequence)

        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute(query)

            except Exception as e:
                print(str(e))
                return False

        return True

    @classmethod
    def create_page_url(cls, entity_object):
        query = '''select nextval('entity_url_version_seq') as inc'''
        seq = RawSql(query).fetch_all()
        if seq:
            sequence = seq[0]['inc'] if seq[0]['inc'] else 0
        else:
            sequence = 0

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
                    if not url:
                        return

                    # build urls for bread crums
                    breadcrums = list()
                    location_id = page_url_dict.get('location_id')
                    address_obj = EntityAddress.objects.get(id=location_id)

                    locality_value = address_obj.value
                    sublocality_value = ''

                    if address_obj.type_blueprint == EntityAddress.AllowedKeys.SUBLOCALITY:
                        address_obj_parent = EntityAddress.objects.get(id=address_obj.parent)
                        locality_value = address_obj_parent.alternative_value
                        sublocality_value = address_obj.alternative_value
                        if address_obj_parent:
                            bread_url = slugify('{prefix}-in-{locality}-{identifier}cit'
                                                .format(identifier=identifier, prefix=forname,
                                                        locality=address_obj_parent.alternative_value))

                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': address_obj_parent.alternative_value, 'url': bread_url})

                            bread_url = slugify('{prefix}-in-{sublocality}-{locality}-{identifier}litcit'.
                                                format(prefix=forname, sublocality=address_obj.alternative_value,
                                                       locality=address_obj_parent.alternative_value, identifier=identifier))


                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': address_obj.alternative_value, 'url': bread_url})

                    extra = {'related_entity_id': entity_object.id, 'location_id': page_url_dict.get('location_id'),
                             'breadcrums': breadcrums, 'locality_value': locality_value, 'sublocality_value': sublocality_value}

                    entity_url_objs = cls.objects.filter(entity_id=entity_object.id, entity_type=entity_object.__class__.__name__, url_type='PAGEURL', is_valid=True)
                    if not entity_url_objs.exists():
                        entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                             url_type=cls.UrlType.PAGEURL, entity_id=entity_object.id,
                                             extras=extra, sitemap_identifier=sitemap_identifier, sequence=sequence)
                        entity_url_obj.save()
                    else:
                        entity_url_obj = entity_url_objs.first()
                        if entity_url_obj.url != url:
                            entity_url_obj.is_valid = False
                            entity_url_obj.save()

                            entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                                 url_type=cls.UrlType.PAGEURL, extras=extra,
                                                 entity_id=entity_object.id,sitemap_identifier=sitemap_identifier,
                                                 sequence=sequence)
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


class EntityUrlsHelper(object):

    def _create_return_personal_urls(self, entity_object):
        raise NotImplemented()

    def create_return_personal_urls(self, entity_object):
        urls = self._create_return_personal_urls(entity_object)
        return urls

    def _create_return_search_urls(self, entity_object):
        raise NotImplemented()

    # def create_return_search_urls(self, entity_object):
    #     urls = self._create_return_search_urls(entity_object)
    #     return urls

    def build_url(self, prefix, location):
        import re
        url = ''
        if location.type == 'LOCALITY':
            ea = EntityAddress.objects.get(id=location.location_id, type=location.type)
            url = "{prefix}-in-{locality}".format(prefix=prefix, locality=ea.alternative_value)
        elif location.type == 'SUBLOCALITY':
            ea_sublocality = EntityAddress.objects.get(id=location.location_id, type=location.type)
            ea_locality = EntityAddress.objects.get(id=ea_sublocality.parent, type='LOCALITY')
            url = "{prefix}-in-{sublocality}-{locality}"\
                .format(prefix=prefix, sublocality=ea_sublocality.alternative_value, locality=ea_locality.alternative_value)

        url = slugify(url)

        if not url and not re.match("^[A-Za-z0-9_-]*$", url):
            return None

        return url


class EntityHelperAsDoctor(EntityUrlsHelper):

    def _create_return_search_urls(self, entity_object):
        urls = dict()
        search_urls = list()

        # Finding all the doctor specialization for appending in to the url.
        doctor_specializations = doc_models.DoctorPracticeSpecialization.objects.filter(doctor=entity_object).all()
        specializations = [doctor_specialization.specialization for doctor_specialization in doctor_specializations]

        # Finding all the hospitals and appending along with the specializations.
        doctor_realted_hospitals = entity_object.hospitals.all().filter(is_live=True)

        for hospital in doctor_realted_hospitals:
            related_hospital_locations = list()

            hospital_locations = hospital.entity.all().filter(valid=True)
            for type in [EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY]:
                if hospital_locations.filter(type=type).exists():
                    related_hospital_locations.append(hospital_locations.filter(type=type).first())

            for location in related_hospital_locations:
                for specialization in specializations:
                    url = self.build_url(specialization.name, location)
                    if location.type == EntityAddress.AllowedKeys.SUBLOCALITY:
                        url = "%s-%s" % (url, 'sptlitcit')
                    elif location.type == EntityAddress.AllowedKeys.LOCALITY:
                        url = "%s-%s" % (url, 'sptcit')
                    if url:
                        search_urls.append({'url': url.lower(), 'specialization': specialization.name,
                                            'specialization_id': specialization.id, 'location_id': location.location_id})

        urls['search_urls'] = {
            'urls': search_urls,
        }

        return urls

    def _create_return_personal_urls(self, entity_object):
        urls = dict()
        search_urls = list()

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
                doctor_page_url = self.build_url("dr-%s-%s" %(entity_object.name, "-".join(specialization_name)),
                                                 query_set_for_personal_url.first())

                if doctor_page_url:
                    doctor_page_url = "%s-%s" % (doctor_page_url, 'dpp')

                urls['page_urls'] = {
                    'urls': doctor_page_url.lower(),
                    'location_id': query_set_for_personal_url.first().location.id
                }

        print(urls)
        return urls


class EntityHelperAsLab(EntityUrlsHelper):

    def _create_return_search_urls(self, entity_object):
        urls = dict()
        search_urls = list()

        lab_locations = entity_object.entity.all().filter(valid=True)
        related_lab_locations = list()

        for type in [EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY]:
            if lab_locations.filter(type=type).exists():
                related_lab_locations.append(lab_locations.filter(type=type).first())

        if entity_object.is_live:
            for location in related_lab_locations:
                url = self.build_url('labs', location)
                if location.type == EntityAddress.AllowedKeys.SUBLOCALITY:
                    url = "%s-%s" % (url, 'lblitcit')
                elif location.type == EntityAddress.AllowedKeys.LOCALITY:
                    url = "%s-%s" % (url, 'lbcit')
                if url:
                    search_urls.append({'url': url.lower(), 'location_id': location.location_id})

        urls['search_urls'] = {
            'urls': search_urls,
        }

        return urls

    def _create_return_personal_urls(self, entity_object):
        urls = dict()

        query_set_for_personal_url = entity_object.entity.all().filter(type="SUBLOCALITY", valid=True)
        if not query_set_for_personal_url.exists():
            query_set_for_personal_url = entity_object.entity.all().filter(type="LOCALITY", valid=True)

        if query_set_for_personal_url.exists():
            lab_page_url = self.build_url("%s" % entity_object.name, query_set_for_personal_url.first())
            if lab_page_url:
                lab_page_url = "%s-%s" % (lab_page_url, 'lpp')

                urls['page_urls'] = {
                    'urls': lab_page_url.lower(),
                    'location_id': query_set_for_personal_url.first().location.id
                }

        print(urls)
        return urls


entity_as_mapping = {
    'DOCTOR': EntityHelperAsDoctor,
    'LAB': EntityHelperAsLab
}