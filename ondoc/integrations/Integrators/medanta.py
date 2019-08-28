from .baseIntegrator import BaseIntegrator
import requests
import json
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, date, timedelta
from django.contrib.contenttypes.models import ContentType
from ondoc.integrations.models import IntegratorDoctorMappings, IntegratorHistory
from ondoc.api.v1.utils import aware_time_zone


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
        # if all_doctors_data['ErrorCode']:
        #     logger.info("[ERROR-MEDANTA] Failed to fetch doctor details - %s", all_doctors_data['ErrorMessage'])
        #     return None

        for doc_data in all_doctors_data:
            print(doc_data)
            defaults = {'integrator_doctor_data': doc_data, 'integrator_class_name': Medanta.__name__, 'first_name': doc_data['DoctorName']}
            IntegratorDoctorMappings.objects.update_or_create(integrator_doctor_id=doc_data['ID'], defaults=defaults)

    def _get_appointment_slots(self, pincode, date, **kwargs):

        dc_obj = kwargs.get('dc_obj', None)
        doctor_id = None
        if dc_obj:
            doc_mapping = IntegratorDoctorMappings.objects.filter(doctor_clinic_id=dc_obj.id, is_active=True).first()
            if doc_mapping:
                doctor_id = doc_mapping.integrator_doctor_id

        if doctor_id:
            converted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y/%m/%d")
            consultation_type = "In Person"
            url = "https://www.medantaeclinic.org/rest/api/user/patient/availablity?consultationType=%s&doctor=%s" \
                  "&fromDate=%s&toDate=%s" % (consultation_type, doctor_id, converted_date, converted_date)

            response = requests.get(url)
            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR-MEDANTA] Failed to get timeslots.")
                return None

            resp_data = response.json()
            print(resp_data)
            if resp_data['status'] == 'SUCCESS':
                available_slots = resp_data["data"]['availability']
                if available_slots:
                    all_slots = set()
                    for avlbl_slot in available_slots:
                        slots = avlbl_slot['slots']
                        if slots:
                            slots = slots.split(',')
                            for s in slots:
                                start = s.split("-")[0].strip()
                                end = s.split("-")[1].strip()
                                all_slots.add(start)
                                all_slots.add(end)

                    sorted_slots = sorted(all_slots)
                    resp_list = self.time_slot_extraction(sorted_slots, date, dc_obj)
                else:
                    resp_list = dict()
                    resp_list[date] = list()
            else:
                resp_list = dict()
                resp_list[date] = list()

            res_data = {"timeslots": resp_list, "upcoming_slots": [], "is_integrated": True}
            return res_data

    def time_slot_extraction(self, slots, date, dc_obj):
        from ondoc.doctor.models import DoctorClinicTiming
        deal_price = None
        mrp = None
        fees = None
        cod_deal_price = None

        weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
        dc_timing = DoctorClinicTiming.objects.filter(doctor_clinic_id=dc_obj.id, day=weekday).first()
        if dc_timing:
            deal_price = dc_timing.deal_price
            mrp = dc_timing.mrp
            fees = dc_timing.fees
            cod_deal_price = dc_timing.cod_deal_price

        am_timings, pm_timings = list(), list()
        am_dict, pm_dict = dict(), dict()
        time_dict = dict()
        for slot in slots:
            hour, minutes = slot.split(":")
            hour, minutes = float(hour), int(minutes)
            minutes = float("%0.2f" % (minutes / 60))
            value = hour + minutes
            data = {"text": slot, "value": value, "price": None, "is_available": True, "on_call": False,
                    "deal_price": deal_price, "mrp": mrp, "fees": fees, "is_price_zero": False, "cod_deal_price": cod_deal_price}

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

    def get_auth_token(self):
        url = '%s/login' % settings.MEDANTA_API_BASE_URL
        body = {'username': 'Docprime_Technologies', 'password': '1234'}
        response = requests.post(url, data=body)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            return None

        response = response.json()
        return response['token']

    def _post_order_details(self, appointment, **kwargs):
        auth_token = self.get_auth_token()
        retry_count = kwargs.get('retry_count', 0)
        integrator_mapping = kwargs.get('integrator_mapping', None)
        if integrator_mapping:
            payload = self.prepare_payload(integrator_mapping, appointment)

            url = "%s/rest/api/external/appointment/booking" % (settings.MEDANTA_API_BASE_URL)
            headers = {'Content-Type': 'application/json', 'X-AuthToken': auth_token}

            response = requests.post(url, data=json.dumps(payload), headers=headers)
            status_code = response.status_code
            if response.status_code != status.HTTP_200_OK or not response.ok:
                h_status = IntegratorHistory.NOT_PUSHED
                IntegratorHistory.create_history(appointment, '', response, url, 'post_order', 'Sims', status_code,
                                                 retry_count, h_status, '')
                logger.error("[ERROR-SIMS] Failed to push appointment - %s", response.json())
                return None
            else:
                response = response.json()
                h_status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
                IntegratorHistory.create_history(appointment, '', response, url, 'post_order', 'Sims', status_code,
                                                 retry_count, h_status, '')
                return response

        return None

    def prepare_payload(self, integrator_mapping, appointment):
        doctor_id = integrator_mapping.integrator_doctor_id
        preferred_date = aware_time_zone(appointment.time_slot_start).strftime("%d/%m/%Y %H:%M:%S")
        # preferred_time = appointment.time_slot_start.strftime("%H:%M")
        name = appointment.profile_detail.get("name", "")
        profile = appointment.profile
        if profile:
            dob = profile.dob.strftime("%d/%m/%Y")

        if profile and profile.gender == 'm':
            gender = 'MALE'
        elif profile and profile.gender == 'f':
            gender = 'FEMALE'
        else:
            gender = "NA"

        payload = {
            "birthDate": dob,
            "isdCode": '91',
            'contactNumber': profile.phone_number,
            'email': profile.email,
            'firstName': name,
            'lastName': 'Ji',
            'gender': gender,
            'consultMode': 'In person',
            'patientQuery': 'For consultation',
            'doctorId': doctor_id,
            'preferredDate': preferred_date,
            'uploads': []
        }

        return payload

    # def _cancel_order(self, appointment, integrator_response, retry_count):
    #     integrator_appointment_id = integrator_response.lead_id
    #     url = "https://www.medantaeclinic.org/rest/api/userDirectCancel/appointment/" \
    #           "cancel/%s?reasonCode=Patient%27s+Requests" % integrator_appointment_id
    #     response = requests.post(url)

