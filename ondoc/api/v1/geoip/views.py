from ondoc.geoip.models import GeoIPEntries, VisitorIpAddress
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from ipware import get_client_ip
import requests
import logging
from django.contrib.gis.geos import Point
from random import randint

logger = logging.getLogger(__name__)


class GeoIPAddressURLViewSet(viewsets.GenericViewSet):

    DELHI_CENTRE_LAT = 28.644800
    DELHI_CENTRE_LONG = 77.216721

    CHAT_VALUE = 0
    LAB_QUERY_VALUE = 1
    DOCTOR_QUERY_VALUE = 2

    CDN_BASE_IMAGE_URL = 'https://cdn.docprime.com/static/web/images/'
    REDIRECT_PRODUCTION_URL_DOCTOR = 'https://docprime.com?journey_type=doctor&utm_source=pb&utm_medium=link&utm_content=doctor'
    REDIRECT_PRODUCTION_URL_LAB = 'https://docprime.com?journey_type=lab&utm_source=pb&utm_medium=link&utm_content=lab'
    REDIRECT_PRODUCTION_URL_CHAT = 'https://docprime.com?journey_type=consult&utm_source=pb&utm_medium=link&utm_content=consult'
    ALT_TEXT_DOCTOR = 'Book Online Doctor Appointment '
    ALT_TEXT_LAB = 'Book Lab Tests'
    ALT_TEXT_CHAT = 'Online Doctor Consultation '
    MOBILE_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_mobile_pb2.png",
                             CDN_BASE_IMAGE_URL + "lab_mobile_pb2.png",
                             CDN_BASE_IMAGE_URL + "doctor_mobile_pb2.png"]
    WEB_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_pb1.png", CDN_BASE_IMAGE_URL + "lab_pb1.png",
                          CDN_BASE_IMAGE_URL + "doctor_pb1.png"]
    ALT_TEXT_LIST = [ALT_TEXT_CHAT, ALT_TEXT_LAB, ALT_TEXT_DOCTOR]
    SEARCH_URL_LIST = [REDIRECT_PRODUCTION_URL_CHAT, REDIRECT_PRODUCTION_URL_LAB, REDIRECT_PRODUCTION_URL_DOCTOR]

    def ip_details(self, request):
        resp = dict()
        resp["status"] = 1
        resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[0]
        resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[0]
        resp["alt_text"] = self.ALT_TEXT_LIST[0]
        resp["access_url"] = 'https://docprime.com'
        resp["latitude"] = self.DELHI_CENTRE_LAT
        resp["longitude"] = self.DELHI_CENTRE_LONG
        resp["city_name"] = 'Delhi'

        req_data = request.query_params
        ip_address = req_data.get("address")
        if req_data.get("detect_ip") == "1":
            ip_address, is_routable = get_client_ip(request)
        if not ip_address:
            return Response(resp)

        visitor_ip_add_obj = VisitorIpAddress.objects.create(ip_address=ip_address, visitor_id=req_data.get("visitor_id"), visit_id=req_data.get("visit_id"))
        if ip_address.startswith('10.'):
            return Response(resp)
        geo_ip_obj = GeoIPEntries.objects.filter(ip_address=ip_address).first()
        url = settings.MAXMIND_CITY_API_URL + str(ip_address)
        if not geo_ip_obj:
            try:
                response = requests.get(url=url, auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY))
                if response.status_code == status.HTTP_200_OK:
                    resp_data = response.json()
                    geo_ip_obj = GeoIPEntries.objects.create(ip_address=ip_address, location_detail=resp_data)
                    resp = self.form_response(resp_data, resp)
                else:
                    pass
            except Exception as e:
                pass
                
        else:
            resp = self.form_response(geo_ip_obj.location_detail, resp)
            resp["status"] = 1

        return Response(resp)

    def form_response(self, location, resp):

        try:
            lat = location["location"]["latitude"]
            long = location["location"]["longitude"]
            user_loc = Point(long, lat)
            centre_loc = Point(self.DELHI_CENTRE_LONG, self.DELHI_CENTRE_LAT)
            dist = user_loc.distance(centre_loc)
            if dist <= settings.MAX_DIST_USER:
                val = self.get_rand_weighted_number(True)
            else:
                val = self.get_rand_weighted_number(False)
            city_name = location["city"]["names"]["en"]

            resp = dict()
            resp["latitude"] = lat
            resp["longitude"] = long
            resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[val]
            resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[val]
            resp["access_url"] = self.SEARCH_URL_LIST[val]
            resp["alt_text"] = self.ALT_TEXT_LIST[val]
            resp["city_name"] = city_name
            resp["status"] = 1
        except Exception:
            pass

        return resp

    def get_rand_weighted_number(self, is_inside):
        x = 3
        if not is_inside:
            x = 2
        rand_val = randint(100000, 999999)
        value = rand_val % x
        resp = None
        if value <= 0:
            resp = self.CHAT_VALUE
        elif value <= 1:
            resp = self.LAB_QUERY_VALUE
        else:
            resp = self.DOCTOR_QUERY_VALUE
        return resp
