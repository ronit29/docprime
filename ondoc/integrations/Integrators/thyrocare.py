from .baseIntegrator import BaseIntegrator
import requests
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from ondoc.integrations.models import IntegratorMapping
from django.contrib.contenttypes.models import ContentType


class Thyrocare(BaseIntegrator):

    # for getting thyrocare API Key
    @classmethod
    def thyrocare_auth(cls):
        username = settings.THYROCARE_USERNAME
        password = settings.THYROCARE_PASSWORD
        url = 'https://www.thyrocare.com/api_beta/common.svc/%s/%s/portalorders/DSA/login' % (username, password)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Thyrocare authentication failed.")
            return None

        resp_data = response.json()
        return {
            'api_key': resp_data['API_KEY']
        }

    @classmethod
    def thyrocare_product_data(cls, obj_id):
        response = cls.thyrocare_auth()
        api_key = response.get('api_key')

        if not api_key:
            logger.error("[ERROR] Not Authenticate")
            return None

        url = 'https://www.thyrocare.com/API_BETA/master.svc/%s/TESTS/products' % (api_key)
        product_data_response = requests.get(url)

        if product_data_response.status_code != status.HTTP_200_OK or not product_data_response.ok:
            logger.info("[ERROR] Thyrocare product fetching failed.")
            return None

        resp_data = product_data_response.json()
        if not resp_data.get('MASTERS', None):
            logger.error("[ERROR] No response from thyrocare master.")

        result_array = resp_data['MASTERS']['TESTS']
        if not result_array:
            logger.info("[ERROR] No tests data found.")
            return None

        for result_obj in result_array:
            IntegratorMapping(integrator_product_data=result_obj, integrator_test_name=result_obj['name'],
                              integrator_class_name=Thyrocare.__name__,
                              service_type=IntegratorMapping.ServiceType.LabTest, object_id=obj_id,
                              content_type=ContentType.objects.get(model='labtest')).save()

    def _get_appointment_slots(self):
        return {}

    def _get_is_user_area_serviceable(self, pincode):
        url = "https://www.thyrocare.com/API_BETA/order.svc/%s/%s/PincodeAvailability" % (settings.THYROCARE_API_KEY, pincode)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR] Thyrocare pincode availability api failed")
            return None

        resp_data = response.json()
        if not resp_data.get('status', None):
            return False

        return True if resp_data['status'] == 'Y' else False
