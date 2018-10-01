from django.db import models
from django.contrib.gis.db import models as postgismodels
from ondoc.authentication import models as auth_model
from django.contrib.postgres.fields import JSONField
from django.contrib.gis.geos import Point
from django.conf import settings
from rest_framework.response import Response
from random import randint

# Create your models here.


class VisitorIpAddress(auth_model.TimeStampedModel):

    ip_address = models.CharField(max_length=50)
    visit_id = models.CharField(max_length=100, blank=True, null=True)
    visitor_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'visitor_ip_address'


class GeoIPEntries(auth_model.TimeStampedModel):

    ip_address = models.CharField(max_length=50)
    location_detail = JSONField()


    class Meta:
        db_table = "geoip_entries"


class Choices(object):
    @classmethod
    def as_choices(cls):
        properties = list(filter(lambda x : not x.startswith ("__"), dir(cls)))
        properties.remove ("as_choices")
        choices = []
        for prop in properties:
            val = getattr(cls, prop)
            choices.append((prop, val))
        return choices


class AdwordLocationCriteria(auth_model.TimeStampedModel):
    class Status(Choices):
        Active = 'Active'
        Inactive = 'Inactive'

    criteria_id = models.PositiveIntegerField()
    name = models.PositiveIntegerField()
    cannonical_name = models.CharField(max_length=1024, null=True, blank=True)
    parent_id = models.PositiveIntegerField()
    country_code = models.CharField(max_length=32, null=True, blank=True)
    target_type = models.CharField(max_length=200, null=True)
    latlong = postgismodels.PointField(geography=True, srid=4326, blank=True, null=True)
    status = models.CharField(max_length=24, default='Active', choices=Status.as_choices())

    class Meta:
        db_table = "adwords_location"
