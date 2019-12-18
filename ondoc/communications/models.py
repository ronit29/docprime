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
from ondoc.doctor.models import OpdAppointment, Hospital, OfflineOPDAppointments
from ondoc.coupon.models import Coupon
from ondoc.diagnostic.models import LabAppointment
from ondoc.provider.models import EConsultation, PartnerLabSamplesCollectOrder
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
    ClickLoginToken, GenericLabAdmin
from ondoc.insurance.models import EndorsementRequest, UserInsurance

from ondoc.notification.models import NotificationAction, SmsNotification, EmailNotification, AppNotification, \
    PushNotification, WhtsappNotification, DynamicTemplates, RecipientEmail
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
                                                                            hospital=spoc.content_object,
                                                                            entity_type=GenericAdmin.HOSPITAL),
                                                                          Q(super_user_permission=True) |
                                                                          Q(Q(permission_type=GenericAdmin.APPOINTMENT),
                                                                            Q(doctor__isnull=True) | Q(doctor=appointment.doctor)))
            if admins:
                admins_with_user = admins.filter(user__isnull=False)
                if admins_with_user:
                    for admin in admins_with_user:
                        if int(admin.user.phone_number) == int(spoc.number):
                            user_and_number.append({'user': admin.user, 'phone_number': spoc.number})
                            if spoc.email:
                                user_and_email.append({'user': admin.user, 'email': spoc.email})
                        else:
                            user_and_number.append({'user': None, 'phone_number': spoc.number})
                            if spoc.email:
                                user_and_email.append({'user': None, 'email': spoc.email})
                else:
                    user_and_number.append({'user': None, 'phone_number': spoc.number})
                    if spoc.email:
                        user_and_email.append({'user': None, 'email': spoc.email})
            else:
                user_and_number.append({'user': None, 'phone_number': spoc.number})
                if spoc.email:
                    user_and_email.append({'user': None, 'email': spoc.email})
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
            body = "Appointment with Dr. {} for {}, {} has been cancelled.".format(
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
            body = "Appointment with Lab - {} for {}, {} has been cancelled.".format(
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
    elif notification_type == NotificationAction.CHAT_NOTIFICATION:
        title = context.get('title')
        body = context.get('body')
    elif notification_type == NotificationAction.E_CONSULT_VIDEO_LINK_SHARE:
        title = "Video Link Shared"
        body = "Video Link has been shared. Please proceed with consultation."
    elif notification_type == NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED:
        title = "New Message"
        body = "A new message has been just posted in the econsultation chat."
    elif notification_type == NotificationAction.PARTNER_LAB_REPORT_UPLOADED:
        title = "Test Report(s) Generated!"
        body = "Lab test(s) report for {} is now available.View now!".format(patient_name)
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
    OFFLINE_OPD_NOTIFICATION_TYPE_MAPPING = \
        {
            OfflineOPDAppointments.BOOKED: NotificationAction.OFFLINE_OPD_APPOINTMENT_BOOKED,
            OfflineOPDAppointments.ACCEPTED: NotificationAction.OFFLINE_OPD_APPOINTMENT_ACCEPTED,
            OfflineOPDAppointments.RESCHEDULED_DOCTOR: NotificationAction.OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR,
            OfflineOPDAppointments.NO_SHOW: NotificationAction.OFFLINE_OPD_APPOINTMENT_NO_SHOW,
            OfflineOPDAppointments.CANCELLED: NotificationAction.OFFLINE_OPD_APPOINTMENT_CANCELLED,
            OfflineOPDAppointments.COMPLETED: NotificationAction.OFFLINE_OPD_INVOICE
        }
    E_CONSULTATION_NOTIFICATION_TYPE_MAPPING = \
        {
            EConsultation.BOOKED: NotificationAction.ECONSULTATION_BOOKED,
            EConsultation.ACCEPTED: NotificationAction.ECONSULTATION_ACCEPTED,
            EConsultation.RESCHEDULED_DOCTOR: NotificationAction.ECONSULTATION_RESCHEDULED_DOCTOR,
            EConsultation.RESCHEDULED_PATIENT: NotificationAction.ECONSULTATION_RESCHEDULED_PATIENT,
            EConsultation.CANCELLED: NotificationAction.ECONSULTATION_CANCELLED,
            EConsultation.COMPLETED: NotificationAction.ECONSULTATION_COMPLETED,
            EConsultation.EXPIRED: NotificationAction.ECONSULTATION_EXPIRED
        }
    PARTNER_LAB_NOTIFICATION_TYPE_MAPPING = \
        {
            PartnerLabSamplesCollectOrder.SAMPLE_EXTRACTION_PENDING: NotificationAction.PARTNER_LAB_SAMPLE_EXTRACTION_PENDING,
            PartnerLabSamplesCollectOrder.SAMPLE_SCAN_PENDING: NotificationAction.PARTNER_LAB_SAMPLE_SCAN_PENDING,
            PartnerLabSamplesCollectOrder.SAMPLE_PICKUP_PENDING: NotificationAction.PARTNER_LAB_SAMPLE_PICKUP_PENDING,
            PartnerLabSamplesCollectOrder.SAMPLE_PICKED_UP: NotificationAction.PARTNER_LAB_SAMPLE_PICKED_UP,
            PartnerLabSamplesCollectOrder.PARTIAL_REPORT_GENERATED: NotificationAction.PARTNER_LAB_PARTIAL_REPORT_GENERATED,
            PartnerLabSamplesCollectOrder.REPORT_GENERATED: NotificationAction.PARTNER_LAB_REPORT_GENERATED,
            PartnerLabSamplesCollectOrder.REPORT_VIEWED: NotificationAction.PARTNER_LAB_REPORT_VIEWED
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
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            body_template = "sms/appointment_accepted.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_booked_patient.txt"
        elif notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            body_template = "sms/appointment_accepted_reminder.txt"
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
        elif notification_type == NotificationAction.DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS:
            body_template = "sms/docprime_appointment_reminder.txt"
        elif notification_type == NotificationAction.OPD_DAILY_SCHEDULE:
            body_template = "sms/provider/opd_daily_schedule.txt"

        elif notification_type == NotificationAction.PROVIDER_ENCRYPTION_ENABLED:
            body_template = "sms/provider/provider_encryption_enabled.txt"
        elif notification_type == NotificationAction.PROVIDER_ENCRYPTION_DISABLED:
            body_template = "sms/provider/provider_encryption_disabled.txt"
        elif notification_type == NotificationAction.REQUEST_ENCRYPTION_KEY:
            body_template = "sms/provider/request_encryption_key.txt"

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
        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_APPROVED:
            body_template = "sms/insurance/insurance_endorsment_approved.txt"
        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_PARTIAL_APPROVED:
            body_template = "sms/insurance/insurance_endorsement_partially_approved.txt"
        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_PENDING:
            body_template = "sms/insurance/insurance_endorsment_pending.txt"
        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_REJECTED:
            body_template = "sms/insurance/insurance_endorsment_rejected.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE:
            body_template = "sms/insurance/insurance_cancel_initiate.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCELLATION:
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
        elif notification_type == NotificationAction.COD_TO_PREPAID and user and user.user_type == User.CONSUMER:
            body_template = "sms/cod_to_prepaid_patient.txt"
        elif notification_type == NotificationAction.COD_TO_PREPAID and (not user or user.user_type == User.DOCTOR):
            body_template = "sms/cod_to_prepaid_doctor.txt"
        elif notification_type == NotificationAction.COD_TO_PREPAID_REQUEST:
            body_template = "sms/cod_to_prepaid_request.txt"
        elif notification_type == NotificationAction.IPD_PROCEDURE_COST_ESTIMATE:
            body_template = "sms/ipd/cost_estimate.txt"
        elif notification_type == NotificationAction.SEND_LENSFIT_COUPON:
            body_template = "sms/send_lensfit_coupon.txt"
    #    elif notification_type == NotificationAction.LAB_CONFIRMATION_CHECK_AFTER_APPOINTMENT:
    #        body_template = "sms/lab/lab_confirmation_check.txt"
    #   elif notification_type == NotificationAction.LAB_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT:
    #        body_template = "sms/lab/lab_confirmation_second_check.txt"
    #    elif notification_type == NotificationAction.LAB_FEEDBACK_AFTER_APPOINTMENT:
    #        body_template = "sms/lab/lab_feedback.txt"

        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_ACCEPTED:
            body_template = "sms/offline_opd_appointment/appointment_accepted.txt"
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_CANCELLED:
            body_template = "sms/offline_opd_appointment/appointment_cancelled.txt"
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR:
            body_template = "sms/offline_opd_appointment/appointment_rescheduled_doctor.txt"
        elif notification_type == NotificationAction.OFFLINE_APPOINTMENT_REMINDER_PROVIDER_SMS:
            body_template = "sms/offline_opd_appointment/schedule_appointment_reminder_sms.txt"
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_COMPLETED:
            body_template = "sms/offline_opd_appointment/appointment_completed.txt"
        elif notification_type == NotificationAction.OFFLINE_PATIENT_WELCOME_MESSAGE:
            body_template = "sms/offline_opd_appointment/welcome_message.txt"

        elif notification_type == NotificationAction.E_CONSULT_SHARE:
            body_template = "sms/econsult/link_share.txt"

        return body_template

    def get_template_object(self, user):
        notification_type = self.notification_type
        obj = None
        if notification_type == NotificationAction.COD_TO_PREPAID_REQUEST:
            obj = DynamicTemplates.objects.filter(template_name="COD_to_Prepaid_SMS_to_customer", approved=True).first()
        elif notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            obj = DynamicTemplates.objects.filter(template_name="Confirmation_IPD_OPD", approved=True).first()
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR) and (self.context.get('payment_type') == 2):
            obj = DynamicTemplates.objects.filter(template_name="Booking_Provider_Pay_at_clinic", approved=True).first()
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR) and (self.context.get('payment_type') == 1 or self.context.get('payment_type') == 3):
            obj = DynamicTemplates.objects.filter(template_name="Booking_Provider_SMS_OPD_Insurance_And_Prepaid", approved=True).first()
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
            obj = DynamicTemplates.objects.filter(template_name="provider_sms_lab_bookings_prepaid_OPD_insurance", approved=True).first()
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER and user.recent_opd_appointment.first().payment_type == 2:
            obj = DynamicTemplates.objects.filter(template_name="Booking_customer_pay_at_clinic", approved=True).first()
        elif notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            obj = DynamicTemplates.objects.filter(template_name="Reminder_appointment", approved=True).first()
        elif notification_type == NotificationAction.SEND_LENSFIT_COUPON:
            obj = DynamicTemplates.objects.filter(template_name="Lensfit_sms", approved=True).first()
        elif notification_type == NotificationAction.PLUS_MEMBERSHIP_CONFIRMED:
            obj = DynamicTemplates.objects.filter(template_name="Docprime_vip_welcome_message", approved=True).first()

        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_ACCEPTED:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_OPD_APPOINTMENT_ACCEPTED", approved=True).first()
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_CANCELLED:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_OPD_APPOINTMENT_CANCELLED", approved=True).first()
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR", approved=True).first()
        elif notification_type == NotificationAction.OFFLINE_APPOINTMENT_REMINDER_PROVIDER_SMS:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_APPOINTMENT_REMINDER_PROVIDER_SMS", approved=True).first()
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_COMPLETED:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_OPD_APPOINTMENT_COMPLETED", approved=True).first()
        elif notification_type == NotificationAction.OFFLINE_PATIENT_WELCOME_MESSAGE:
            obj = DynamicTemplates.objects.filter(template_name="OFFLINE_PATIENT_WELCOME_MESSAGE", approved=True).first()

        elif notification_type == NotificationAction.PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY and user and user.user_type == User.DOCTOR:
            obj = DynamicTemplates.objects.filter(template_name="cloud_labs_order_success_provider", approved=True).first()
        elif notification_type == NotificationAction.PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY:
            obj = DynamicTemplates.objects.filter(template_name="cloud_labs_order_success_patient", approved=True).first()
        elif notification_type == NotificationAction.PARTNER_LAB_REPORT_UPLOADED and user and user.user_type == User.DOCTOR:
            obj = DynamicTemplates.objects.filter(template_name="cloud_labs_report_success_provider", approved=True).first()
        elif notification_type == NotificationAction.PARTNER_LAB_REPORT_UPLOADED:
            obj = DynamicTemplates.objects.filter(template_name="cloud_labs_report_success_patient", approved=True).first()
        elif notification_type == NotificationAction.REMINDER_MESSAGE_MEDANTA_AND_ARTEMIS:
            obj = DynamicTemplates.objects.filter(template_name="Reminder_message_Medanta_Artemis", approved=True).first()
        return obj

    def trigger(self, receiver, template, context):
        user = receiver.get('user')
        phone_number = receiver.get('phone_number')
        if not phone_number:
            phone_number = user.phone_number
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
        elif phone_number and user and user.purchased_insurance.order_by('-id').first() and \
                user.purchased_insurance.order_by('-id').first().cancel_customer_type == UserInsurance.OTHER and \
                notification_type in [NotificationAction.INSURANCE_CANCEL_INITIATE,
                                      NotificationAction.INSURANCE_CANCELLATION]:
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

        elif phone_number and not notification_type == NotificationAction.INSURANCE_CANCELLATION_APPROVED:
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
        click_login_token_obj = ClickLoginToken(user=user, token=token, expiration_time=expiration_time, url_key=url_key)
        provider_login_url = settings.PROVIDER_APP_DOMAIN + "/sms/login?key=" + url_key + \
                                        "&url=/sms-redirect/" + appointment_type + "/appointment/" + str(appointment.id)
        context['provider_login_url'] = generate_short_url(provider_login_url)
        return context, click_login_token_obj

    def send(self, receivers):
        dispatch_response, receivers = self.dispatch(receivers)
        if dispatch_response:
            return

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

    def dispatch(self, receivers):
        context = self.context
        instance = context.get("instance")
        if not context:
            return None, receivers

        receivers_left = list()

        click_login_token_objects = list()
        for receiver in receivers:
            if receiver.get('user') and receiver.get('user').user_type == User.DOCTOR \
                    and not instance.__class__ in [PartnerLabSamplesCollectOrder]:
                context, click_login_token_obj = self.save_token_to_context(context, receiver.get('user'))
                click_login_token_objects.append(click_login_token_obj)
            elif context.get('provider_login_url'):
                context.pop('provider_login_url')

            obj = self.get_template_object(receiver.get('user'))
            if not obj:
                receivers_left.append(receiver)
            else:
                # click_login_token_objects = list()
                user = receiver.get('user')
                phone_number = receiver.get('phone_number')
                if not phone_number:
                    phone_number = user.phone_number

                instance = context.get('instance')

                # Hospital and labs which has the flag open to communication, send notificaiton to them only.
                if (instance.__class__.__name__ == LabAppointment.__name__) and (not user or user.user_type == User.DOCTOR):
                    if not instance.lab.open_for_communications():
                        continue

                if (instance.__class__.__name__ == OpdAppointment.__name__) and (not user or user.user_type == User.DOCTOR):
                    if instance.hospital and not instance.hospital.open_for_communications():
                        continue

                obj.send_notification(context, phone_number, self.notification_type, user=user)

        ClickLoginToken.objects.bulk_create(click_login_token_objects) if click_login_token_objects else None

        if not receivers_left:
            return True, receivers_left

        return False, receivers_left


class WHTSAPPNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        context = copy.deepcopy(context)
        context.pop('time_slot_start', None)
        self.context = context

    @staticmethod
    def get_pipe_separated_string_from_list(list):
        pipe_separared_string = list[0] if len(list) == 1 else ''
        if not pipe_separared_string:
            pipe_separared_string = ' | '.join(list)
        return pipe_separared_string

    @staticmethod
    def get_pipe_separated_indexed_string_from_list(list):
        pipe_separated_indexed_string = list[0] if len(list) == 1 else ''
        if not pipe_separated_indexed_string:
            pipe_separated_indexed_string = ' | '.join(
                [(str(index) + '. ' + list_element) for index, list_element in enumerate(list, 1)])
        return pipe_separated_indexed_string

    def get_template_and_data(self, user):
        notification_type = self.notification_type
        body_template = ''
        data = []
        # if notification_type == NotificationAction.APPOINTMENT_ACCEPTED or \
        #         notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:

        if notification_type == NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT:
            body_template = "appointment_completion_prepaid"

            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('hospital_address'))
            data.append(self.context.get('patient_name'))
            sms_obj = SMSNotification(NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT, self.context)
            context, click_login_token_obj = sms_obj.save_token_to_context(self.context, user)
            data.append(context['provider_login_url'])

        elif notification_type == NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_PAY_AT_CLINIC:
            body_template = "appointment_completion_cod"

            data.append(self.context.get('doctor_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('hospital_address'))
            data.append(self.context.get('patient_name'))
            if self.context.get('instance').payment_type == 2:
                data.append(str(self.context.get('cod_amount')))
            else:
                data.append(str(self.context.get('instance').effective_price))
            sms_obj = SMSNotification(NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_PAY_AT_CLINIC, self.context)
            context, click_login_token_obj = sms_obj.save_token_to_context(self.context, user)
            data.append(context['provider_login_url'])

        elif notification_type == NotificationAction.PROVIDER_LAB_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT:
            body_template = "appointment_completion_prepaid"

            data.append(self.context.get('lab_name'))
            data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            data.append(self.context.get('pickup_address'))
            data.append(self.context.get('patient_name'))
            sms_obj = SMSNotification(NotificationAction.PROVIDER_LAB_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT, self.context)
            context, click_login_token_obj = sms_obj.save_token_to_context(self.context, user)
            data.append(context['provider_login_url'])

        elif notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
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
                            format(cod_amount=str(self.context.get('cod_amount'))))
            else:
                data.append(" ")

        # elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
        #     body_template = "opd_appointment_booking_patient"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('instance').hospital.name)
        #     data.append(self.context.get('instance').hospital.get_hos_address())
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_booked_doctor"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('instance').hospital.name)
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').profile.phone_number)
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
        #     body_template = "opd_appointment_rescheduled_patient_initiated_to_patient"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('instance').hospital.name)
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_rescheduled_patient_initiated_to_doctor"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').profile.phone_number)
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user and user.user_type == User.CONSUMER:
        #     body_template = "opd_appointment_rescheduled_patient_initiated_to_patient"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('instance').hospital.name)
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_cancelled_doctor"
        #
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(self.context.get('instance').hospital.name)
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #
        # elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
        #     instance = self.context.get('instance')
        #
        #     if instance.payment_type in [OpdAppointment.COD, OpdAppointment.INSURANCE]:
        #         body_template = "appointment_cancelled_doctor"
        #
        #         data.append(self.context.get('doctor_name'))
        #         data.append(
        #             datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #         data.append(self.context.get('instance').hospital.name)
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('doctor_name'))
        #
        #     else:
        #
        #         body_template = "opd_appointment_cancellation_patient"
        #
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('doctor_name'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('doctor_name'))
        #
        # elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
        #     body_template = "prescription_uploaded"
        #
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('patient_name'))
        #
        # elif notification_type == NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT:
        #     body_template = 'appointment_confirmation_check'
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('opd_appointment_complete_url'))
        #     data.append(self.context.get('reschdule_appointment_bypass_url'))
        #
        # elif notification_type == NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT:
        #     body_template = 'appointment_confirmation_second_check'
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('doctor_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('opd_appointment_complete_url'))
        #     data.append(self.context.get('reschdule_appointment_bypass_url'))

        # elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED or \
        #         notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:

        elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:

            instance = self.context.get('instance')
            if not instance.is_home_pickup:
                body_template = "appointment_accepted"

                data.append(self.context.get('patient_name'))
                data.append(self.context.get('lab_name'))
                data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
                data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
                data.append(self.context.get('instance').otp)
                data.append(self.context.get('instance').id)
                data.append(self.context.get('patient_name'))
                data.append(self.context.get('lab_name'))

                if instance.lab and instance.lab.get_lab_address():
                    data.append(instance.lab.get_lab_address())
                else:
                    data.append("NA")

                data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
            else:
                pass

        # elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
        #     instance = self.context.get('instance')
        #     if not instance.is_home_pickup:
        #         body_template = "appointment_booked_patient"
        #
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         if instance.lab and instance.lab.get_lab_address():
        #             data.append(instance.lab.get_lab_address())
        #         else:
        #             data.append("NA")
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #     else:
        #         pass

        # elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_booked_lab"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').profile.phone_number)
        #     data.append(self.context.get('lab_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))

        # elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user and user.user_type == User.CONSUMER:
        #     body_template = "appointment_rescheduled_patient_initiated_to_patient"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     data.append(self.context.get('instance').id)
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #
        # elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_rescheduled_patient_initiated_to_lab"
        #
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     data.append(self.context.get('instance').id)
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('instance').profile.phone_number)
        #     data.append(self.context.get('lab_name'))
        #
        # elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user and user.user_type == User.CONSUMER:
        #     body_template = "appointment_rescheduled_lab_initiated_to_patient"
        #
        #     data.append(self.context.get('lab_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #
        # elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
        #
        #     instance = self.context.get('instance')
        #
        #     if instance.payment_type in [OpdAppointment.COD, OpdAppointment.INSURANCE]:
        #         body_template = "labappointment_cancellation_patient_v1"
        #
        #         data.append(self.context.get('patient_name'))
        #         data.append(
        #             datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #         data.append(self.context.get('lab_name'))
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         data.append(
        #             datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #
        #     else:
        #         body_template = "labappointment_cancel_without_insurance_patient"
        #
        #         data.append(self.context.get('patient_name'))
        #         data.append(
        #             datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #         data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #         data.append(self.context.get('lab_name'))
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         data.append(
        #             datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y %H:%M'))
        #
        # elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and (not user or user.user_type == User.DOCTOR):
        #     body_template = "appointment_cancelled_lab"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%d-%m-%Y'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('instance').time_slot_start), '%H:%M'))
        #     data.append(self.context.get('instance').id)
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('lab_name'))
        #
        # elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
        #     body_template = "lab_report_uploaded"
        #
        #     data.append(self.context.get('lab_name'))
        #     data.append(self.context.get('patient_name'))
        #
        # elif notification_type == NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT:
        #     body_template = "opd_after_completion"
        #
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('doctor_name'))
        #     data.append(self.context.get('opd_appointment_feedback_url'))
        #
        # elif notification_type == NotificationAction.REFUND_BREAKUP:
        #     body_template = "appointment_refund_breakup"
        #
        #     data.append(self.context.get('amount'))
        #     if self.context.get('booking_id'):
        #         data.append('for you booking id %d' % self.context.get('instance').id)
        #     else:
        #         data.append('.')
        #
        #     if self.context.get('ctrnx_id'):
        #         data.append('The transaction ID for this refund is : DPRF%s' % str(self.context.get('ctrnx_id')))
        #     else:
        #         data.append(' ')
        #
        # elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
        #     instance = self.context.get('instance')
        #     if instance.is_thyrocare:
        #         body_template = "labappointment_thyrocare_report_v1"
        #
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         lab_reports = []
        #         for report in self.context.get('reports', []):
        #             temp_short_url = generate_short_url(report)
        #             lab_reports.append(temp_short_url)
        #         data.append(", ".join(lab_reports))
        #         data.append(self.context.get('chat_url'))
        #
        #     else:
        #         body_template = "labappointment_report_v1"
        #
        #         data.append(self.context.get('instance').id)
        #         data.append(self.context.get('patient_name'))
        #         data.append(self.context.get('lab_name'))
        #         lab_reports = []
        #         for report in self.context.get('reports', []):
        #             temp_short_url = generate_short_url(report)
        #             lab_reports.append(temp_short_url)
        #         data.append(", ".join(lab_reports))

        # elif notification_type == NotificationAction.IPD_PROCEDURE_COST_ESTIMATE:
        #     pass
            # body_template = "cost_estimate"
            #
            # data.append(self.context.get('instance'))

        # elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
        #     body_template = "sms/lab/lab_report_send_crm.txt"
        #     lab_reports = []
        #     for report in self.context.get('reports', []):
        #         temp_short_url = generate_short_url(report)
        #         lab_reports.append(temp_short_url)
        #     self.context['lab_reports'] = lab_reports

        # elif notification_type == NotificationAction.PARTNER_LAB_REPORT_UPLOADED and user and user.user_type == User.DOCTOR:
        #
        #     instance = self.context.get('instance')
        #     body_template = "cloudlabs_report_generated_partner"
        #     data.append(self.context.get('order_id'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('order_date_time')), '%b %d, %Y, %-I:%M %P'))
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('patient_age'))
        #     lab_tests_ordered_string = self.get_pipe_separated_string_from_list(self.context.get('lab_tests_ordered'))
        #     data.append(lab_tests_ordered_string)
        #     report_list_string = self.get_pipe_separated_indexed_string_from_list(self.context.get('report_list'))
        #     data.append(report_list_string)
        #
        # elif notification_type == NotificationAction.PARTNER_LAB_REPORT_UPLOADED:
        #
        #     instance = self.context.get('instance')
        #     body_template = "cloudlabs_report_generated_v2"
        #     data.append(self.context.get('hospital_name'))
        #     data.append(self.context.get('patient_name'))
        #     data.append(self.context.get('patient_age'))
        #     data.append(self.context.get('order_id'))
        #     data.append(datetime.strftime(aware_time_zone(self.context.get('order_date_time')), '%b %d, %Y, %-I:%M %P'))
        #     lab_tests_ordered_string = self.get_pipe_separated_string_from_list(self.context.get('lab_tests_ordered'))
        #     data.append(lab_tests_ordered_string)
        #     report_list_string = self.get_pipe_separated_indexed_string_from_list(self.context.get('report_list'))
        #     data.append(report_list_string)

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
                logger.info('[ERROR] Could not send Whtsapp message to user as suitable template not found for the '
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

    def get_template_object(self, user):
        notification_type = self.notification_type
        obj = None
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED or notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            obj = DynamicTemplates.objects.filter(template_type=DynamicTemplates.TemplateType.EMAIL, template_name="").first()
        if notification_type == NotificationAction.SEND_LENSFIT_COUPON:
            obj = DynamicTemplates.objects.filter(template_type=DynamicTemplates.TemplateType.EMAIL, template_name="Lensfit_email", approved=True).first()
        if notification_type == NotificationAction.IPDIntimateEmailNotification:
            obj = DynamicTemplates.objects.filter(template_type=DynamicTemplates.TemplateType.EMAIL, template_name="EMail_to_provider_for_ipd_hospitals_for_request_query", approved=True).first()
        if notification_type in (NotificationAction.LAB_APPOINTMENT_ACCEPTED, NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB, NotificationAction.LAB_APPOINTMENT_BOOKED,
                                NotificationAction.LAB_APPOINTMENT_CANCELLED, NotificationAction.LAB_INVOICE):
            obj = DynamicTemplates.objects.filter(template_type=DynamicTemplates.TemplateType.EMAIL, template_name="Email_to_lab_on_appointment_booked",
                                                  approved=True).first()
        return obj

    def get_template(self, user):
        notification_type = self.notification_type
        context = self.context
        body_template = ''
        subject_template = ''
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:

            if context.get("instance").is_credit_letter_required_for_appointment() and not context.get("instance").is_payment_type_cod():
                credit_letter = context.get("instance").get_valid_credit_letter()
                if not credit_letter:
                    logger.error("Got error while getting pdf for opd credit letter")
                    return '', ''
                context.update({"credit_letter": credit_letter})
                context.update({"credit_letter_url": credit_letter.file.url})
                context.update(
                    {"attachments": [
                        {"filename": util_file_name(credit_letter.file.url),
                         "path": util_absolute_url(credit_letter.file.url)}]})

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
        elif notification_type == NotificationAction.PROVIDER_MATRIX_LEAD_EMAIL:
            body_template = "email/provider/matrix_lead_creation/body.html"
            subject_template = "email/provider/matrix_lead_creation/subject.txt"
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

        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_APPROVED:

            coi = context.get("instance").coi
            if not coi:
                logger.error("Got error while creating pdf after endorsment for opd invoice")
                return '', ''
            context.update({"coi": coi})
            context.update({"coi_url": coi.url})
            context.update(
                {"attachments": [
                    {"filename": util_file_name(coi.url),
                     "path": util_absolute_url(coi.url)}]})

            body_template = "email/insurance_endorsment_approved/body.html"
            subject_template = "email/insurance_endorsment_approved/subject.txt"

        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_PENDING:
            body_template = "email/insurance_endorsment_pending/body.html"
            subject_template = "email/insurance_endorsment_pending/subject.txt"

        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_REJECTED:
            body_template = "email/insurance_endorsment_rejected/body.html"
            subject_template = "email/insurance_endorsment_rejected/subject.txt"

        elif notification_type == NotificationAction.INSURANCE_ENDORSMENT_PARTIAL_APPROVED:
            body_template = "email/insurance_endorsement_partially_approved/body.html"
            subject_template = "email/insurance_endorsement_partially_approved/subject.txt"

        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            attachments = []
            for report_link in context.get('reports', []):
                attachments.append({"filename": util_file_name(report_link), "path": util_absolute_url(report_link)})
            context.update({'attachments': attachments})
            body_template = "email/lab/lab_report_send_crm/body.html"
            subject_template = "email/lab/lab_report_send_crm/subject.txt"
        elif notification_type == NotificationAction.IPD_PROCEDURE_MAIL:
            body_template = "email/ipd/ipd_lead/new_lead/body.html"
            subject_template = "email/ipd/ipd_lead/new_lead/subject.txt"
        elif notification_type == NotificationAction.IPD_PROCEDURE_COST_ESTIMATE:
            body_template = "email/ipd/ipd_lead/cost_estimate/body.html"
            subject_template = "email/ipd/ipd_lead/cost_estimate/subject.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE:
            body_template = "email/insurance_cancel_initiate/body.html"
            subject_template = "email/insurance_cancel_initiate/subject.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCELLATION_APPROVED:
            body_template = "email/insurance_cancellation_approved/body.html"
            subject_template = "email/insurance_cancellation_approved/subject.txt"
        elif notification_type == NotificationAction.INSURANCE_CANCELLATION:
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
        elif notification_type == NotificationAction.COD_TO_PREPAID:
            body_template = "email/cod_to_prepaid_patient/body.html"
            subject_template = "email/cod_to_prepaid_patient/subject.txt"
        elif notification_type == NotificationAction.COD_TO_PREPAID and user and user.user_type == User.CONSUMER:
            body_template = "email/cod_to_prepaid_patient/body.html"
            subject_template = "email/cod_to_prepaid_patient/subject.txt"
        elif notification_type == NotificationAction.COD_TO_PREPAID and (not user or user.user_type == User.DOCTOR):
            body_template = "email/cod_to_prepaid_/body.html"
            subject_template = "email/cod_to_prepaid_patient/subject.txt"
        #elif notification_type == NotificationAction.SEND_LENSFIT_COUPON and user and user.user_type == User.CONSUMER:
        #    body_template = "email/lensfit_coupon/body.html"
        #    subject_template = "email/lensfit_coupon/subject.txt"
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

        elif (email or send_without_email) and user and user.purchased_insurance.order_by('-id').first() and \
                        user.purchased_insurance.order_by('-id').first().cancel_customer_type == UserInsurance.OTHER and \
                        (notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE or \
                        notification_type == NotificationAction.INSURANCE_CANCELLATION_APPROVED or \
                        notification_type == NotificationAction.INSURANCE_CANCELLATION or \
                        notification_type == NotificationAction.INSURANCE_ENDORSMENT_PENDING):
            if notification_type == NotificationAction.INSURANCE_CANCEL_INITIATE or \
                notification_type == NotificationAction.INSURANCE_ENDORSMENT_PENDING:
                bcc = settings.INSURANCE_OPS_EMAIL
            elif notification_type == NotificationAction.INSURANCE_CANCELLATION_APPROVED:
                email = settings.INSURANCE_CANCELLATION_APPROVAL_ALERT_TO_EMAIL
                cc = settings.INSURANCE_CANCELLATION_APPROVAL_ALERT_CC_EMAIL
                # email = 'ankushg@docprime.com'
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

    def send(self, receivers, *args, **kwargs):
        dispatch_response, receivers = self.dispatch(receivers, *args, **kwargs)
        if dispatch_response:
            return

        context = self.context
        if not context:
            return
        for receiver in receivers:
            template = self.get_template(receiver.get('user'))
            if template:
                self.trigger(receiver, template, context)

    def dispatch(self, receivers, *args, **kwargs):
        context = self.context
        if not context:
            return None, receivers

        receivers_left = list()

        for receiver in receivers:
            obj = self.get_template_object(receiver.get('user'))
            if not obj:
                receivers_left.append(receiver)
            else:
                email = receiver.get('email')
                context = copy.deepcopy(context)
                instance = context.get('instance', None)
                receiver_user = receiver.get('user')

                send_without_email = False
                if (instance.__class__.__name__ == LabAppointment.__name__) and (
                        not receiver_user or receiver_user.user_type == User.DOCTOR):
                    if not instance.lab.open_for_communications():
                        email = None
                        send_without_email = True

                if (instance.__class__.__name__ == OpdAppointment.__name__) and (
                        not receiver_user or receiver_user.user_type == User.DOCTOR):
                    if instance.hospital and not instance.hospital.open_for_communications():
                        email = None
                        send_without_email = True

                if email or send_without_email:
                    recipient_obj = RecipientEmail(email)
                    obj.send_notification(context, recipient_obj, self.notification_type, user=receiver_user, *args, **kwargs)

        if not receivers_left:
            return True, receivers_left

        return False, receivers_left


class APPNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = copy.deepcopy(context)

    def trigger(self, receiver, context):
        user = receiver
        context = copy.deepcopy(context)
        context.pop("instance", None)
        context.pop('time_slot_start', None)
        context.pop('hospitals_not_required_unique_code', None)
        context.pop('procedures', None)
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
        context.pop('order_date_time', None)
        context.pop('hospitals_not_required_unique_code', None)
        context.pop('procedures', None)
        if user:
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

    def __init__(self, appointment, notification_type=None, extra={}):
        self.appointment = appointment
        self.extra = extra
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.OPD_NOTIFICATION_TYPE_MAPPING.get(appointment.status)

    def get_context(self):
        patient_name = self.appointment.profile.name if self.appointment.profile.name else ""
        doctor_name = self.appointment.doctor.name if self.appointment.doctor.name else ""
        appointment_id = self.appointment.id
        hospital_name = self.appointment.hospital.name
        hospital_address = self.appointment.hospital.get_hos_address()
        payment_type = self.appointment.payment_type
        cod_amount = 'Not Applicable'
        if payment_type == 2:
            cod_amount = self.appointment.get_cod_amount()

        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = self.appointment.time_slot_start.astimezone(est)
        procedures = self.appointment.get_procedures()
        mask_number_instance = self.appointment.mask_number.filter(is_deleted=False).first()
        mask_number = ''
        coupon_discount = self.appointment.discount
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
        opd_appointment_cod_to_prepaid_url, cod_to_prepaid_discount = self.appointment.get_cod_to_prepaid_url_and_discount(
            token_object['token'].decode("utf-8"))
        opd_appointment_complete_url = booking_url + "&callbackurl=opd/appointment/{}?complete=true".format(
            self.appointment.id)
        appointment_type = 'opd'
        url_key = get_random_string(length=ClickLoginToken.URL_KEY_LENGTH)
        provider_login_url = settings.PROVIDER_APP_DOMAIN + "/sms/login?key=" + url_key + \
                             "&url=/sms-redirect/" + appointment_type + "/appointment/" + str(appointment_id)
        opd_appointment_feedback_url = booking_url + "&callbackurl=opd/appointment/{}".format(self.appointment.id)
        reschdule_appointment_bypass_url = booking_url + "&callbackurl=opd/doctor/{}/{}/book?reschedule={}".format(
            self.appointment.doctor.id, self.appointment.hospital.id, self.appointment.id)
        # hospitals_not_required_unique_code = set(json.loads(settings.HOSPITALS_NOT_REQUIRED_UNIQUE_CODE))
        credit_letter_url = self.appointment.get_credit_letter_url()
        lensfit_coupon = self.extra.get('lensfit_coupon')
        context = {
            "doctor_name": doctor_name,
            "hospital_address": hospital_address,
            "hospital_name": hospital_name,
            "patient_name": patient_name,
            "id": appointment_id,
            "instance": self.appointment,
            "clinic_or_hospital": clinic_or_hospital,
            "procedures": procedures,
            "coupon_discount": str(coupon_discount) if coupon_discount else None,
            "url": "/opd/appointment/{}".format(appointment_id),
            "action_type": NotificationAction.OPD_APPOINTMENT,
            "action_id": appointment_id,
            "payment_type": payment_type,
            "image_url": "",
            "time_slot_start": time_slot_start,
            "attachments": {},  # Updated later
            "screen": NotificationAction.APPOINTMENT,
            "type": "doctor",
            "cod_amount": cod_amount,
            "mask_number": mask_number,
            "email_banners": email_banners_html if email_banners_html is not None else "",
            "opd_appointment_complete_url": generate_short_url(opd_appointment_complete_url),
            "opd_appointment_feedback_url": generate_short_url(opd_appointment_feedback_url),
            "reschdule_appointment_bypass_url": generate_short_url(reschdule_appointment_bypass_url),
            "show_amounts": bool(payment_type != OpdAppointment.INSURANCE),
            "opd_appointment_cod_to_prepaid_url": generate_short_url(
                opd_appointment_cod_to_prepaid_url) if opd_appointment_cod_to_prepaid_url else None,
            "cod_to_prepaid_discount": cod_to_prepaid_discount,
            "hospitals_not_required_unique_code": not self.appointment.is_credit_letter_required_for_appointment(),
            "credit_letter_url": generate_short_url(credit_letter_url) if credit_letter_url else None,
            "instance_id": self.appointment.id,
            "time_slot_start_date": str(time_slot_start.strftime("%b %d %Y")),
            "time_slot_start_time": str(time_slot_start.strftime("%I:%M %p")),
            "is_payment_type_cod": self.appointment.is_payment_type_cod(),
            "instance_otp": self.appointment.otp,
            "is_credit_letter_required_for_appointment": self.appointment.is_credit_letter_required_for_appointment(),
            "is_otp_required": self.appointment.is_otp_required_wrt_hospitals(),
            "lensfit_coupon": lensfit_coupon,
	    "provider_login_url": generate_short_url(provider_login_url)
        }
        return context

    def send(self, is_valid_for_provider=True):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers(is_valid_for_provider)
        if notification_type == NotificationAction.DOCTOR_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
        elif notification_type in [NotificationAction.REFUND_BREAKUP,
                                   NotificationAction.REFUND_COMPLETED] and context.get('instance').payment_type == 3:
            # As no notification to be sent in case of insurance.
            pass

        elif notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT or \
                notification_type == NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT or \
                notification_type == NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT or \
                notification_type == NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT or \
                notification_type == NotificationAction.COD_TO_PREPAID_REQUEST:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))

            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS or notification_type == NotificationAction.REMINDER_MESSAGE_MEDANTA_AND_ARTEMIS:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.COD_TO_PREPAID or \
                notification_type == NotificationAction.SEND_LENSFIT_COUPON:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            # whtsapp_notification = WHTSAPPNotification(notification_type, context) # TODO : SHASHANK_SINGH dont know how!!
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            # whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type in (NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_PAY_AT_CLINIC,
                                   NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT):
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))

    def get_receivers(self, is_valid_for_provider):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        doctor_spocs_app_recievers = []
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers

        doctor_spocs = instance.hospital.get_spocs_for_communication() if instance.hospital else []
        spocs_to_be_communicated = []
        if notification_type in [NotificationAction.DOCTOR_INVOICE]:
            if instance.payment_type not in [2, 3]:
                receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
                                 NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
                                 NotificationAction.PRESCRIPTION_UPLOADED,
                                 NotificationAction.OPD_OTP_BEFORE_APPOINTMENT,
                                 NotificationAction.OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.OPD_FEEDBACK_AFTER_APPOINTMENT,
                                 NotificationAction.COD_TO_PREPAID,
                                 NotificationAction.COD_TO_PREPAID_REQUEST,
                                 NotificationAction.SEND_LENSFIT_COUPON,
                                 NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_PAY_AT_CLINIC,
                                 NotificationAction.PROVIDER_OPD_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT,
                                 NotificationAction.REMINDER_MESSAGE_MEDANTA_AND_ARTEMIS
                                 ]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.APPOINTMENT_BOOKED,
                                   NotificationAction.APPOINTMENT_CANCELLED,
                                   NotificationAction.COD_TO_PREPAID]:
            spocs_to_be_communicated = doctor_spocs
            if not is_valid_for_provider:
                spocs_to_be_communicated = []
            doctor_spocs_app_recievers = GenericAdmin.get_appointment_admins(instance)
            # receivers.extend(doctor_spocs)
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS]:
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

    def __init__(self, appointment, notification_type=None, extra={}):
        self.appointment = appointment
        self.extra = extra
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.LAB_NOTIFICATION_TYPE_MAPPING.get(appointment.status)

    def get_context(self):
        instance = self.appointment
        patient_name = instance.profile.name.title() if instance.profile.name else ""
        patient_age = instance.profile.get_age()
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
        lensfit_coupon = self.extra.get('lensfit_coupon')

        for test in tests:
            test['mrp'] = str(test['mrp'])
            test['deal_price'] = str(test['deal_price'])
            test['discount'] = str(test['discount'])
        mask_number_instance = self.appointment.mask_number.filter(is_deleted=False).first()
        mask_number = ''
        if mask_number_instance:
            mask_number = mask_number_instance.mask_number

        is_thyrocare_report = False
        chat_url = ""
        if instance and instance.lab and instance.lab.network and instance.lab.network.id == settings.THYROCARE_NETWORK_ID:
            is_thyrocare_report = True
            chat_url = "https://docprime.com/mobileviewchat?utm_source=Thyrocare&booking_id=%s" % instance.id
            # # chat_url = '%s/mobileviewchat?utm_source=Thyrocare&booking_id=%s&msg=startchat' % (settings.API_BASE_URL, instance.id)
            # # chat_url = '%s/livechat?product=DocPrime&cb=1&source=Thyrocare&booking_id=%s&msg=startchat' % (settings.CHAT_API_URL, instance.id)
            # chat_url = '%s/livechat?product=DocPrime&cb=1&source=Thyrocare&booking_id=%s&msg=startchat' % (settings.CHAT_API_URL, instance.id)
            chat_url = generate_short_url(chat_url)

        context = {
            "lab_name": lab_name,
            "patient_name": patient_name,
            "age": patient_age,
            "id": instance.id,
            "instance": instance,
            "url": "/lab/appointment/{}".format(instance.id),
            "action_type": NotificationAction.LAB_APPOINTMENT,
            "action_id": instance.id,
            "image_url": "",
            "pickup_address": self.appointment.get_pickup_address(),
            "coupon_discount": str(self.appointment.discount) if self.appointment.discount else None,
            "time_slot_start": time_slot_start,
            "time_slot_start_date": str(time_slot_start.strftime("%b %d %Y")),
            "time_slot_start_time": str(time_slot_start.strftime("%I:%M %p")),
            "tests": tests,
            "reports": report_file_links,
            "attachments": {},  # Updated later
            "screen": NotificationAction.APPOINTMENT,
            "type": "lab",
            "mask_number": mask_number,
            "email_banners": email_banners_html if email_banners_html is not None else "",
            "lab_appointment_complete_url": generate_short_url(lab_appointment_complete_url),
            "lab_appointment_feedback_url": generate_short_url(lab_appointment_feedback_url),
            "reschedule_appointment_bypass_url": generate_short_url(reschedule_appointment_bypass_url),
            "is_thyrocare_report": is_thyrocare_report,
            "chat_url": chat_url,
            "show_amounts": bool(self.appointment.payment_type != OpdAppointment.INSURANCE),
            "lensfit_coupon": lensfit_coupon,
            "visit_type": 'home' if instance.is_home_pickup else 'lab'
        }
        return context

    def send(self, is_valid_for_provider=True):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers(is_valid_for_provider)

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
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.SEND_LENSFIT_COUPON:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.PROVIDER_LAB_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT:
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))

    def get_receivers(self, is_valid_for_provider):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        lab_admins_app_recievers = list()
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers
        # lab_spocs = instance.get_lab_admins()
        lab_managers = instance.lab.get_managers_for_communication() if instance.lab else []
        lab_managers_to_be_communicated = []
        if notification_type in [NotificationAction.LAB_INVOICE]:
            if instance.payment_type not in [2, 3]:
                receivers.append(instance.user)
        elif notification_type in [NotificationAction.LAB_APPOINTMENT_ACCEPTED,
                                 NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
                                 NotificationAction.LAB_REPORT_UPLOADED,
                                 NotificationAction.LAB_OTP_BEFORE_APPOINTMENT,
                                 NotificationAction.LAB_CONFIRMATION_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_FEEDBACK_AFTER_APPOINTMENT,
                                 NotificationAction.LAB_REPORT_SEND_VIA_CRM,
                                 NotificationAction.SEND_LENSFIT_COUPON,
                                 NotificationAction.PROVIDER_LAB_APPOINTMENT_CONFIRMATION_ONLINE_PAYMENT
                                 ]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.LAB_APPOINTMENT_BOOKED,
                                   NotificationAction.LAB_APPOINTMENT_CANCELLED]:
            lab_managers_to_be_communicated = lab_managers
            if not is_valid_for_provider:
                lab_managers_to_be_communicated = []

            lab_admins_app_recievers = GenericLabAdmin.get_appointment_admins(instance)
            # receivers.extend(lab_spocs)
            receivers.append(instance.user)
        receivers = list(set(receivers))
        user_and_phone_number = []
        user_and_email = []
        app_receivers = push_receivers = receivers + lab_admins_app_recievers
        user_and_tokens = []

        user_and_token = [{'user': token.user, 'token': token.token, 'app_name': token.app_name} for token in
                          NotificationEndpoint.objects.filter(user__in=push_receivers).order_by('user')]
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
            'coi_short_url': generate_short_url(instance.coi.url),
            'insurer_name': instance.insurance_plan.insurer.name,
            'user_bank' : instance.user_bank.last()
        }

        if self.notification_type == NotificationAction.INSURANCE_ENDORSMENT_APPROVED:
            # endorsement_list = list()
            # rejected = 0
            # endorsed_members = instance.endorse_members.filter(~Q(status=EndorsementRequest.PENDING))
            # for mem in endorsed_members:
            #     if mem.status == 3:
            #         rejected = rejected + 1
            #
            #     mem_data = {
            #         'name': mem.member.get_full_name().title(),
            #         'relation': mem.member.relation,
            #         'status': EndorsementRequest.STATUS_CHOICES[mem.status-1][1]
            #     }
            #     endorsement_list.append(mem_data)
            #
            # context['endorsement_list'] = endorsement_list
            # context['few_rejected'] = True if rejected > 0 else False
            approved_endorsed_members = instance.endorse_members.filter((Q(mail_status=EndorsementRequest.MAIL_PENDING) |
                                                                         Q(mail_status__isnull=True)),
                                                                         status=EndorsementRequest.APPROVED)
            approved_endorsed_members_context = self.get_endorsed_context(approved_endorsed_members)
            # context = context.update(approved_endorsed_members_context)
            context['approved_members'] = approved_endorsed_members_context['members']

        if self.notification_type == NotificationAction.INSURANCE_ENDORSMENT_PENDING:
            pending_endorsed_members = instance.endorse_members.filter(status=EndorsementRequest.PENDING)
            pending_endorsed_members_context = self.get_endorsed_context(pending_endorsed_members)
            context['pending_members'] = pending_endorsed_members_context['members']

        if self.notification_type == NotificationAction.INSURANCE_ENDORSMENT_PARTIAL_APPROVED:
            partially_approved_endorsed_members = instance.endorse_members.filter(~Q(status=EndorsementRequest.PENDING),
                                                                                  (Q(mail_status=EndorsementRequest.MAIL_PENDING) |
                                                                                   Q(mail_status__isnull=True)))
            partial_approved_context = self.get_endorsed_context(partially_approved_endorsed_members)
            context['partially_members'] = partial_approved_context['members']
        return context

    def get_endorsed_context(self, members):
        member_list = list()
        scope = ['first_name', 'middle_name', 'last_name', 'dob', 'title', 'email', 'address', 'pincode', 'gender',
                 'relation', 'town', 'district', 'state']
        context = {}
        for end_member in members:
            for s in scope:
                if end_member.status == EndorsementRequest.REJECT or end_member.status == EndorsementRequest.PENDING:
                    if not getattr(end_member, s) == getattr(end_member.member, s):
                        pending_member_data = {
                            'name': end_member.member.get_full_name().title(),
                            'field_name': self.get_field_name(s),
                            'previous_name': getattr(end_member.member, s),
                            'modified_name': getattr(end_member, s),
                            'status': EndorsementRequest.STATUS_CHOICES[end_member.status-1][1]
                        }
                        member_list.append(pending_member_data)
                elif end_member.status == EndorsementRequest.APPROVED:
                    old_member_obj = end_member.member.member_history.order_by('-id').first()
                    if not old_member_obj:
                        return context
                    if not getattr(end_member, s) == getattr(old_member_obj, s):
                        pending_member_data = {
                            'name': end_member.member.get_full_name().title(),
                            'field_name': self.get_field_name(s),
                            'previous_name': getattr(old_member_obj, s),
                            'modified_name': getattr(end_member, s),
                            'status': EndorsementRequest.STATUS_CHOICES[end_member.status-1][1]
                        }
                        member_list.append(pending_member_data)

        context['members'] = member_list
        return context

    def get_field_name(self, val):
        res = val
        if "_" in val:
            res = val.replace("_", " ")
        return res

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

        if notification_type in [NotificationAction.INSURANCE_CONFIRMED, NotificationAction.INSURANCE_CANCEL_INITIATE,
                                 NotificationAction.INSURANCE_CANCELLATION_APPROVED,
                                 NotificationAction.INSURANCE_CANCELLATION,
                                 NotificationAction.INSURANCE_ENDORSMENT_APPROVED,
                                 NotificationAction.INSURANCE_ENDORSMENT_PENDING,
                                 NotificationAction.INSURANCE_ENDORSMENT_REJECTED,
                                 NotificationAction.INSURANCE_ENDORSMENT_PARTIAL_APPROVED]:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))

            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))


