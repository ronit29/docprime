from __future__ import absolute_import, unicode_literals
from ondoc.account.models import Order
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import logging
import datetime
from datetime import date
from ondoc.authentication.models import Address
from ondoc.api.v1.utils import resolve_address
from ondoc.common.models import AppointmentMaskNumber

logger = logging.getLogger(__name__)


def prepare_and_hit(self, data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.doctor.models import DoctorDocument
    from ondoc.diagnostic.models import LabDocument

    appointment = data.get('appointment')
    task_data = data.get('task_data')
    is_home_pickup = 0
    home_pickup_address = None
    appointment_type = ''
    kyc = 0
    location = ''

    if task_data.get('type') == 'OPD_APPOINTMENT':
        booking_url = '%s/admin/doctor/opdappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
        kyc = 1 if DoctorDocument.objects.filter(doctor=appointment.doctor, document_type__in=[DoctorDocument.CHEQUE,
                    DoctorDocument.PAN]).distinct('document_type').count() == 2 else 0

        if appointment.hospital.location:
            location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (appointment.hospital.location.y, appointment.hospital.location.x)

    elif task_data.get('type') == 'LAB_APPOINTMENT':
        booking_url = '%s/admin/diagnostic/labappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
        kyc = 1 if LabDocument.objects.filter(lab=appointment.lab, document_type__in=[LabDocument.CHEQUE,
                    LabDocument.PAN]).distinct('document_type').count() == 2 else 0

        if appointment.lab.location:
            location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (appointment.lab.location.y, appointment.lab.location.x)

        appointment_type = 'Lab Visit'
        if appointment.is_home_pickup:
            is_home_pickup = 1
            appointment_type = 'Home Visit'
            home_pickup_address = appointment.get_pickup_address()

    patient_address = ""
    if hasattr(appointment, 'address') and appointment.address:
        patient_address = resolve_address(appointment.address)
    service_name = ""
    if task_data.get('type') == 'LAB_APPOINTMENT':
        service_name = ','.join([test_obj.test.name for test_obj in appointment.test_mappings.all()])  # DONE SHASHANK_SINGH CHANGE 13

    order = data.get('order')

    dob_value = ''
    try:
        dob_value = datetime.datetime.strptime(appointment.profile_detail.get('dob'), "%Y-%m-%d").strftime("%d-%m-%Y")\
                        if appointment.profile_detail.get('dob', None) else ''
    except Exception as e:
        pass

    p_email = ''
    if appointment.profile:
        p_email = appointment.profile.email

    mask_number_instance = appointment.mask_number.filter(is_deleted=False, is_mask_number=True).first()
    mask_number = ''
    if mask_number_instance:
        mask_number = mask_number_instance.mask_number

    appointment_details = {
        'AppointmentStatus': appointment.status,
        'Age': calculate_age(appointment),
        'Email': p_email,
        'VirtualNo': mask_number,
        'OTP': '',
        'KYC': kyc,
        'Location': location,
        'PaymentStatus': 300,
        'OrderID': order.id if order else 0,
        'DocPrimeBookingID': appointment.id,
        'BookingDateTime': int(appointment.created_at.timestamp()),
        'AppointmentDateTime': int(appointment.time_slot_start.timestamp()),
        'BookingType': 'DC' if task_data.get('type') == 'LAB_APPOINTMENT' else 'D',
        'AppointmentType': appointment_type,
        'IsHomePickUp' : is_home_pickup,
        'HomePickupAddress': home_pickup_address,
        'PatientName': appointment.profile_detail.get("name", ''),
        'PatientAddress': patient_address,
        'ProviderName': getattr(appointment, 'doctor').name if task_data.get('type') == 'OPD_APPOINTMENT' else getattr(appointment, 'lab').name,
        'ServiceName': service_name,
        'InsuranceCover': 0,
        'MobileList': data.get('mobile_list'),
        'BookingUrl': booking_url,
        'Fees': float(appointment.fees) if task_data.get('type') == 'OPD_APPOINTMENT' else float(appointment.agreed_price),
        'EffectivePrice': float(appointment.effective_price),
        'MRP': float(appointment.mrp) if task_data.get('type') == 'OPD_APPOINTMENT' else float(appointment.price),
        'DealPrice': float(appointment.deal_price),
        'DOB': dob_value,
        'ProviderAddress': appointment.hospital.get_hos_address() if task_data.get('type') == 'OPD_APPOINTMENT' else appointment.lab.get_lab_address()
    }

    request_data = {
        'DocPrimeUserId': appointment.user.id,
        'LeadID': appointment.matrix_lead_id if appointment.matrix_lead_id else 0,
        'Name': appointment.profile.name,
        'PrimaryNo': appointment.user.phone_number,
        'LeadSource': 'DocPrime',
        'EmailId': appointment.profile.email,
        'Gender': 1 if appointment.profile.gender == 'm' else 2 if appointment.profile.gender == 'f' else 0,
        'CityId': 0,
        'ProductId': task_data.get('product_id'),
        'SubProductId': task_data.get('sub_product_id'),
        'AppointmentDetails': appointment_details
    }

    #logger.error(json.dumps(request_data))

    url = settings.MATRIX_API_URL
    matrix_api_token = settings.MATRIX_API_TOKEN
    response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                              'Content-Type': 'application/json'})

    if response.status_code != status.HTTP_200_OK or not response.ok:
        logger.info("[ERROR] Appointment could not be published to the matrix system")
        logger.info("[ERROR] %s", response.reason)

        countdown_time = (2 ** self.request.retries) * 60 * 10
        logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
        print(countdown_time)
        self.retry([data], countdown=countdown_time)

    resp_data = response.json()

    if not resp_data.get('Id', None):
        logger.error(json.dumps(request_data))
        raise Exception("[ERROR] Id not recieved from the matrix while pushing appointment lead.")

    # save the appointment with the matrix lead id.
    qs = None
    if task_data.get('type') == 'OPD_APPOINTMENT':
        qs = OpdAppointment.objects.filter(id=appointment.id)
    elif task_data.get('type') == 'LAB_APPOINTMENT':
        qs = LabAppointment.objects.filter(id=appointment.id)

    if qs:
        qs.update(matrix_lead_id=int(resp_data.get('Id')))

    # appointment.matrix_lead_id = resp_data.get('Id', None)
    # appointment.matrix_lead_id = int(appointment.matrix_lead_id)
    # data = {'push_again_to_matrix':False}
    # appointment.save(**data)

    print(str(resp_data))
    if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
        #logger.info("[SUCCESS] Appointment successfully published to the matrix system")
        pass
    else:
        logger.info("[ERROR] Appointment could not be published to the matrix system")

