from __future__ import absolute_import, unicode_literals

from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import time
import logging

logger = logging.getLogger(__name__)


def prepare_and_hit(self, data):

    appointment = data.get('appointment')
    task_data = data.get('task_data')

    appointment_details = {
        'DocPrimeBookingID': appointment.id,
        'BookingDateTime': time.mktime(appointment.created_at.timetuple()),
        'AppointmentDateTime': time.mktime(appointment.time_slot_start.timetuple()),
        'BookingType': 'DC' if task_data.get('type') == 'LAB_APPOINTMENT' else 'D',
        'AppointmentType': '',
        'PatientName': appointment.profile.name,
        'PatientAddress': appointment.user.address_set.all().first().address if len(appointment.user.address_set.all()) else '',
        'ProviderName': getattr(appointment, 'doctor').name if task_data.get('type') == 'OPD_APPOINTMENT' else getattr(appointment, 'lab').name,
        'ServiceName': "Blood test,city scan",
        'InsuranceCover': 1,
        'MobileList': data.get('mobile_list')
    }

    request_data = {
        'Name': appointment.profile.name,
        'PrimaryNo': appointment.user.phone_number,
        'LeadSource': 'DocPrime',
        'EmailId': 'testsk@gmail.com',
        'Gender': 1 if appointment.profile.gender == 'm' else 2 if appointment.profile.gender == 'f' else 0,
        'CityId': 0,
        'ProductId': task_data.get('product_id'),
        'SubProductId': task_data.get('sub_product_id'),
        'AppointmentDetails': appointment_details
    }

    url = settings.MATRIX_API_URL
    response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': 'RG9jcHJpbWU= d2Vi',
                                                              'Content-Type': 'application/json'})

    if response.status_code != status.HTTP_200_OK or not response.ok:
        logger.info("[ERROR] Appointment could not be published to the matrix system")
        logger.info("[ERROR] %s", response.reason)

        countdown_time = (2 ** self.request.retries) * 60 * 10
        logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
        print(countdown_time)
        self.retry([data], countdown=countdown_time)

    resp_data = response.json()
    print(str(resp_data))
    if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
        logger.info("[SUCCESS] Appointment successfully published to the matrix system")
    else:
        logger.info("[ERROR] Appointment could not be published to the matrix system")


@task(bind=True, max_retries=2)
def push_appointment_to_matrix(self, data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        if data.get('type') == 'OPD_APPOINTMENT':
            ACTIVE_APPOINTMENT_STATUS = [OpdAppointment.BOOKED, OpdAppointment.ACCEPTED,
                                         OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.RESCHEDULED_DOCTOR]

            appointment = OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, pk=appointment_id).first()
            mobile_list = list()
            # User mobile number
            mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})
            # Doctor mobile numbers
            doctor_mobiles = [doctor_mobile.number for doctor_mobile in appointment.doctor.mobiles.all()]
            doctor_mobiles = [{'MobileNo': number, 'Name': appointment.doctor.name, 'Type': 2} for number in doctor_mobiles]
            mobile_list.extend(doctor_mobiles)
        elif data.get('type') == 'LAB_APPOINTMENT':
            ACTIVE_APPOINTMENT_STATUS = [LabAppointment.BOOKED, LabAppointment.ACCEPTED,
                                         LabAppointment.RESCHEDULED_PATIENT, LabAppointment.RESCHEDULED_LAB]
            appointment = LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, pk=appointment_id).first()

            mobile_list = list()
            # User mobile number
            mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})

        # Preparing the data and now pushing the data to the matrix system.
        prepare_and_hit(self, {'appointment': appointment, 'mobile_list': mobile_list, 'task_data': data})

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment to the matrix- " + str(e))
