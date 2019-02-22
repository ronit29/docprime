from .baseIntegrator import BaseIntegrator
import requests
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping
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
    def thyrocare_data(cls, obj_id, type):
        response = cls.thyrocare_auth()
        api_key = response.get('api_key')

        if not api_key:
            logger.error("[ERROR] Not Authenticate")
            return None

        url = 'https://www.thyrocare.com/API_BETA/master.svc/%s/%s/products' % (api_key, type)
        product_data_response = requests.get(url)

        if product_data_response.status_code != status.HTTP_200_OK or not product_data_response.ok:
            logger.info("[ERROR] Thyrocare fetching failed.")
            return None

        resp_data = product_data_response.json()
        if not resp_data.get('MASTERS', None):
            logger.error("[ERROR] No response from thyrocare master.")

        result_array = resp_data['MASTERS'][type]
        if not result_array:
            logger.info("[ERROR] No tests data found.")
            return None

        for result_obj in result_array:
            if type == 'TESTS':
                try:
                    IntegratorMapping.objects.get(integrator_test_name=result_obj['name'], object_id=obj_id)
                except IntegratorMapping.DoesNotExist:
                    IntegratorMapping(integrator_product_data=result_obj, integrator_test_name=result_obj['name'],
                                      integrator_class_name=Thyrocare.__name__,
                                      service_type=IntegratorMapping.ServiceType.LabTest, object_id=obj_id,
                                      content_type=ContentType.objects.get(model='labnetwork')).save()
            else:
                try:
                    IntegratorProfileMapping.objects.get(integrator_package_name=result_obj['name'], object_id=obj_id)
                except IntegratorProfileMapping.DoesNotExist:
                    IntegratorProfileMapping(integrator_product_data=result_obj, integrator_package_name=result_obj['name'],
                                             integrator_class_name=Thyrocare.__name__,
                                             service_type=IntegratorProfileMapping.ServiceType.LabTest, object_id=obj_id,
                                             content_type=ContentType.objects.get(model='labnetwork')).save()

    @classmethod
    def thyrocare_product_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    @classmethod
    def thyrocare_profile_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    def _get_appointment_slots(self, pincode, date):
        url = 'https://www.thyrocare.com/API_BETA/ORDER.svc/%s/%s/GetAppointmentSlots' % (pincode, date)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR] Thyrocare Time slot api failed.")
            return None

        resp_data = response.json()
        return resp_data

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

    def __post_order_details(self, lab_appointment):
        # Need to update when thyrocare API works. Static value for now
        payload = { 'Api_key': settings.THYROCARE_API_KEY, 'orderid': '4301', 'address': 'c-19/13', 'pincode': '122001', 'product': 'TESTS', 'Std': '', 'phone_no': '', 'mobile': '9460746448', 'email':'mayankgupta@docprime.com', 'Tsp': '', 'service_type': 'H', 'order_by': 'Mayank', 'rate': '180', 'hc': '20', 'appt_date': '2019-02-01 05:00 PM', 'reports': 'N', 'ref_code':'', 'pay_type':'Prepaid', 'Geo_loction':'', 'bencount':'1', 'bendataxml': '<NewDataSet><Ben_details><Name>Mayank</Name><Age>30</Age><Gender>M</Gender></Ben_details></NewDataSet>'}
        headers = { 'Content-Type': "application/json" }
        url = "https://www.thyrocare.com/API_BETA/ORDER.svc/Postorderdata"

        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == status.HTTP_201_CREATED:
            return True
        return False