def calculate_age(appointment):
    if not appointment.profile:
        return 0
    if not appointment.profile.dob:
        return 0
    dob = appointment.profile.dob
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


@task(bind=True, max_retries=2)
def push_appointment_to_matrix(self, data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            # logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise Exception("Appointment id not found, could not push to Matrix")

        order_product_id = 0
        appointment = None
        if data.get('type') == 'OPD_APPOINTMENT':
            order_product_id = 1
            appointment = OpdAppointment.objects.filter(pk=appointment_id).first()
            if not appointment:
                raise Exception("Appointment could not found against id - " + str(appointment_id))
            mobile_list = list()
            # User mobile number
            mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})
            # SPOC details
            for spoc_obj in appointment.hospital.spoc_details.all():
                number = ''
                if spoc_obj.number:
                    number = str(spoc_obj.number)
                if spoc_obj.std_code:
                    number = str(spoc_obj.std_code) + number
                if number:
                    number = int(number)

                spoc_type = dict(spoc_obj.CONTACT_TYPE_CHOICES)[spoc_obj.contact_type]
                spoc_name = '%s (Hospital) (%s)' % (spoc_obj.name, spoc_type)
                if spoc_obj.details:
                    spoc_name = spoc_name + '(%s)' % spoc_obj.details
                mobile_list.append({'MobileNo': number,
                                    'Name': spoc_name,
                                    'Type': spoc_obj.contact_type})

            # Doctor mobile numbers
            doctor_mobiles = [doctor_mobile.number for doctor_mobile in appointment.doctor.mobiles.all()]
            doctor_mobiles = [{'MobileNo': number, 'Name': appointment.doctor.name, 'Type': 2} for number in doctor_mobiles]
            mobile_list.extend(doctor_mobiles)
        elif data.get('type') == 'LAB_APPOINTMENT':
            order_product_id = 2
            appointment = LabAppointment.objects.filter(pk=appointment_id).first()

            if not appointment:
                raise Exception("Appointment could not found against id - " + str(appointment_id))

            mobile_list = list()
            # Lab mobile number
            mobile_list.append({'MobileNo': appointment.lab.primary_mobile, 'Name': appointment.lab.name, 'Type': 3})

            # User mobile number
            mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})

        appointment_order = Order.objects.filter(product_id=order_product_id, reference_id=appointment_id).first()

        # Preparing the data and now pushing the data to the matrix system.
        if appointment:
            prepare_and_hit(self, {'appointment': appointment, 'mobile_list': mobile_list, 'task_data': data, 'order': appointment_order})
        else:
            logger.error("Appointment not found for the appointment id ", appointment_id)

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment to the matrix- " + str(e))


