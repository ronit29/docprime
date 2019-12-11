from __future__ import absolute_import, unicode_literals

import requests
from celery import task
import logging
from django.conf import settings
from rest_framework import status
import json
from ondoc.salespoint.mongo_models import SalesPointLog

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=3)
def push_lab_appointment_to_integrator(self, data):
    from django.contrib.contenttypes.models import ContentType
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.integrations.models import IntegratorResponse, IntegratorTestMapping
    from ondoc.integrations import service

    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Matrix")

        appointment = LabAppointment.objects.filter(pk=appointment_id).first()

        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        if appointment.status == LabAppointment.BOOKED:
            lab = appointment.lab
            lab_tests = appointment.tests.all()
            lab_network = lab.network

            if not lab or not lab_tests or not lab_network:
                logger.error("[ERROR] Cant find lab, lab_network or lab_test")

            lab_network_content_type = ContentType.objects.get_for_model(lab_network)

            if not lab_tests:
                raise Exception('[ERROR] Could not find any test and packages for the appointment id %d' % appointment.id)

            # check integrator mapping available for each test
            integrator_mapping = True
            for test in lab_tests:
                integrator_mapping = IntegratorTestMapping.objects.filter(content_type=lab_network_content_type, object_id=lab_network.id, test=test, is_active=True).first()
                if not integrator_mapping:
                    integrator_mapping = False

            if not integrator_mapping:
                raise Exception("[ERROR] Mapping not found for booked test or package - appointment id %d" % appointment.id)

            integrator_obj = service.create_integrator_obj(integrator_mapping.integrator_class_name)
            retry_count = push_lab_appointment_to_integrator.request.retries
            integrator_response = integrator_obj.post_order(appointment, tests=lab_tests, retry_count=retry_count)

            if not integrator_response:
                countdown_time = (1 ** self.request.retries) * 60
                print(countdown_time)
                self.retry([data], countdown=countdown_time)

            # save integrator response
            resp_data = integrator_response
            IntegratorResponse.objects.create(lead_id=resp_data['lead_id'], dp_order_id=resp_data['dp_order_id'],
                                              integrator_order_id=resp_data['integrator_order_id'],
                                              content_object=appointment, response_data=resp_data['response_data'],
                                              integrator_class_name=integrator_mapping.integrator_class_name)

        elif appointment.status == LabAppointment.CANCELLED:
            saved_response = IntegratorResponse.objects.filter(object_id=appointment.id).first()
            if not saved_response:
                raise Exception("[ERROR] Cant find integrator response for appointment id " + str(appointment.id))

            integrator_obj = service.create_integrator_obj(saved_response.integrator_class_name)
            retry_count = push_lab_appointment_to_integrator.request.retries
            response = integrator_obj.cancel_integrator_order(appointment, saved_response, retry_count)

            if not response:
                countdown_time = (1 ** self.request.retries) * 60
                print(countdown_time)
                self.retry([data], countdown=countdown_time)

    except Exception as e:
        logger.error(str(e))


@task(bind=True, max_retries=3)
def get_integrator_order_status(self, *args, **kwargs):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.integrations.models import IntegratorResponse, IntegratorHistory

    appointment_id = kwargs.get('appointment_id', None)
    appointment = LabAppointment.objects.filter(pk=appointment_id).first()

    if not appointment:
        raise Exception("Appointment could not found against id - " + str(appointment_id))

    integrator_response = IntegratorResponse.objects.filter(object_id=appointment.id).first()

    if not integrator_response:
        raise Exception("Integrator Response not found for appointment id - " + str(appointment_id))

    url = "%s/order.svc/%s/%s/%s/all/OrderSummary" % (settings.THYROCARE_BASE_URL, settings.THYROCARE_API_KEY,
                                                      integrator_response.dp_order_id,
                                                      integrator_response.response_data['MOBILE'])
    response = requests.get(url)
    status_code = response.status_code
    response = response.json()
    retry_count = get_integrator_order_status.request.retries
    if response.get('RES_ID') == 'RES0000' and response['BEN_MASTER'][0]['STATUS'].upper() == "ACCEPTED":
        if not appointment.status in [5, 6, 7]:
            appointment.status = 5
            appointment.save()
            status = IntegratorHistory.PUSHED_AND_ACCEPTED
            IntegratorHistory.create_history(appointment, url, response, url, 'order_summary', 'Thyrocare',
                                             status_code, retry_count, status, 'integrator_api')
    else:
        countdown_time = (2 ** self.request.retries) * 60 * 2
        print(countdown_time)
        status = IntegratorHistory.PUSHED_AND_NOT_ACCEPTED
        IntegratorHistory.create_history(appointment, url, response, url, 'order_summary', 'Thyrocare',
                                         status_code, retry_count, status, '')
        self.retry(**kwargs, countdown=countdown_time)


