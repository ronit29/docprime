from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from .service import get_meta_by_latlong
import logging
logger = logging.getLogger(__name__)
import json
from decimal import Decimal
from ondoc.doctor import models as doc_models


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


class GeoIpResults(models.Model):

    value = models.TextField()
    latitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)
    longitude = models.DecimalField(null=True, max_digits=10, decimal_places=8)

    class Meta:
        db_table = 'geo_ip_results'


class EntityAddress(models.Model):

    class AllowedKeys(Choices):
        LOCALITY = 'LOCALITY'
        SUBLOCALITY = 'SUBLOCALITY'
        ADMINISTRATIVE_AREA_LEVEL_1 = 'ADMINISTRATIVE_AREA_LEVEL_1'
        ADMINISTRATIVE_AREA_LEVEL_2 = 'ADMINISTRATIVE_AREA_LEVEL_2'
        COUNTRY = 'COUNTRY'

    type = models.CharField(max_length=128, blank=False, null=False, choices=AllowedKeys.as_choices())
    value = models.TextField()
    type_blueprint = models.CharField(max_length=128, blank=False, null=True)
    postal_code = models.PositiveIntegerField(null=True)
    parent = models.IntegerField(null=True)

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
        if not kwargs.get('content_object', None):
            raise ValueError('Missing parameter: content_object')

        parent_id = None
        postal_code = None
        ea_list = list()
        for meta in meta_data:

            if meta['key'] in cls.AllowedKeys.availabilities():
                if meta['key'].startswith('SUBLOCALITY'):
                    postal_code = meta['POSTAL_CODE']
                saved_data = cls.objects.filter(type=meta['key'], postal_code=postal_code, type_blueprint=meta['type'], value=meta['value'], parent=parent_id)
                if len(saved_data) == 1:
                    entity_address = saved_data[0]
                    parent_id = entity_address.id
                elif len(saved_data) == 0:
                    entity_address = cls(type=meta['key'], postal_code=postal_code, type_blueprint=meta['type'], value=meta['value'], parent=parent_id)
                    entity_address.save()
                    parent_id = entity_address.id

            if entity_address.type in ['LOCALITY', 'SUBLOCALITY']:
                ea_list.append(entity_address)

        return ea_list

    class Meta:
        db_table = 'entity_address'


class EntityLocationRelationship(models.Model):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    valid = models.BooleanField(default=True)
    location = models.ForeignKey(EntityAddress, on_delete=models.CASCADE)
    type = models.CharField(max_length=128, blank=False, null=False, choices=EntityAddress.AllowedKeys.as_choices())

    @classmethod
    def create(cls, *args, **kwargs):
        try:
            ea_list = EntityAddress.get_or_create(**kwargs)
            for ea in ea_list:
                if not cls.objects.filter(content_type=ContentType.objects.get_for_model(kwargs.get('content_object')),
                                          object_id=kwargs.get('content_object').id, type=ea.type, location=ea).exists():
                    entity_location_relation = cls(content_object=kwargs.get('content_object'), type=ea.type, location=ea)
                    entity_location_relation.save()
            return True
        except Exception as e:
            print(str(e))
            return False

    class Meta:
        db_table = 'entity_location_relations'


class EntityUrls(models.Model):
    class UrlType(Choices):
        PAGEURL = 'PAGEURL'
        SEARCHURL = 'SEARCHURL'

    url = models.CharField(blank=False, null=True, max_length=500, unique=True)
    url_type = models.CharField(max_length=24, choices=UrlType.as_choices(), null=True)
    entity_type = models.CharField(max_length=24, null=True)
    extras = models.TextField(default=json.dumps({}))
    entity_id = models.PositiveIntegerField(null=True, default=None)
    is_valid = models.BooleanField(default=True)

    @property
    def additional_info(self):
        return json.loads(self.extras)

    @classmethod
    def create(cls, entity_object):
        try:
            entity_helper = entity_as_mapping[entity_object.__class__.__name__.upper()]
            entity_helper_obj = entity_helper()
            url_dict = entity_helper_obj.create_return_urls(entity_object)

            if isinstance(url_dict, dict):
                if url_dict.get('search_urls'):
                    search_url_dict = url_dict['search_urls']
                    urls = search_url_dict.get('urls', [])
                    for url in urls:
                        finalized_url = url.pop('url')
                        extra = url
                        if not cls.objects.filter(url=finalized_url).exists():
                            entity_url_obj = cls(url=finalized_url.lower(), entity_type=entity_object.__class__.__name__,
                                                 url_type=cls.UrlType.SEARCHURL, extras=json.dumps(extra))
                            entity_url_obj.save()

                if url_dict.get('page_urls'):
                    page_url_dict = url_dict['page_urls']
                    url = page_url_dict.get('urls')
                    if not url:
                        return

                    extra = {'related_entity_id': entity_object.id}
                    entity_url_objs = cls.objects.filter(entity_id=entity_object.id, entity_type=entity_object.__class__.__name__, url_type='PAGEURL', is_valid=True)
                    if not entity_url_objs.exists():
                        entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                             url_type=cls.UrlType.PAGEURL, entity_id=entity_object.id)
                        entity_url_obj.save()
                    else:
                        entity_url_obj = entity_url_objs.first()
                        if entity_url_obj.url != url:
                            entity_url_obj.is_valid = False
                            entity_url_obj.save()

                            entity_url_obj = cls(url=url.lower(), entity_type=entity_object.__class__.__name__,
                                                 url_type=cls.UrlType.PAGEURL, extras=json.dumps(extra),
                                                 entity_id=entity_object.id)
                            entity_url_obj.save()
            return True

        except Exception as e:
            print(str(e))
            return False

    class Meta:
        db_table = 'entity_urls'


