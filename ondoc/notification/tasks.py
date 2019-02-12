from __future__ import absolute_import, unicode_literals

import copy
import datetime
import json
import math
import traceback
from collections import OrderedDict
from io import BytesIO

from django.db import transaction
from django.forms import model_to_dict
from django.utils import timezone
from openpyxl import load_workbook

from ondoc.api.v1.utils import aware_time_zone, util_absolute_url
from ondoc.common.models import AppointmentMaskNumber
from ondoc.notification.labnotificationaction import LabNotificationAction
from ondoc.notification import models as notification_models
from celery import task
import logging
from django.conf import settings
import requests
from rest_framework import status
from django.utils.safestring import mark_safe
from ondoc.notification.models import NotificationAction

logger = logging.getLogger(__name__)


@task
def send_lab_notifications_refactored(appointment_id):
    from ondoc.diagnostic import models as lab_models
    from ondoc.communications.models import LabNotification
    instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
    if not instance or not instance.user:
        return
    try:
        instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
        if not instance or not instance.user:
            return
        if instance.status == lab_models.LabAppointment.COMPLETED:
            instance.generate_invoice()
        counter = 1
        is_masking_done = False
        while counter < 3:
            if is_masking_done:
                break
            else:
                is_masking_done = generate_appointment_masknumber(
                    ({'type': 'LAB_APPOINTMENT', 'appointment_id': instance.id}))
        # generate_appointment_masknumber(({'type': 'LAB_APPOINTMENT', 'appointment_id': instance.id}))
        lab_notification = LabNotification(instance)
        lab_notification.send()
    except Exception as e:
        logger.error(str(e))


@task
def send_lab_notifications(appointment_id):
    from ondoc.diagnostic import models as lab_models
    instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
    if not instance:
        return
    if not instance.user:
        return
    # lab_managers = lab_models.LabManager.objects.filter(lab=instance.lab)
    lab_managers = instance.get_lab_admins()
    if instance.status == lab_models.LabAppointment.COMPLETED:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_INVOICE,
        )
        return
    if instance.status == lab_models.LabAppointment.ACCEPTED:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_ACCEPTED,
        )
        return
    if instance.status == lab_models.LabAppointment.RESCHEDULED_PATIENT:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT)
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
        )
        return
    if instance.status == lab_models.LabAppointment.RESCHEDULED_LAB:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
        )
        return
    if instance.status == lab_models.LabAppointment.CANCELLED:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_CANCELLED)
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_CANCELLED,
        )
        return
    if instance.status == lab_models.LabAppointment.BOOKED:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_BOOKED)
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_BOOKED,
        )
        return


@task()
def send_opd_notifications_refactored(appointment_id):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.communications.models import OpdNotification
    try:
        instance = OpdAppointment.objects.filter(id=appointment_id).first()
        if not instance or not instance.user:
            return
        if instance.status == OpdAppointment.COMPLETED:
            instance.generate_invoice()
        counter = 1
        is_masking_done = False
        while counter < 3:
            if is_masking_done:
                break
            else:
                is_masking_done = generate_appointment_masknumber(
                    ({'type': 'OPD_APPOINTMENT', 'appointment_id': instance.id}))
        opd_notification = OpdNotification(instance)
        opd_notification.send()
    except Exception as e:
        logger.error(str(e))


@task
def send_opd_notifications(appointment_id):
    from ondoc.authentication.models import GenericAdmin
    from ondoc.doctor.models import OpdAppointment
    instance = OpdAppointment.objects.filter(id=appointment_id).first()
    if not instance:
        return
    if not instance.user:
        return
    doctor_admins = GenericAdmin.get_appointment_admins(instance)
    if instance.user and instance.status == OpdAppointment.ACCEPTED:
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_ACCEPTED,
        )
    elif instance.status == OpdAppointment.RESCHEDULED_PATIENT:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT)
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT)
    elif instance.status == OpdAppointment.RESCHEDULED_DOCTOR:
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR)
    elif instance.status == OpdAppointment.BOOKED:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_BOOKED)
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_BOOKED)
    elif instance.status == OpdAppointment.CANCELLED:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_CANCELLED)
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_CANCELLED)
    elif instance.status == OpdAppointment.COMPLETED:
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.DOCTOR_INVOICE,
        )

