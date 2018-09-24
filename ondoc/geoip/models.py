from django.db import models
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
