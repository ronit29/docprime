import requests
import logging
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import json


def get_meta_by_latlong(lat, long):
    from .models import GeoIpResults
    saved_json = GeoIpResults.objects.filter(latitude=lat, longitude=long)

    if not saved_json.exists():
        response = requests.get('https://maps.googleapis.com/maps/api/geocode/json?sensor=false',
                                params={'latlng': '%s,%s' % (lat, long), 'key': settings.REVERSE_GEOCODING_API_KEY})
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
            logger.info("[ERROR] %s", response.reason)
            return []

        resp_data = response.json()
        GeoIpResults(value=json.dumps(resp_data), latitude=lat, longitude=long).save()

    else:
        resp_data = json.loads(saved_json.first().value)

    if resp_data.get('status', None) == 'OK' and len(resp_data.get('results', [])) > 0:
        obj = resp_data['results'][0]
        address_component = obj.get('address_components', [])
        resp_data = dict()
        for component in address_component:
            for key in component.get('types', []):
                sub_data = resp_data.get(key.upper(), None)
                resp_data[key.upper()] = component['long_name']

        result_list = list()

        for type in ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2', 'LOCALITY', 'SUBLOCALITY']:

            if type.upper() in resp_data.keys():
                result_list.append({'key': type, 'value': resp_data[type.upper()]})

        return result_list

    else:
        logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
        logger.info("[ERROR] %s", response.reason)
        return []