# @task(bind=True, max_retries=2)
# def generate_appointment_masknumber(self, data):
#     from ondoc.doctor.models import OpdAppointment
#     from ondoc.diagnostic.models import LabAppointment
#     appointment_type = data.get('type')
#     try:
#         appointment_id = data.get('appointment_id', None)
#         if not appointment_id:
#             # logger.error("[CELERY ERROR: Incorrect values provided.]")
#             raise Exception("Appointment id not found, could not get mask number")
#
#         if appointment_type == 'OPD_APPOINTMENT':
#             appointment = OpdAppointment.objects.filter(id=appointment_id).first()
#         elif data.get('type') == 'LAB_APPOINTMENT':
#             appointment = LabAppointment.objects.filter(id=appointment_id).first()
#         if not appointment:
#             raise Exception("Appointment could not found against id - " + str(appointment_id))
#
#         phone_number = appointment.user.phone_number
#         time_slot = appointment.time_slot_start
#         updated_time_slot = time_slot + datetime.timedelta(days=1)
#         validity_up_to = int((time_slot + datetime.timedelta(days=1)).timestamp())
#         if not phone_number:
#             raise Exception("phone Number could not found against id - " + str(appointment_id))
#         request_data = {
#             "ExpirationDate": validity_up_to,
#             "FromId": appointment.id,
#             "ToNumber": phone_number
#         }
#         url = settings.MATRIX_NUMBER_MASKING
#         matrix_api_token = settings.MATRIX_API_TOKEN
#         response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
#                                                                               'Content-Type': 'application/json'})
#
#         if response.status_code != status.HTTP_200_OK or not response.ok:
#             logger.info("[ERROR] Appointment could not be get Mask Number")
#             logger.info("[ERROR] %s", response.reason)
#             countdown_time = (2 ** self.request.retries) * 60 * 10
#             logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
#             print(countdown_time)
#             self.retry([data], countdown=countdown_time)
#
#         mask_number = response.json()
#         existing_mask_number_obj = appointment.mask_number.filter(is_deleted=False).first()
#         if existing_mask_number_obj:
#             existing_mask_number_obj.is_deleted = True
#             existing_mask_number_obj.save()
#             AppointmentMaskNumber(content_object=appointment, mask_number=mask_number,
#                                                  validity_up_to=updated_time_slot, is_deleted=False).save()
#         else:
#             AppointmentMaskNumber(content_object=appointment, mask_number=mask_number,
#                                                  validity_up_to=updated_time_slot, is_deleted=False).save()
#     except Exception as e:
#         logger.error("Error in Celery. Failed get mask number for appointment " + str(e))


