from __future__ import absolute_import, unicode_literals
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ondoc.account.models import Order
from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import logging
import datetime
from ondoc.authentication.models import Address, SPOCDetails, QCModel
from ondoc.api.v1.utils import log_requests_on, generate_short_url
from ondoc.common.models import AppointmentMaskNumber
from ondoc.crm.constants import matrix_product_ids, matrix_subproduct_ids, constants

logger = logging.getLogger(__name__)
from ondoc.matrix.mongo_models import MatrixLog

# def prepare_and_hit(self, data):
#     from ondoc.doctor.models import OpdAppointment
#     from ondoc.diagnostic.models import LabAppointment
#     from ondoc.doctor.models import DoctorDocument
#     from ondoc.diagnostic.models import LabDocument
#
#     appointment = data.get('appointment')
#     task_data = data.get('task_data')
#     is_home_pickup = 0
#     home_pickup_address = None
#     appointment_type = ''
#     kyc = 0
#     location = ''
#     booking_url = ''
#
#     if task_data.get('type') == 'OPD_APPOINTMENT':
#         booking_url = '%s/admin/doctor/opdappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
#         kyc = 1 if DoctorDocument.objects.filter(doctor=appointment.doctor, document_type__in=[DoctorDocument.CHEQUE,
#                     DoctorDocument.PAN]).distinct('document_type').count() == 2 else 0
#
#         if appointment.hospital.location:
#             location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (appointment.hospital.location.y, appointment.hospital.location.x)
#
#     elif task_data.get('type') == 'LAB_APPOINTMENT':
#         booking_url = '%s/admin/diagnostic/labappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
#         kyc = 1 if LabDocument.objects.filter(lab=appointment.lab, document_type__in=[LabDocument.CHEQUE,
#                     LabDocument.PAN]).distinct('document_type').count() == 2 else 0
#
#         if appointment.lab.location:
#             location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (appointment.lab.location.y, appointment.lab.location.x)
#
#         appointment_type = 'Lab Visit'
#         if appointment.is_home_pickup:
#             is_home_pickup = 1
#             appointment_type = 'Home Visit'
#             home_pickup_address = appointment.get_pickup_address()
#
#     patient_address = ""
#     if hasattr(appointment, 'address') and appointment.address:
#         patient_address = resolve_address(appointment.address)
#     service_name = ""
#     if task_data.get('type') == 'LAB_APPOINTMENT':
#         service_name = ','.join([test_obj.test.name for test_obj in appointment.test_mappings.all()])
#
#     order_id = data.get('order_id')
#
#     dob_value = ''
#     try:
#         dob_value = datetime.datetime.strptime(appointment.profile_detail.get('dob'), "%Y-%m-%d").strftime("%d-%m-%Y")\
#                         if appointment.profile_detail.get('dob', None) else ''
#     except Exception as e:
#         pass
#
#     p_email = ''
#     if appointment.profile:
#         p_email = appointment.profile.email
#
#     mask_number_instance = appointment.mask_number.filter(is_deleted=False, is_mask_number=True).first()
#     mask_number = ''
#     if mask_number_instance:
#         mask_number = mask_number_instance.mask_number
#
#     provider_booking_id = ''
#     merchant_code = ''
#     provider_payment_status = ''
#     settlement_date = None
#     payment_URN = ''
#     amount = None
#     is_ipd_hospital = '0'
#     if task_data.get('type') == 'LAB_APPOINTMENT':
#         is_ipd_hospital = '0'
#         location_verified = appointment.lab.is_location_verified
#         provider_id = appointment.lab.id
#         merchant = appointment.lab.merchant.all().last()
#         if merchant:
#             merchant_code = merchant.id
#
#         if appointment.lab and appointment.lab.network and appointment.lab.network.id == settings.THYROCARE_NETWORK_ID:
#             integrator_obj = appointment.integrator_response.all().first()
#             if integrator_obj:
#                 provider_booking_id = integrator_obj.integrator_order_id
#     elif task_data.get('type') == 'OPD_APPOINTMENT':
#         is_ipd_hospital = '1' if appointment.hospital and appointment.hospital.has_ipd_doctors() else '0'
#         location_verified = appointment.hospital.is_location_verified
#         provider_id = appointment.doctor.id
#         merchant = appointment.doctor.merchant.all().last()
#         if merchant:
#             merchant_code = merchant.id
#
#     merchant_payout = appointment.merchant_payout
#     if merchant_payout:
#         provider_payment_status = dict(merchant_payout.STATUS_CHOICES)[merchant_payout.status]
#         settlement_date = int(merchant_payout.payout_time.timestamp()) if merchant_payout.payout_time else None
#         payment_URN = merchant_payout.utr_no
#         amount = merchant_payout.payable_amount
#
#     # insured_member = appointment.profile.insurance.filter().order_by('id').last()
#     # user_insurance = None
#     # if insured_member:
#     #     user_insurance = insured_member.user_insurance
#
#     user_insurance = appointment.insurance
#
#     # user_insurance = appointment.user.active_insurance
#     primary_proposer_name = None
#
#     # if user_insurance and user_insurance.is_valid():
#     #     primary_proposer = user_insurance.get_primary_member_profile()
#     #     primary_proposer_name = primary_proposer.get_full_name() if primary_proposer else None
#
#     # policy_details = {
#     #     "ProposalNo": None,
#     #     'PolicyPaymentSTATUS': 300 if user_insurance else 0,
#     #     "BookingId": user_insurance.id if user_insurance else None,
#     #     "ProposerName": primary_proposer_name,
#     #     "PolicyId": user_insurance.policy_number if user_insurance else None,
#     #     "InsurancePlanPurchased": user_insurance.insurance_plan.name if user_insurance else None,
#     #     "PurchaseDate": int(user_insurance.purchase_date.timestamp()) if user_insurance else None,
#     #     "ExpirationDate": int(user_insurance.expiry_date.timestamp()) if user_insurance else None,
#     #     "COILink": user_insurance.coi.url if user_insurance and  user_insurance.coi is not None and user_insurance.coi.name else None,
#     #     "PeopleCovered": user_insurance.insurance_plan.get_people_covered() if user_insurance else ""
#     # }
#
#     appointment_details = {
#         'IPDHospital': is_ipd_hospital,
#         'IsInsured': 'yes' if user_insurance else 'no',
#         'InsurancePolicyNumber': str(user_insurance.policy_number) if user_insurance else None,
#         'AppointmentStatus': appointment.status,
#         'Age': calculate_age(appointment),
#         'Email': p_email,
#         'VirtualNo': mask_number,
#         'OTP': '',
#         'KYC': kyc,
#         'Location': location,
#         'PaymentType': appointment.payment_type,
#         'PaymentTypeId': appointment.payment_type,
#         'PaymentStatus': 300,
#         'OrderID': order_id if order_id else 0,
#         'DocPrimeBookingID': appointment.id,
#         'BookingDateTime': int(appointment.created_at.timestamp()),
#         'AppointmentDateTime': int(appointment.time_slot_start.timestamp()),
#         'BookingType': 'DC' if task_data.get('type') == 'LAB_APPOINTMENT' else 'D',
#         'AppointmentType': appointment_type,
#         'IsHomePickUp' : is_home_pickup,
#         'HomePickupAddress': home_pickup_address,
#         'PatientName': appointment.profile_detail.get("name", ''),
#         'PatientAddress': patient_address,
#         'ProviderName': getattr(appointment, 'doctor').name + " - " + appointment.hospital.name if task_data.get('type') == 'OPD_APPOINTMENT' else getattr(appointment, 'lab').name,
#         'ServiceName': service_name,
#         'InsuranceCover': 0,
#         'MobileList': data.get('mobile_list'),
#         'BookingUrl': booking_url,
#         'Fees': float(appointment.fees) if task_data.get('type') == 'OPD_APPOINTMENT' else float(appointment.agreed_price),
#         'EffectivePrice': float(appointment.effective_price),
#         'MRP': float(appointment.mrp) if task_data.get('type') == 'OPD_APPOINTMENT' else float(appointment.price),
#         'DealPrice': float(appointment.deal_price),
#         'DOB': dob_value,
#         'ProviderAddress': appointment.hospital.get_hos_address() if task_data.get('type') == 'OPD_APPOINTMENT' else appointment.lab.get_lab_address(),
#         'ProviderID': provider_id,
#         'ProviderBookingID': provider_booking_id,
#         'MerchantCode': merchant_code,
#         'ProviderPaymentStatus': provider_payment_status,
#         'PaymentURN': payment_URN,
#         'Amount': float(amount) if amount else None,
#         'SettlementDate': settlement_date,
#         'LocationVerified': location_verified
#     }
#
#     request_data = {
#         'DocPrimeUserId': appointment.user.id,
#         'LeadID': appointment.matrix_lead_id if appointment.matrix_lead_id else 0,
#         'Name': appointment.profile.name,
#         'PrimaryNo': appointment.user.phone_number,
#         'LeadSource': 'DocPrime',
#         'EmailId': appointment.profile.email,
#         'Gender': 1 if appointment.profile.gender == 'm' else 2 if appointment.profile.gender == 'f' else 0,
#         'CityId': 0,
#         'ProductId': task_data.get('product_id'),
#         'SubProductId': task_data.get('sub_product_id'),
#         'AppointmentDetails': appointment_details
#     }
#
#     #logger.error(json.dumps(request_data))
#
#     url = settings.MATRIX_API_URL
#     matrix_api_token = settings.MATRIX_API_TOKEN
#     response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
#                                                               'Content-Type': 'application/json'})
#
#     if response.status_code != status.HTTP_200_OK or not response.ok:
#         logger.error(json.dumps(request_data))
#         logger.info("[ERROR] Appointment could not be published to the matrix system")
#         logger.info("[ERROR] %s", response.reason)
#
#         countdown_time = (2 ** self.request.retries) * 60 * 10
#         logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
#         print(countdown_time)
#         self.retry([data], countdown=countdown_time)
#
#     resp_data = response.json()
#
#     if not resp_data.get('Id', None):
#         logger.error(json.dumps(request_data))
#         raise Exception("[ERROR] Id not recieved from the matrix while pushing appointment lead.")
#
#     # save the appointment with the matrix lead id.
#     qs = None
#     if task_data.get('type') == 'OPD_APPOINTMENT':
#         qs = OpdAppointment.objects.filter(id=appointment.id)
#     elif task_data.get('type') == 'LAB_APPOINTMENT':
#         qs = LabAppointment.objects.filter(id=appointment.id)
#
#     if qs:
#         qs.update(matrix_lead_id=int(resp_data.get('Id')))
#
#     # appointment.matrix_lead_id = resp_data.get('Id', None)
#     # appointment.matrix_lead_id = int(appointment.matrix_lead_id)
#     # data = {'push_again_to_matrix':False}
#     # appointment.save(**data)
#
#     print(str(resp_data))
#     if isinstance(resp_data, dict) and resp_data.get('IsSaved', False):
#         #logger.info("[SUCCESS] Appointment successfully published to the matrix system")
#         pass
#     else:
#         logger.info("[ERROR] Appointment could not be published to the matrix system")
#
#
# def calculate_age(appointment):
#     if not appointment.profile:
#         return 0
#     if not appointment.profile.dob:
#         return 0
#     dob = appointment.profile.dob
#     today = date.today()
#     return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
#
#
# @task(bind=True, max_retries=2)
# def push_appointment_to_matrix(self, data):
#     from ondoc.doctor.models import OpdAppointment
#     from ondoc.diagnostic.models import LabAppointment
#     try:
#         appointment_id = data.get('appointment_id', None)
#         if not appointment_id:
#             # logger.error("[CELERY ERROR: Incorrect values provided.]")
#             raise Exception("Appointment id not found, could not push to Matrix")
#
#         order_product_id = 0
#         appointment = None
#         if data.get('type') == 'OPD_APPOINTMENT':
#             order_product_id = 1
#             appointment = OpdAppointment.objects.filter(pk=appointment_id).first()
#             if not appointment:
#                 raise Exception("Appointment could not found against id - " + str(appointment_id))
#             mobile_list = list()
#             # User mobile number
#             mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})
#             auto_ivr_enabled = appointment.hospital.is_auto_ivr_enabled()
#             # SPOC details
#             for spoc_obj in appointment.hospital.spoc_details.all():
#                 number = ''
#                 if spoc_obj.number:
#                     number = str(spoc_obj.number)
#                 if spoc_obj.std_code:
#                     number = str(spoc_obj.std_code) + number
#                 if number:
#                     number = int(number)
#
#                 # spoc_type = dict(spoc_obj.CONTACT_TYPE_CHOICES)[spoc_obj.contact_type]
#                 if number:
#                     spoc_name = spoc_obj.name
#                     mobile_list.append({'MobileNo': number,
#                                         'Name': spoc_name,
#                                         'DesignationID': spoc_obj.contact_type,
#                                         'AutoIVREnable': str(auto_ivr_enabled).lower(),
#                                         'Type': 2})
#
#             # Doctor mobile numbers
#             doctor_mobiles = [doctor_mobile.number for doctor_mobile in appointment.doctor.mobiles.all()]
#             doctor_mobiles = [{'MobileNo': number, 'Name': appointment.doctor.name, 'Type': 2} for number in doctor_mobiles]
#             mobile_list.extend(doctor_mobiles)
#         elif data.get('type') == 'LAB_APPOINTMENT':
#             order_product_id = 2
#             appointment = LabAppointment.objects.filter(pk=appointment_id).first()
#
#             if not appointment:
#                 raise Exception("Appointment could not found against id - " + str(appointment_id))
#
#             mobile_list = list()
#             auto_ivr_enabled = appointment.lab.is_auto_ivr_enabled()
#
#             for contact_person in appointment.lab.labmanager_set.all():
#                 number = ''
#                 if contact_person.number:
#                     number = str(contact_person.number)
#                 if number:
#                     number = int(number)
#
#                 if number:
#                     contact_type = dict(contact_person.CONTACT_TYPE_CHOICES)[contact_person.contact_type]
#                     contact_name = contact_person.name
#                     mobile_list.append({'MobileNo': number,
#                                         'Name': contact_name,
#                                         'DesignationID': contact_person.contact_type,
#                                         'AutoIVREnable': str(auto_ivr_enabled).lower(),
#                                         'Type': 3})
#
#
#             # Lab mobile number
#             mobile_list.append({'MobileNo': appointment.lab.primary_mobile, 'Name': appointment.lab.name, 'Type': 3})
#
#             # User mobile number
#             mobile_list.append({'MobileNo': appointment.user.phone_number, 'Name': appointment.profile.name, 'Type': 1})
#
#         appointment_order = Order.objects.filter(product_id=order_product_id, reference_id=appointment_id).first()
#
#         # Preparing the data and now pushing the data to the matrix system.
#         if appointment:
#             prepare_and_hit(self, {'appointment': appointment, 'mobile_list': mobile_list, 'task_data': data, 'order_id': appointment_order.id})
#         else:
#             logger.error("Appointment not found for the appointment id ", appointment_id)
#
#     except Exception as e:
#         logger.error("Error in Celery. Failed pushing Appointment to the matrix- " + str(e))


