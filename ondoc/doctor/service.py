import requests
import logging
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import json
from .models import GoogleDetailing
from copy import deepcopy


def get_doctor_detail_from_google(place_sheet_obj):
    api_key = settings.GOOGLE_MAP_API_KEY
    try:
        # For doctor_clinic_address.
        if not place_sheet_obj.doctor_place_search:
            # Hitting the google api for find the place for doctor_clinic_address.
            request_parameter = place_sheet_obj.doctor_clinic_address
            response = requests.get('https://maps.googleapis.com/maps/api/place/findplacefromtext/json?inputtype=textquery',
                                    params={'key': api_key, 'input': request_parameter})
            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Google API for fetching doctor_clinic_address place id.")
                logger.info("[ERROR] %s", response.reason)
                return False
            else:
                resp_data = response.json()
        else:
            resp_data = json.loads(place_sheet_obj.doctor_place_search)

        doctor_place_search_data = deepcopy(resp_data)

        if resp_data.get('candidates', None) and isinstance(resp_data.get('candidates'), list) and len(resp_data.get('candidates')) > 0:
            candidate = resp_data.get('candidates')[0]
            place_id = candidate.get('place_id')
            if not place_id:
                return False
        else:
            logger.info("[ERROR] Invalid data recieved from google api for doctor_clinic_data.")
            return False

        if not place_sheet_obj.doctor_detail:
            # Now hitting the google api for fetching details of the doctor regarding place_id obtained above.
            response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
                                    params={'key': api_key, 'place_id': place_id})
            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Google API for fetching detail on basis of place_id")
                logger.info("[ERROR] %s", response.reason)
                return False
            else:
                resp_data = response.json()
        else:
            resp_data = json.loads(place_sheet_obj.doctor_detail)

        doctor_detail_search_data = deepcopy(resp_data)
        if not resp_data.get('result', None):
            logger.info("[ERROR] Invalid data recieved from google detail api for doctor_clinic_address.")
            return False

        result = resp_data.get('result')
        # Extract the useful information from the above api.
        doctor_formatted_address = result.get('formatted_address', '')
        doctor_number = result.get('formatted_phone_number', '')
        doctor_international_number = result.get('international_phone_number', '')
        doctor_name = result.get('name', '')

        resp_data = None



        # For clinic_address.
        if not place_sheet_obj.clinic_place_search:
            # Hitting the google api for find the place for clinic_address.
            request_parameter = place_sheet_obj.clinic_address
            response = requests.get('https://maps.googleapis.com/maps/api/place/findplacefromtext/json?inputtype=textquery',
                                    params={'key': api_key, 'input': request_parameter})
            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Google API for fetching clinic_address place id.")
                logger.info("[ERROR] %s", response.reason)
                return False
            else:
                resp_data = response.json()
        else:
            resp_data = json.loads(place_sheet_obj.clinic_place_search)

        clinic_place_search_data = deepcopy(resp_data)

        if resp_data.get('candidates', None) and isinstance(resp_data.get('candidates'), list) and len(resp_data.get('candidates')) > 0:
            candidate = resp_data.get('candidates')[0]
            place_id = candidate.get('place_id')
            if not place_id:
                return False
        else:
            logger.info("[ERROR] Invalid data recieved from google api for clinic_address.")
            return False

        if not place_sheet_obj.clinic_detail:
            # Now hitting the google api for fetching details of the doctor regarding place_id obtained above.
            response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
                                    params={'key': api_key, 'place_id': place_id})
            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Google API for fetching detail on basis of place_id for clinic_address")
                logger.info("[ERROR] %s", response.reason)
                return False
            else:
                resp_data = response.json()
        else:
            resp_data = json.loads(place_sheet_obj.clinic_detail)

        clinic_detail_search_data = deepcopy(resp_data)
        if not resp_data.get('result', None):
            logger.info("[ERROR] Invalid data recieved from google detail api for clinic_address.")
            return False

        result = resp_data.get('result')
        # Extract the useful information from the above api.
        clinic_formatted_address = result.get('formatted_address', '')
        clinic_number = result.get('formatted_phone_number', '')
        clinic_international_number = result.get('international_phone_number', '')
        clinic_name = result.get('name', '')

        place_sheet_obj.doctor_place_search = json.dumps(doctor_place_search_data)
        place_sheet_obj.clinic_place_search = json.dumps(clinic_place_search_data)
        place_sheet_obj.doctor_detail = json.dumps(doctor_detail_search_data)
        place_sheet_obj.clinic_detail = json.dumps(clinic_detail_search_data)
        place_sheet_obj.doctor_number = doctor_number
        place_sheet_obj.clinic_number = clinic_number
        place_sheet_obj.doctor_international_number = doctor_international_number
        place_sheet_obj.clinic_international_number = clinic_international_number
        place_sheet_obj.doctor_formatted_address = doctor_formatted_address
        place_sheet_obj.clinic_formatted_address = clinic_formatted_address
        place_sheet_obj.doctor_name = doctor_name
        place_sheet_obj.clinic_name = clinic_name
        place_sheet_obj.save()

        return True
    except Exception as e:
        print(str(e))
        return False


