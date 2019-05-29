import copy
import json
import random
from collections import defaultdict
from itertools import groupby
from datetime import datetime
import pytz
import jwt
from ondoc.authentication.backends import JWTAuthentication
from django.db.models import F, Q
# from hardcopy import bytestring_to_pdf

from ondoc.api.v1.utils import util_absolute_url, util_file_name, generate_short_url
from ondoc.banner.models import EmailBanner
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from ondoc.common.models import UserConfig
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile, InMemoryUploadedFile
from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields.jsonb import KeyTransform
from django.utils.crypto import get_random_string
import logging
from django.conf import settings
from django.utils import timezone
from weasyprint import HTML

from ondoc.account.models import Invoice, Order
from ondoc.authentication.models import UserProfile, GenericAdmin, NotificationEndpoint, AgentToken, UserSecretKey, \
    ClickLoginToken

from ondoc.notification.models import NotificationAction, SmsNotification, EmailNotification, AppNotification, \
    PushNotification, WhtsappNotification
# from ondoc.notification.sqs_client import publish_message
from ondoc.notification.rabbitmq_client import publish_message
# import datetime
from ondoc.api.v1.utils import aware_time_zone

User = get_user_model()
logger = logging.getLogger(__name__)


def get_spoc_email_and_number_hospital(spocs, appointment):
    user_and_email = []
    user_and_number = []
    for spoc in spocs:
        if spoc.number and spoc.number in range(1000000000, 9999999999):
            admins = GenericAdmin.objects.prefetch_related('user').filter(Q(phone_number=str(spoc.number),
                                                                            hospital=spoc.content_object),
                                                                          Q(super_user_permission=True) |
                                                                          Q(Q(permission_type=GenericAdmin.APPOINTMENT),
                                                                            Q(doctor__isnull=True) | Q(doctor=appointment.doctor)))
            if admins:
                admins_with_user = admins.filter(user__isnull=False)
                if admins_with_user.exists():
                    for admin in admins_with_user:
                        if int(admin.user.phone_number) == int(spoc.number):
                            user_and_number.append({'user': admin.user, 'phone_number': spoc.number})
                            if spoc.email:
                                user_and_email.append({'user': admin.user, 'email': spoc.email})
                        else:
                            user_and_number.append({'user': None, 'phone_number': spoc.number})
                            if spoc.email:
                                user_and_email.append({'user': None, 'email': spoc.email})

                admins_without_user = admins.exclude(id__in=admins_with_user)
                if admins_without_user.exists():
                    for admin in admins_without_user:
                        created_user = User.objects.create(phone_number=spoc.number, user_type=User.DOCTOR,
                                                           auto_created=True)
                        admin.user = created_user
                        admin.save()
                        user_and_number.append({'user': created_user, 'phone_number': spoc.number})
                        if spoc.email:
                            user_and_email.append({'user': created_user, 'email': spoc.email})
            else:
                user_and_number.append({'user': None, 'phone_number': spoc.number})
        elif spoc.email:
            user_and_email.append({'user': None, 'email': spoc.email})
    return user_and_email, user_and_number


def get_lab_manager_email_and_number(managers):
    user_and_email = []
    user_and_number = []
    all_email = set()
    all_phone_number = set()
    for manager in managers:
        if manager.email:
            all_email.add(manager.email)
        if manager.number and manager.number in range(1000000000, 9999999999):
            all_phone_number.add(manager.number)
    for phone_number in all_phone_number:
        user_and_number.append({'user': None, 'phone_number': phone_number})
    for email in all_email:
        user_and_email.append({'user': None, 'email': email})
    return user_and_email, user_and_number


def unique_emails(list_):
    """Function accepts list of dictionaries and returns list of unique dictionaries"""
    if not list_:
        return list_
    temp = set()

    for item in list_:
        if item.get('email', None) or item.get('user', None):
            temp.add((item.get('user'), item.get('email').strip().lower()))
    return [{'user': item[0], 'email': item[1]} for item in temp]


def unique_phone_numbers(list_):
    """Function accepts list of dictionaries and returns list of unique dictionaries"""
    if not list_:
        return list_
    temp = set()

    for item in list_:
        if item.get('phone_number', None) or item.get('user', None):
            temp.add((item.get('user'), str(item.get('phone_number')).strip().lower()))

    return [{'user': item[0], 'phone_number': item[1]} for item in temp]


