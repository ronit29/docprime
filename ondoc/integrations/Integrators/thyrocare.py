from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from ondoc.api.v1.utils import TimeSlotExtraction
from .baseIntegrator import BaseIntegrator
import requests
import json
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, date
from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping, IntegratorResponse, IntegratorReport
from ondoc.diagnostic.models import LabReport, LabReportFile
from django.contrib.contenttypes.models import ContentType
from ondoc.api.v1.utils import resolve_address, aware_time_zone


class Thyrocare(BaseIntegrator):

    # for getting thyrocare API Key
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

    @classmethod
    def thyrocare_data(cls, obj_id, type):
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
            defaults = {'integrator_product_data': result_obj, 'service_type': IntegratorMapping.ServiceType.LabTest,
                        'integrator_class_name': Thyrocare.__name__, 'content_type': ContentType.objects.get(model='labnetwork')}

            if type == 'TESTS':
                IntegratorMapping.objects.update_or_create(integrator_test_name=result_obj['name'], object_id=obj_id, defaults=defaults)
            else:
                IntegratorProfileMapping.objects.update_or_create(integrator_package_name=result_obj['name'], object_id=obj_id, defaults=defaults)

    @classmethod
    def thyrocare_product_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    @classmethod
    def thyrocare_profile_data(cls, obj_id, type):
        cls.thyrocare_data(obj_id, type)

    def _get_appointment_slots(self, pincode, date, **kwargs):
        obj = TimeSlotExtraction()

        url = '%s/ORDER.svc/%s/%s/GetAppointmentSlots' % (settings.THYROCARE_BASE_URL, pincode, date)
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
        url = "%s/order.svc/%s/%s/PincodeAvailability" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY, pincode)
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
        url = "%s/ORDER.svc/Postorderdata" % (settings.THYROCARE_BASE_URL)

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

        order_id = "DP{}".format(lab_appointment.id)
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
            "appt_date": aware_time_zone(lab_appointment.time_slot_start).strftime("%Y-%m-%d %I:%M:%S %p"),
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

    @classmethod
    def get_generated_report(cls):
        integrator_bookings = IntegratorResponse.objects.filter(integrator_class_name=Thyrocare.__name__, report_received=False)
        formats = ['pdf', 'xml']
        for booking in integrator_bookings:
            lead_id = booking.lead_id
            mobile = booking.content_object.profile.phone_number
            result = dict()

            for format in formats:
                url = "%s/order.svc/%s/GETREPORTS/%s/%s/%s/Myreport" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY, lead_id, format, mobile)
                # url = "https://www.thyrocare.com/APIs/order.svc/sNhdlQjqvoD7zCbzf56sxppBJX3MmdWSAomi@RBhXRrVcGyko7hIzQ==/GETREPORTS/SP46592004/%s/8898881529/Myreport" %(format)
                response = requests.get(url)
                response = response.json()
                if response.get('RES_ID') == 'RES0000':
                    result[format] = response["URL"]
                else:
                    logger.error("[ERROR] %s" % response.get('RESPONSE'))

            if result:
                cls.save_reports(booking, result)

    @classmethod
    def save_reports(cls, integrator_response, result):
        # Save reports URL
        obj, created = IntegratorReport.objects.get_or_create(integrator_response_id=integrator_response.id, pdf_url=result["pdf"], xml_url=result["xml"])

        # Update integrator response when both type of report present
        if obj.pdf_url and obj.xml_url:
            cls.upload_report(obj)
            IntegratorResponse.objects.filter(pk=integrator_response.pk).update(report_received=True)


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
        except Exception as e:
            logger.error(str(e))

