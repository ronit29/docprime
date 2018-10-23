import requests
import logging
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import json
from .models import GoogleDetailing


def get_doctor_detail_from_google(place_sheet_obj):
    api_key = settings.GOOGLE_MAP_API_KEY
    try:
        for parameter in GoogleDetailing.Parameter.availabilities():
            if parameter == GoogleDetailing.Parameter.DOCTOR_CLINIC_ADDRESS:
                request_parameter = place_sheet_obj.doctor_clinic_address
            else:
                request_parameter = place_sheet_obj.clinic_address

            # Hitting the google api for find the place.
            kind = GoogleDetailing.Kind.FINDPLACE
            saved_json = GoogleDetailing.objects.filter(doc_place_sheet=place_sheet_obj, kind=kind, parameter=parameter)

            if not saved_json.exists():
                response = requests.get('https://maps.googleapis.com/maps/api/place/findplacefromtext/json?inputtype=textquery',
                                        params={'key': api_key, 'input': request_parameter})
                if response.status_code != status.HTTP_200_OK or not response.ok:
                    logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
                    logger.info("[ERROR] %s", response.reason)
                    return False
                else:
                    resp_data = response.json()

                    if resp_data.get('candidates', None) and isinstance(resp_data.get('candidates'), list) and \
                            len(resp_data.get('candidates')) > 0:
                        GoogleDetailing(raw_value=json.dumps(resp_data), kind=kind,
                                        parameter=parameter, doc_place_sheet=place_sheet_obj).save()
                    else:
                        logger.info("[ERROR] Google API for fetching the place id.")
                        logger.info("[ERROR] %s", response.reason)
                        return False

            else:
                resp_data = json.loads(saved_json.first().raw_value)

            candidate = resp_data.get('candidates')[0]
            place_id = candidate.get('place_id')
            if not place_id:
                return False

            # Now hitting the google api for fetching details of the doctor regarding place_id obtained above.

            kind = GoogleDetailing.Kind.DETAIL
            saved_json = GoogleDetailing.objects.filter(doc_place_sheet=place_sheet_obj, kind=kind, parameter=parameter)

            if not saved_json.exists():
                response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
                                        params={'key': api_key, 'place_id': place_id})
                if response.status_code != status.HTTP_200_OK or not response.ok:
                    logger.info("[ERROR] Google API for fetching the location via latitude and longitude failed.")
                    logger.info("[ERROR] %s", response.reason)
                    return False
                else:
                    resp_data = response.json()

                    if resp_data.get('result', None):
                        GoogleDetailing(raw_value=json.dumps(resp_data), kind=kind,
                                        parameter=parameter, doc_place_sheet=place_sheet_obj).save()
                    else:
                        logger.info("[ERROR] Google API for fetching the details on basis on place_id")
                        logger.info("[ERROR] %s", response.reason)
                        return False

            else:
                resp_data = json.loads(saved_json.first().raw_value)

        return True
    except Exception as e:
        print(str(e))
        return False


