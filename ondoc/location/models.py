from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from .service import get_meta_by_latlong
import logging
logger = logging.getLogger(__name__)
import json
from decimal import Decimal


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


class EntityAddress(models.Model):

    class AllowedKeys(Choices):
        LOCALITY = 'LOCALITY'
        SUBLOCALITY = 'SUBLOCALITY'
        ADMINISTRATIVE_AREA_LEVEL_1 = 'ADMINISTRATIVE_AREA_LEVEL_1'
        ADMINISTRATIVE_AREA_LEVEL_2 = 'ADMINISTRATIVE_AREA_LEVEL_1'
        COUNTRY = 'COUNTRY'

    type = models.CharField(max_length=128, blank=False, null=False, choices=AllowedKeys.as_choices())
    value = models.TextField()
    centroid = models.DecimalField(default=Decimal(0.00000000), max_digits=10, decimal_places=8)
    parent = models.IntegerField(null=True)

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
        if not kwargs.get('content_object', None):
            raise ValueError('Missing parameter: content_object')

        parent_id = None
        ea_list = list()
        for meta in meta_data:
            if meta['key'] not in cls.AllowedKeys.availabilities():
                logger.error("{key} is not the supported key ".format(key=meta['key']))
                raise ValueError('Not a supported key')

            if meta['key'] in cls.AllowedKeys.availabilities():
                saved_data = cls.objects.filter(type=meta['key'], value=meta['value'], parent=parent_id)
                if len(saved_data) == 1:
                    entity_address = saved_data[0]
                    parent_id = entity_address.id
                elif len(saved_data) == 0:
                    entity_address = cls(type=meta['key'], value=meta['value'], parent=parent_id)
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

    location = models.ForeignKey(EntityAddress, on_delete=models.CASCADE)
    type = models.CharField(max_length=128, blank=False, null=False, choices=EntityAddress.AllowedKeys.as_choices())

    @classmethod
    def create(cls, *args, **kwargs):
        ea_list = EntityAddress.get_or_create(**kwargs)
        for ea in ea_list:
            entity_location_relation = cls(content_object=kwargs.get('content_object'), type=ea.type, location=ea)
            entity_location_relation.save()

    class Meta:
        db_table = 'entity_location_relations'


class EntityUrls(models.Model):
    url = models.CharField(blank=False, null=True, max_length=500, unique=True)
    extras = models.TextField(default=json.dumps({}))
    is_valid = models.BooleanField(default=True)
    valid_reference = models.IntegerField(default=0)

    def create(self, *args, **kwargs):


    class Meta:
        db_table = 'entity_urls'



class DoctorsUrls(EntityUrls):

    def create(self, *args, **kwargs):

        pass

    class Meta:
        abstract = True