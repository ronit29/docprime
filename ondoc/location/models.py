from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from .service import get_meta_by_latlong
import logging
logger = logging.getLogger(__name__)
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

    # Generic relationship

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    @classmethod
    def create(cls, *args, **kwargs):
        meta_data = get_meta_by_latlong(kwargs.get('latitude'), kwargs.get('longitude'))
        if not kwargs.get('content_object', None):
            raise ValueError('Missing parameter: content_object')

        parent_id = None
        for meta in meta_data:
            if meta['key'] not in cls.AllowedKeys.availabilities():
                logger.error("{key} is not the supported key ".format(key=meta['key']))
                raise ValueError('Not a supported key')

            if meta['key'] in cls.AllowedKeys.availabilities():
                saved_data = cls.objects.filter(type=meta['key'], value=meta['value'], parent=parent_id)
                if len(saved_data) == 1:
                    location = saved_data[0]
                    parent_id = location.id
                elif len(saved_data) == 0:
                    entity_address = cls(type=meta['key'], value=meta['value'], content_object=kwargs.get('content_object'),
                                         parent=parent_id)
                    entity_address.save()
                    parent_id = entity_address.id
            else:
                entity_address = cls(type=meta['key'], value=meta['value'], content_object=kwargs.get('content_object'),
                                     parent=parent_id)
                entity_address.save()
                parent_id = entity_address.id


    class Meta:
        db_table = 'entity_address'
