import logging
import requests
import json
from django.conf import settings
from ondoc.integrations.models import IntegratorTestMapping, IntegratorCity, IntegratorTestCityMapping
from .baseIntegrator import BaseIntegrator
logger = logging.getLogger(__name__)
from datetime import date, timedelta
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import resolve_address
from ondoc.account.models import Order
from rest_framework import status
from django.utils import timezone


class Lalpath(BaseIntegrator):

    @classmethod
    def get_test_data(cls):
        url = "%s/BulkDataTestCityPrice" % settings.LAL_PATH_BASE_URL
        obj_id = settings.LAL_PATH_NETWORK_ID
        headers = {'apiKey': settings.LAL_PATH_DATA_API_KEY, 'Content-Type': "application/json"}
        response = requests.request("POST", url, headers=headers)
        response = response.json()

        all_data = response['Response']
        for data in all_data:
            integrator_city_id = data['CityID']
            integrator_city_name = data['CityName']
            integrator_city = IntegratorCity.objects.filter(city_id=integrator_city_id).first()
            if not integrator_city:
                integrator_city = IntegratorCity.objects.create(city_id=integrator_city_id,
                                                                city_name=integrator_city_name)

            for test in data['Test']:
                defaults = {'integrator_product_data': test, 'integrator_class_name': Lalpath.__name__,
                            'content_type': ContentType.objects.get(model='labnetwork'),
                            'service_type': IntegratorTestMapping.ServiceType.LabTest,
                            'name_params_required': False, 'test_type': 'TEST'}
                itm_obj, created = IntegratorTestMapping.objects.update_or_create(integrator_test_name=test['TestName'],
                                                                                  object_id=obj_id, defaults=defaults)
                IntegratorTestCityMapping.objects.create(integrator_city=integrator_city,
                                                         integrator_test_mapping=itm_obj)
                print(test['TestName'])

    def get_auth_token(self):
        username = settings.LAL_PATH_USERNAME
        password = settings.LAL_PATH_PASSWORD
        url = "https://lalpathlabs.com/partner/api/v1/login"
        payload = {"username": username, "password": password}
        headers = {'Content-Type': "application/json"}
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == status.HTTP_200_OK or not response.ok:
            resp_data = response.json()
            return resp_data["token"]

        return None

    def _post_order_details(self, lab_appointment, **kwargs):
        from ondoc.integrations.models import IntegratorHistory
        tests = kwargs.get('tests', None)
        retry_count = kwargs.get('retry_count', 0)
        payload = self.prepare_data(tests, lab_appointment)
        url = "%s/CreateOrder" % settings.LAL_PATH_BASE_URL
        api_key = self.get_auth_token()
        if api_key:
            headers = {'apiKey': api_key, 'Content-Type': "application/json"}
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            status_code = response.status_code
            if response.status_code != status.HTTP_200_OK or not response.ok:
                history_status = IntegratorHistory.NOT_PUSHED
                IntegratorHistory.create_history(lab_appointment, payload, response.json(), url, 'post_order', 'Lalpath',
                                                 status_code, retry_count, history_status, '')
                logger.error("[ERROR-Lalpath] %s" % response.json())
            else:
                # Add details to history table
                history_status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
                IntegratorHistory.create_history(lab_appointment, payload, response.json(), url, 'post_order', 'Lalpath',
                                                 status_code, retry_count, history_status, '')
                lal_path_response_id = response.json().get('OrderID')
                resp_data = {
                    "lead_id": lal_path_response_id,
                    "dp_order_id": lab_appointment.id,
                    "integrator_order_id": lal_path_response_id,
                    "response_data": response.json()
                }
                return resp_data
        return None

    def prepare_data(self, tests, lab_appointment):
        profile = lab_appointment.profile
        patient_address = ""
        if hasattr(lab_appointment, 'address') and lab_appointment.address:
            patient_address = resolve_address(lab_appointment.address)
            # address_id = lab_appointment.address.get('id')
            # Address.objects.filter(id=address_id).first()

        if profile:
            age = self.calculate_age(profile)
            if profile.gender:
                gender = profile.gender
                if gender == 'm':
                    gender = '1'
                    if age > 15:
                        salution = '1'
                    else:
                        salution = '4'
                else:
                    gender = '2'
                    salution = '2'

        number = "9560488461"
        mask_number = lab_appointment.mask_number.all().filter(is_deleted=False).first()
        if mask_number:
            number = mask_number.mask_number
            if len(number) > 10:
                number = number[1:]

        lab = lab_appointment.lab
        patient_details = {
            "SALUTATION": salution,
            "LName": profile.name,
            "age": str(age),
            "gender": gender,
            "mobile": number,
            "email": "",
            "city": lab.city if lab else "",
            "Address": patient_address,
            "Preferred_Date": lab_appointment.time_slot_start.strftime("%d/%m/%Y")
        }

        if lab:
            lab_codes = lab.lab_code.all().first()

        test_details = []
        order_amount = 0
        if tests:
            for test in tests:
                integrator_test = IntegratorTestMapping.objects.filter(test_id=test.id, is_active=True,
                                                                       integrator_class_name=Lalpath.__name__).first()
                if not integrator_test:
                    raise Exception("[ERROR] No tests data found in integrator.")
                data = {
                    "TestName": integrator_test.integrator_test_name,
                    "TestCode": integrator_test.integrator_product_data['TestCode'],
                    "mrp": integrator_test.integrator_product_data['MRP'], "discount": "0",
                    "price": integrator_test.integrator_product_data['MRP']
                }
                order_amount += int(data['mrp'])
                test_details.append(data)

        if order_amount >= 2000:
            hcc = 0
        else:
            hcc = 100

        order_details = {
            "orderAmt": order_amount,
            "actualAmt": order_amount,
            "payable_amt": order_amount,
            "HCC": hcc,
            "InvoiceCode": settings.LAL_PATH_INVOICE_CODE,
            "LabCode": lab_codes.lab_code if lab_codes else "",
            "WareHouseCode": lab_codes.warehouse_code if lab_codes else "",
            "invoiceid": "DPLP"+str(lab_appointment.id)
        }

        request_data = {
            "Order": order_details,
            "Patient": patient_details,
            "TestDetails": test_details,
            "isEmailRequired": False
        }

        return request_data

    def calculate_age(self, profile):
        if not profile:
            return 0
        if not profile.dob:
            return 0
        dob = profile.dob
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def _order_summary(self, integrator_response):
        from ondoc.integrations.models import IntegratorHistory
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.common.models import AppointmentHistory

        dp_appointment = integrator_response.content_object
        lab_appointment_content_type = ContentType.objects.get_for_model(dp_appointment)
        integrator_history = IntegratorHistory.objects.filter(object_id=dp_appointment.id,
                                                              content_type=lab_appointment_content_type).order_by('id').last()
        if integrator_history:
            status = integrator_history.status
            if dp_appointment.status not in [LabAppointment.CANCELLED, LabAppointment.COMPLETED]:
                if dp_appointment.time_slot_start + timedelta(days=1) > timezone.now():
                    url = "%s/CheckOrderStatus" % settings.LAL_PATH_BASE_URL
                    api_key = settings.LAL_PATH_DATA_API_KEY
                    if api_key:
                        headers = {'apiKey': api_key, 'Content-Type': "application/json"}
                        payload = {'OrderId': integrator_response.integrator_order_id}
                        response = requests.post(url, data=json.dumps(payload), headers=headers)
                        status_code = response.status_code
                        response = response.json()
                        if response['data']:
                            res_data = sorted(response['data'], key=lambda i: i['id'], reverse=True)
                            integrator_status = res_data[0]['status_code']
                            if int(integrator_status) == 40:
                                if dp_appointment.status not in [5, 6, 7]:
                                    dp_appointment._source = AppointmentHistory.API
                                    dp_appointment.action_accepted()
                                    status = IntegratorHistory.PUSHED_AND_ACCEPTED
                            elif int(integrator_status) in [30, 50]:
                                if not dp_appointment.status == 6:
                                    dp_appointment.action_cancelled(1)
                                    status = IntegratorHistory.CANCELLED
                            elif int(integrator_status) in [80]:
                                if not dp_appointment.status == 7:
                                    dp_appointment.action_completed()

                            IntegratorHistory.create_history(dp_appointment, url, response, url, 'order_summary_cron',
                                                             'Lalpath', status_code, 0, status, 'integrator_api')
                        else:
                            print("[LalPath-ERROR] %s %s" % (integrator_response.id, response.get('RESPONSE')))