@task(bind=True, max_retries=2)
def push_signup_lead_to_matrix(self, data):
    try:
        from ondoc.web.models import OnlineLead
        lead_id = data.get('lead_id', None)
        if not lead_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        online_lead_obj = OnlineLead.objects.get(id=lead_id)

        if not online_lead_obj:
            raise Exception("Online lead could not found against id - " + str(lead_id))

        utm = online_lead_obj.utm_params if online_lead_obj.utm_params else {}

        request_data = {
            'Name': online_lead_obj.name,
            'PrimaryNo': online_lead_obj.mobile,
            'LeadSource': online_lead_obj.source if online_lead_obj.source else 'Unknown',
            'LeadID': online_lead_obj.matrix_lead_id if online_lead_obj.matrix_lead_id else 0,
            'EmailId': online_lead_obj.email,
            'Gender': 0,
            'CityId': online_lead_obj.city_name.id if online_lead_obj.city_name and online_lead_obj.city_name.id else 0,
            'ProductId': data.get('product_id'),
            'SubProductId': data.get('sub_product_id'),
            'CreatedOn': int(online_lead_obj.created_at.timestamp()),
            'UtmCampaign': utm.get('utm_campaign', ''),
            'UTMMedium': utm.get('utm_medium', ''),
            'UtmSource': utm.get('utm_source', ''),
            'UtmTerm': utm.get('utm_term', ''),
        }

        #logger.error(json.dumps(request_data))

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Lead could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()
        #logger.error(response.text)

        # save the appointment with the matrix lead id.

        if not resp_data.get('Id', None):
            logger.error(json.dumps(request_data))
            raise Exception("[ERROR] Id not recieved from the matrix while pushing online lead.")

        online_lead_obj.matrix_lead_id = resp_data.get('Id', None)
        online_lead_obj.matrix_lead_id = int(online_lead_obj.matrix_lead_id)

        data = {'push_again_to_matrix':False}
        online_lead_obj.save(**data)

        print(str(resp_data))
        if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
            #logger.info("[SUCCESS] Lead successfully published to the matrix system")
            pass
        else:
            logger.info("[ERROR] Lead could not be published to the matrix system")



        # Preparing the data and now pushing the data to the matrix system.
        # prepare_and_hit(self, {'appointment': appointment, 'mobile_list': mobile_list, 'task_data': data})

    except Exception as e:
        logger.error("Error in Celery. Failed pushing online lead to the matrix- " + str(e))


@task(bind=True, max_retries=2)
def push_order_to_matrix(self, data):
    try:
        order_id = data.get('order_id', None)
        if not order_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        order_obj = Order.objects.get(id=order_id)

        if not order_obj:
            raise Exception("Order could not found against id - " + str(order_id))

        appointment_details = order_obj.appointment_details()
        request_data = {
            'LeadSource': 'DocPrime',
            'HospitalName': appointment_details.get('hospital_name'),
            'Name': appointment_details.get('profile_name', ''),
            'BookedBy': appointment_details.get('user_number', None),
            'LeadID': order_obj.matrix_lead_id if order_obj.matrix_lead_id else 0,
            'PrimaryNo': appointment_details.get('user_number',None),
            'ProductId': 5,
            'SubProductId': 4,
            'AppointmentDetails': {
                'OrderID': appointment_details.get('order_id', 0),
                'ProviderName': appointment_details.get('doctor_name', '') if appointment_details.get('doctor_name') else appointment_details.get('lab_name'),
                'BookingDateTime': int(data.get('created_at')),
                'AppointmentDateTime': int(data.get('timeslot')),
            }
        }

        #logger.error(json.dumps(request_data))

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Order could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            #logger.error(response.text)

            if not resp_data.get('Id', None):
                logger.error(json.dumps(request_data))
                raise Exception("[ERROR] Id not recieved from the matrix while pushing order to matrix.")

            # save the order with the matrix lead id.
            order_obj.matrix_lead_id = resp_data.get('Id', None)
            order_obj.matrix_lead_id = int(order_obj.matrix_lead_id)

            order_obj.save()

            #print(str(resp_data))
            if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
                #logger.info("[SUCCESS] Order successfully published to the matrix system")
                pass
            else:
                logger.info("[ERROR] Order could not be published to the matrix system")

    except Exception as e:
        logger.error("Error in Celery. Failed pushing order to the matrix- " + str(e))