class ProviderAppNotification(Notification):

    def __init__(self, hospital, action_user, notification_type=None):
        self.hospital = hospital
        self.notification_type = notification_type
        self.action_user = action_user

    def get_context(self):
        context = {
            "id": self.hospital.id,
            "instance": self.hospital,
            "hospital_name": self.hospital.name,
            "encrypted_by": self.hospital.encrypt_details.encrypted_by if hasattr(self.hospital, 'encrypt_details') else None,
            "action_user": self.action_user,
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.PROVIDER_ENCRYPTION_ENABLED:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('encryption_status_sms_receivers', []))
        elif notification_type == NotificationAction.PROVIDER_ENCRYPTION_DISABLED:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('encryption_status_sms_receivers', []))
        elif notification_type == NotificationAction.REQUEST_ENCRYPTION_KEY:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('encryption_key_request_sms_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.hospital
        admins_phone_number = GenericAdmin.objects.filter(is_disabled=False, hospital=instance, entity_type=GenericAdmin.HOSPITAL)\
                                                  .values_list('phone_number', flat=True)\
                                                  .distinct()
        user_and_phone_number = list()
        encryption_key_request_sms_receivers = list()
        for number in admins_phone_number:
            if number:
                user_and_phone_number.append({'user': None, 'phone_number': number})
        if hasattr(self.hospital, 'encrypt_details') and self.hospital.encrypt_details.is_valid:
            encryption_key_request_sms_receivers.append({"user": None, "phone_number": self.hospital.encrypt_details.encrypted_by.phone_number})
        all_receivers['encryption_status_sms_receivers'] = user_and_phone_number
        all_receivers['encryption_key_request_sms_receivers'] = encryption_key_request_sms_receivers
        return all_receivers


class IpdLeadNotification(Notification):
    def __init__(self, ipd_procedure_lead, notification_type=None):
        self.ipd_procedure_lead = ipd_procedure_lead
        if notification_type:
            self.notification_type = notification_type

    def get_context(self):
        context = {
            "instance": self.ipd_procedure_lead
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        email_notification = EMAILNotification(notification_type, context)
        sms_notification = SMSNotification(notification_type, context)
        whtsapp_notification = WHTSAPPNotification(notification_type, context)
        email_notification.send(all_receivers.get('email_receivers', []))
        sms_notification.send(all_receivers.get('sms_receivers', []))
        # whtsapp_notification.send(all_receivers.get('sms_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.ipd_procedure_lead
        phone_numbers = []
        emails = []
        notification_type = self.notification_type
        if not instance:
            return []

        if notification_type in [NotificationAction.IPD_PROCEDURE_COST_ESTIMATE]:
            phone_numbers.append({'phone_number': instance.phone_number}) if instance.phone_number else None;
            emails.append({'email': instance.email}) if instance.email else None;

        emails = unique_emails(emails)
        phone_numbers = unique_phone_numbers(phone_numbers)
        all_receivers['sms_receivers'] = phone_numbers
        all_receivers['email_receivers'] = emails

        return all_receivers


class OfflineOpdAppointments(Notification):

    def __init__(self, appointment, notification_type=None, **kwargs):
        self.appointment = appointment
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.OFFLINE_OPD_NOTIFICATION_TYPE_MAPPING[appointment.status]
        if kwargs.get('receivers'):
            self.receivers = kwargs.get('receivers')

    def get_context(self):
        patient_name = self.appointment.user.name.title()
        doctor_name = self.appointment.doctor.name
        doctor_display_name = self.appointment.doctor.get_display_name()

        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = self.appointment.time_slot_start.astimezone(est)

        clinic_or_hospital = "Clinic"
        if self.appointment.hospital.assoc_doctors.filter(enabled=True).count() > 10:
            clinic_or_hospital = "Hospital"
        context = {
            "doctor_name": doctor_name,
            "doctor_display_name": doctor_display_name,
            "hospital_address": self.appointment.hospital.get_hos_address(),
            "hospital_name": self.appointment.hospital.name,
            "patient_name": patient_name,
            "id": self.appointment.id,
            "instance": self.appointment,
            "clinic_or_hospital": clinic_or_hospital,
            "action_type": NotificationAction.OFFLINE_OPD_APPOINTMENT,
            "action_id": self.appointment.id,
            "opd_time_slot_start": time_slot_start,
            "welcome_message": self.appointment.user.welcome_message,
            "admin_phone_no": self.appointment.booked_by.phone_number,
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.receivers if hasattr(self, 'receivers') else self.get_receivers()
        if notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_ACCEPTED:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_CANCELLED:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_NO_SHOW:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.OFFLINE_OPD_APPOINTMENT_COMPLETED:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.OFFLINE_PATIENT_WELCOME_MESSAGE:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))

    def get_receivers(self):
        all_receivers = list()
        return all_receivers


class EConsultationComm(Notification):

    def __init__(self, e_consultation, notification_type=None, **kwargs):
        self.e_consultation = e_consultation
        patient, patient_number = self.e_consultation.get_patient_and_number()
        self.patient = patient
        self.patient_number = patient_number
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = self.E_CONSULTATION_NOTIFICATION_TYPE_MAPPING[e_consultation.status]
        if kwargs.get('receivers'):
            self.receivers = kwargs.get('receivers')
        if kwargs.get('comm_types'):
            self.comm_types = kwargs.get('comm_types')

    def get_context(self):
        patient_name = self.patient.name.title()
        doctor_name = self.e_consultation.doctor.name
        doctor_display_name = self.e_consultation.doctor.get_display_name()

        # est = pytz.timezone(settings.TIME_ZONE)
        # time_slot_start = self.e_consultation.time_slot_start.astimezone(est)

        context = {
            "doctor_name": doctor_name,
            "doctor_display_name": doctor_display_name,
            "patient_name": patient_name,
            "id": self.e_consultation.id,
            "instance": self.e_consultation,
            "action_type": NotificationAction.E_CONSULTATION,
            "action_id": self.e_consultation.id,
            "link": self.e_consultation.link,
            "screen": NotificationAction.E_CONSULT_CHAT_VIEW,
            "is_open_screen": True,
            "screen_params": {
                "id": self.e_consultation.id
            }
        }
        return context

    def get_receivers(self):
        receivers = self.receivers if hasattr(self, 'receivers') else None
        all_receivers = dict()
        sms_receivers = list()
        email_receivers = list()
        push_receivers = list()
        if self.notification_type in (NotificationAction.E_CONSULT_VIDEO_LINK_SHARE, ):
            push_receivers.append(self.patient.user)
        if self.notification_type in (NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED, ) and receivers:
            push_receivers.extend(receivers)
            sms_receivers = [{"user": receiver, "phone_number": receiver.phone_number} for receiver in receivers]
            email_receivers = [{"user": receiver, "email": receiver.email} for receiver in receivers if receiver.email]
        user_and_tokens = NotificationEndpoint.get_user_and_tokens(receivers=push_receivers, action_type=NotificationAction.E_CONSULTATION)
        all_receivers['sms_receivers'] = sms_receivers
        all_receivers['email_receivers'] = email_receivers
        all_receivers['push_receivers'] = user_and_tokens
        return all_receivers

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()
        comm_types = self.comm_types if hasattr(self, 'comm_types') else None
        if notification_type == NotificationAction.E_CONSULT_SHARE:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        elif notification_type == NotificationAction.E_CONSULT_VIDEO_LINK_SHARE:
            push_notification = PUSHNotification(notification_type, context)
            push_notification.send(all_receivers.get('push_receivers', []))
        elif notification_type == NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED:
            push_notification = PUSHNotification(notification_type, context)
            push_notification.send(all_receivers.get('push_receivers', []))
            if comm_types and NotificationAction.SMS_NOTIFICATION in comm_types:
                sms_notification = SMSNotification(notification_type, context)
                sms_notification.send(all_receivers.get('sms_receivers', []))
            if comm_types and NotificationAction.EMAIL_NOTIFICATION in comm_types:
                email_notification = EMAILNotification(notification_type, context)
                email_notification.send(all_receivers.get('email_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            whtsapp_notification = WHTSAPPNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            whtsapp_notification.send(all_receivers.get('sms_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))


class VipNotification(Notification):

    def __init__(self, plus_user_obj, notification_type=None):
        self.plus_user_obj= plus_user_obj
        self.notification_type = notification_type

    def get_context(self):
        instance = self.plus_user_obj

        context = {
            'expiry_date': str(aware_time_zone(instance.expire_date).date().strftime('%d %b %Y')),
        }

        return context

    def get_receivers(self):

        all_receivers = {}
        instance = self.plus_user_obj
        if not instance:
            return {}

        user_and_phone_number = []
        user_and_email = []

        proposer = instance.get_primary_member_profile()

        user_and_email.append({'user': instance.user, 'email': proposer.email})
        user_and_phone_number.append({'user': instance.user, 'phone_number': proposer.phone_number})

        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email

        return all_receivers

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type in [NotificationAction.PLUS_MEMBERSHIP_CONFIRMED]:

            # email_notification = EMAILNotification(notification_type, context)
            # email_notification.send(all_receivers.get('email_receivers', []))

            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))


