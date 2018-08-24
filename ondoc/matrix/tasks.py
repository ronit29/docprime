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
        appointment_details = {
            'DocPrimeBookingID': opd_appointment.id,
            'BookingDateTime': time.mktime(opd_appointment.created_at.timetuple()),
            'AppointmentDateTime': time.mktime(opd_appointment.time_slot_start.timetuple()),
            'BookingType': 'DC',
            'AppointmentType': '',
            'PatientName':opd_appointment.profile_detail.get('name'),
            'PatientAddress': ''
        }

        request_data = {
            'Name': '',
            'PrimaryNo': opd_appointment.user.phone_number,
            'LeadSource': 'DocPrime',
            'EmailId': 'testsk@gmail.com',
            'Gender': opd_appointment.profile.gender,
            'CityId': '',
            'ProductId': data.get('product_id'),
            'SubProductId': data.get('sub_product_id'),
            'AppointmentDetails': appointment_details
        }

        url = settings.PG_REFUND_URL
        print(url)
        response = requests.post(url, data=request_data, headers={})
        resp_data = response.json()


    except Exception as e:
        logger.error("Error in Celery. Failed pushing Opd Appointment to the matrix- " + str(e))
