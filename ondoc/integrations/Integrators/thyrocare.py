from decimal import Decimal

from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from django.db.models import Q

from ondoc.api.v1.utils import TimeSlotExtraction
from .baseIntegrator import BaseIntegrator
import requests
import json
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, date, timedelta
from ondoc.diagnostic.models import LabReport, LabReportFile, LabAppointment
from ondoc.common.models import AppointmentHistory
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import thyrocare_resolve_address, aware_time_zone
from django.utils import timezone
import time


class Thyrocare(BaseIntegrator):

    # This method provides thyrocare API Key
    @classmethod
    def thyrocare_auth(cls):
        url = '%s/common.svc/%s/%s/portalorders/DSA/login' % (settings.THYROCARE_BASE_URL, settings.THYROCARE_USERNAME, settings.THYROCARE_PASSWORD)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Thyrocare authentication failed.")
            return None

        resp_data = response.json()
        return {
            'api_key': resp_data['API_KEY']
        }

    # This provides all the test data of thyrocare.
    @classmethod
    def thyrocare_data(cls, obj_id, type):
        from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping, IntegratorTestMapping
        response = cls.thyrocare_auth()
        api_key = response.get('api_key')

        if not api_key:
            logger.error("[ERROR] Not Authenticate")
            return None

        url = '%s/master.svc/%s/%s/products' % (settings.THYROCARE_BASE_URL, api_key, type)
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
            name_required_tests = settings.THYROCARE_NAME_PARAM_REQUIRED_TESTS.split(',')
            name_params_required = False
            if result_obj['code'] in name_required_tests:
                name_params_required = True

            defaults = {'integrator_product_data': result_obj, 'integrator_class_name': Thyrocare.__name__,
                        'content_type': ContentType.objects.get(model='labnetwork'), 'service_type': IntegratorTestMapping.ServiceType.LabTest,
                        'name_params_required': name_params_required, 'test_type': result_obj['type']}

            IntegratorTestMapping.objects.update_or_create(integrator_test_name=result_obj['name'], object_id=obj_id, defaults=defaults)

            # if type == 'TESTS':
            #     name_required_tests = settings.THYROCARE_NAME_PARAM_REQUIRED_TESTS.split(',')
            #     name_params_required = False
            #     if result_obj['code'] in name_required_tests:
            #         name_params_required = True
            #
            #     defaults = {'integrator_product_data': result_obj, 'integrator_class_name': Thyrocare.__name__,
            #                 'content_type': ContentType.objects.get(model='labnetwork'), 'service_type': IntegratorMapping.ServiceType.LabTest,
            #                 'name_params_required': name_params_required}
            #     IntegratorMapping.objects.update_or_create(integrator_test_name=result_obj['name'], object_id=obj_id, defaults=defaults)
            # else:
            #     defaults = {'integrator_product_data': result_obj, 'integrator_class_name': Thyrocare.__name__,
            #                 'content_type': ContentType.objects.get(model='labnetwork'), 'integrator_type': result_obj['type'],
            #                 'service_type': IntegratorProfileMapping.ServiceType.LabTest}
            #     IntegratorProfileMapping.objects.update_or_create(integrator_package_name=result_obj['name'], object_id=obj_id, defaults=defaults)

    @classmethod
    def thyrocare_product_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    @classmethod
    def thyrocare_profile_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    @classmethod
    def thyrocare_offer_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    # This method provides available time slots for selected date.
    def _get_appointment_slots(self, pincode, date, **kwargs):
        if not pincode or not date:
            resp_list = dict()
            resp_list[date] = list()

            res_data = {"time_slots": resp_list, "upcoming_slots": [], "is_thyrocare": True}
            return res_data

        url = '%s/ORDER.svc/%s/%s/GetAppointmentSlots' % (settings.THYROCARE_BASE_URL, pincode, date)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR] Thyrocare Time slot api failed.")
            resp_list = dict()
            resp_list[date] = list()
            res_data = {"time_slots": resp_list, "upcoming_slots": [], "is_thyrocare": True}
            return res_data

        resp_data = response.json()
        available_slots = resp_data.get('LSlotDataRes', [])

        if available_slots:
            slots = set()
            for slot in available_slots:
                start = slot['Slot'].split("-")[0].strip()
                end = slot['Slot'].split("-")[1].strip()
                slots.add(start)
                slots.add(end)

            sorted_slots = sorted(slots)
            resp_list = self.time_slot_extraction(sorted_slots, date)
        else:
            resp_list = dict()
            resp_list[date] = list()

        res_data = {"time_slots": resp_list, "upcoming_slots": [], "is_thyrocare": True}
        return res_data

    # This method check if area is serviceable or not.
    def _get_is_user_area_serviceable(self, pincode):
        url = "%s/order.svc/%s/%s/PincodeAvailability" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY, pincode)
        response = requests.get(url)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR] Thyrocare pincode availability api failed")
            return None

        resp_data = response.json()
        if not resp_data.get('status', None):
            return False

        return True if resp_data['status'] == 'Y' else False

    # This method is use to push appointment to thyrocare.
    def _post_order_details(self, lab_appointment, **kwargs):
        from ondoc.integrations.models import IntegratorHistory

        tests = kwargs.get('tests', None)
        # packages = kwargs.get('packages', None)
        retry_count = kwargs.get('retry_count', 0)
        payload = self.prepare_data(tests, lab_appointment)

        headers = {'Content-Type': "application/json"}
        url = "%s/ORDER.svc/Postorderdata" % settings.THYROCARE_BASE_URL
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        status_code = response.status_code
        response = response.json()
        if response.get('RES_ID') == 'RES0000':
            # Add details to history table
            status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
            IntegratorHistory.create_history(lab_appointment, payload, response, url, 'post_order', 'Thyrocare', status_code, retry_count, status, '')
            resp_data = {
                "lead_id": response['ORDERRESPONSE']['PostOrderDataResponse'][0]['LEAD_ID'],
                "dp_order_id": response['ORDER_NO'],
                "integrator_order_id": response['REF_ORDERID'],
                "response_data": response
            }
            return resp_data
        else:
            status = IntegratorHistory.NOT_PUSHED
            IntegratorHistory.create_history(lab_appointment, payload, response, url, 'post_order', 'Thyrocare', status_code, retry_count, status, '')
            logger.error("[ERROR] %s" % response.get('RESPONSE'))

        return None

    # Preparing data for order.
    def prepare_data(self, tests, lab_appointment):
        from ondoc.integrations.models import IntegratorTestMapping

        profile = lab_appointment.profile
        if hasattr(lab_appointment, 'address') and lab_appointment.address:
            patient_address = thyrocare_resolve_address(lab_appointment.address)
            pincode = lab_appointment.address["pincode"]
        else:
            patient_address = ""
            pincode = ""

        if profile and profile.email:
            email = profile.email
        else:
            email = "provider@docprime.com"

        order_id = "DP{}".format(lab_appointment.id)
        if profile and profile.gender:
            gender = profile.gender.upper()
        else:
            gender = "M"

        bendataxml = "<NewDataSet><Ben_details><Name>%s</Name><Age>%s</Age><Gender>%s</Gender></Ben_details></NewDataSet>" % (profile.name, self.calculate_age(profile), gender)
        payload = {
            "api_key": settings.THYROCARE_API_KEY,
            "orderid": order_id,
            "address": patient_address,
            "pincode": pincode,
            "mobile": profile.phone_number if profile else "",
            "email": email,
            "service_type": "H",
            "order_by": profile.name if profile else "",
            "hc": "0",
            "appt_date": aware_time_zone(lab_appointment.time_slot_start).strftime("%Y-%m-%d %I:%M:%S %p"),
            "reports": "N",
            "ref_code": settings.THYROCARE_REF_CODE,
            "pay_type": "PREPAID",
            "bencount": "1",
            "bendataxml": bendataxml,
            "std": "91"
        }

        product = list()
        rate = 0
        if tests:
            for test in tests:
                integrator_test = IntegratorTestMapping.objects.filter(test_id=test.id, integrator_class_name=Thyrocare.__name__, is_active=True).first()
                if not integrator_test:
                    raise Exception("[ERROR] No tests data found in integrator.")

                if integrator_test.test_type == "TEST":
                    if integrator_test.name_params_required:
                        name = integrator_test.integrator_product_data["name"]
                    else:
                        name = integrator_test.integrator_product_data["code"]
                    product.append(name)
                elif integrator_test.test_type == "OFFER":
                    product.append(integrator_test.integrator_product_data["testnames"])
                    payload["report_code"] = integrator_test.integrator_product_data["code"]
                elif integrator_test.test_type == "PROFILE":
                    product.append(integrator_test.integrator_product_data["name"])
                else:
                    if integrator_test.integrator_product_data["testnames"] == 'null':
                        name = integrator_test.integrator_product_data["name"]
                    else:
                        name = integrator_test.integrator_product_data["testnames"]
                    product.append(name)

                rate += int(integrator_test.integrator_product_data["rate"]["b2c"])

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

    # This method provides report of lab test.
    @classmethod
    def get_generated_report(cls):
        from ondoc.integrations.models import IntegratorResponse
        if settings.THYROCARE_INTEGRATION_ENABLED:
            try:
                integrator_bookings = IntegratorResponse.objects.filter(integrator_class_name=Thyrocare.__name__, report_received=False)
                formats = ['pdf', 'xml']
                for booking in integrator_bookings:
                    print(booking.id)
                    dp_appointment = booking.content_object
                    if dp_appointment.time_slot_start + timedelta(days=1) <= timezone.now():
                        lead_id = booking.lead_id
                        mobile = booking.content_object.profile.phone_number
                        result = dict()

                        for format in formats:
                            url = "%s/order.svc/%s/GETREPORTS/%s/%s/%s/Myreport" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY, lead_id, format, mobile)
                            print(url)
                            response = requests.get(url)
                            response = response.json()
                            if response.get('RES_ID') == 'RES0000':
                                result[format] = response["URL"]
                            else:
                                logger.info("[ERROR] %s" % response.get('RESPONSE'))

                        if result:
                            cls.save_reports(booking, result)
            except Exception as e:
                logger.error(str(e))

    # This method is use to save report urls to db and update appointment.
    @classmethod
    def save_reports(cls, integrator_response, result):
        from ondoc.integrations.models import IntegratorResponse, IntegratorReport

        # Save reports URL
        if result.get('pdf', '') and result.get('xml', ''):
            obj, created = IntegratorReport.objects.get_or_create(integrator_response_id=integrator_response.id, pdf_url=result["pdf"], xml_url=result["xml"])

            # Update integrator response when both type of report present
            if obj.pdf_url and obj.xml_url:
                cls.upload_report(obj)
                IntegratorResponse.objects.filter(pk=integrator_response.pk).update(report_received=True)

    # This method is use to upload reports to s3 server and send to users.
    @classmethod
    def upload_report(cls, report):
        formats = ['pdf', 'xml']
        try:
            for format in formats:
                if format == 'pdf':
                    report_url = report.pdf_url
                else:
                    report_url = report.xml_url

                request = requests.get(report_url, stream=True)
                filename = "appointment_%s_report.%s" % (report.integrator_response.object_id, format)
                lf = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')

                for block in request.iter_content(1024 * 8):

                    # If no more file then stop
                    if not block:
                        break

                    # Write image block to temporary file
                    lf.write(block)

                lf.seek(0)
                lf.content_type = "application/%s" % format
                in_memory_file = InMemoryUploadedFile(lf, None, filename, lf.content_type, lf.tell(), None)

                lab_report, created = LabReport.objects.update_or_create(appointment_id=report.integrator_response.object_id)
                if lab_report:
                    LabReportFile.objects.create(report_id=lab_report.id, name=in_memory_file)
                    # Send Reports to Patient
                    from ondoc.notification.tasks import send_lab_reports
                    if format == 'pdf':
                        try:
                            send_lab_reports.apply_async((report.integrator_response.object_id,), countdown=1)
                        except Exception as e:
                            logger.error(str(e))
        except Exception as e:
            logger.error(str(e))

    # This method is use to cancel the booked appointment.
    def _cancel_order(self, appointment, integrator_response, retry_count):
        from ondoc.integrations.models import IntegratorHistory

        url = "%s/ORDER.svc/cancelledorder" % settings.THYROCARE_BASE_URL
        if appointment.cancellation_comments and appointment.cancellation_reason:
            reason = appointment.cancellation_reason.name + " " + appointment.cancellation_comments
        elif appointment.cancellation_reason:
            reason = appointment.cancellation_reason.name
        else:
            reason = ""

        payload = {
            "UserId": 2147,
            "OrderNo": integrator_response.integrator_order_id,
            "VisitId": integrator_response.integrator_order_id,
            "BTechId": 0,
            "Status": 2,
            "RemarksId": 67,
            "ReasonId": 172,  # Not interested
            "Others": reason,
            "AppointmentDate": "",
            "AppointmentSlot": ""
        }
        headers = {'Content-Type': "application/json"}
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        status_code = response.status_code
        response = response.json()
        if json.loads(response['RESPONSE'])['Response'] == "SUCCESS":
            status = IntegratorHistory.CANCELLED
            IntegratorHistory.create_history(appointment, payload, response, url, 'cancel_order', 'Thyrocare',
                                             status_code, retry_count, status, '')
            return response
        else:
            status = IntegratorHistory.NOT_PUSHED
            IntegratorHistory.create_history(appointment, payload, response, url, 'cancel_order', 'Thyrocare',
                                             status_code, retry_count, status, '')
            logger.error("[ERROR] %s" % response.get('RESPONSE'))

    # To get order summary of a pushed order.
    def _order_summary(self, integrator_response):
        from ondoc.integrations.models import IntegratorHistory

        dp_appointment = integrator_response.content_object
        lab_appointment_content_type = ContentType.objects.get_for_model(dp_appointment)
        integrator_history = IntegratorHistory.objects.filter(object_id=dp_appointment.id,
                                                              content_type=lab_appointment_content_type).order_by('id').last()
        if integrator_history:
            status = integrator_history.status
            if not dp_appointment.status in [LabAppointment.CANCELLED, LabAppointment.COMPLETED]:
                if dp_appointment.time_slot_start + timedelta(days=1) > timezone.now():
                    url = "%s/order.svc/%s/%s/%s/all/OrderSummary" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY,
                                                                      integrator_response.dp_order_id,
                                                                      integrator_response.response_data['MOBILE'])
                    response = requests.get(url)
                    status_code = response.status_code
                    response = response.json()
                    if response.get('RES_ID') == 'RES0000':
                        ## RESCHUDULE CASE AFTER DISSCUSSION
                        # thyrocare_appointment_time = response['LEADHISORY_MASTER'][0]['APPOINT_ON'][0]['DATE']
                        # thyrocare_appointment_time = datetime.strptime(thyrocare_appointment_time, "%d-%m-%Y %H:%M").strftime("%Y-%m-%d")
                        # dp_appointment_time = dp_appointment.time_slot_start.strftime("%Y-%m-%d")
                        # if not thyrocare_appointment_time == dp_appointment_time:
                        #     dp_appointment.time_slot_start = thyrocare_appointment_time
                        #     dp_appointment.status = 3
                        #     dp_appointment.save()

                        # check integrator order status and update docprime booking
                        if response['BEN_MASTER'][0]['STATUS'].upper() == 'YET TO ASSIGN':
                            status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
                        elif response['BEN_MASTER'][0]['STATUS'].upper() == 'YET TO CONFIRM':
                            status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
                        elif response['BEN_MASTER'][0]['STATUS'].upper() == "ACCEPTED":
                            if not dp_appointment.status in [5, 6, 7]:
                                # dp_appointment.status = 5
                                # dp_appointment.save()
                                dp_appointment._source = AppointmentHistory.API
                                dp_appointment.action_accepted()
                                status = IntegratorHistory.PUSHED_AND_ACCEPTED
                        elif response['BEN_MASTER'][0]['STATUS'].upper() == 'CANCELLED':
                            if not dp_appointment.status == 6:
                                # dp_appointment.status = 6
                                # dp_appointment.save()
                                dp_appointment.action_cancelled(1)
                                status = IntegratorHistory.CANCELLED

                        IntegratorHistory.create_history(dp_appointment, url, response, url, 'order_summary_cron', 'Thyrocare', status_code, 0, status, 'integrator_api')
                    else:
                        print("[ERROR] %s %s" % (integrator_response.id, response.get('RESPONSE')))

    def time_slot_extraction(self, slots, date):
        am_timings, pm_timings = list(), list()
        am_dict, pm_dict = dict(), dict()
        time_dict = dict()
        for slot in slots:
            hour, minutes = slot.split(":")
            hour, minutes = float(hour), int(minutes)
            minutes = float("%0.2f" % (minutes/60))
            value = hour + minutes
            data = {"text": slot, "value": value, "price": None, "is_available": True, "on_call": False}

            if value >= 12.0:
                pm_timings.append(data)
            else:
                am_timings.append(data)

        am_dict["title"] = "AM"
        am_dict["type"] = "AM"
        am_dict["timing"] = am_timings
        pm_dict["title"] = "PM"
        pm_dict["type"] = "PM"
        pm_dict["timing"] = pm_timings

        time_dict[date] = list()
        time_dict[date].append(am_dict)
        time_dict[date].append(pm_dict)
        return time_dict

    # This method provides test parameters.
    @classmethod
    def get_test_parameter(cls):
        from ondoc.diagnostic.models import TestParameterChat
        from ondoc.integrations.models import IntegratorTestParameterMapping

        url = "%s/ORDER.svc/%s/ALL/GetReferenceValue" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY)
        response = requests.get(url)
        response = response.json()
        if response['RES_ID'] == 'RES0000':
            test_parameters = response['TEST_MASTER']
            if test_parameters:
                for parameter in test_parameters:
                    integrator_data = {'response_data': parameter}
                    data = {'age_to': parameter['AGE_TO'], 'age_from': parameter['AGE_FROM'], 'gender': parameter['GENDER'], 'min_range': parameter['MIN_RANGE'], 'max_range': parameter['MAX_RANGE']}
                    if parameter['MIN_RANGE'] == '':
                        data['min_range'] = None

                    if parameter['MAX_RANGE'] == '':
                        data['max_range'] = None

                    # Save to model
                    print(parameter)
                    test_parameter = TestParameterChat.objects.update_or_create(test_name=parameter['TEST_NAME'], defaults=data)
                    IntegratorTestParameterMapping.objects.update_or_create(integrator_test_name=parameter['TEST_NAME'], test_parameter_chat_id=test_parameter[0].id,
                                                                     integrator_class_name=Thyrocare.__name__, defaults=integrator_data)