class PartnerLabNotification(Notification):

    def __init__(self, partner_lab_order_obj, notification_type=None, report_list=list()):
        self.partner_lab_order_obj = partner_lab_order_obj
        self.notification_type = notification_type if notification_type else self.PARTNER_LAB_NOTIFICATION_TYPE_MAPPING[partner_lab_order_obj.status]
        self.patient_mobile = str(partner_lab_order_obj.offline_patient.get_patient_mobile())
        self.report_list = report_list

    def get_context(self):
        instance = self.partner_lab_order_obj
        lab_tests_ordered = list()
        mrp = 0
        for obj in instance.selected_tests_details:
            lab_tests_ordered.append(obj['lab_test_name'])
            mrp += obj['b2c_rate']
        context = {
            "instance": instance,
            "order_id": instance.id,
            "patient_name": instance.offline_patient.name,
            "hospital_name": instance.hospital.name,
            "patient_age": instance.offline_patient.get_age(),
            "mrp": mrp if mrp else None,
            "order_date_time": instance.created_at,
            "lab_tests_ordered": lab_tests_ordered,
            "admin_contact_no": instance.created_by.phone_number,
            "support_email": "cloudlabs@docprime.com",
            "report_list": self.report_list,
            "action_type": NotificationAction.PARTNER_LAB,
            "action_id": instance.id,
            "screen": NotificationAction.PARTNER_LAB_ORDER_DETAILS,
            "is_open_screen": True,
            "screen_params": {
                "order_id": instance.id
            }
        }
        return context

    def get_receivers(self):
        notification_type = self.notification_type
        push_receivers = list()
        all_receivers = {}
        instance = self.partner_lab_order_obj
        if not instance:
            return {}

        user_and_phone_number = []
        user_and_email = []
        if notification_type in [NotificationAction.PARTNER_LAB_REPORT_UPLOADED]:
            if instance.created_by:
                push_receivers.append(instance.created_by)
                user_and_phone_number.append({'user': instance.created_by, 'phone_number': instance.created_by.phone_number})
            if self.patient_mobile:
                user_and_phone_number.append({'user': instance.offline_patient.user, 'phone_number': self.patient_mobile})
        if notification_type in [NotificationAction.PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY]:
            if instance.created_by:
                user_and_phone_number.append({'user': instance.created_by, 'phone_number': instance.created_by.phone_number})
            if self.patient_mobile:
                user_and_phone_number.append({'user': instance.offline_patient.user, 'phone_number': self.patient_mobile})
        user_and_tokens = NotificationEndpoint.get_user_and_tokens(receivers=push_receivers,
                                                                   action_type=NotificationAction.PARTNER_LAB)
        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['push_receivers'] = user_and_tokens

        return all_receivers

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type in [NotificationAction.PARTNER_LAB_REPORT_UPLOADED]:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
            push_notification = PUSHNotification(notification_type, context)
            push_notification.send(all_receivers.get('push_receivers', []))
            whatsapp_notification = WHTSAPPNotification(notification_type, context)
            whatsapp_notification.send(all_receivers.get('sms_receivers', []))
        if notification_type in [NotificationAction.PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY]:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
