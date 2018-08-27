from __future__ import absolute_import, unicode_literals

from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import time
import logging

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=2)
def push_appointment_to_matrix(self, data):
    from ondoc.doctor.models import OpdAppointment
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        ACTIVE_APPOINTMENT_STATUS = [OpdAppointment.BOOKED, OpdAppointment.ACCEPTED,
                                     OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.RESCHEDULED_DOCTOR]

        opd_appointment = OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, pk=appointment_id).first()
        mobile_list = list()
        # User mobile number
        mobile_list.append({'MobileNo': opd_appointment.user.phone_number, 'Name': opd_appointment.profile.name, 'Type': 1})
        # Doctor mobile numbers
        doctor_mobiles = [doctor_mobile.number for doctor_mobile in opd_appointment.doctor.mobiles.all()]
        doctor_mobiles = [{'MobileNo': number, 'Name': opd_appointment.doctor.name, 'Type': 2} for number in doctor_mobiles]
        mobile_list.extend(doctor_mobiles)

        appointment_details = {
            'DocPrimeBookingID': opd_appointment.id,
            'BookingDateTime': time.mktime(opd_appointment.created_at.timetuple()),
            'AppointmentDateTime': time.mktime(opd_appointment.time_slot_start.timetuple()),
            'BookingType': 'DC',
            'AppointmentType': '',
            'PatientName': opd_appointment.profile.name,
            'PatientAddress': opd_appointment.user.address_set.all().first().address if len(opd_appointment.user.address_set.all()) else '',
            'ProviderName': "city clinic",
            'ServiceName': "Blood test,city scan",
            'InsuranceCover': 1,
            'MobileList': mobile_list
        }

        request_data = {
            'Name': opd_appointment.profile.name,
            'PrimaryNo': opd_appointment.user.phone_number,
            'LeadSource': 'DocPrime',
            'EmailId': 'testsk@gmail.com',
            'Gender': opd_appointment.profile.gender,
            'CityId': '',
            'ProductId': data.get('product_id'),
            'SubProductId': data.get('sub_product_id'),
            'AppointmentDetails': appointment_details
        }

        url = settings.MATRIX_API_URL
        response = requests.post(url, data=request_data, headers={'authorization': 'RG9jcHJpbWU= d2Vi',
                                                                  'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Appointment could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)
        else:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Refund Failure with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()
        print(str(resp_data))
        if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
            logger.info("[SUCCESS] Appointment successfully published to the matrix system")
        else:
            logger.info("[ERROR] Appointment could not be published to the matrix system")

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Opd Appointment to the matrix- " + str(e))
