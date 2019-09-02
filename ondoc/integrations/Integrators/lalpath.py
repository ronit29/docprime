from decimal import Decimal

from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from django.db.models import Q

from ondoc.api.v1.utils import TimeSlotExtraction
from ondoc.integrations.models import IntegratorTestMapping, IntegratorCity, IntegratorTestCityMapping
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
    def get_test_data(cls, obj_id):
        url = "%s/BulkDataTestCityPrice" % settings.LAL_PATH_BASE_URL
        headers = {'apiKey': settings.LAL_PATH_DATA_API_KEY, 'Content-Type': "application/json"}
        response = requests.request("POST", url, headers=headers)
        response = response.json()

        all_data = response['Response']
        for data in all_data:
            integrator_city_id = data['CityID']
            integrator_city_name = data['CityName']
            integrator_city = IntegratorCity.objects.filter(city_id=integrator_city_id).first()
            if not integrator_city:
                integrator_city = IntegratorCity.objects.create(city_id=integrator_city_id, city_name=integrator_city_name)

            for test in data['Test']:
                defaults = {'integrator_product_data': test, 'integrator_class_name': Lalpath.__name__,
                            'content_type': ContentType.objects.get(model='labnetwork'),
                            'service_type': IntegratorTestMapping.ServiceType.LabTest,
                            'name_params_required': False, 'test_type': 'TEST'}
                itm_obj, created = IntegratorTestMapping.objects.update_or_create(integrator_test_name=test['TestName'],
                                                                                  object_id=obj_id, defaults=defaults)
                IntegratorTestCityMapping.objects.create(integrator_city=integrator_city, integrator_test_mapping=itm_obj)
                print(test['TestName'])




