from ondoc.geoip.models import GeoIPEntries, VisitorIpAddress, AdwordLocationCriteria
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from ipware import get_client_ip
import requests
import logging
from django.db import transaction
from random import randint
import geoip2.webservice

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
    ALT_TEXT_DOCTOR = 'Book Online Doctor Appointment'
    ALT_TEXT_LAB = 'Book Lab Tests'
    ALT_TEXT_CHAT = 'Online Doctor Consultation'
    MOBILE_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_mobile_pb2.png",
                             CDN_BASE_IMAGE_URL + "lab_mobile_pb2.png",
                             CDN_BASE_IMAGE_URL + "doctor_mobile_pb2.png"]
    WEB_IMAGE_URL_LIST = [CDN_BASE_IMAGE_URL + "chat_pb1.png", CDN_BASE_IMAGE_URL + "lab_pb1.png",
                          CDN_BASE_IMAGE_URL + "doctor_pb1.png"]
    ALT_TEXT_LIST = [ALT_TEXT_CHAT, ALT_TEXT_LAB, ALT_TEXT_DOCTOR]
    SEARCH_URL_LIST = [REDIRECT_PRODUCTION_URL_CHAT, REDIRECT_PRODUCTION_URL_LAB, REDIRECT_PRODUCTION_URL_DOCTOR]

    @transaction.non_atomic_requests
    def ip_details(self, request):
        resp = dict()
        resp["status"] = 1
        val = self.get_rand_weighted_number(True)
        resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[val]
        resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[val]
        resp["alt_text"] = self.ALT_TEXT_LIST[val]
        resp["access_url"] = self.SEARCH_URL_LIST[val]
        # resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[0]
        # resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[0]
        # resp["alt_text"] = self.ALT_TEXT_LIST[0]
        # resp["access_url"] = self.REDIRECT_PRODUCTION_URL_CHAT
        resp["latitude"] = self.DELHI_CENTRE_LAT
        resp["longitude"] = self.DELHI_CENTRE_LONG
        resp["city_name"] = 'Delhi'

        # req_data = request.query_params
        # ip_address = req_data.get("address")
        # if req_data.get("detect_ip") == "1":
        #     ip_address, is_routable = get_client_ip(request)
        # if not ip_address:
        #     return Response(resp)

        # visitor_ip_add_obj = VisitorIpAddress.objects.create(ip_address=ip_address, visitor_id=req_data.get("visitor_id"), visit_id=req_data.get("visit_id"))
        # if ip_address.startswith('10.'):
        #     return Response(resp)
        # geo_ip_obj = GeoIPEntries.objects.filter(ip_address=ip_address).first()
        # url = settings.MAXMIND_CITY_API_URL + str(ip_address)
        # if not geo_ip_obj:
        #     try:
        #         response = requests.get(url=url, auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY))
        #         if response.status_code == status.HTTP_200_OK:
        #             resp_data = response.json()
        #             geo_ip_obj = GeoIPEntries.objects.create(ip_address=ip_address, location_detail=resp_data)
        #             resp = self.form_response(resp_data, resp)
        #         else:
        #             pass
        #     except Exception as e:
        #         pass
        #
        # else:
        #     resp = self.form_response(geo_ip_obj.location_detail, resp)
        #     resp["status"] = 1

        return Response(resp)

    # def form_response(self, location, resp):
    #
    #     try:
    #         lat = location["location"]["latitude"]
    #         long = location["location"]["longitude"]
    #         user_loc = Point(long, lat)
    #         centre_loc = Point(self.DELHI_CENTRE_LONG, self.DELHI_CENTRE_LAT)
    #         dist = user_loc.distance(centre_loc)
    #         if dist <= settings.MAX_DIST_USER:
    #             val = self.get_rand_weighted_number(True)
    #         else:
    #             val = self.get_rand_weighted_number(False)
    #         city_name = location["city"]["names"]["en"]
    #
    #         resp = dict()
    #         resp["latitude"] = lat
    #         resp["longitude"] = long
    #         resp["web_image_url"] = self.WEB_IMAGE_URL_LIST[val]
    #         resp["mobile_image_url"] = self.MOBILE_IMAGE_URL_LIST[val]
    #         resp["access_url"] = self.SEARCH_URL_LIST[val]
    #         resp["alt_text"] = self.ALT_TEXT_LIST[val]
    #         resp["city_name"] = city_name
    #         resp["status"] = 1
    #     except Exception:
    #         pass
    #
    #     return resp

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

    @transaction.non_atomic_requests
    def get_geoip_data(self, request):

        default = dict()
        default["latitude"] = None
        default["longitude"] = None
        default["city"] = None

        ip_address, is_routable = get_client_ip(request)
        if False and ip_address.startswith('60'):
            ip_keys = ['HTTP_X_FORWARDED_FOR', 'X_FORWARDED_FOR',
            'HTTP_CLIENT_IP',
            'HTTP_X_REAL_IP',
            'HTTP_X_FORWARDED',
            'HTTP_X_CLUSTER_CLIENT_IP',
            'HTTP_FORWARDED_FOR',
            'HTTP_FORWARDED',
            'HTTP_VIA',
            'REMOTE_ADDR']
            results = []
            for key in ip_keys:
                value = request.META.get(key, request.META.get(key.replace('_', '-'), '')).strip()
                x = dict()
                x[key] = value
                results.append(x)
            logger.error(results)

        if not ip_address or not is_routable:
            return Response(default)

        req_data = request.query_params
        visitor_ip_add_obj = VisitorIpAddress.objects.create(ip_address=ip_address,
                                                             visitor_id=req_data.get("visitor_id"),
                                                             visit_id=req_data.get("visit_id"))

        geo_ip_obj = GeoIPEntries.objects.filter(ip_address=ip_address).first()
        url = settings.MAXMIND_CITY_API_URL + str(ip_address)
        if not geo_ip_obj:
            try:
                client = geoip2.webservice.Client(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY)
                response = client.city(ip_address)
                resp = {}
                resp['city'] = response.city.name
                resp['latitude'] = response.location.latitude
                resp['longitude'] = response.location.longitude
                resp['status'] = 1

                geo_ip_obj = GeoIPEntries.objects.create(ip_address=ip_address, location_detail=resp)
                return Response(resp)
            except Exception as e:
                pass
        else:
            return Response(geo_ip_obj.location_detail)       

        return Response(default)

    @transaction.non_atomic_requests
    def get_lat_long_city(self, request):
        resp = dict()
        resp["latitude"] = self.DELHI_CENTRE_LAT
        resp["longitude"] = self.DELHI_CENTRE_LONG
        resp["city"] = 'Delhi'

        ip_address, is_routable = get_client_ip(request)
        if not ip_address:
            return Response(resp)

        req_data = request.query_params
        visitor_ip_add_obj = VisitorIpAddress.objects.create(ip_address=ip_address,
                                                             visitor_id=req_data.get("visitor_id"),
                                                             visit_id=req_data.get("visit_id"))
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
                    resp["latitude"] = resp_data["location"]["latitude"]
                    resp["longitude"] = resp_data["location"]["longitude"]
                    resp["city"] = resp_data["city"]["names"]["en"]
                else:
                    pass
            except Exception as e:
                pass

        else:
            try:
                resp["latitude"] = geo_ip_obj.location_detail["location"]["latitude"]
                resp["longitude"] = geo_ip_obj.location_detail["location"]["longitude"]
                resp["city"] = geo_ip_obj.location_detail["city"]["names"]["en"]
                resp["status"] = 1
            except Exception:
                pass

        return Response(resp)


class AdwordLocationCriteriaViewset(viewsets.GenericViewSet):

    def get_queryset(self):
        return AdwordLocationCriteria.objects.filter(status=AdwordLocationCriteria.Status.Active)

    @transaction.non_atomic_requests
    def retrieve(self, request, criteria_id):
        if not criteria_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(criteria_id=criteria_id)
        if queryset.exists():
            data = {}
            obj = queryset.first()
            if obj.latlong:
                data['latitude'] = obj.latlong.y
                data['longitude'] = obj.latlong.x
            return Response(status=status.HTTP_200_OK, data=data)
        else:
            return Response({"error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)
