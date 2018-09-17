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

    if resp_data.get('status', None) == 'OK' and isinstance(resp_data.get('results'), list) and len(resp_data.get('results')) > 0:
        result_array = resp_data['results']

        response_list = list()

        # Take the address component with longest length as it can provide us the most relevant address.
        max_length = 0
        address_component = None
        for result_obj in result_array:
            if len(result_obj.get('address_components', [])) > max_length:
                address_component = result_obj.get('address_components')
                max_length = len(result_obj.get('address_components'))

        if not address_component:
            return response_list

        resp_data = dict()
        # address_component.reverse()

        for component in address_component:
            for key in component.get('types', []):
                resp_data[key.upper()] = component['long_name']

        for type in ['COUNTRY', 'ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_2', 'LOCALITY', 'SUBLOCALITY',
                     'SUBLOCALITY_LEVEL_1', 'SUBLOCALITY_LEVEL_2', 'SUBLOCALITY_LEVEL_3']:

            if type.upper() in resp_data.keys():
                if type.upper().startswith('SUBLOCALITY_LEVEL'):
                    response_list.append({'key': 'SUBLOCALITY', 'type': type, 'postal_code': resp_data['POSTAL_CODE'],
                                          'value': resp_data[type.upper()]})
                else:
                    response_list.append({'key': type, 'type': type, 'postal_code': resp_data['POSTAL_CODE'],
                                          'value': resp_data[type.upper()]})

        return response_list

    else:
        logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
        logger.info("[ERROR] %s", response.reason)
        return []


