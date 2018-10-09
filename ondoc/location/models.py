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


def split_and_append(initial_str, spliter, appender):
    value_chunks = initial_str.split(spliter)
    return appender.join(value_chunks)


class Choices(object):
    @classmethod
    def as_choices(cls):
        properties = list(filter(lambda x : not x.startswith ("__"), dir(cls)))
        properties.remove ("as_choices")
        properties.remove ("availabilities")
        choices = []
        for prop in properties:
            val = getattr(cls, prop)
            choices.append((prop, val))
        return choices

    @classmethod
    def availabilities(cls):
        props = list(filter(lambda x: not x.startswith("__"), dir(cls)))
        props.remove("as_choices")
        props.remove("availabilities")
        return props


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
                    entity_address = cls(type=meta['key'], centroid=point, postal_code=postal_code, type_blueprint=meta['type'], value=meta['value'], parent=parent_id)
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

    url = models.CharField(blank=False, null=True, max_length=500, unique=True, db_index=True)
    url_type = models.CharField(max_length=24, choices=UrlType.as_choices(), null=True)
    entity_type = models.CharField(max_length=24, null=True)
    extras = JSONField()
    entity_id = models.PositiveIntegerField(null=True, default=None)
    is_valid = models.BooleanField(default=True)
    count = models.IntegerField(max_length=30, null=True, default=0)
    sitemap_identifier = models.CharField(max_length=28, null=True, choices=SitemapIdentifier.as_choices())

    @property
    def additional_info(self):
        return self.extras

    @classmethod
    def create_doctor_search_urls(cls):
        from ondoc.doctor.models import DoctorPracticeSpecialization, DoctorClinic
        try:
            current_timestamp = datetime.datetime.now()
            specializations = doc_models.PracticeSpecialization.objects.all()
            locations_set = EntityAddress.objects.filter\
                (type_blueprint__in=[EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY])
            for location in locations_set:
                for specialization in specializations:
                    location_json = {}
                    count = 0
                    if location.type == 'LOCALITY':
                        sitemap_identifier = cls.SitemapIdentifier.SPECIALIZATION_CITY
                        url = "{prefix}-in-{locality}-sptcit".format(prefix=specialization.name, locality=location.value)
                        # Storing the locality data for fallback cases.
                        location_json['locality_id'] = location.id
                        location_json['locality_value'] = location.value
                        location_json['locality_latitude'] = location.centroid.y if location.centroid is not None and hasattr(location.centroid, 'y') else 0.0
                        location_json['locality_longitude'] = location.centroid.x if location.centroid is not None and hasattr(location.centroid, 'x') else 0.0
                        ref_location = Point(float(location_json['locality_longitude']),
                                             float(location_json['locality_latitude']))
                        distance = 15000

                    else:
                        sitemap_identifier = cls.SitemapIdentifier.SPECIALIZATION_LOCALITY_CITY
                        ea_locality = EntityAddress.objects.get(id=location.parent)
                        url = "{prefix}-in-{sublocality}-{locality}-sptlitcit".format(prefix=specialization.name, sublocality=location.value, locality=ea_locality.value)
                        # storing the sublocality and locality data for fallback cases.
                        location_json['sublocality_id'] = location.id
                        location_json['sublocality_value'] = location.value
                        location_json['sublocality_latitude'] = location.centroid.y if location.centroid is not None and hasattr(location.centroid, 'y') else 0.0
                        location_json['sublocality_longitude'] = location.centroid.x if location.centroid is not None and hasattr(location.centroid, 'x') else 0.0
                        location_json['locality_id'] = ea_locality.id
                        location_json['locality_value'] = ea_locality.value
                        location_json['locality_latitude'] = ea_locality.centroid.y if ea_locality.centroid is not None and hasattr(ea_locality.centroid, 'y') else 0.0
                        location_json['locality_longitude'] = ea_locality.centroid.x if ea_locality.centroid is not None and hasattr(ea_locality.centroid, 'x') else 0.0
                        location_json['breadcrum_url'] = slugify("{prefix}-in-{locality}-sptcit".format(prefix=specialization.name, locality=ea_locality.value))
                        ref_location = Point(float(location_json['sublocality_longitude']),
                                             float(location_json['sublocality_latitude']))
                        distance = 5000

                    url = slugify(url)
                    url = url.lower()
                    extra = {'specialization': specialization.name, 'specialization_id': specialization.id,
                             'location_json': location_json}

                    pnt = GEOSGeometry(ref_location, srid=4326)

                    doctors_in_range = DoctorClinic.objects.filter(
                        hospital__location__distance_lte=(pnt, distance)).values('doctor')

                    for doctor in doctors_in_range:
                        doc_spec = DoctorPracticeSpecialization.objects.filter(specialization=specialization, doctor=doctor.get('doctor'))
                        if doc_spec.exists():
                            count += 1

                    url_qs = cls.objects.filter(url=url)
                    if url_qs.exists():
                        url_obj = url_qs.first()
                        url_obj.extras = extra
                        url_obj.count = count
                        url_obj.save()
                    else:
                        entity_url_obj = cls(url=url, entity_type='Doctor',
                                             url_type=cls.UrlType.SEARCHURL, extras=extra, count=count,
                                             sitemap_identifier=sitemap_identifier)
                        entity_url_obj.save()
                        print(url)

                if location.type == 'LOCALITY':
                    sitemap_identifier = cls.SitemapIdentifier.DOCTORS_CITY
                    doctor_in_city_url = "doctors-in-{location}-sptcit".format(location=location.value)
                else:
                    sitemap_identifier = cls.SitemapIdentifier.DOCTORS_LOCALITY_CITY
                    ea_locality = EntityAddress.objects.get(id=location.parent)
                    doctor_in_city_url = "doctors-in-{sublocality}-{locality}-sptlitcit".\
                        format(sublocality=location.value, locality=ea_locality.value)

                count = 0
                if doctor_in_city_url:
                    if doctors_in_range.exists():
                        count = doctors_in_range.count()

                    doctor_in_city_url = slugify(doctor_in_city_url)
                    extra = {'location_id': location.id, 'location_json': location_json}

                    url_qs = cls.objects.filter(url=doctor_in_city_url)
                    if url_qs.exists():
                        url_obj = url_qs.first()
                        url_obj.extras = extra
                        url_obj.count = count
                        url_obj.save()
                    else:
                        entity_url_obj = cls(url=doctor_in_city_url,
                                             entity_type='Doctor',
                                             url_type=cls.UrlType.SEARCHURL, extras=extra, count=count,
                                             sitemap_identifier=sitemap_identifier)
                        entity_url_obj.save()
                        print(doctor_in_city_url)

            undesirable_urls_qs = cls.objects.filter(updated_at__lte=current_timestamp, url_type=cls.UrlType.SEARCHURL,
                                                     entity_type='Doctor')
            if undesirable_urls_qs.exists():
                undesirable_urls_qs.delete()

            return True
        except Exception as e:
            print(str(e))
            return False

    @classmethod
    def create_lab_search_urls(cls):
        from ondoc.diagnostic.models import Lab
        try:
            current_timestamp = datetime.datetime.now()
            locations_set = EntityAddress.objects.filter \
                (type_blueprint__in=[EntityAddress.AllowedKeys.LOCALITY, EntityAddress.AllowedKeys.SUBLOCALITY])
            for location in locations_set:
                location_json = {}
                if location.type == 'LOCALITY':
                    sitemap_identifier = cls.SitemapIdentifier.LAB_CITY
                    url = "labs-in-{locality}-lbcit".format(locality=location.value)
                    # Storing the locality data for fallback cases.
                    location_json['locality_id'] = location.id
                    location_json['locality_value'] = location.value
                    location_json['locality_latitude'] = location.centroid.y if location.centroid is not None and hasattr(location.centroid, 'y') else 0.0
                    location_json['locality_longitude'] = location.centroid.x if location.centroid is not None and hasattr(location.centroid, 'x') else 0.0
                    ref_location = Point(float(location_json['locality_longitude']),
                                         float(location_json['locality_latitude']))
                    distance = 15000

                else:
                    sitemap_identifier = cls.SitemapIdentifier.LAB_LOCALITY_CITY
                    ea_locality = EntityAddress.objects.get(id=location.parent)
                    url = "labs-in-{sublocality}-{locality}-lblitcit".format(sublocality=location.value, locality=ea_locality.value)
                    # storing the sublocality and locality data for fallback cases.
                    location_json['sublocality_id'] = location.id
                    location_json['sublocality_value'] = location.value
                    location_json['sublocality_latitude'] = location.centroid.y if location.centroid is not None and hasattr(location.centroid, 'y') else 0.0
                    location_json['sublocality_longitude'] = location.centroid.x if location.centroid is not None and hasattr(location.centroid, 'x') else 0.0
                    location_json['locality_id'] = ea_locality.id
                    location_json['locality_value'] = ea_locality.value
                    location_json['locality_latitude'] = ea_locality.centroid.y if ea_locality.centroid is not None and hasattr(ea_locality.centroid, 'y') else 0.0
                    location_json['locality_longitude'] = ea_locality.centroid.x if ea_locality.centroid is not None and hasattr(ea_locality.centroid, 'x') else 0.0
                    location_json['breadcrum_url'] = slugify("labs-in-{locality}-lbcit".format(locality=ea_locality.value))
                    ref_location = Point(float(location_json['sublocality_longitude']),
                                         float(location_json['sublocality_latitude']))
                    distance = 5000

                url = slugify(url)
                url = url.lower()
                extra = {'location_json': location_json}

                pnt = GEOSGeometry(ref_location, srid=4326)

                qs = Lab.objects.filter(location__distance_lte=(pnt, distance))
                count = qs.count()

                url_qs = cls.objects.filter(url=url)
                if url_qs.exists():
                    url_obj = url_qs.first()
                    url_obj.extras = extra
                    url_obj.count = count
                    url_obj.save()
                else:
                    entity_url_obj = cls(url=url, entity_type='Lab',
                                         url_type=cls.UrlType.SEARCHURL, extras=extra, count=count,
                                         sitemap_identifier=sitemap_identifier)
                    entity_url_obj.save()
                    print(url)

            undesirable_urls_qs = cls.objects.filter(updated_at__lte=current_timestamp, url_type=cls.UrlType.SEARCHURL,
                                                     entity_type='Lab')
            if undesirable_urls_qs.exists():
                undesirable_urls_qs.delete()
            return True
        except Exception as e:
            print(str(e))
            return False

    @classmethod
    def create_page_url(cls, entity_object):
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
                    if address_obj.type_blueprint == EntityAddress.AllowedKeys.SUBLOCALITY:
                        address_obj_parent = EntityAddress.objects.get(id=address_obj.parent)
                        if address_obj_parent:
                            bread_url = slugify('{prefix}-in-{locality}-{identifier}cit'
                                                .format(identifier=identifier, prefix=forname,
                                                        locality=address_obj_parent.value))
                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': address_obj_parent.value, 'url': bread_url})

                            bread_url = slugify('{prefix}-in-{sublocality}-{locality}-{identifier}litcit'.
                                                format(prefix=forname, sublocality=address_obj.value,
                                                       locality=address_obj_parent.value, identifier=identifier))
                            if EntityUrls.objects.filter(url=bread_url).exists():
                                breadcrums.append({'name': address_obj.value, 'url': bread_url})

                    extra = {'related_entity_id': entity_object.id, 'location_id': page_url_dict.get('location_id'),
                             'breadcrums': breadcrums}

                    entity_url_objs = cls.objects.filter(entity_id=entity_object.id, entity_type=entity_object.__class__.__name__, url_type='PAGEURL', is_valid=True)
                    if not entity_url_objs.exists():
                        entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                             url_type=cls.UrlType.PAGEURL, entity_id=entity_object.id,
                                             extras=extra, sitemap_identifier=sitemap_identifier)
                        entity_url_obj.save()
                    else:
                        entity_url_obj = entity_url_objs.first()
                        if entity_url_obj.url != url:
                            entity_url_obj.is_valid = False
                            entity_url_obj.save()

                            entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                                 url_type=cls.UrlType.PAGEURL, extras=extra,
                                                 entity_id=entity_object.id,sitemap_identifier=sitemap_identifier)
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

    def create_return_search_urls(self, entity_object):
        urls = self._create_return_search_urls(entity_object)
        return urls

    def build_url(self, prefix, location):
        url = ''
        if location.type == 'LOCALITY':
            ea = EntityAddress.objects.get(id=location.location_id, type=location.type)
            url = "{prefix}-in-{locality}".format(prefix=prefix, locality=ea.value)
        elif location.type == 'SUBLOCALITY':
            ea_sublocality = EntityAddress.objects.get(id=location.location_id, type=location.type)
            ea_locality = EntityAddress.objects.get(id=ea_sublocality.parent, type='LOCALITY')
            url = "{prefix}-in-{sublocality}-{locality}"\
                .format(prefix=prefix, sublocality=ea_sublocality.value, locality=ea_locality.value)

        url = slugify(url)
        # url = split_and_append(url, ' ', '-')
        # url = split_and_append(url, '/', '-')

        if not url:
            url = None

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