def get_title_body(notification_type, context, user):
    # notification_type = self.notification_type
    # context = self.context
    patient_name = context.get('patient_name')
    doctor_name = context.get('doctor_name', None)
    lab_name = context.get('lab_name', None)
    time_slot_start = context.get('time_slot_start', None)
    instance = context.get('instance')
    title = ''
    body = ''
    if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
        title = "Appointment Confirmed"
        body = "Appointment Confirmed for {} requested with Dr. {} for {}, {}.".format(
            patient_name, doctor_name, time_slot_start.strftime("%d/%m/%y"),
            time_slot_start.strftime("%I:%M %P"), doctor_name)
    elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment with Dr. {}".format(doctor_name)
    elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment with Dr. {}".format(doctor_name)
    elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment from Dr. {}".format(doctor_name)
    elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
        title = "New Appointment"
        # body = "New Appointment for {} at {}, {} with Dr. {}. You will receive a confirmation as soon as it is accepted by the doctor.".format(
        #     patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"), doctor_name)
        body = "New Appointment is received for {} with Dr. {} for {}, {}. Awaiting confirmation from the doctor.".format(
            patient_name, doctor_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
    elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.DOCTOR:
        title = "New Appointment"
        body = "New appointment for {} at {}, {}. Please confirm.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
    elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.DOCTOR:
        title = "Appointment Cancelled"
        body = "Appointment with {} at {}  {} has been cancelled.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
    elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
        if instance.cancellation_type != instance.AUTO_CANCELLED:
            body = "Appointment with Dr. {} for {}, {} has been cancelled as per your request.".format(
                doctor_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
        else:
            body = "Appointment with Dr. {} for {}, {} has been cancelled due to unavailability of doctor manager.".format(
                doctor_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
        title = "Appointment Cancelled"
    # elif notification_type == NotificationAction.DOCTOR_INVOICE:
    #     title = "Invoice Generated"
    #     body = "Invoice for appointment ID-{} has been generated.".format(instance.id)
    elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
        title = "Prescription Uploaded"
        body = "Prescription available for your appointment with Dr. {} on {}".format(
            doctor_name, time_slot_start.strftime("%d/%m/%y"))

    elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
        title = "Appointment Confirmed"
        body = "Appointment Confirmed for {} requested with Lab - {} for {}, {}.".format(
            patient_name, lab_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"), lab_name)
    elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment with Lab - {}".format(lab_name)
    elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.DOCTOR:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment with Lab - {}".format(lab_name)
    elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
        title = "Appointment Reschedule"
        body = "Reschedule request received for the appointment from Lab - {}".format(lab_name)
    elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
        title = "New Appointment"
        body = "New Appointment is received for {} with Lab - {} for {}, {} . Awaiting confirmation from the lab".format(
            patient_name, lab_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
    elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.DOCTOR:
        title = "New Appointment"
        body = "New appointment for {} at {}, {}. Please confirm.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
    elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
        if instance.cancellation_type != instance.AUTO_CANCELLED:
            body = "Appointment with Lab - {} for {}, {} has been cancelled as per your request.".format(
                lab_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
        else:
            body = "Appointment with Lab - {} for {}, {} has cancelled due to unavailability of lab manager.".format(
                lab_name, time_slot_start.strftime("%d/%m/%y"), time_slot_start.strftime("%I:%M %P"))
        title = "Appointment Cancelled"
    elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED:
        title = "Appointment Cancelled"
        body = "Appointment with {} at {}  {} has been cancelled.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"),
            time_slot_start.strftime("%d/%m/%y"))
    # elif notification_type == NotificationAction.LAB_INVOICE:
    #     title = "Invoice Generated"
    #     body = "Invoice for appointment ID-{} has been generated.".format(instance.id)
    elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
        title = "Report Uploaded"
        body = "Report available for your appointment with Lab - {} on {}".format(
            lab_name, time_slot_start.strftime("%d/%m/%y"))
    context.update({'title': title, 'body': body})


class Notification:
    SMS = 1
    EMAIL = 2
    PUSH = 3
    IN_APP = 4
    OPD_NOTIFICATION_TYPE_MAPPING = \
        {
            OpdAppointment.ACCEPTED: NotificationAction.APPOINTMENT_ACCEPTED,
            OpdAppointment.RESCHEDULED_PATIENT: NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
            OpdAppointment.RESCHEDULED_DOCTOR: NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
            OpdAppointment.BOOKED: NotificationAction.APPOINTMENT_BOOKED,
            OpdAppointment.CANCELLED: NotificationAction.APPOINTMENT_CANCELLED,
            OpdAppointment.COMPLETED: NotificationAction.DOCTOR_INVOICE
        }
    LAB_NOTIFICATION_TYPE_MAPPING = \
        {
            LabAppointment.ACCEPTED: NotificationAction.LAB_APPOINTMENT_ACCEPTED,
            LabAppointment.RESCHEDULED_PATIENT: NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
            LabAppointment.RESCHEDULED_LAB: NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
            LabAppointment.BOOKED: NotificationAction.LAB_APPOINTMENT_BOOKED,
            LabAppointment.CANCELLED: NotificationAction.LAB_APPOINTMENT_CANCELLED,
            LabAppointment.COMPLETED: NotificationAction.LAB_INVOICE
        }


class SMSNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        context = copy.deepcopy(context)
        context.pop('time_slot_start', None)
        self.context = context

    def get_template(self, user):
        notification_type = self.notification_type
        body_template = ''
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED or \
                notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            body_template = "sms/appointment_accepted.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_booked_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/appointment_booked_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_rescheduled_patient_initiated_to_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/appointment_rescheduled_patient_initiated_to_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_rescheduled_doctor_initiated_to_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/appointment_cancelled_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_cancelled_patient.txt"
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template = "sms/prescription_uploaded.txt"
        elif notification_type == NotificationAction.APPOINTMENT_REMINDER_PROVIDER_SMS:
            body_template = "sms/appointment_reminder.txt"

        elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED or \
                notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:
            body_template = "sms/lab/appointment_accepted.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_booked_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/lab/appointment_booked_lab.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_rescheduled_patient_initiated_to_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/lab/appointment_rescheduled_patient_initiated_to_lab.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_rescheduled_lab_initiated_to_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_cancelled_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/lab/appointment_cancelled_lab.txt"
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            body_template = "sms/lab/lab_report_uploaded.txt"
        elif notification_type == NotificationAction.INSURANCE_CONFIRMED:
            body_template = "sms/insurance/insurance_confirmed.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE:
            body_template = "sms/insurance/insurance_cancellation.txt"
        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            body_template = "sms/lab/lab_report_send_crm.txt"
            lab_reports = []
            for report in self.context.get('reports', []):
                temp_short_url = generate_short_url(report)
                lab_reports.append(temp_short_url)
            self.context['lab_reports'] = lab_reports
        elif notification_type == NotificationAction.REFUND_COMPLETED:
            body_template = "sms/refund_completed.txt"
        elif notification_type == NotificationAction.REFUND_BREAKUP:
            body_template = "sms/refund_breakup.txt"
        elif notification_type == NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT:
            body_template = "sms/appointment_confirmation_check.txt"
        elif notification_type == NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT:
            body_template = "sms/appointment_confirmation_second_check.txt"
        elif notification_type == NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT:
            body_template = "sms/appointment_feedback.txt"
        elif notification_type == NotificationAction.LAB_CONFIRMATION_CHECK_AFTER_APPOINTMENT:
            body_template = "sms/lab/lab_confirmation_check.txt"
        elif notification_type == NotificationAction.LAB_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT:
            body_template = "sms/lab/lab_confirmation_second_check.txt"
        elif notification_type == NotificationAction.LAB_FEEDBACK_AFTER_APPOINTMENT:
            body_template = "sms/lab/lab_feedback.txt"
        return body_template

    def trigger(self, receiver, template, context):
        user = receiver.get('user')
        phone_number = receiver.get('phone_number')
        notification_type = self.notification_type
        context = copy.deepcopy(context)
        html_body = render_to_string(template, context=context)

        instance = context.get('instance')
        receiver_user = receiver.get('user')

        # Hospital and labs which has the flag open to communication, send notificaiton to them only.
        if (instance.__class__.__name__ == LabAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if not instance.lab.open_for_communications():
                return

        if (instance.__class__.__name__ == OpdAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if instance.hospital and not instance.hospital.open_for_communications():
                return

        if phone_number and user and user.user_type == User.DOCTOR and notification_type in [
            NotificationAction.LAB_APPOINTMENT_CANCELLED,
            NotificationAction.LAB_APPOINTMENT_BOOKED,
            NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT]:
            sms_noti = SmsNotification.objects.create(
                phone_number=phone_number,
                notification_type=notification_type,
                content=html_body
            )
            message = {
                "data": model_to_dict(sms_noti),
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        elif phone_number:
            sms_noti = SmsNotification.objects.create(
                user=user,
                phone_number=phone_number,
                notification_type=notification_type,
                content=html_body
            )
            message = {
                "data": model_to_dict(sms_noti),
                "type": "sms"
            }
            message = json.dumps(message)
            if phone_number not in settings.OTP_BYPASS_NUMBERS:
                publish_message(message)

    def save_token_to_context(self, context, user):
        appointment = context.get("instance")
        user_key = UserSecretKey.objects.get_or_create(user=user)
        payload = JWTAuthentication.provider_sms_payload_handler(user, appointment)
        token = jwt.encode(payload, user_key[0].key)
        token = str(token, 'utf-8')
        appointment_type = 'opd' if appointment.__class__ == OpdAppointment else 'lab'
        url_key = get_random_string(length=ClickLoginToken.URL_KEY_LENGTH)
        unique_key_found = False
        while not unique_key_found:
            if ClickLoginToken.objects.filter(url_key=url_key).exists():
                url_key = get_random_string(length=30)
            else:
                unique_key_found = True
        expiration_time = datetime.fromtimestamp(payload.get('exp'))
        # ClickLoginToken.objects.create(user=user, token=token, expiration_time=expiration_time, url_key=url_key)
        click_login_token_obj = ClickLoginToken(user=user, token=token, expiration_time=expiration_time, url_key=url_key)
        provider_login_url = settings.PROVIDER_APP_DOMAIN + "/sms/login?key=" + url_key + \
                                        "&url=/sms-redirect/" + appointment_type + "/appointment/" + str(appointment.id)
        context['provider_login_url'] = generate_short_url(provider_login_url)
        return context, click_login_token_obj

    def send(self, receivers):
        context = self.context
        if not context:
            return
        click_login_token_objects = list()
        for receiver in receivers:
            template = self.get_template(receiver.get('user'))
            if receiver.get('user') and receiver.get('user').user_type == User.DOCTOR:
                context, click_login_token_obj = self.save_token_to_context(context, receiver['user'])
                click_login_token_objects.append(click_login_token_obj)
            elif context.get('provider_login_url'):
                context.pop('provider_login_url')
            if template:
                self.trigger(receiver, template, context)
        ClickLoginToken.objects.bulk_create(click_login_token_objects)


class WHTSAPPNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        context = copy.deepcopy(context)
        context.pop('time_slot_start', None)
        self.context = context

    def get_template_and_data(self, user):
        notification_type = self.notification_type
        body_template = ''
        data = []
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED or \
                notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            body_template = "appointment_accepted_opd_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').otp)
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            if self.context.get('instance').payment_type == 2:
                data.append('Amount To Be Paid :Rs ' + str(self.context.get('cod_amount')))
            else:
                data.append('Amount Paid : Rs ' + str(self.context.get('instance').effective_price))

            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').hospital.get_hos_address())

            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

            if self.context.get('instance').payment_type == 2:
                data.append('Please pay Rs {cod_amount} at the center at the time of appointment.'.
                            format(cod_amount=str(self.context.get('code_amount'))))
            else:
                data.append(" ")

        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "opd_appointment_booking_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').hospital.get_hos_address())
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_booked_doctor"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').hospital.name)
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').profile.phone_number)
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').hospital.get_hos_address())

        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "opd_appointment_rescheduled_patient_initiated_to_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_rescheduled_patient_initiated_to_doctor"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').profile.phone_number)
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user and user.user_type == User.CONSUMER:
            body_template = "opd_appointment_rescheduled_patient_initiated_to_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_cancelled_doctor"

            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(self.context.get('instance').hospital.name)
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))

        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "opd_appointment_cancellation_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))

        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template = "prescription_uploaded"

            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('patient_name'))

        elif notification_type == NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT:
            body_template = 'appointment_confirmation_check'

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('opd_appointment_complete_url'))
            data.append(self.context.get('reschdule_appointment_bypass_url'))

        elif notification_type == NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT:
            body_template = 'appointment_confirmation_second_check'

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('opd_appointment_complete_url'))
            data.append(self.context.get('reschdule_appointment_bypass_url'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED or \
                notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:
            body_template = "appointment_accepted"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('instance').otp)
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))

            pickup_address = 'NA'
            if self.context.get('pickup_address'):
                pickup_address = self.context.get('pickup_address')

            data.append(pickup_address)
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
        #     body_template = "appointment_booked_patient"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     pickup_address = 'NA'
        #     if self.context.get('pickup_address'):
        #         pickup_address = self.context.get('pickup_address')
        #
        #     data.append(pickup_address)
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_booked_lab"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').profile.phone_number)
            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "appointment_rescheduled_patient_initiated_to_patient"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(self.context.get('instance').id)
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_rescheduled_patient_initiated_to_lab"


            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(self.context.get('instance').id)
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('instance').profile.phone_number)
            data.append(self.context.get('lab_name'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user and user.user_type == User.CONSUMER:
            body_template = "appointment_rescheduled_lab_initiated_to_patient"

            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "lab_appointment_cancellation_patient"

            data.append(self.context.get('patient_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('lab_name'))
            data.append(self.context.get('lab_name'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            # TODO: not implemented yet. So just setting generic text.
            data.append('Paid amount')

        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "appointment_cancelled_lab"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
            data.append(self.context.get('instance').id)
            data.append(self.context.get('patient_name'))
            data.append(self.context.get('lab_name'))

        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            body_template = "lab_report_uploaded"

            data.append(self.context.get('lab_name'))
            data.append(self.context.get('patient_name'))

        elif notification_type == NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT:
            body_template = "opd_after_completion"

            data.append(self.context.get('patient_name'))
            data.append(self.context.get('doctor_name'))
            data.append(self.context.get('opd_appointment_feedback_url'))

        elif notification_type == NotificationAction.REFUND_BREAKUP:
            body_template = "appointment_refund_breakup"

            data.append(self.context.get('amount'))
            if self.context.get('booking_id'):
                data.append('for you booking id %d' % self.context.get('instance').id)
            else:
                data.append('.')

            if self.context.get('ctrnx_id'):
                data.append('The transaction ID for this refund is : DPRF%s' % str(self.context.get('ctrnx_id')))
            else:
                data.append(' ')

        # elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
        #     body_template = "sms/lab/lab_report_send_crm.txt"
        #     lab_reports = []
        #     for report in self.context.get('reports', []):
        #         temp_short_url = generate_short_url(report)
        #         lab_reports.append(temp_short_url)
        #     self.context['lab_reports'] = lab_reports
        return body_template, data

    def trigger(self, receiver, template, context, **kwargs):
        user = receiver.get('user')
        phone_number = receiver.get('phone_number')
        notification_type = self.notification_type

        context = copy.deepcopy(context)

        instance = context.get('instance')
        receiver_user = receiver.get('user')

        # Hospital and labs which has the flag open to communication, send notificaiton to them only.
        if (instance.__class__.__name__ == LabAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if not instance.lab.open_for_communications():
                return

        if (instance.__class__.__name__ == OpdAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if instance.hospital and not instance.hospital.open_for_communications():
                return

        if phone_number and user and user.user_type == User.DOCTOR and notification_type in [
            NotificationAction.LAB_APPOINTMENT_CANCELLED,
            NotificationAction.LAB_APPOINTMENT_BOOKED,
            NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT]:
            whtsapp_noti = WhtsappNotification.objects.create(
                phone_number=phone_number,
                notification_type=notification_type,
                template_name=template,
                payload=kwargs.get('payload', {}),
                extras={}
            )
            message = {
                "data": whtsapp_noti.payload,
                "type": "social_message"
            }
            message = json.dumps(message)
            publish_message(message)
        elif phone_number:
            whtsapp_noti = WhtsappNotification.objects.create(
                user=user,
                phone_number=phone_number,
                notification_type=notification_type,
                template_name=template,
                payload=kwargs.get('payload', {}),
                extras={}
            )
            message = {
                "data": whtsapp_noti.payload,
                "type": "social_message"
            }
            message = json.dumps(message)
            if phone_number not in settings.OTP_BYPASS_NUMBERS:
                publish_message(message)

    def send(self, receivers):
        context = self.context
        if not context:
            return
        for receiver in receivers:
            receiver_user = receiver.get('user')

            instance = self.context.get('instance')
            if receiver_user and receiver_user.user_type == User.CONSUMER and not instance.profile.whatsapp_optin:
                continue

            template, data = self.get_template_and_data(receiver_user)

            undesired_params = list(filter(lambda param: not param, data))
            if not template:
                logger.error('[ERROR] Could not send Whtsapp message to user as suitable template not found for the '
                             'case. Notification type %s for appointment id %d'
                             % (self.notification_type, self.context.get('instance').id))

            if undesired_params:
                logger.error('[ERROR] Could not send Whtsapp message to user as missing parameters for the appointment '
                             'id %d. Params %s' % (self.context.get('instance').id, str(data)))

            # prepare payload for the whtsapp service.
            payload = {
                'phone_number': receiver.get('phone_number'),
                'message': '',
                'message_type': 'HSM',
                'template': {
                    'name': template,
                    'params': data
                },
                'media': {}
            }

            if template:
                self.trigger(receiver, template, context, payload=payload)


class EMAILNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        context = copy.deepcopy(context)
        context.pop('time_slot_start', None)
        self.context = context

    def get_template(self, user):
        notification_type = self.notification_type
        context = self.context
        body_template = ''
        subject_template = ''
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            body_template = "email/appointment_accepted/body.html"
            subject_template = "email/appointment_accepted/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "email/appointment_booked_patient/body.html"
            subject_template = "email/appointment_booked_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "email/appointment_booked_doctor/body.html"
            subject_template = "email/appointment_booked_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "email/appointment_rescheduled_patient_initiated_to_patient/body.html"
            subject_template = "email/appointment_rescheduled_patient_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "email/appointment_rescheduled_patient_initiated_to_doctor/body.html"
            subject_template = "email/appointment_rescheduled_patient_initiated_to_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user and user.user_type == User.CONSUMER:
            body_template = "email/appointment_rescheduled_doctor_initiated_to_patient/body.html"
            subject_template = "email/appointment_rescheduled_doctor_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "email/appointment_cancelled_doctor/body.html"
            subject_template = "email/appointment_cancelled_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "email/appointment_cancelled_patient/body.html"
            subject_template = "email/appointment_cancelled_patient/subject.txt"
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template = "email/prescription_uploaded/body.html"
            subject_template = "email/prescription_uploaded/subject.txt"
        elif notification_type == NotificationAction.DOCTOR_INVOICE:
            invoices = context.get("instance").generate_invoice(context)
            if not invoices:
                logger.error("Got error while creating pdf for opd invoice")
                return '', ''
            context.update({"invoice": invoices[0]})
            context.update({"invoice_url": invoices[0].file.url})
            context.update(
                {"attachments": [
                    {"filename": util_file_name(invoices[0].file.url),
                     "path": util_absolute_url(invoices[0].file.url)}]})
            body_template = "email/doctor_invoice/body.html"
            subject_template = "email/doctor_invoice/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
            body_template = "email/lab/appointment_accepted/body.html"
            subject_template = "email/lab/appointment_accepted/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_booked_patient/body.html"
            subject_template = "email/lab/appointment_booked_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            body_template = "email/lab/appointment_booked_lab/body.html"
            subject_template = "email/lab/appointment_booked_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_rescheduled_patient_initiated_to_patient/body.html"
            subject_template = "email/lab/appointment_rescheduled_patient_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
            body_template = "email/lab/appointment_rescheduled_patient_initiated_to_lab/body.html"
            subject_template = "email/lab/appointment_rescheduled_patient_initiated_to_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_rescheduled_lab_initiated_to_patient/body.html"
            subject_template = "email/lab/appointment_rescheduled_lab_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_cancelled_patient/body.html"
            subject_template = "email/lab/appointment_cancelled_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
            body_template = "email/lab/appointment_cancelled_lab/body.html"
            subject_template = "email/lab/appointment_cancelled_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            body_template = "email/lab/lab_report_uploaded/body.html"
            subject_template = "email/lab/lab_report_uploaded/subject.txt"
        elif notification_type == NotificationAction.LAB_INVOICE:
            invoices = context.get("instance").generate_invoice(context)
            if not invoices:
                logger.error("Got error while creating pdf for lab invoice")
                return '', ''
            context.update({"invoice": invoices[0]})
            context.update({"invoice_url": invoices[0].file.url})
            context.update(
                {"attachments": [{"filename": util_file_name(invoices[0].file.url),
                                  "path": util_absolute_url(invoices[0].file.url)}]})
            body_template = "email/lab_invoice/body.html"
            subject_template = "email/lab_invoice/subject.txt"
        elif notification_type == NotificationAction.INSURANCE_CONFIRMED:

            coi = context.get("instance").coi
            if not coi:
                logger.error("Got error while creating pdf for opd invoice")
                return '', ''
            context.update({"coi": coi})
            context.update({"coi_url": coi.url})
            context.update(
                {"attachments": [
                    {"filename": util_file_name(coi.url),
                     "path": util_absolute_url(coi.url)}]})

            body_template = "email/insurance_confirmed/body.html"
            subject_template = "email/insurance_confirmed/subject.txt"

        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            attachments = []
            for report_link in context.get('reports', []):
                attachments.append({"filename": util_file_name(report_link), "path": util_absolute_url(report_link)})
            context.update({'attachments': attachments})
            body_template = "email/lab/lab_report_send_crm/body.html"
            subject_template = "email/lab/lab_report_send_crm/subject.txt"
        elif notification_type == NotificationAction.IPD_PROCEDURE_MAIL:
            body_template = "email/ipd_lead/body.html"
            subject_template = "email/ipd_lead/subject.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE:
            body_template = "email/insurance_cancelled/body.html"
            subject_template = "email/insurance_cancelled/subject.txt"
        elif notification_type == NotificationAction.PRICING_ALERT_EMAIL:
            body_template = "email/lab/lab_pricing_change/body.html"
            subject_template = "email/lab/lab_pricing_change/subject.txt"
        elif notification_type == NotificationAction.LAB_LOGO_CHANGE_MAIL:
            instance = context.get("instance", None)
            if instance:
                logo = context.get("instance").name
                if not logo:
                    logger.error("No logo found for logo change mail")
                    return '', ''
                context.update({"logo": logo})
                context.update({"coi_url": logo.url})
                context.update(
                    {"attachments": [
                        {"filename": util_file_name(logo.url),
                         "path": util_absolute_url(logo.url)}]})

                body_template = "email/lab_document_logo/body.html"
                subject_template = "email/lab_document_logo/subject.txt"

        return subject_template, body_template

    def trigger(self, receiver, template, context):
        if not template[0] and not template[1]:
            return
        cc = []
        bcc = [settings.PROVIDER_EMAIL]
        attachments = context.get('attachments', [])
        user = receiver.get('user')
        email = receiver.get('email')
        notification_type = self.notification_type
        context = copy.deepcopy(context)
        instance = context.get('instance', None)
        receiver_user = receiver.get('user')

        # Hospital and labs which has the flag open to communication, send notificaiton to them only.
        send_without_email = False
        if (instance.__class__.__name__ == LabAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if not instance.lab.open_for_communications():
                email = None
                send_without_email = True

        if (instance.__class__.__name__ == OpdAppointment.__name__) and (not receiver_user or receiver_user.user_type == User.DOCTOR):
            if instance.hospital and not instance.hospital.open_for_communications():
                email = None
                send_without_email = True

        email_subject = render_to_string(template[0], context=context)
        html_body = render_to_string(template[1], context=context)
        if (email or send_without_email) and user and user.user_type == User.DOCTOR and notification_type in [
            NotificationAction.LAB_APPOINTMENT_CANCELLED,
            NotificationAction.LAB_APPOINTMENT_BOOKED,
            NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT]:
            email_noti = EmailNotification.objects.create(
                email=email,
                notification_type=notification_type,
                content=html_body,
                email_subject=email_subject,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                content_object = instance
            )
            message = {
                "data": model_to_dict(email_noti),
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        elif (email or send_without_email):
            email_noti = EmailNotification.objects.create(
                user=user,
                email=email,
                notification_type=notification_type,
                content=html_body,
                email_subject=email_subject,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                content_object=instance

            )
            message = {
                "data": model_to_dict(email_noti),
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    def send(self, receivers):
        context = self.context
        if not context:
            return
        for receiver in receivers:
            template = self.get_template(receiver.get('user'))
            if template:
                self.trigger(receiver, template, context)


class APPNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = copy.deepcopy(context)

    def trigger(self, receiver, context):
        user = receiver
        context = copy.deepcopy(context)
        context.pop("instance", None)
        context.pop('time_slot_start', None)
        app_noti = AppNotification.objects.create(
            user=user,
            notification_type=self.notification_type,
            content=context
        )
        message = {
            "data": model_to_dict(app_noti),
            "type": "app"
        }
        message = json.dumps(message)
        publish_message(message)

    def send(self, receivers):
        context = self.context
        if not context:
            return
        for receiver in receivers:
            get_title_body(self.notification_type, context, receiver)
            self.trigger(receiver, context)


class PUSHNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = copy.deepcopy(context)

    def trigger(self, receiver, context):
        user = receiver.get('user')
        tokens = receiver.get('tokens')
        context = copy.deepcopy(context)
        context.pop("instance", None)
        context.pop('time_slot_start', None)
        target_app = user.user_type
        push_noti = PushNotification.objects.create(
            user=user,
            notification_type=self.notification_type,
            content=context,
            target_app=target_app
        )

        data = model_to_dict(push_noti)
        data["tokens"] = tokens
        message = {
            "data": data,
            "type": "push"
        }
        message = json.dumps(message)
        publish_message(message)

    def send(self, receivers):
        context = self.context
        if not context:
            return
        for receiver in receivers:
            get_title_body(self.notification_type, context, receiver.get('user'))
            self.trigger(receiver, context)


class OpdNotification(Notification):

    def __init__(self, appointment, notification_type=None):
        self.appointment = appointment
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.OPD_NOTIFICATION_TYPE_MAPPING[appointment.status]

    def get_context(self):
        patient_name = self.appointment.profile.name if self.appointment.profile.name else ""
        doctor_name = self.appointment.doctor.name if self.appointment.doctor.name else ""
        procedures = self.appointment.get_procedures()
        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = self.appointment.time_slot_start.astimezone(est)
        mask_number_instance = self.appointment.mask_number.filter(is_deleted=False).first()
        mask_number=''
        if mask_number_instance:
            mask_number = mask_number_instance.mask_number

        email_banners_html = EmailBanner.get_banner(self.appointment, self.notification_type)
        # email_banners_html = UserConfig.objects.filter(key__iexact="email_banners") \
        #             .annotate(html_code=KeyTransform('html_code', 'data')).values_list('html_code', flat=True).first()

        # Implmented According to DOCNEW-360
        # auth_token = AgentToken.objects.create_token(user=self.appointment.user)
        clinic_or_hospital = "Clinic"
        if self.appointment.hospital.assoc_doctors.filter(enabled=True).count() > 10:
            clinic_or_hospital = "Hospital"
        token_object = JWTAuthentication.generate_token(self.appointment.user)
        booking_url = settings.BASE_URL + '/sms/booking?token={}'.format(token_object['token'].decode("utf-8"))
        opd_appointment_complete_url = booking_url + "&callbackurl=opd/appointment/{}?complete=true".format(self.appointment.id)
        opd_appointment_feedback_url = booking_url + "&callbackurl=opd/appointment/{}".format(self.appointment.id)
        reschdule_appointment_bypass_url = booking_url + "&callbackurl=opd/doctor/{}/{}/book?reschedule={}".format(self.appointment.doctor.id, self.appointment.hospital.id, self.appointment.id)
        context = {
            "doctor_name": doctor_name,
            "patient_name": patient_name,
            "id": self.appointment.id,
            "instance": self.appointment,
            "clinic_or_hospital": clinic_or_hospital,
            "procedures": procedures,
            "coupon_discount": str(self.appointment.discount) if self.appointment.discount else None,
            "url": "/opd/appointment/{}".format(self.appointment.id),
            "action_type": NotificationAction.OPD_APPOINTMENT,
            "action_id": self.appointment.id,
            "payment_type": dict(OpdAppointment.PAY_CHOICES)[self.appointment.payment_type],
            "image_url": "",
            "time_slot_start": time_slot_start,
            "attachments": {},  # Updated later
            "screen": "appointment",
            "type": "doctor",
            "cod_amount": int(self.appointment.mrp),
            "mask_number": mask_number,
            "email_banners": email_banners_html if email_banners_html is not None else "",
            "opd_appointment_complete_url": generate_short_url(opd_appointment_complete_url),
            "opd_appointment_feedback_url": generate_short_url(opd_appointment_feedback_url),
            "reschdule_appointment_bypass_url": generate_short_url(reschdule_appointment_bypass_url)
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.DOCTOR_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
        elif notification_type in [NotificationAction.REFUND_BREAKUP, NotificationAction.REFUND_COMPLETED] and context.get('instance').payment_type == 3:
            # As no notification to be sent in case of insurance.
            pass

        elif notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT or \
                notification_type == NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT or \
                notification_type == NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT or \
                notification_type == NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))

            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type== NotificationAction.APPOINTMENT_REMINDER_PROVIDER_SMS:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))

        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        doctor_spocs_app_recievers = []
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers

        doctor_spocs = instance.hospital.get_spocs_for_communication() if instance.hospital else []
        spocs_to_be_communicated = []
        if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
                                 NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
                                 NotificationAction.PRESCRIPTION_UPLOADED,
                                 NotificationAction.DOCTOR_INVOICE,
                                 NotificationAction.OPD_OTP_BEFORE_APPOINTMENT,
                                 NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.APPOINTMENT_BOOKED,
                                   NotificationAction.APPOINTMENT_CANCELLED]:
            spocs_to_be_communicated = doctor_spocs
            doctor_spocs_app_recievers = GenericAdmin.get_appointment_admins(instance)
            # receivers.extend(doctor_spocs)
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_REMINDER_PROVIDER_SMS]:
            spocs_to_be_communicated = doctor_spocs
            doctor_spocs_app_recievers = GenericAdmin.get_appointment_admins(instance)
        receivers = list(set(receivers))
        user_and_phone_number = []
        user_and_email = []
        app_receivers = receivers
        user_and_tokens = []

        push_recievers = receivers+doctor_spocs_app_recievers
        user_and_token = [{'user': token.user, 'token': token.token, 'app_name': token.app_name} for token in
                          NotificationEndpoint.objects.filter(user__in=push_recievers).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append(
                {'user': user, 'tokens': [{"token": t['token'], "app_name": t["app_name"]} for t in user_token_group]})

        for user in receivers:
            if user.user_type == User.CONSUMER:
                email = instance.profile.email
                phone_number = instance.profile.phone_number
                # send notification to default profile also
                default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
                if default_user_profile and (
                        default_user_profile.id != instance.profile.id) and default_user_profile.phone_number:
                    user_and_phone_number.append(
                        {'user': user, 'phone_number': default_user_profile.phone_number})
                if default_user_profile and (
                        default_user_profile.id != instance.profile.id) and default_user_profile.email:
                    user_and_email.append({'user': user, 'email': default_user_profile.email})
            else:
                email = user.email
                phone_number = user.phone_number

            if phone_number:
                user_and_phone_number.append({'user': user, 'phone_number': phone_number})
            if email:
                user_and_email.append({'user': user, 'email': email})
        spoc_emails, spoc_numbers = get_spoc_email_and_number_hospital(spocs_to_be_communicated, instance)
        user_and_phone_number.extend(spoc_numbers)
        user_and_email.extend(spoc_emails)
        user_and_email = unique_emails(user_and_email)
        user_and_phone_number = unique_phone_numbers(user_and_phone_number)
        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['app_receivers'] = app_receivers + doctor_spocs_app_recievers
        all_receivers['push_receivers'] = user_and_tokens

        return all_receivers


class LabNotification(Notification):

    def __init__(self, appointment, notification_type=None):
        self.appointment = appointment
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.LAB_NOTIFICATION_TYPE_MAPPING[appointment.status]

    def get_context(self):
        instance = self.appointment
        patient_name = instance.profile.name.title() if instance.profile.name else ""
        lab_name = instance.lab.name.title() if instance.lab.name else ""
        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = self.appointment.time_slot_start.astimezone(est)
        tests = self.appointment.get_tests_and_prices()
        report_file_links = instance.get_report_urls()
        token_object = JWTAuthentication.generate_token(self.appointment.user)
        booking_url = settings.BASE_URL + '/sms/booking?token={}'.format(token_object['token'].decode("utf-8"))
        lab_appointment_complete_url = booking_url + "&callbackurl=lab/appointment/{}?complete=true".format(self.appointment.id)
        lab_appointment_feedback_url = booking_url + "&callbackurl=lab/appointment/{}".format(self.appointment.id)
        reschedule_appointment_bypass_url = booking_url + "&callbackurl=lab/{}/timeslots?reschedule=true".format(self.appointment.lab.id)

        email_banners_html = EmailBanner.get_banner(instance, self.notification_type)
        # email_banners_html = UserConfig.objects.filter(key__iexact="email_banners") \
        #             .annotate(html_code=KeyTransform('html_code', 'data')).values_list('html_code', flat=True).first()


        for test in tests:
            test['mrp'] = str(test['mrp'])
            test['deal_price'] = str(test['deal_price'])
            test['discount'] = str(test['discount'])
        mask_number_instance = self.appointment.mask_number.filter(is_deleted=False).first()
        mask_number = ''
        if mask_number_instance:
            mask_number = mask_number_instance.mask_number
        context = {
            "lab_name": lab_name,
            "patient_name": patient_name,
            "id": instance.id,
            "instance": instance,
            "url": "/lab/appointment/{}".format(instance.id),
            "action_type": NotificationAction.LAB_APPOINTMENT,
            "action_id": instance.id,
            "image_url": "",
            "pickup_address": self.appointment.get_pickup_address(),
            "coupon_discount": str(self.appointment.discount) if self.appointment.discount else None,
            "time_slot_start": time_slot_start,
            "tests": tests,
            "reports": report_file_links,
            "attachments": {},  # Updated later
            "screen": "appointment",
            "type": "lab",
            "mask_number": mask_number,
            "email_banners": email_banners_html if email_banners_html is not None else "",
            "lab_appointment_complete_url": generate_short_url(lab_appointment_complete_url),
            "lab_appointment_feedback_url": generate_short_url(lab_appointment_feedback_url),
            "reschedule_appointment_bypass_url": generate_short_url(reschedule_appointment_bypass_url),
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.LAB_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))

        elif notification_type in [NotificationAction.REFUND_BREAKUP, NotificationAction.REFUND_COMPLETED] and context.get('instance').payment_type == 3:
            # As no notification to be sent in case of insurance.
            pass

        elif notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))

        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers
        # lab_spocs = instance.get_lab_admins()
        lab_managers = instance.lab.get_managers_for_communication() if instance.lab else []
        lab_managers_to_be_communicated = []
        if notification_type in [NotificationAction.LAB_APPOINTMENT_ACCEPTED,
                                 NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
                                 NotificationAction.LAB_REPORT_UPLOADED,
                                 NotificationAction.LAB_INVOICE,
                                 NotificationAction.LAB_OTP_BEFORE_APPOINTMENT,
                                 NotificationAction.LAB_CONFIRMATION_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_FEEDBACK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_REPORT_SEND_VIA_CRM]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.LAB_APPOINTMENT_BOOKED,
                                   NotificationAction.LAB_APPOINTMENT_CANCELLED]:
            lab_managers_to_be_communicated = lab_managers
            # receivers.extend(lab_spocs)
            receivers.append(instance.user)
        receivers = list(set(receivers))
        user_and_phone_number = []
        user_and_email = []
        app_receivers = receivers
        user_and_tokens = []

        user_and_token = [{'user': token.user, 'token': token.token, 'app_name': token.app_name} for token in
                          NotificationEndpoint.objects.filter(user__in=receivers).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append(
                {'user': user, 'tokens': [{"token": t['token'], "app_name": t["app_name"]} for t in user_token_group]})

        for user in receivers:
            if user.user_type == User.CONSUMER:
                email = instance.profile.email
                phone_number = instance.profile.phone_number
                # send notification to default profile also
                default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
                if default_user_profile and (
                        default_user_profile.id != instance.profile.id) and default_user_profile.phone_number:
                    user_and_phone_number.append(
                        {'user': user, 'phone_number': default_user_profile.phone_number})
                if default_user_profile and (
                        default_user_profile.id != instance.profile.id) and default_user_profile.email:
                    user_and_email.append({'user': user, 'email': default_user_profile.email})
            else:
                email = user.email
                phone_number = user.phone_number

            if phone_number:
                user_and_phone_number.append({'user': user, 'phone_number': phone_number})
            if email:
                user_and_email.append({'user': user, 'email': email})
        user_and_phone_number = unique_phone_numbers(user_and_phone_number)
        user_and_email = unique_emails(user_and_email)
        manager_emails, manager_numbers = get_lab_manager_email_and_number(lab_managers_to_be_communicated)
        user_and_phone_number.extend(manager_numbers)
        user_and_email.extend(manager_emails)
        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['app_receivers'] = app_receivers
        all_receivers['push_receivers'] = user_and_tokens

        return all_receivers


class InsuranceNotification(Notification):

    def __init__(self, insurance, notification_type=None):
        self.insurance = insurance
        self.notification_type = notification_type

    def get_context(self):
        instance = self.insurance
        insured_members = instance.members.all()
        proposer = list(filter(lambda member: member.relation.lower() == 'self', insured_members))
        proposer = proposer[0]

        # proposer_fname = proposer.first_name if proposer.first_name else ""
        # proposer_mname = proposer.middle_name if proposer.middle_name else ""
        # proposer_lname = proposer.last_name if proposer.last_name else ""
        #
        # proposer_name = '%s %s %s %s' % (proposer.title, proposer_fname, proposer_mname, proposer_lname)
        proposer_name = proposer.get_full_name()

        member_list = list()
        count = 1
        for member in insured_members:
            # fname = member.first_name if member.first_name else ""
            # mname = member.middle_name if member.middle_name else ""
            # lname = member.last_name if member.last_name else ""
            #
            # name = '%s %s %s' % (fname, mname, lname)
            name = member.get_full_name()
            data = {
                'name': name.title(),
                'member_number': count,
                'dob': member.dob.strftime('%d-%m-%Y'),
                'relation': member.relation.title(),
                'id': member.id,
                'gender': member.gender.title(),
                'age': int((datetime.now().date() - member.dob).days/365),
            }
            member_list.append(data)
            count = count + 1

        context = {
            'instance': instance,
            'purchase_date': str(aware_time_zone(instance.purchase_date).date().strftime('%d %b %Y')),
            'expiry_date': str(aware_time_zone(instance.expiry_date).date().strftime('%d %b %Y')),
            'premium': instance.premium_amount,
            'proposer_name': proposer_name.title(),
            'current_date': timezone.now().date().strftime('%d %b %Y'),
            'policy_number': instance.policy_number,
            'total_member_covered': len(member_list),
            'plan': instance.insurance_plan.name,
            'insured_members': member_list,
            'insurer_logo': instance.insurance_plan.insurer.logo.url,
            'coi_url': instance.coi.url,
            'insurer_name': instance.insurance_plan.insurer.name
        }

        return context

    def get_receivers(self):

        all_receivers = {}
        instance = self.insurance
        if not instance:
            return {}

        user_and_phone_number = []
        user_and_email = []

        insured_members = instance.members.all()
        proposer = list(filter(lambda member: member.relation.lower() == 'self', insured_members))
        proposer = proposer[0]

        user_and_email.append({'user': instance.user, 'email': proposer.email})
        user_and_phone_number.append({'user': instance.user, 'phone_number': proposer.phone_number})

        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email

        return all_receivers

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type in [NotificationAction.INSURANCE_CONFIRMED, NotificationAction.INSURANCE_CANCEL_INITIATE]:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))

            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
