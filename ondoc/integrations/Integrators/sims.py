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


class Sims(BaseIntegrator):

    # This method is use to get all the doctor data from hospital.
    @classmethod
    def get_doctor_data(cls):
        url = '%s/GetDoctor' % settings.SIMS_BASE_URL
        doctors_data_response = requests.get(url)

        if doctors_data_response.status_code != status.HTTP_200_OK or not doctors_data_response.ok:
            logger.info("[ERROR-SIMS] Failed to fetch doctor details.")
            return None

        all_doctors_data = doctors_data_response.json()
        for doc_data in all_doctors_data:
            print(doc_data)
            defaults = {'integrator_doctor_data': doc_data, 'integrator_class_name': Sims.__name__,
                        'specialities': doc_data['Doctor_Specialisation'], 'first_name': doc_data['Doctor_name']
                       }
            IntegratorDoctorMappings.objects.update_or_create(integrator_doctor_id=doc_data['Doctor_id'], defaults=defaults)