# This method is use to push appointment data to matrix
@task(bind=True, max_retries=2)
def push_appointment_to_matrix(self, data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.notification.tasks import save_matrix_logs
    from ondoc.common.models import GeneralMatrixLeads
    from ondoc.common.lead_engine import lead_class_referance

    log_requests_on()
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Matrix")

        order_product_id = 0
        appointment = None
        product_id = data.get('product_id')
        sub_product_id = data.get('sub_product_id')

        if data.get('type') == 'OPD_APPOINTMENT':
            order_product_id = 1
            appointment = OpdAppointment.objects.filter(pk=appointment_id).first()
            if not appointment:
                raise Exception("Appointment could not found against id - " + str(appointment_id))
        elif data.get('type') == 'LAB_APPOINTMENT':
            order_product_id = 2
            appointment = LabAppointment.objects.filter(pk=appointment_id).first()
            if not appointment:
                raise Exception("Appointment could not found against id - " + str(appointment_id))

        appointment_user = appointment.user
        if appointment_user:
            last_24_time = datetime.datetime.now() - datetime.timedelta(days=1)
            if GeneralMatrixLeads.objects.filter(created_at__gte=last_24_time, phone_number=int(appointment_user.phone_number),
                                                 lead_type__in=['DROPOFF', 'LABADS'], matrix_lead_id__isnull=False).exists():

                lead_engine_obj = lead_class_referance("CANCELDROPOFFLEADVIAAPPOINTMENT", appointment)
                success = lead_engine_obj.process_lead()
                if not success:
                    print("Could not able to publish the lead to matrix for cancel dropoff for phone number %s" % str(appointment_user.phone_number))

        appointment_order = Order.objects.filter(product_id=order_product_id, reference_id=appointment_id).first()
        request_data = appointment.get_matrix_data(appointment_order, product_id, sub_product_id)

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        qs = None
        if data.get('type') == 'OPD_APPOINTMENT':
            qs = OpdAppointment.objects.filter(id=appointment.id)
            obj_type = 'opd_appointment'
        elif data.get('type') == 'LAB_APPOINTMENT':
            qs = LabAppointment.objects.filter(id=appointment.id)
            obj_type = 'lab_appointment'

        if settings.SAVE_LOGS:
            save_matrix_logs.apply_async((qs.first().id, obj_type, request_data, response.json()), countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Appointment could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()

        if not resp_data.get('Id', None):
            return
            # logger.error(json.dumps(request_data))
            # raise Exception("[ERROR] Id not recieved from the matrix while pushing appointment lead.")

        # save the appointment with the matrix lead id.

        if qs:
            qs.update(matrix_lead_id=int(resp_data.get('Id')))

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

# This method is use to push signup data to matrix
@task(bind=True, max_retries=2)
def push_signup_lead_to_matrix(self, data):
    log_requests_on()
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

        continue_url = settings.ADMIN_BASE_URL + reverse('admin:doctor_doctor_add')

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
            'ExitPointUrl': continue_url
        }

        #logger.error(json.dumps(request_data))

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
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


# This method is use to push order data to matrix
@task(bind=True, max_retries=2)
def push_order_to_matrix(self, data):
    log_requests_on()
    try:
        if not data:
            raise Exception('Data not received for the task.')

        order_id = data.get('order_id', None)
        if not order_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        order_obj = Order.objects.filter(id=order_id).first()

        if not order_obj:
            raise Exception("Order could not found against id - " + str(order_id))

        if order_obj.parent:
            raise Exception("should not push child order in case of payment failure - " + str(order_id))

        if order_obj and order_obj.user and order_obj.product_id == Order.DOCTOR_PRODUCT_ID:
            for temp_obj in order_obj.orders.all():
                if temp_obj.action_data.get('hospital'):
                    from ondoc.doctor.models import Hospital
                    ho = Hospital.objects.filter(id=temp_obj.action_data.get('hospital')).first()
                    if ho and ho.has_ipd_doctors():
                        return

        if order_obj and order_obj.user and not order_obj.user.is_valid_lead(order_obj.created_at, check_lab_appointment=True):
            return

        phone_number = order_obj.user.phone_number
        name = order_obj.user.full_name
        # appointment_details = order_obj.appointment_details()
        # if not appointment_details:
        #     raise Exception('Appointment details not found for order.')

        request_data = {
            'LeadSource': 'DocPrime',
            'Name': name,
            'BookedBy': phone_number,
            'LeadID': order_obj.matrix_lead_id if order_obj.matrix_lead_id else 0,
            'PrimaryNo': phone_number,
            'ProductId': 5,
            'SubProductId': 4,
        }

        #logger.error(json.dumps(request_data))

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Order could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            if not resp_data:
                raise Exception('Data received from matrix is null or empty.')
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


# This method is use to save ipd and provider signup lead data to matrix
@task(bind=True, max_retries=2)
def create_or_update_lead_on_matrix(self, data):
    from ondoc.doctor.models import Doctor
    from ondoc.doctor.models import Hospital
    from ondoc.doctor.models import HospitalNetwork
    from ondoc.doctor.models import ProviderSignupLead
    from ondoc.procedure.models import IpdProcedureLead
    from ondoc.communications.models import EMAILNotification
    from ondoc.notification.models import NotificationAction
    from ondoc.diagnostic.models import IPDMedicinePageLead
    log_requests_on()
    try:
        obj_id = data.get('obj_id', None)
        obj_type = data.get('obj_type', None)
        if not obj_id or not obj_type:
            logger.error("CELERY ERROR: Incorrect values provided.")
            raise ValueError()

        product_id = matrix_product_ids.get('opd_products', 1)
        if obj_type == IpdProcedureLead.__name__:
            product_id = matrix_product_ids.get('ipd_procedure', 9)
        if obj_type == IPDMedicinePageLead.__name__:
            product_id = matrix_product_ids.get('consumer', 5)

        sub_product_id = matrix_subproduct_ids.get(obj_type.lower(), 4)
        if obj_type == ProviderSignupLead.__name__:
            sub_product_id = matrix_subproduct_ids.get(Doctor.__name__.lower(), 4)
        if obj_type == IpdProcedureLead.__name__:
            sub_product_id = matrix_subproduct_ids.get('idp_subproduct_id', 0)
        if obj_type == IPDMedicinePageLead.__name__:
            sub_product_id = matrix_product_ids.get(IPDMedicinePageLead.__name__.lower(), 4)

        ct = ContentType.objects.get(model=obj_type.lower())
        model_used = ct.model_class()
        content_type = ContentType.objects.get_for_model(model_used)
        if obj_type == ProviderSignupLead.__name__:
            exit_point_url = settings.ADMIN_BASE_URL + reverse('admin:doctor_doctor_add')
        elif obj_type == IPDMedicinePageLead.__name__:
            exit_point_url = ''
        else:
            exit_point_url = settings.ADMIN_BASE_URL + reverse(
                'admin:{}_{}_change'.format(content_type.app_label, content_type.model), kwargs={"object_id": obj_id})
        obj = model_used.objects.filter(id=obj_id).first()
        if not obj:
            raise Exception("{} could not found against id - {}".format(obj_type, obj_id))

        mobile = '0'
        email = ''
        gender = 0
        name = obj.name if hasattr(obj, 'name') and obj.name else ''
        lead_source = None
        request_data = {}
        potential_ipd_lead = 0
        if obj_type == Doctor.__name__:
            lead_source = 'referral'
            if obj.gender and obj.gender == 'm':
                gender = 1
            elif obj.gender and obj.gender == 'f':
                gender = 2
        elif obj_type == Hospital.__name__:
            lead_source = 'ProviderApp' if obj.source_type == Hospital.PROVIDER and obj.is_listed_on_docprime else 'referral'
            spoc_details = obj.spoc_details.filter(contact_type=SPOCDetails.SPOC, email__isnull=False).first()
            if not spoc_details:
                spoc_details = obj.spoc_details.filter(contact_type=SPOCDetails.SPOC).first()
            if spoc_details:
                mobile = str(spoc_details.std_code) if spoc_details.std_code else ''
                mobile += str(spoc_details.number) if spoc_details.number else ''
                email = spoc_details.email if spoc_details.email else ''
        elif obj_type == HospitalNetwork.__name__:
            lead_source = 'referral'
            spoc_details = obj.spoc_details.filter(contact_type=SPOCDetails.SPOC).first()
            if spoc_details:
                mobile = str(spoc_details.std_code) if spoc_details.std_code else ''
                mobile += str(spoc_details.number) if spoc_details.number else ''
            # spoc_details = obj.hospitalnetworkmanager_set.filter(contact_type=2).first()
            # if spoc_details:
            #     mobile += str(spoc_details.number) if hasattr(spoc_details, 'number') and spoc_details.number else ''
        elif obj_type == ProviderSignupLead.__name__:
            lead_source = 'ProviderApp'
            mobile = obj.phone_number
            email = obj.email if obj.email else ''
            if obj.type == ProviderSignupLead.DOCTOR:
                name = obj.name + ' (Doctor)'
            elif obj.type == ProviderSignupLead.HOSPITAL_ADMIN:
                name = obj.name + ' (Hospital Admin)'
        elif obj_type == IpdProcedureLead.__name__:
            potential_ipd_lead = 1 if obj.is_potential_ipd() else 0
            lead_source = obj.source
            if lead_source.lower() == 'crm' and not obj.is_potential_ipd():
                return
            mobile = obj.phone_number
            email = obj.email if obj.email else ''
            name = obj.name
            if obj.gender and obj.gender == 'm':
                gender = 1
            elif obj.gender and obj.gender == 'f':
                gender = 2
            obj.update_idp_data(request_data)
        elif obj_type == IPDMedicinePageLead.__name__:
            lead_source = obj.lead_source
            mobile = obj.phone_number
        mobile = int(mobile)

        # if not mobile:
        #     return
        if not lead_source:
            return
        request_data.update({
            'LeadSource': lead_source,
            'LeadID': obj.matrix_lead_id if hasattr(obj, 'matrix_lead_id') and obj.matrix_lead_id else 0,
            'PrimaryNo': mobile,
            'EmailId': email,
            'IPDPotential': potential_ipd_lead,
            'QcStatus': obj.data_status if hasattr(obj, 'data_status') else 0,
            'OnBoarding': obj.onboarding_status if hasattr(obj, 'onboarding_status') else 0,
            'Gender': gender,
            'ProductId': product_id,
            'SubProductId': sub_product_id,
            'Name': name,
            'ExitPointUrl': exit_point_url,
            'CityId': obj.matrix_city.id if hasattr(obj, 'matrix_city') and obj.matrix_city and obj.matrix_city.id else 0
        })
        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN

        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                             'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] {} with ID {} could not be published to the matrix system".format(obj_type, obj_id))
            logger.info("[ERROR] %s", response.reason)
            countdown_time = (2 ** self.request.retries) * 60 * 10
            # logging.error("Lead creation on the Matrix System failed with response - " + str(response.content))
            logger.error("Matrix URL - "+ url +", Payload - "+ json.dumps(request_data) + ", Matrix Response - " + json.dumps(response.json()) + "")
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            if not (resp_data.get('Id', None) or resp_data.get('IsSaved', False)):
                return
                # logger.error("[ERROR] ID not received from the matrix while creating lead for {} with ID {}. ".format(obj_type, obj_id)+json.dumps(request_data))
                # raise Exception("[ERROR] ID not received from the matrix while creating lead for {} with ID {}.")

            # save the order with the matrix lead id.
            # obj = model_used.objects.select_for_update().filter(id=obj_id).first()
            if obj and hasattr(obj, 'matrix_lead_id') and not obj.matrix_lead_id:
                # obj.matrix_lead_id = resp_data.get('Id', None)
                # obj.matrix_lead_id = int(obj.matrix_lead_id)
                mlid = resp_data.get('Id', None)
                if mlid:
                    mx_lead_id = int(mlid)
                    queryset = model_used.objects.filter(id=obj.id)
                    queryset.update(matrix_lead_id=mx_lead_id)
                if lead_source == 'ProviderApp':
                    receivers = [{"user": None, "email": "kabeer@docprime.com"},
                                 {"user": None, "email": "simranjeet@docprime.com"},
                                 {"user": None, "email": "prithvijeet@docprime.com"},
                                 {"user": None, "email": "sanat@docprime.com"}]
                    email_notification = EMAILNotification(NotificationAction.PROVIDER_MATRIX_LEAD_EMAIL,
                                                           context={"data": request_data})
                    try:
                        email_notification.send(receivers)
                    except Exception as e:
                        logger.error("Error in Celery. Failed to send email notifications - " + str(e))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing order to the matrix- " + str(e))


# This method is use to update QC status on matrix for onboarding
@task(bind=True, max_retries=3)
def update_onboarding_qcstatus_to_matrix(self, data):
    from ondoc.procedure.models import IpdProcedureLead
    log_requests_on()
    try:
        obj_id = data.get('obj_id', None)
        obj_type = data.get('obj_type', None)
        if not obj_id or not obj_type:
            logger.error("CELERY ERROR: Incorrect values provided.")
            raise ValueError()
        ct = ContentType.objects.get(model=obj_type.lower())
        model_used = ct.model_class()
        content_type = ContentType.objects.get_for_model(model_used)
        exit_point_url = settings.ADMIN_BASE_URL + reverse('admin:{}_{}_change'.format(content_type.app_label, content_type.model), kwargs={"object_id": obj_id})
        obj = model_used.objects.filter(id=obj_id).first()
        if not obj:
            raise Exception("{} could not found against id - {}".format(obj_type, obj_id))

        comment = ''
        from ondoc.common.models import Remark
        if hasattr(obj, 'remark'):
            remark_obj = obj.remark.order_by('-created_at').first()
            if remark_obj:
                comment = remark_obj.content

        assigned_user = ''
        if data.get('assigned_matrix_user', None):
            assigned_user = data.get('assigned_user')
        elif hasattr(obj, 'data_status'):
            if obj.data_status == QCModel.SUBMITTED_FOR_QC:
                history_obj = obj.history.filter(status=QCModel.REOPENED).order_by('-created_at').first()
                if history_obj:
                    qc_user = history_obj.user if hasattr(history_obj.user, 'staffprofile') and history_obj.user.staffprofile.employee_id else ''
                    if qc_user and qc_user.is_member_of(constants['QC_GROUP_NAME']):
                        assigned_user = qc_user.staffprofile.employee_id

            else:
                history_obj = obj.history.filter(status=QCModel.SUBMITTED_FOR_QC).order_by('-created_at').first()
                if history_obj:
                    assigned_user = history_obj.user.staffprofile.employee_id if hasattr(history_obj.user,
                                                                                         'staffprofile') and history_obj.user.staffprofile.employee_id else ''

        obj_matrix_lead_id = obj.matrix_lead_id if hasattr(obj, 'matrix_lead_id') and obj.matrix_lead_id else 0
        if not obj_matrix_lead_id:
            return

        if obj_type == IpdProcedureLead.__name__:
            new_status = obj.status
        else:
            new_status = obj.data_status

        request_data = {
            "LeadID": obj_matrix_lead_id,
            "Comment": comment,
            "NewJourneyURL": exit_point_url,
            "AssignedUser": assigned_user,
            "CRMStatusId": new_status
        }
        if getattr(obj, 'planned_date', None):
            request_data.update({'PlannedDate': int(obj.planned_date.timestamp())})
        if hasattr(obj, 'get_appointment_time') and obj.get_appointment_time is not None:
            request_data.update({'AppointmentDate': int(obj.get_appointment_time)})

        url = settings.MATRIX_STATUS_UPDATE_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN

        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info("[ERROR] Status couldn't be updated for {} with ID {} to the matrix system".format(obj_type, obj_id))
            logger.info("[ERROR] %s", response.reason)
            countdown_time = (2 ** self.request.retries) * 60 * 10
            # logging.error("Update with status sync with the Matrix System failed with response - " + str(response.content))
            logger.error("Matrix URL - " + url + ", Payload - " + json.dumps(request_data) + ", Matrix Response - " + json.dumps(response.json()) + "")
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            if not resp_data.get('IsSaved', False):
                logger.error("[ERROR] {} with ID {} not saved to matrix while updating status. ".format(obj_type, obj_id) + json.dumps(request_data))
                # raise Exception("[ERROR] {} with ID {} not saved to matrix while updating status.".format(obj_type, obj_id))
    except Exception as e:
        logger.error("Error in Celery. Failed to update status to the matrix - " + str(e))


# This method is use to create QC status on matrix for onboarding
@task(bind=True, max_retries=2)
def push_onboarding_qcstatus_to_matrix(self, data):
    from ondoc.doctor.models import Doctor
    from ondoc.diagnostic.models import Lab
    log_requests_on()
    try:
        obj_id = data.get('obj_id', None)
        obj_type = data.get('obj_type', None)
        if not obj_id or not obj_type:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        product_id = 0
        gender = 0
        obj = None
        mobile = None
        exit_point_url = None

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
            logger.error(json.dumps(request_data))
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
        logger.error("Error in Celery. Failed pushing qc status to the matrix- " + str(e))


# This method is use to send non bookable doctors data to matrix
@task(bind=True, max_retries=2)
def push_non_bookable_doctor_lead_to_matrix(self, nb_doc_lead_id):
    from ondoc.web.models import NonBookableDoctorLead
    log_requests_on()
    try:
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
            logger.error(json.dumps(request_data))
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
    except Exception as e:
        logger.error("Error while pushing the non bookable doctor lead to matrix. ", str(e))


# To create ipd lead from opd appointment
@task(bind=True, max_retries=2)
def create_ipd_lead_from_opd_appointment(self, data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.procedure.models import IpdProcedureLead
    obj_id = data.get('obj_id')
    if not obj_id:
        logger.error("[CELERY ERROR: Incorrect values provided.]")
        raise ValueError()
    obj = OpdAppointment.objects.filter(id=obj_id).first()
    if not obj:
        return
    is_valid = IpdProcedureLead.is_valid_hospital_for_lead(obj.hospital)
    if not is_valid:
        return
    data = obj.convert_ipd_lead_data()
    data['status'] = IpdProcedureLead.NEW
    data['source'] = IpdProcedureLead.CRM
    obj_created = IpdProcedureLead(**data)
    obj_created.save()


@task()
def decrypted_invoice_pdfs(hospital_ids):
    import operator
    from functools import reduce
    from django.db.models import Q
    from ondoc.doctor import models as doc_models

    # for hospital_id in hospital_ids:
    #     encrypted_invoices = doc_models.PartnersAppInvoice.objects.filter(appointment__hospital_id=hospital_id, is_encrypted=True).order_by('created_at')
    #     for invoice in encrypted_invoices:
    #         previous_version_invoice = doc_models.PartnersAppInvoice.objects.filter(appointment=invoice.appointment, is_encrypted=False).order_by('-updated_at').first()
    #         if previous_version_invoice:
    #             serial = previous_version_invoice.invoice_serial_id.split('-')[-2]
    #             version = str(int(previous_version_invoice.invoice_serial_id.split('-')[-1]) + 1).zfill(2)
    #         else:
    #             last_serial = doc_models.PartnersAppInvoice.last_serial(invoice.appointment)
    #             serial = last_serial + 1
    #             version = '01'
    #         invoice.invoice_serial_id = 'INV-' + str(invoice.appointment.hospital.id) + '-' + str(invoice.appointment.doctor.id) + '-' + str(serial) + '-' + version
    #         invoice.generate_invoice(invoice.selected_invoice_items, invoice.appointment)
    #         invoice.is_encrypted = False
    #         invoice.save()

    for hospital_id in hospital_ids:

        encrypted_invoices = doc_models.PartnersAppInvoice.objects.select_related('appointment') \
                                                                  .prefetch_related('appointment__user',
                                                                                    'appointment__user__patient_mobiles',
                                                                                    'appointment__doctor',
                                                                                    'appointment__doctor__doctor_number',
                                                                                    'appointment__hospital') \
                                                                  .filter(appointment__hospital_id=hospital_id, is_encrypted=True).order_by('created_at')

        appointments = set()
        for invoice in encrypted_invoices:
            appointments.add(invoice.appointment)
        hospital_doctor_combo_ids = set()
        for appointment in appointments:
            hospital_doctor_combo_ids.add(str(appointment.hospital.id) + '-' + str(appointment.doctor.id))

        query = reduce(operator.and_, (Q(invoice_serial_id__contains=combo) for combo in hospital_doctor_combo_ids))
        last_serial_invoices = doc_models.PartnersAppInvoice.objects.filter(query)

        combo_latest_file_value = dict()
        combo_latest_version_value = dict()
        appointment_file_mapping = dict()
        for invoice in last_serial_invoices:
            serial_id_elements = invoice.invoice_serial_id.split('-')
            file_value = int(serial_id_elements[-2])
            version_value = int(serial_id_elements[-1])
            hosp_doc_combo = '-'.join(serial_id_elements[1:3])
            hosp_doc_file_combo = '-'.join(serial_id_elements[1:4])
            if not invoice.appointment in appointment_file_mapping or appointment_file_mapping.get(invoice.appointment) < file_value:
                appointment_file_mapping[invoice.appointment] = file_value
            if hosp_doc_combo not in combo_latest_file_value or combo_latest_file_value.get(hosp_doc_combo) < file_value:
                combo_latest_file_value[hosp_doc_combo] = file_value
            if hosp_doc_file_combo not in combo_latest_version_value or combo_latest_version_value.get(hosp_doc_file_combo) < version_value:
                combo_latest_version_value[hosp_doc_file_combo] = version_value

        for invoice in encrypted_invoices:
            hosp_doc_combo = str(invoice.appointment.hospital.id) + '-' + str(invoice.appointment.doctor.id)
            if not hosp_doc_combo in combo_latest_file_value:
                file = str(doc_models.PartnersAppInvoice.INVOICE_SERIAL_ID_START + 1)
                version = '01'
            else:
                file_value = appointment_file_mapping.get(invoice.appointment)
                if file_value:
                    file = str(file_value)
                    hosp_doc_file_combo = hosp_doc_combo + '-' + file
                    version_value = combo_latest_version_value[hosp_doc_file_combo]
                    version_value += 1
                    combo_latest_version_value[hosp_doc_file_combo] = version_value
                    version = str(version_value).zfill(2)
                else:
                    file_value = combo_latest_file_value[hosp_doc_combo]
                    file_value += 1
                    combo_latest_file_value[hosp_doc_combo] = file_value
                    appointment_file_mapping[invoice.appointment] = file_value
                    file = str(file_value)
                    version_value = 1
                    hosp_doc_file_combo = hosp_doc_combo + '-' + file
                    combo_latest_version_value[hosp_doc_file_combo] = version_value
                    version = str(version_value).zfill(2)

            invoice.invoice_serial_id = 'INV-' + str(invoice.appointment.hospital.id) + '-' + str(invoice.appointment.doctor.id) + '-' + str(file) + '-' + version
            invoice.generate_invoice(invoice.selected_invoice_items, invoice.appointment)
            invoice.is_encrypted = False
            invoice.save()


@task()
def decrypted_prescription_pdfs(hospital_ids, key):
    from ondoc.prescription import models as pres_models
    from ondoc.api.v1 import utils as v1_utils
    from django.db.models import Q
    from functools import reduce
    import operator
    import hashlib

    passphrase = hashlib.md5(key.encode())
    passphrase = passphrase.hexdigest()[:16]

    # for hospital_id in hospital_ids:
    #
    #     encrypted_prescriptions = pres_models.PresccriptionPdf.objects.prefetch_related('history').filter(Q(is_encrypted=True), (Q(opd_appointment__hospital_id=hospital_id) | Q(offline_opd_appointment__hospital_id=hospital_id))).order_by('created_at')
    #
    #     for prescription in encrypted_prescriptions:
    #         appointment = None
    #         appointments_previous_prescription = None
    #         if prescription.appointment_type == pres_models.PresccriptionPdf.DOCPRIME_OPD:
    #             appointment = prescription.opd_appointment
    #             appointments_previous_prescription = pres_models.PresccriptionPdf.objects.filter(is_encrypted=False, opd_appointment=appointment).order_by('-serial_id').first()
    #         elif prescription.appointment_type == pres_models.PresccriptionPdf.OFFLINE:
    #             appointment = prescription.offline_opd_appointment
    #             appointments_previous_prescription = pres_models.PresccriptionPdf.objects.filter(is_encrypted=False, offline_opd_appointment=appointment).order_by('-serial_id').first()
    #
    #         if not appointment:
    #             raise Exception('Could not get docprime opd or offline appointment')
    #
    #         if not appointments_previous_prescription:
    #             serial_id = prescription.get_serial(appointment)
    #             serial_id_elements = serial_id.split('-')
    #             serial_id_elements.insert(0, str(appointment.hospital.id))
    #             serial_id_elements.insert(1, str(appointment.doctor.id))
    #             serial_id_elements[-3] = str(int(serial_id_elements[-3]) + 1)                # serial number incremented
    #         else:
    #             serial_id_elements = appointments_previous_prescription.serial_id.split('-')
    #             serial_id_elements[-3] = appointments_previous_prescription.serial_id.split('-')[-3]                            # serial number
    #             serial_id_elements[-2] = str(int(appointments_previous_prescription.serial_id.split('-')[-2]) + 1).zfill(2)     # file number incremented
    #
    #         version = prescription.decrypt_prescription_history(appointment, passphrase)
    #         if version:
    #             serial_id_elements[-1] = str(int(version) + 1).zfill(2)  # version incremented
    #         prescription.serial_id = '-'.join(serial_id_elements)
    #
    #         exception = v1_utils.patient_details_name_phone_number_decrypt(prescription.patient_details, passphrase)
    #         if exception:
    #             logger.error('Error while decrypting - ' + str(exception))
    #             raise Exception("Error while decrypting - " + str(exception))
    #
    #         prescription.is_encrypted = False
    #         prescription.prescription_file = prescription.get_pdf(appointment)
    #         prescription.save()

    for hospital_id in hospital_ids:

        encrypted_prescriptions = pres_models.PresccriptionPdf.objects.prefetch_related('history') \
                                                                      .filter(Q(is_encrypted=True),
                                                                              (Q(opd_appointment__hospital_id=hospital_id) |
                                                                               Q(offline_opd_appointment__hospital_id=hospital_id))) \
                                                                      .order_by('created_at')
        appointments = set()
        for prescription in encrypted_prescriptions:
            pres_appointment = prescription.opd_appointment if prescription.appointment_type == pres_models.PresccriptionPdf.DOCPRIME_OPD else prescription.offline_opd_appointment
            appointments.add(pres_appointment)

        hospital_doctor_combo_ids = set()
        for appointment in appointments:
            hospital_doctor_combo_ids.add(str(appointment.hospital.id) + '-' + str(appointment.doctor.id))

        query = reduce(operator.and_, (Q(serial_id__contains=combo) for combo in hospital_doctor_combo_ids))
        last_serial_prescription = pres_models.PresccriptionPdf.objects.filter(query)

        combo_latest_serial_value = dict()
        combo_latest_file_value = dict()
        combo_latest_version_value = dict()
        appointment_serial_mapping = dict()
        for prescription in last_serial_prescription:
            pres_appointment = prescription.opd_appointment if prescription.appointment_type == pres_models.PresccriptionPdf.DOCPRIME_OPD else prescription.offline_opd_appointment
            serial_id_elements = prescription.serial_id.split('-')
            serial_value = int(serial_id_elements[-3])
            file_value = int(serial_id_elements[-2])
            version_value = int(serial_id_elements[-1])
            hosp_doc_combo = '-'.join(serial_id_elements[:2])
            hosp_doc_serial_combo = '-'.join(serial_id_elements[:3])
            hosp_doc_serial_file_combo = '-'.join(serial_id_elements[:4])
            if not pres_appointment in appointment_serial_mapping or appointment_serial_mapping.get(pres_appointment) < serial_value:
                appointment_serial_mapping[pres_appointment] = serial_value

            if hosp_doc_combo not in combo_latest_serial_value or combo_latest_serial_value.get(
                    hosp_doc_combo) < serial_value:
                combo_latest_serial_value[hosp_doc_combo] = serial_value
            if hosp_doc_serial_combo not in combo_latest_file_value or combo_latest_file_value.get(
                    hosp_doc_serial_combo) < file_value:
                combo_latest_file_value[hosp_doc_serial_combo] = file_value
            if hosp_doc_serial_file_combo not in combo_latest_version_value or combo_latest_version_value.get(
                    hosp_doc_serial_file_combo) < version_value:
                combo_latest_version_value[hosp_doc_serial_file_combo] = version_value

        for prescription in encrypted_prescriptions:

            pres_appointment = prescription.opd_appointment if prescription.appointment_type == pres_models.PresccriptionPdf.DOCPRIME_OPD else prescription.offline_opd_appointment
            hosp_doc_combo = str(pres_appointment.hospital.id) + '-' + str(pres_appointment.doctor.id)
            if not hosp_doc_combo in combo_latest_serial_value:
                serial = str(pres_models.PresccriptionPdf.SERIAL_ID_START + 1)
                file = '01'
                version = '01'
            else:
                serial_value = appointment_serial_mapping.get(pres_appointment)
                if serial_value:
                    serial = str(serial_value)
                    hosp_doc_serial_combo = hosp_doc_combo + '-' + serial
                    file_value = combo_latest_file_value[hosp_doc_serial_combo]
                    file_value += 1

                else:
                    serial_value = combo_latest_serial_value[hosp_doc_combo]
                    serial_value += 1
                    combo_latest_serial_value[hosp_doc_combo] = serial_value
                    appointment_serial_mapping[pres_appointment] = serial_value
                    serial = str(serial_value)
                    hosp_doc_serial_combo = hosp_doc_combo + '-' + serial
                    file_value = 1

                file = str(file_value).zfill(2)
                combo_latest_file_value[hosp_doc_serial_combo] = file_value
                hosp_doc_serial_file_combo = hosp_doc_serial_combo + '-' + file
                version = prescription.decrypt_prescription_history(pres_appointment, serial, file, passphrase)
                if version:
                    version_value = int(version) + 1
                    version = str(version_value).zfill(2)
                else:
                    version_value = 1
                    version = '01'
                combo_latest_version_value[hosp_doc_serial_file_combo] = version_value

            serial_id_elements = [str(pres_appointment.hospital.id),
                                  str(pres_appointment.doctor.id),
                                  serial, file, version]
            prescription.serial_id = '-'.join(serial_id_elements)

            exception = v1_utils.patient_details_name_phone_number_decrypt(prescription.patient_details, passphrase)
            if exception:
                logger.error('Error while decrypting - ' + str(exception))
                raise Exception("Error while decrypting - " + str(exception))

            prescription.is_encrypted = False
            prescription.prescription_file = prescription.get_pdf(pres_appointment)
            prescription.save()


# To create ipd lead from lab appointment
@task(bind=True, max_retries=2)
def create_ipd_lead_from_lab_appointment(self, data):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.procedure.models import IpdProcedureLead
    obj_id = data.get('obj_id')
    if not obj_id:
        logger.error("[CELERY ERROR: Incorrect values provided.]")
        raise ValueError()
    obj = LabAppointment.objects.filter(id=obj_id).first()
    if not obj:
        return

    is_valid = IpdProcedureLead.is_valid_lab_for_lead(obj.lab)
    if not is_valid:
        return

    data = obj.convert_ipd_lead_data()
    data['status'] = IpdProcedureLead.NEW
    data['source'] = IpdProcedureLead.CRM
    obj_created = IpdProcedureLead(**data)
    obj_created.save()


# Check if ipd lead is valid or not
@task(bind=True, max_retries=2)
def check_for_ipd_lead_validity(self, data):
    from ondoc.procedure.models import IpdProcedureLead
    obj_id = data.get('obj_id')
    if not obj_id:
        logger.error("[CELERY ERROR: Incorrect values provided.]")
        raise ValueError()
    obj = IpdProcedureLead.objects.filter(id=obj_id).first()
    if not obj:
        return
    if obj.is_valid:
        return
    try:
        obj.validate_lead()
    except Exception as e:
        pass


# To create retail appointment lead
@task(bind=True, max_retries=2)
def push_retail_appointment_to_matrix(self, data):
    from ondoc.doctor.models import OpdAppointment
    log_requests_on()
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Matrix")

        appointment = OpdAppointment.objects.filter(pk=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        # if not appointment.is_retail_booking():
        #     raise Exception("Not a Retail Appointment - " + str(appointment_id))

        request_data = appointment.get_matrix_retail_booking_data()

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})
        logger.info(json.dumps(request_data))
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Retail Appointment could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Retail Appointment sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()
        logger.info(resp_data)
        if not resp_data.get('Id', None):
            logger.error(json.dumps(request_data))
            raise Exception("[ERROR] Id not recieved from the matrix while pushing retail appointment lead.")

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Retail Appointment to the matrix- " + str(e))


# Push order details to salespoint
@task(bind=True, max_retries=2)
def push_order_to_spo(self, data):
    try:
        if not data:
            raise Exception('Data not received for the task.')

        order_id = data.get('order_id', None)
        if not order_id:
            logger.error("[ERROR-SPO Order: Incorrect values provided.]")
            raise ValueError()

        order_obj = Order.objects.filter(id=order_id).first()

        if not order_obj:
            raise Exception("Order could not found against id - " + str(order_id))

        if order_obj and order_obj.user and order_obj.product_id == Order.LAB_PRODUCT_ID:
            if not order_obj.action_data.get('spo_data', None):
                return

        spo_data = order_obj.action_data.get('spo_data')
        phone_number = order_obj.user.phone_number
        name = order_obj.user.full_name

        request_data = {
            'LeadSource': 'DocPrime',
            'PatientName': name,
            'BookedBy': phone_number,
            'OrderId': order_obj.id,
            'PrimaryNo': phone_number,
            'ProductId': 5,
            'SubProductId': 2,
            'DocPrimeUserId': order_obj.user.id,
            'UtmTerm': spo_data.get('UtmTerm', ''),
            'UtmMedium': spo_data.get('UtmMedium', ''),
            'UtmCampaign': spo_data.get('UtmCampaign', ''),
            'UtmSource': spo_data.get('UtmSource', ''),
            'LeadID': 0
        }

        #logger.error(json.dumps(request_data))

        url = settings.VIP_SALESPOINT_URL
        spo_api_token = settings.VIP_SALESPOINT_AUTHTOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': spo_api_token,
                                                                              'Content-Type': 'application/json'})
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error("[ERROR-SPO] Failed to push order details - " + str(json.dumps(request_data)))

            countdown_time = (2 ** self.request.retries) * 60 * 10
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            resp_data = resp_data['data']
            if resp_data.get('error', None):
                logger.error("[ERROR-SPO] Order could not be published to the SPO system - " + str(
                    json.dumps(request_data)))
                logger.info("[ERROR-SPO] %s", resp_data.get('errorDetails', []))
            else:
                logger.info("Order push to spo successfully.")

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment to the SPO- " + str(e))


