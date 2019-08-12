from .baseIntegrator import BaseIntegrator
import requests
import json
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, date, timedelta
from django.contrib.contenttypes.models import ContentType
from ondoc.integrations.models import IntegratorDoctorMappings


class Medanta(BaseIntegrator):

    @classmethod
    def get_doctor_data(cls):
        url = '%s' % settings.MEDANTA_DOCTOR_LIST_URL
        header_name = settings.MEDANTA_DOCTOR_LIST_USER_HEADER
        header_value = settings.MEDANTA_DOCTOR_LIST_USER_VALUE
        header_pass_name = settings.MEDANTA_DOCTOR_LIST_PASSWORD_HEADER
        header_pass_value = settings.MEDANTA_DOCTOR_LIST_PASSWORD_VALUE
        headers = {header_name: header_value, header_pass_name: header_pass_value}
        doctors_data_response = requests.get(url, headers=headers)

        if doctors_data_response.status_code != status.HTTP_200_OK or not doctors_data_response.ok:
            logger.info("[ERROR-MEDANTA] Failed to fetch doctor details.")
            return None

        all_doctors_data = json.loads(doctors_data_response.json())
        if all_doctors_data['ErrorCode']:
            logger.info("[ERROR-MEDANTA] Failed to fetch doctor details - %s", all_doctors_data['ErrorMessage'])
            return None

        for doc_data in all_doctors_data:
            print(doc_data)
            defaults = {'integrator_doctor_data': doc_data, 'integrator_class_name': Medanta.__name__, 'first_name': doc_data['DoctorName']}
            IntegratorDoctorMappings.objects.update_or_create(integrator_doctor_id=doc_data['ID'], defaults=defaults)