@task(bind=True, max_retries=2)
def push_onboarding_qcstatus_to_matrix(self, data):
    from ondoc.doctor.models import Doctor
    from ondoc.diagnostic.models import Lab

    try:
        obj_id = data.get('obj_id', None)
        obj_type = data.get('obj_type', None)
        if not obj_id or not obj_type:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        product_id = 0
        gender = 0
        if obj_type == 'Lab':
            obj = Lab.objects.get(id=obj_id)
            mobile = obj.primary_mobile
            product_id = 4
            exit_point_url = '%s/admin/diagnostic/lab/%s/change' % (settings.ADMIN_BASE_URL, obj_id)

        elif obj_type == 'Doctor':

            exit_point_url = '%s/admin/doctor/doctor/%s/change' % (settings.ADMIN_BASE_URL, obj_id)
            obj = Doctor.objects.get(id=obj_id)
            if obj.gender and obj.gender == 'm':
                gender = 1
            elif obj.gender and obj.gender == 'f':
                gender = 2

            product_id = 1
            mobile = obj.mobiles.filter(is_primary=True).first()
            if mobile:
                mobile = mobile.number

        if not obj:
            raise Exception("Doctor or lab could not found against id - " + str(obj_id))

        request_data = {
            'LeadSource': 'DocPrime',
            'LeadID': obj.matrix_lead_id if obj.matrix_lead_id else 0,
            'ProductId': product_id,
            'PrimaryNo': mobile if mobile else 0,
            'QcStatus': obj.data_status,
            'OnBoarding': obj.onboarding_status,
            'Gender': gender,
            'SubProductId': 0,
            'Name': obj.name,
            'ExitPointUrl': exit_point_url,
        }

        #logger.error(json.dumps(request_data))

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Order could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            #logger.error(response.text)

            if not resp_data.get('Id', None):
                logger.error(json.dumps(request_data))
                raise Exception("[ERROR] Id not recieved from the matrix while pushing doctor or lab lead.")

            # save the order with the matrix lead id.
            obj.matrix_lead_id = resp_data.get('Id', None)
            obj.matrix_lead_id = int(obj.matrix_lead_id)
            obj.save()

    except Exception as e:
        logger.error("Error in Celery. Failed pushing order to the matrix- " + str(e))


@task(bind=True, max_retries=2)
def push_non_bookable_doctor_lead_to_matrix(self, nb_doc_lead_id):
    from ondoc.web.models import NonBookableDoctorLead
    obj = NonBookableDoctorLead.objects.filter(id= nb_doc_lead_id).first()
    if not obj:
        raise Exception('Could not get non bookable doctor for the id ', nb_doc_lead_id)

    exit_point_url = ""
    if obj.doctor and obj.doctor.id and obj.hospital and obj.hospital.id:
        exit_point_url = "%s/opd/doctor/%d?hospital_id=%d" % (settings.CONSUMER_APP_DOMAIN, obj.doctor.id, obj.hospital.id)

    request_data = {
        'ExitPointUrl': exit_point_url,
        'LeadSource': obj.source,
        'PrimaryNo': int(obj.from_mobile),
        'Name': obj.name if obj.name else 'not applicable',
        'ProductId': 5,
        'SubProductId': 2,
        'AppointmentDetails': {
            'ProviderName': obj.doctor.name if obj.doctor else '',
            'ProviderAddress': obj.hospital.get_hos_address() if obj.hospital else ''
        }
    }

    url = settings.MATRIX_API_URL
    matrix_api_token = settings.MATRIX_API_TOKEN
    response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                          'Content-Type': 'application/json'})

    if response.status_code != status.HTTP_200_OK or not response.ok:
        logger.info("[ERROR] NB Doctor Lead could not be published to the matrix system")
        logger.info("[ERROR] %s", response.reason)
        countdown_time = (2 ** self.request.retries) * 60 * 10
        logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
        print(countdown_time)
        self.retry(obj.id, countdown=countdown_time)
    else:
        resp_data = response.json()
        # logger.error(response.text)
        if not resp_data.get('Id', None):
            logger.error(json.dumps(request_data))
            raise Exception("[ERROR] Id not received from the matrix while pushing NB doctor lead.")

        # save the order with the matrix lead id.
        obj.matrix_lead_id = resp_data.get('Id', None)
        obj.matrix_lead_id = int(obj.matrix_lead_id)
        obj.save()