@task(bind=True, max_retries=2)
def create_prescription_lead_to_matrix(self, data):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.notification.tasks import save_matrix_logs
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push prescription lead to Matrix")

        appointment = LabAppointment.objects.filter(id=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        booking_url = '%s/admin/diagnostic/labappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
        if appointment.profile.phone_number:
            phone_number = appointment.profile.phone_number
        else:
            phone_number = appointment.user.phone_number
        feedback_url = "%s/chat-ratings?&appointment_id=%s" \
                         % (settings.BASE_URL, appointment.id)
        tiny_feedback_url = generate_short_url(feedback_url)

        request_data = {
            "Name": appointment.profile.name if appointment.profile else "",
            "ProductId": 14,
            "PrimaryNo": phone_number,
            "LeadSource": "Prescriptions",
            "ExitPointUrl": booking_url,
            "VIPPlanName": None,
            "IPDBookingId": appointment.id,
            "URL": tiny_feedback_url
        }

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})
        if settings.SAVE_LOGS:
            save_matrix_logs.apply_async((appointment.id, 'lab_appointment', request_data, response.json()), countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info(json.dumps(request_data))
            logger.info("[ERROR] Appointment Prescription could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logger.error("Appointment Prescription syc with the Matrix System failed with response - " + str(response))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()
        print(resp_data)

        if not resp_data.get('Id', None):
            return

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment Prescription lead to matrix- " + str(e))


@task(bind=True, max_retries=1)
def send_report_review_data_to_chat(self, data):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.notification.tasks import save_matrix_logs

    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push prescription lead to Matrix")

        appointment = LabAppointment.objects.filter(id=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        feedback_url = "%s/chat-ratings?&appointment_id=%s" % (settings.BASE_URL, appointment.id)
        tiny_feedback_url = generate_short_url(feedback_url)

        booking_url = '%s/admin/diagnostic/labappointment/%s/change' % (settings.ADMIN_BASE_URL, appointment.id)
        profile = appointment.profile
        age = appointment.calculate_age()
        lab_tests = appointment.tests.all()
        test_data = []
        for test in lab_tests:
            test_details = {
                "test_id": test.id,
                "mrp": "00.00",
                "test": {
                    "id": test.id,
                    "name": test.name,
                    "pre_test_info": test.pre_test_info,
                    "why": test.why,
                    "show_details": test.show_details,
                    "url": test.url
                },
                "agreed_price": 0.0,
                "deal_price": 0.0,
                "test_type": test.test_type,
                "is_home_collection_enabled": False
            }

            test_data.append(test_details)

        request_data = {
            "id": appointment.id,
            "profile": {
                "id": profile.id,
                "name": profile.name,
                "email": profile.email,
                "gender": profile.gender,
                "phone_number": profile.phone_number,
                "is_otp_verified": profile.is_otp_verified,
                "is_default_user": profile.is_default_user,
                "profile_image": None,
                "age": age,
                "user": appointment.user.id,
                "dob": str(profile.dob),
                "is_insured": False,
                "updated_at": str(profile.updated_at),
                "whatsapp_optin": profile.whatsapp_optin,
                "whatsapp_is_declined": profile.whatsapp_is_declined,
                "insurance_status": 0,
                "is_vip_member": False,
                "is_vip_gold_member": False
            },
            "lab_test": test_data,
            "reports": appointment.get_report_urls(),
            "report_files": appointment.get_report_type(),
            "ExitPointUrl": booking_url,
            "url": tiny_feedback_url
        }

        url = settings.CHAT_LAB_REPORT_API_URL
        chat_lab_report_api_token = settings.CHAT_LAB_REPORT_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': chat_lab_report_api_token,
                                                                              'Content-Type': 'application/json'})
        if settings.SAVE_LOGS:
            save_matrix_logs.apply_async((appointment.id, 'lab_appointment', request_data, response.json()),
                                         countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.info(json.dumps(request_data))
            logger.info("[ERROR] Chat Report Review Data Push Failed")
            logger.info("[ERROR] %s", response)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logger.error("Chat Report Review Data Push Failed  - " + str(response))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)

        resp_data = response.json()
        print(resp_data)

        if resp_data.get('message', '') == 'Success':
            print('Data Pushed to Chat.')

    except Exception as e:
        logger.error("Error in Celery. Failed pushing Appointment Prescription lead to matrix- " + str(e))
