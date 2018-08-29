import requests
import logging
from rest_framework import status
import logging
logger = logging.getLogger(__name__)


def get_meta_by_latlong(lat, long):
    response = requests.get('http://maps.googleapis.com/maps/api/geocode/json?sensor=false',
                 params={'latlng': '44.42514,26.10540'})
    if response.status_code != status.HTTP_200_OK or not response.ok:
        logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
        logger.info("[ERROR] %s", response.reason)
        return {}

    resp_data = response.json()
    if resp_data.get('status',None) == 'OK' and len(resp_data.get('results', [])) > 0:
        obj = resp_data['results'][0]
        address_component = obj.get('address_components', [])
        resp_data = dict()
        for component in address_component:
            for key in component.get('types', []):
                resp_data[key.upper()] = component['long_name']

        result_list = list()

        from .models import EntityAddress

        for type in EntityAddress.AllowedKeys.availabilities():
            if type.upper() in resp_data.keys():
                result_list.append({'key': type, 'value': resp_data[key.upper()]})
        return result_list

    else:
        logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
        logger.info("[ERROR] %s", response.reason)
        return {}