@task(max_retries=1)
def send_opd_rating_message(appointment_id, type):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    from django.conf import settings
    data = {}
    name = ''
    try:
        if type == 'opd':
            appointment = OpdAppointment.objects.filter(id=appointment_id, is_rated=False, status=OpdAppointment.COMPLETED).first()
            name = appointment.doctor.name if appointment else None
        else:
            appointment = LabAppointment.objects.filter(id=appointment_id, is_rated=False, status=LabAppointment.COMPLETED).first()
            name = appointment.lab.name if appointment else None
        if appointment:
            number = appointment.user.phone_number
            data['phone_number'] = number
            app_url = settings.CONSUMER_APP_DOMAIN
            text_url = str(app_url)+ "/" + str(type) + "/appointment/" + str(appointment_id)
            text = '''You have successfully completed your appointment with %s . Rate your experience %s''' % (name, text_url)
            data['text'] = mark_safe(text)
            notification_models.SmsNotification.send_rating_link(data)
    except Exception as e:
        logger.error(str(e))
        pass

@task(bind=True, max_retries=5)
def set_order_dummy_transaction(self, order_id, user_id):
    from ondoc.account.models import Order, DummyTransactions
    from ondoc.account.models import User
    try:
        order_row = Order.objects.filter(id=order_id).first()
        user = User.objects.filter(id=user_id).first()

        if order_row and order_row.parent:
            raise Exception("Cannot create dummy payout for a child order.")

        if order_row and user:
            if order_row.getTransactions():
                #print("dummy Transaction already set")
                return

            appointment = order_row.getAppointment()
            if not appointment:
                raise Exception("No Appointment found.")

            total_price = order_row.get_total_price()

            token = settings.PG_DUMMY_TRANSACTION_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_DUMMY_TRANSACTION_URL

            req_data = {
                "customerId": user_id,
                "mobile": user.phone_number,
                "email": user.email or "dummyemail@docprime.com",
                "productId": order_row.product_id,
                "orderId": order_id,
                "name": appointment.profile.name,
                "txAmount": 0,
                "couponCode": "",
                "couponAmt": str(total_price),
                "paymentMode": "DC",
                "AppointmentId": appointment.id,
                "buCallbackSuccessUrl": "",
                "buCallbackFailureUrl": ""
            }

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                #logger.error(resp_data)
                if resp_data.get("ok") is not None and resp_data.get("ok") == 1:
                    tx_data = {}
                    tx_data['user'] = user
                    tx_data['product_id'] = order_row.product_id
                    tx_data['order_no'] = resp_data.get('orderNo')
                    tx_data['order_id'] = order_row.id
                    tx_data['reference_id'] = appointment.id
                    tx_data['type'] = DummyTransactions.CREDIT
                    tx_data['amount'] = total_price
                    tx_data['payment_mode'] = "DC"

                    # tx_data['transaction_id'] = resp_data.get('orderNo')
                    # tx_data['response_code'] = response.get('responseCode')
                    # tx_data['bank_id'] = response.get('bankTxId')
                    # transaction_time = parse(response.get("txDate"))
                    # tx_data['transaction_date'] = transaction_time
                    # tx_data['bank_name'] = response.get('bankName')
                    # tx_data['currency'] = response.get('currency')
                    # tx_data['status_code'] = response.get('statusCode')
                    # tx_data['pg_name'] = response.get('pgGatewayName')
                    # tx_data['status_type'] = response.get('txStatus')
                    # tx_data['pb_gateway_name'] = response.get('pbGatewayName')

                    DummyTransactions.objects.create(**tx_data)
                    #print("SAVED DUMMY TRANSACTION")
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))

    except Exception as e:
        logger.error("Error in Setting Dummy Transaction of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
        self.retry([order_id, user_id], countdown=300)

@task
def send_offline_appointment_message(number, text, type):
    data = {}
    data['phone_number'] = number
    data['text'] = mark_safe(text)
    try:
        notification_models.SmsNotification.send_rating_link(data)
    except Exception as e:
        logger.error("Error sending " + str(type) + " message - " + str(e))

def generate_appointment_masknumber(data):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    appointment_type = data.get('type')
    try:
        is_masking_done = False
        is_maskable = True
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            # logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise Exception("Appointment id not found, could not get mask number")

        if appointment_type == 'OPD_APPOINTMENT':
            appointment = OpdAppointment.objects.filter(id=appointment_id).first()
            if not appointment:
                raise Exception("Appointment not found, could not get mask number")
            is_network_enabled_hospital = appointment.hospital
            if is_network_enabled_hospital:
                is_maskable = is_network_enabled_hospital.is_mask_number_required
            else:
                is_maskable = True
        elif data.get('type') == 'LAB_APPOINTMENT':
            appointment = LabAppointment.objects.filter(id=appointment_id).first()
            if not appointment:
                raise Exception("Appointment not found, could not get mask number")
            is_network_enabled_lab = appointment.lab.network
            if is_network_enabled_lab:
                is_maskable = is_network_enabled_lab.is_mask_number_required
            else:
                is_maskable = True
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        phone_number = appointment.user.phone_number
        time_slot = appointment.time_slot_start
        updated_time_slot = time_slot + datetime.timedelta(days=1)
        validity_up_to = int((time_slot + datetime.timedelta(days=1)).timestamp())
        if not phone_number:
            raise Exception("phone Number could not found against id - " + str(appointment_id))
        if is_maskable:
            request_data = {
                "ExpirationDate": validity_up_to,
                "FromId": appointment.id,
                "ToNumber": phone_number
            }
            url = settings.MATRIX_NUMBER_MASKING
            matrix_api_token = settings.MATRIX_API_TOKEN
            response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                                  'Content-Type': 'application/json'})

            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Appointment could not be get Mask Number")
                logger.info("[ERROR] %s", response.reason)
                # countdown_time = (2 ** self.request.retries) * 60 * 10
                # logging.error("Appointment sync with the Matrix System failed with response - " + str(response.content))
                # print(countdown_time)
                # self.retry([data], countdown=countdown_time)

            mask_number = response.json()
        else:
            mask_number = phone_number
        if mask_number:
            existing_mask_number_obj = appointment.mask_number.filter(is_deleted=False).first()
            if existing_mask_number_obj:
                existing_mask_number_obj.is_deleted = True
                existing_mask_number_obj.save()
                AppointmentMaskNumber(content_object=appointment, mask_number=mask_number,
                                                     validity_up_to=updated_time_slot, is_deleted=False).save()
                is_masking_done = True
            else:
                AppointmentMaskNumber(content_object=appointment, mask_number=mask_number,
                                                     validity_up_to=updated_time_slot, is_deleted=False).save()
                is_masking_done = True
        else:
            raise Exception("Failed to generate Mask Number for the appointment - " + str(appointment_id))
    except Exception as e:
        logger.error("Error in Celery. Failed to get mask number for appointment " + str(e))
    return is_masking_done