@task(bind=True, max_retries=2)
def push_appointment_to_spo(self, data):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.account.models import Order
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Matrix")

        product_id = data.get('product_id')
        sub_product_id = data.get('sub_product_id')

        order_product_id = 2
        appointment = LabAppointment.objects.filter(pk=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        appointment_order = Order.objects.filter(product_id=order_product_id, reference_id=appointment_id).first()
        request_data = appointment.get_spo_data(appointment_order, product_id, sub_product_id)

        url = settings.VIP_SALESPOINT_URL
        spo_api_token = settings.VIP_SALESPOINT_AUTHTOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': spo_api_token,
                                                                              'Content-Type': 'application/json'})
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR-SPO] Failed to push appointment details - " + str(json.dumps(request_data)))

            countdown_time = (2 ** self.request.retries) * 60 * 10
            self.retry([data], countdown=countdown_time)
            SalesPointLog.create_spo_logs(appointment, request_data, response)
        else:
            resp_data = response.json()
            resp_data = resp_data['data']
            if resp_data.get('error', None):
                logger.info("[ERROR-SPO] Appointment could not be published to the SPO system - " + str(json.dumps(request_data)))
                logger.info("[ERROR-SPO] %s", resp_data.get('errorDetails', []))
            else:
                logger.info("Response = " + str(resp_data))
                lead_id = resp_data.get('leadId', '')
                if lead_id:
                    # save the appointment with the spo lead id.
                    qs = LabAppointment.objects.filter(id=appointment.id)
                    if qs:
                        qs.update(spo_lead_id=int(lead_id))

            SalesPointLog.create_spo_logs(appointment, request_data, resp_data)
        # logger.error("[NO_SUCCESS-SPO] Lead ID")
    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment to the SPO- " + str(e))


@task(bind=True, max_retries=3)
def push_opd_appointment_to_integrator(self, data):
    from ondoc.diagnostic.models import OpdAppointment
    from ondoc.integrations.models import IntegratorResponse, IntegratorDoctorMappings, IntegratorDoctorClinicMapping
    from ondoc.integrations import service

    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Integrator")

        appointment = OpdAppointment.objects.filter(pk=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        if not appointment.integrator_response_available():
            dc_obj = appointment.get_doctor_clinic()
            if not dc_obj:
                raise Exception("Doctor Clinic id not found, could not push to Integrator")

            if appointment.status == OpdAppointment.BOOKED:
                # integrator_mapping = IntegratorDoctorMappings.objects.filter(doctor_clinic_id=dc_obj, is_active=True).first()
                dc_mapping = IntegratorDoctorClinicMapping.objects.filter(doctor_clinic_id=dc_obj.id).first()
                if not dc_mapping:
                    raise Exception("[ERROR] Mapping not found for doctor or hospital - appointment id %d" % appointment.id)

                integrator_mapping = IntegratorDoctorMappings.objects.filter(id=dc_mapping.integrator_doctor_mapping_id).first()
                if not integrator_mapping:
                    raise Exception("[ERROR] Mapping not found for doctor or hospital - appointment id %d" % appointment.id)

                integrator_obj = service.create_integrator_obj(integrator_mapping.integrator_class_name)
                retry_count = push_opd_appointment_to_integrator.request.retries
                integrator_response = integrator_obj.post_order(appointment, dc_obj=dc_obj,
                                                                integrator_mapping=integrator_mapping,
                                                                retry_count=retry_count)

                if not integrator_response:
                    countdown_time = (1 ** self.request.retries) * 60
                    print(countdown_time)
                    self.retry([data], countdown=countdown_time)

                resp_data = integrator_response
                if not IntegratorResponse.objects.filter(object_id=appointment.id).first():
                    IntegratorResponse.objects.create(lead_id=resp_data['appointmentId'], dp_order_id=appointment.id,
                                                      integrator_order_id=resp_data['appointmentId'],
                                                      content_object=appointment, response_data=resp_data,
                                                      integrator_class_name=integrator_mapping.integrator_class_name)
        # elif appointment.status == OpdAppointment.CANCELLED:
        #     saved_response = IntegratorResponse.objects.filter(object_id=appointment.id).first()
        #     if not saved_response:
        #         raise Exception("[ERROR] Cant find integrator response for appointment id " + str(appointment.id))
        #
        #     integrator_obj = service.create_integrator_obj(saved_response.integrator_class_name)
        #     retry_count = push_opd_appointment_to_integrator.request.retries
        #     response = integrator_obj.cancel_integrator_order(appointment, saved_response, retry_count)
        #
        #     if not response:
        #         countdown_time = (1 ** self.request.retries) * 60
        #         print(countdown_time)
        #         self.retry([data], countdown=countdown_time)

    except Exception as e:
        logger.error(str(e))