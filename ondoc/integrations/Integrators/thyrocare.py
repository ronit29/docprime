from ondoc.api.v1.utils import TimeSlotExtraction
from .baseIntegrator import BaseIntegrator
import requests
import json
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from datetime import timedelta, datetime, date
from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import resolve_address, aware_time_zone


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

    def _get_appointment_slots(self, pincode, date, **kwargs):
        obj = TimeSlotExtraction()

        url = 'https://www.thyrocare.com/API_BETA/ORDER.svc/%s/%s/GetAppointmentSlots' % (pincode, date)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR] Thyrocare Time slot api failed.")
            return None

        resp_data = response.json()
        available_slots = resp_data.get('LSlotDataRes', [])

        if available_slots:
            start = available_slots[0]['Slot'].split("-")[0]
            hour, minutes = start.split(":")
            hour, minutes = float(hour), int(minutes)
            minutes = float("%0.2f" % (minutes/60))
            start = hour + minutes

            end = available_slots[len(available_slots)-1]['Slot'].split("-")[1]

            hour, minutes = end.split(":")
            hour, minutes = float(hour), int(minutes)
            minutes = float("%0.2f" % (minutes/60))
            end = hour + minutes

            obj.form_time_slots(datetime.strptime(date, '%d-%m-%Y').weekday(), start, end, None, True)

        resp_list = obj.get_timing_slots(date, is_thyrocare=True)
        is_home_pickup = kwargs.get('is_home_pickup', False)
        today_min, tomorrow_min, today_max = obj.initial_start_times(is_thyrocare=True, is_home_pickup=is_home_pickup, time_slots=resp_list)

        res_data = {
            "time_slots": resp_list,
            "today_min": today_min,
            "tomorrow_min": tomorrow_min,
            "today_max": today_max
        }

        return res_data

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

    def _post_order_details(self, lab_appointment, **kwargs):
        # Need to update when thyrocare API works. Static value for now

        tests = kwargs.get('tests', None)
        packages = kwargs.get('packages', None)
        payload = self.prepare_data(tests, packages, lab_appointment)

        headers = {'Content-Type': "application/json"}
        url = "https://www.thyrocare.com/API_BETA/ORDER.svc/Postorderdata"

        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response = response.json()
        if response.get('RES_ID') == 'RES0000':
            return response
        else:
            logger.error("[ERROR] %s" % response.get('RESPONSE'))

        return None

    def prepare_data(self, tests, packages, lab_appointment):
        profile = lab_appointment.profile
        if hasattr(lab_appointment, 'address') and lab_appointment.address:
            patient_address = resolve_address(lab_appointment.address)
            pincode = lab_appointment.address["pincode"]
        else:
            patient_address = "Dummy Address(No address found for user)"
            pincode = "122002"

        order_id = "DP00{}".format(lab_appointment.id)
        bendataxml = "<NewDataSet><Ben_details><Name>%s</Name><Age>%s</Age><Gender>%s</Gender></Ben_details></NewDataSet>" % (profile.name, self.calculate_age(profile), profile.gender)

        payload = {
            "api_key": settings.THYROCARE_API_KEY,
            "orderid": order_id,
            "address": patient_address,
            "pincode": pincode,
            "mobile": profile.phone_number if profile else "",
            "email": profile.email if profile else "",
            "service_type": "H",
            "order_by": profile.name if profile else "",
            "hc": "0",
            "appt_date": aware_time_zone(lab_appointment.time_slot_start).strftime("%Y-%m-%d %I:%M:%S %p"),  # Need to change it to IST
            "reports": "N",
            "ref_code": "7738943013",  # Fixed for Test Need to ask
            "pay_type": "POSTPAID",
            "bencount": "1",
            "bendataxml": bendataxml,
            "std": "91"
        }

        product = list()
        rate = 0
        if tests:
            for test in tests:
                integrator_test = IntegratorMapping.objects.filter(test_id=test.id, integrator_class_name=Thyrocare.__name__, is_active=True).first()
                if integrator_test:
                    product.append(integrator_test.integrator_product_data["code"])
                    rate += int(integrator_test.integrator_product_data["rate"]["b2c"])
                else:
                    logger.info("[ERROR] No tests data found in integrator.")

        if packages:
            for package in packages:
                integrator_package = IntegratorProfileMapping.objects.filter(package_id=package.id, integrator_class_name=Thyrocare.__name__, is_active=True).first()
                if integrator_package:
                    product.append(integrator_package.integrator_package_name)
                    rate += int(integrator_package.integrator_product_data["rate"]["b2c"])
                else:
                    logger.info("[ERROR] No package data found in integrator for.")

        if product:
            product_str = ",".join(product )
            payload["product"] = product_str

        payload["rate"] = rate

        return payload

    def calculate_age(self, profile):
        if not profile:
            return 0
        if not profile.dob:
            return 0
        dob = profile.dob
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))