@task
def send_appointment_reminder_message(number, patient_name, doctor, hospital_name, date):
    data = {}
    data['phone_number'] = number
    text = '''Dear %s, you have an appointment scheduled with %s at %s on %s''' % (patient_name, doctor, hospital_name, date)
    data['text'] = mark_safe(text)
    try:
        notification_models.SmsNotification.send_rating_link(data)
    except Exception as e:
        logger.error("Error sending Reminder message - " + str(e))

@task
def send_appointment_location_message(number, hospital_lat, hospital_long):
    data = {}
    data['phone_number'] = number

    link = '''http://maps.google.com/maps?q=loc:%s,%s''' % (hospital_lat, hospital_long)
    text = '''Location for your Upcoming Appointment %s ''' % (link)
    data['text'] = mark_safe(text)
    try:
        notification_models.SmsNotification.send_rating_link(data)
    except Exception as e:
        logger.error("Error sending Location message - " + str(e))

@task()
def process_payout(payout_id):
    from ondoc.account.models import MerchantPayout, Order
    from ondoc.account.models import DummyTransactions

    try:
        if not payout_id:
            raise Exception("No payout specified")

        payout_data = MerchantPayout.objects.filter(id=payout_id).first()
        if not payout_data or payout_data.status == payout_data.PAID:
            raise Exception("Payment already done for this payout")


        default_payment_mode = payout_data.get_default_payment_mode()

        appointment = payout_data.get_appointment()
        billed_to = payout_data.get_billed_to()
        merchant = payout_data.get_merchant()
        order_data = None

        if not appointment or not billed_to or not merchant:
            raise Exception("Insufficient Data " + str(payout_data))

        if not merchant.verified_by_finance or not merchant.enabled:
            raise Exception("Merchant is not verified or is not enabled. " + str(payout_data))

        associated_merchant = billed_to.merchant.first()
        if not associated_merchant.verified:
            raise Exception("Associated Merchant not verified. " + str(payout_data))

        # assuming 1 to 1 relation between Order and Appointment
        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()

        if not order_data:
             raise Exception("Order not found for given payout " + str(payout_data))


        all_txn = order_data.getTransactions()

        if not all_txn or all_txn.count() == 0:
            raise Exception("No transactions found for given payout " + str(payout_data))

        req_data = { "payload" : [], "checkSum" : "" }
        req_data2 = { "payload" : [], "checkSum" : "" }

        idx = 0
        for txn in all_txn:
            
            curr_txn = OrderedDict()
            curr_txn["idx"] = idx
            curr_txn["orderNo"] = txn.order_no
            curr_txn["orderId"] = txn.order.id
            curr_txn["txnAmount"] = str(txn.amount)
            curr_txn["settledAmount"] = str(payout_data.payable_amount)
            curr_txn["merchantCode"] = merchant.id
            if txn.transaction_id:
                curr_txn["pgtxId"] = txn.transaction_id
            curr_txn["refNo"] = payout_data.payout_ref_id
            curr_txn["bookingId"] = appointment.id
            curr_txn["paymentType"] = payout_data.payment_mode if payout_data.payment_mode else default_payment_mode
            req_data["payload"].append(curr_txn)
            idx += 1
            if isinstance(txn, DummyTransactions) and txn.amount>0:
                curr_txn2 = copy.deepcopy(curr_txn)
                curr_txn2["txnAmount"] = str(0)
                curr_txn2["idx"] = len(req_data2.get('payload'))
                req_data2["payload"].append(curr_txn2)

        payout_status = None
        if len(req_data2.get('payload'))>0:
            payout_status = request_payout(req_data2, order_data)

        if not payout_status or not payout_status.get('status'):
            payout_status = request_payout(req_data, order_data)

        if payout_status:
            payout_data.api_response = payout_status.get("response")
            if payout_status.get("status"):
                payout_data.payout_time = datetime.datetime.now()
                payout_data.status = payout_data.PAID
            else:
                payout_data.retry_count += 1

            payout_data.save()


    except Exception as e:
        logger.error("Error in processing payout - with exception - " + str(e))

