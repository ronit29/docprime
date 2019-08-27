from decimal import Decimal

from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from django.db.models import Q

from ondoc.api.v1.utils import TimeSlotExtraction
from ondoc.integrations.models import IntegratorTestMapping
from .baseIntegrator import BaseIntegrator
import requests
from django.conf import settings
import json
from rest_framework import status
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, date, timedelta
from ondoc.diagnostic.models import LabReport, LabReportFile, LabAppointment
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import thyrocare_resolve_address, aware_time_zone
from django.utils import timezone
import time


class Lalpath(BaseIntegrator):

    @classmethod
    def get_test_data(self):
        url = "%s/BulkDataTestCityPrice" % settings.LAL_PATH_BASE_URL
        headers = {'apiKey': settings.LAL_PATH_API_KEY}
        response = requests.request("POST", url, headers=headers)
        response = response.json()

        all_data = response['Response']
        for data in all_data:
            integrator_city_id = data['CityID']
            integrator_city = data['CityName']
            for test in data['Test']:
                defaults = {'integrator_product_data': test, 'integrator_class_name': Lalpath.__name__,
                            'content_type': ContentType.objects.get(model='labnetwork'),
                            'service_type': IntegratorTestMapping.ServiceType.LabTest,
                            'name_params_required': False, 'test_type': 'TEST'}
                IntegratorTestMapping.objects.update_or_create(integrator_test_name=test['TestName'],
                                                               object_id=45, integrator_city=integrator_city,
                                                               integrator_city_id=integrator_city_id,
                                                               defaults=defaults)
                print(test['TestName'])






