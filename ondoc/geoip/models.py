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
    DELHI_CENTRE_LAT = 28.644800
    DELHI_CENTRE_LONG = 77.216721

    CHAT_VALUE = 0
    LAB_QUERY_VALUE = 1
    DOCTOR_QUERY_VALUE = 2

    CDN_BASE_IMAGE_URL = 'https://cdn.docprime.com/static/web/images/'
    HOME_PRODUCTION_URL = 'https://docprime.com/'
    MOBILE_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_mobile_pb.svg",
                             CDN_BASE_IMAGE_URL + "lab_mobile_pb.svg",
                             CDN_BASE_IMAGE_URL + "doctor_mobile_pb.svg"]
    WEB_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_pb.svg", CDN_BASE_IMAGE_URL + "lab_pb.svg",
                          CDN_BASE_IMAGE_URL + "doctor_pb.svg"]
    SEARCH_URL_LIST = [HOME_PRODUCTION_URL, HOME_PRODUCTION_URL, HOME_PRODUCTION_URL]

    ip_address = models.CharField(max_length=50)
    location_detail = JSONField()

    def form_response(self):
        lat = self.location_detail["location"]["latitude"]
        long = self.location_detail["location"]["longitude"]
        user_loc = Point(long, lat)
        centre_loc = Point(self.DELHI_CENTRE_LONG, self.DELHI_CENTRE_LAT)
        dist = user_loc.distance(centre_loc)
        if dist <= settings.MAX_DIST_USER:
            val = self.get_rand_weighted_number(True)
        else:
            val = self.get_rand_weighted_number(False)
        resp = dict()
        resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[val]
        resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[val]
        resp["access_url"] = self.SEARCH_URL_LIST[val]
        resp["latitude"] = lat
        resp["longitude"] = long
        resp["city_name"] = self.location_detail["city"]["names"]["en"]
        return resp

    def get_rand_weighted_number(self, is_inside):
        x = 4
        if not is_inside:
            x = 3
        rand_val = randint(100000, 999999)
        value = rand_val % x
        resp = None
        if value <= 1:
            resp = self.CHAT_VALUE
        elif value <= 2:
            resp = self.LAB_QUERY_VALUE
        else:
            resp = self.DOCTOR_QUERY_VALUE
        return resp

    class Meta:
        db_table = "geoip_entries"
