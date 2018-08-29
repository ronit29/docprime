from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from .service import get_meta_by_latlong
import logging
logger = logging.getLogger(__name__)


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
        SUBLALITY = 'SUBLOCALITY'
        ROUTE = 'ROUTE'
        STREET_NUMBER = 'STREET_NUMBER'

    type = models.CharField(max_length=128, blank=False, null=False, choices=AllowedKeys.as_choices())
    value = models.TextField()

    # Generic relationship

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    @classmethod
    def create(cls, *args, **kwargs):
        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
        if kwargs.get('content_object', None):
            raise ValueError('Missing parameter: content_object')

        for meta in meta_data:
            if meta['key'] not in cls.AllowedKeys.availabilities():
                logger.error("{key} is not the supported key ".format(key=meta['key']))
                raise ValueError('Not a supported key')

            entity_address = cls(type=meta['key'], value=meta['value'], content_object=kwargs.get('content_object'))
            entity_address.save()

    class Meta:
        db_table = 'entity_address'