class EntityUrlsRelation(models.Model):

    url = models.ForeignKey(EntityUrls, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'entity_url_relations'


class EntityUrlsHelper(object):

    def _create_return_urls(self, entity_object):
        raise NotImplemented()

    def create_return_urls(self, entity_object):
        urls = self._create_return_urls(entity_object)
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

        url = split_and_append(url, ' ', '-')

        if not url:
            url = None

        return url

    def _get_entities(self):
        raise NotImplemented()

    def get_entities(self):
        entities = self._get_entities()
        return entities


class EntityHelperAsDoctor(EntityUrlsHelper):

    def _create_return_urls(self, entity_object):
        urls = dict()
        search_urls = list()

        # Finding all the doctor specialization for appending in to the url.
        doctor_specializations = doc_models.DoctorSpecialization.objects.filter(doctor=entity_object).all()
        specializations = [doctor_specialization.specialization for doctor_specialization in doctor_specializations]

        # Finding all the hospitals and appending along with the specializations.
        doctor_realted_hospitals = entity_object.hospitals.all().filter(is_live=True)

        # for hospital in doctor_realted_hospitals:
        #     if hospital.data_status == 3:
        #
        #         hospital_locations = hospital.entity.all()
        #         for location in hospital_locations:
        #             for specialization in specializations:
        #                 url = self.build_url(specialization.name, location)
        #
        #                 if location.type == EntityAddress.AllowedKeys.SUBLOCALITY:
        #                     url = "%s-%s" % (url, 'sptlitcit')
        #                 elif location.type == EntityAddress.AllowedKeys.LOCALITY:
        #                     url = "%s-%s" % (url, 'sptcit')
        #
        #                 if url:
        #                     search_urls.append({'url': url.lower(), 'specialization': specialization.name,
        #                                         'specialization_id': specialization.id, 'location_id': location.location_id})
        #
        # urls['search_urls'] = {
        #     'urls': search_urls,
        # }

        hospital_for_doctor_page = None

        if doctor_realted_hospitals.filter(hospital_type=1).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(hospital_type=1).first()
        elif doctor_realted_hospitals.filter(hospital_type=2).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(hospital_type=2).first()
        elif doctor_realted_hospitals.filter(hospital_type=3).exists():
            hospital_for_doctor_page = doctor_realted_hospitals.filter(hospital_type=3).first()

        if hospital_for_doctor_page:
            specialization_name = [specialization.name for specialization in specializations]
            doctor_page_url = self.build_url("dr-%s-%s" %(entity_object.name, "-".join(specialization_name)),
                                             hospital_for_doctor_page.entity.all().filter(type="SUBLOCALITY").first())

            urls['page_urls'] = {
                'urls': doctor_page_url.lower(),
            }

        print(urls)
        return urls


class EntityHelperAsLab(EntityUrlsHelper):

    def _create_return_urls(self, entity_object):
        urls = dict()
        # search_urls = list()

        # lab_locations = entity_object.entity.filter(is_live=True).all()

        # if entity_object.data_status == 3:
        #     for location in lab_locations:
        #         url = self.build_url('labs', location)
        #         if location.type == EntityAddress.AllowedKeys.SUBLOCALITY:
        #             url = "%s-%s" % (url, 'lblitcit')
        #         elif location.type == EntityAddress.AllowedKeys.LOCALITY:
        #             url = "%s-%s" % (url, 'lbcit')
        #         if url:
        #             search_urls.append({'url': url.lower(), 'location_id': location.location_id})
        #
        # urls['search_urls'] = {
        #     'urls': search_urls,
        # }

        query_set_for_personal_url = entity_object.entity.all().filter(type="SUBLOCALITY", valid=True)
        if not query_set_for_personal_url.exists():
            query_set_for_personal_url = entity_object.entity.all().filter(type="LOCALITY", valid=True)

        if query_set_for_personal_url.exists():
            lab_page_url = self.build_url("%s" % entity_object.name, query_set_for_personal_url.first())
            if lab_page_url:
                lab_page_url = "%s-%s" % (lab_page_url, 'lab')

                urls['page_urls'] = {
                    'urls': lab_page_url.lower(),
                }

        print(urls)
        return urls


entity_as_mapping = {
    'DOCTOR': EntityHelperAsDoctor,
    'LAB': EntityHelperAsLab
}