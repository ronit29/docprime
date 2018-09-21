from ondoc.api.v1.utils import get_request_ip
from ondoc.geoip.models import GeoIPEntries, VisitorIpAddress
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)


class GeoIPAddressURLViewSet(viewsets.GenericViewSet):

    def ip_details(self, request):
        resp = dict()
        req_data = request.query_params
        ip_address = req_data.get("address")
        if req_data.get("detect_ip") == "1":
            ip_address = get_request_ip(request)
        if not ip_address:
            resp["message"] = "Address Field is required"
            resp["status"] = 0
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        visitor_ip_add_obj = VisitorIpAddress.objects.create(ip_address=ip_address, visitor_id=req_data.get("visitor_id"), visit_id=req_data.get("visit_id"))

        geo_ip_obj = GeoIPEntries.objects.filter(ip_address=ip_address).first()
        url = settings.MAXMIND_CITY_API_URL + str(ip_address)
        if not geo_ip_obj:
            try:
                response = requests.get(url=url, auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY))
                if response.status_code == status.HTTP_200_OK:
                    resp_data = response.json()
                    geo_ip_obj = GeoIPEntries.objects.create(ip_address=ip_address, location_detail=resp_data)
                    resp = geo_ip_obj.form_response()
                    resp["status"] = 1
                else:
                    resp["status"] = 0
                    resp["message"] = "Cannot get details"
                    logger.error(
                        "Cannot get details from Max Mind for ip address - " + ip_address)
            except Exception as e:
                resp["status"] = 0
                resp["message"] = "Exception while getting details"
                logger.error(
                    "Exception while getting details from Max Mind for ip address - " + ip_address + " with exception - " + str(
                        e))
        else:
            resp = geo_ip_obj.form_response()
            resp["status"] = 1

        return Response(resp)