def request_payout(req_data, order_data):
    from ondoc.api.v1.utils import create_payout_checksum

    req_data["checkSum"] = create_payout_checksum(req_data["payload"], order_data.product_id)
    headers = {
        "auth": settings.PG_REFUND_AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    url = settings.PG_SETTLEMENT_URL
    resp_data = None

    response = requests.post(url, data=json.dumps(req_data), headers=headers)
    resp_data = response.json()

    if response.status_code == status.HTTP_200_OK:
        if resp_data.get("ok") is not None and resp_data.get("ok") == '1':
            success_payout = False
            result = resp_data.get('result')
            if result:
                for res_txn in result:
                    success_payout = res_txn['status'] == "SUCCESSFULLY_INSERTED"

            if success_payout:
                return {"status": 1, "response": resp_data}
            
    
    logger.error("payout failed for request data - " + str(req_data))
    return {"status" : 0, "response" : resp_data}

@task()
def opd_send_otp_before_appointment(appointment_id, previous_appointment_date_time):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.communications.models import OpdNotification
    try:
        instance = OpdAppointment.objects.filter(id=appointment_id).first()
        if not instance or \
                not instance.user or \
                str(math.floor(instance.time_slot_start.timestamp())) != previous_appointment_date_time \
                or instance.status != OpdAppointment.ACCEPTED:
            # logger.error(
            #     'instance : {}, time : {}, str: {}'.format(str(model_to_dict(instance)),
            #                                                previous_appointment_date_time,
            #                                                str(math.floor(instance.time_slot_start.timestamp()))))
            return
        opd_notification = OpdNotification(instance, NotificationAction.OPD_OTP_BEFORE_APPOINTMENT)
        opd_notification.send()
    except Exception as e:
        logger.error(str(e))

@task()
def lab_send_otp_before_appointment(appointment_id, previous_appointment_date_time):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.communications.models import LabNotification
    try:
        instance = LabAppointment.objects.filter(id=appointment_id).first()
        if not instance or \
                not instance.user or \
                str(math.floor(instance.time_slot_start.timestamp())) != previous_appointment_date_time \
                or instance.status != LabAppointment.ACCEPTED:
            # logger.error(
            #     'instance : {}, time : {}, str: {}'.format(str(model_to_dict(instance)),
            #                                                previous_appointment_date_time,
            #                                                str(math.floor(instance.time_slot_start.timestamp()))))
            return
        lab_notification = LabNotification(instance, NotificationAction.LAB_OTP_BEFORE_APPOINTMENT)
        lab_notification.send()
    except Exception as e:
        logger.error(str(e))

@task()
def send_lab_reports(appointment_id):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.communications.models import LabNotification
    try:
        instance = LabAppointment.objects.filter(id=appointment_id).first()
        if not instance:
            return
        lab_notification = LabNotification(instance, NotificationAction.LAB_REPORT_SEND_VIA_CRM)
        lab_notification.send()
    except Exception as e:
        logger.error(str(e))

@task()
def upload_doctor_data(obj_id):
    from ondoc.doctor.models import UploadDoctorData
    from ondoc.crm.management.commands import upload_doctor_data as upload_command
    instance = UploadDoctorData.objects.filter(id=obj_id).first()
    errors = []
    if not instance or not instance.status == UploadDoctorData.IN_PROGRESS:
        return
    try:
        source = instance.source
        batch = instance.batch
        lines = instance.lines if instance and instance.lines else 100000000
        wb = load_workbook(instance.file)
        sheets = wb.worksheets
        doctor = upload_command.UploadDoctor(errors)
        qualification = upload_command.UploadQualification(errors)
        experience = upload_command.UploadExperience(errors)
        membership = upload_command.UploadMembership(errors)
        award = upload_command.UploadAward(errors)
        hospital = upload_command.UploadHospital(errors)
        specialization = upload_command.UploadSpecialization(errors)
        with transaction.atomic():
            # doctor.p_image(sheets[0], source, batch)
            doctor.upload(sheets[0], source, batch, lines, instance.user)
            qualification.upload(sheets[1], lines)
            experience.upload(sheets[2], lines)
            membership.upload(sheets[3], lines)
            award.upload(sheets[4], lines)
            hospital.upload(sheets[5], source, batch, lines)
            specialization.upload(sheets[6], lines)
            if len(errors)>0:
                raise Exception('errors in data')
        instance.status = UploadDoctorData.SUCCESS
        instance.save()
    except Exception as e:
        error_message = traceback.format_exc() + str(e)
        logger.error(error_message)
        instance.status = UploadDoctorData.FAIL
        if errors:
            instance.error_msg = errors
        else:
            instance.error_msg = [{'line number': 0, 'message': error_message}]
        instance.save(retry=False)

@task()
def send_pg_acknowledge(order_id=None, order_no=None):
    try:
        if order_id is None or order_no is None:
            logger.error("Cannot acknowledge without order_id and order_no")
            return

        url = settings.PG_PAYMENT_ACKNOWLEDGE_URL + "?orderNo=" + str(order_no) + "&orderId=" + str(order_id)
        response = requests.get(url)
        if response.status_code == status.HTTP_200_OK:
            print("Payment acknowledged")

    except Exception as e:
        logger.error("Error in sending pg acknowledge - " + str(e))