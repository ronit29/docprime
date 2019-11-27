import json
import re

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import FileExtensionValidator
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.forms.models import model_to_dict
from ondoc.authentication.models import TimeStampedModel
from ondoc.authentication.models import NotificationEndpoint
from ondoc.authentication.models import UserProfile
from ondoc.account import models as account_model
from ondoc.api.v1.utils import readable_status_choices, generate_short_url
# from ondoc.doctor.models import Hospital, Doctor
from ondoc.notification.rabbitmq_client import publish_message
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
from django.conf import settings
from num2words import num2words
from itertools import groupby
import datetime
from datetime import timedelta
import pytz
import logging
import string
import random
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from django.core.files import File
from django.contrib.postgres.fields import ArrayField
from ondoc.common.helper import Choices
from django.utils.safestring import mark_safe
from collections import OrderedDict
from django.template import Context, Template
import copy
import random, string

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationAction:
    SMS_NOTIFICATION = 1001
    EMAIL_NOTIFICATION = 1002
    PUSH_NOTIFICATION = 1003

    NOTIFICATION_CHOICES = ((SMS_NOTIFICATION, "SMS Notification"), (EMAIL_NOTIFICATION, "Email Notification"),
                            (PUSH_NOTIFICATION, "Push Notification"))

    APPOINTMENT_ACCEPTED = 1
    APPOINTMENT_CANCELLED = 2
    APPOINTMENT_RESCHEDULED_BY_PATIENT = 3
    APPOINTMENT_RESCHEDULED_BY_DOCTOR = 4
    APPOINTMENT_BOOKED = 5

    LAB_APPOINTMENT_ACCEPTED = 20
    LAB_APPOINTMENT_CANCELLED = 21
    LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT = 22
    LAB_APPOINTMENT_RESCHEDULED_BY_LAB = 23
    LAB_APPOINTMENT_BOOKED = 24
    LAB_REPORT_UPLOADED = 25
    LAB_REPORT_SEND_VIA_CRM = 26

    PRESCRIPTION_UPLOADED = 6
    PAYMENT_PENDING = 7
    RECEIPT = 8

    DOCTOR_INVOICE = 10
    LAB_INVOICE = 11

    INSURANCE_CONFIRMED=15
    INSURANCE_ENDORSMENT_APPROVED=82
    INSURANCE_ENDORSMENT_REJECTED=83
    INSURANCE_ENDORSMENT_PENDING=84
    INSURANCE_ENDORSMENT_PARTIAL_APPROVED=85
    INSURANCE_CANCELLATION_APPROVED=86
    INSURANCE_CANCEL_INITIATE = 73
    INSURANCE_CANCELLATION=74
    INSURANCE_FLOAT_LIMIT=75
    INSURANCE_MIS=76
    OPD_OTP_BEFORE_APPOINTMENT = 30
    LAB_OTP_BEFORE_APPOINTMENT = 31
    OPD_CONFIRMATION_CHECK_AFTER_APPOINTMENT = 32
    OPD_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT = 33
    OPD_FEEDBACK_AFTER_APPOINTMENT = 34

    REFUND_BREAKUP = 40
    REFUND_COMPLETED = 42

    CASHBACK_CREDITED = 55

    IPD_PROCEDURE_MAIL = 60
    IPD_PROCEDURE_COST_ESTIMATE = 61

    LAB_LOGO_CHANGE_MAIL = 70
    PRICING_ALERT_EMAIL = 72

    DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS = 69
    PROVIDER_ENCRYPTION_ENABLED = 78
    PROVIDER_ENCRYPTION_DISABLED = 79
    LOGIN_OTP = 80
    REQUEST_ENCRYPTION_KEY = 81
    CHAT_NOTIFICATION = 87
    PROVIDER_MATRIX_LEAD_EMAIL = 88

    COD_TO_PREPAID = 91
    COD_TO_PREPAID_REQUEST = 92

    OPD_DAILY_SCHEDULE = 98
    USERPROFILE_EMAIL_UPDATE = 99
    LAB_CONFIRMATION_CHECK_AFTER_APPOINTMENT = 93
    LAB_CONFIRMATION_SECOND_CHECK_AFTER_APPOINTMENT = 94
    LAB_FEEDBACK_AFTER_APPOINTMENT = 95

    CONTACT_US_EMAIL = 65

    OFFLINE_OPD_APPOINTMENT_BOOKED = 130
    OFFLINE_OPD_APPOINTMENT_ACCEPTED = 131
    OFFLINE_OPD_APPOINTMENT_CANCELLED = 132
    OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR = 133
    OFFLINE_OPD_APPOINTMENT_NO_SHOW = 134
    OFFLINE_OPD_INVOICE = 135
    OFFLINE_OPD_APPOINTMENT_COMPLETED = 136
    OFFLINE_APPOINTMENT_REMINDER_PROVIDER_SMS = 137
    OFFLINE_PATIENT_WELCOME_MESSAGE = 138

    ECONSULTATION_BOOKED = 150
    ECONSULTATION_ACCEPTED = 151
    ECONSULTATION_RESCHEDULED_DOCTOR = 152
    ECONSULTATION_RESCHEDULED_PATIENT = 153
    ECONSULTATION_CANCELLED = 154
    ECONSULTATION_COMPLETED = 155
    ECONSULTATION_EXPIRED = 156
    E_CONSULT_SHARE = 157
    E_CONSULT_VIDEO_LINK_SHARE = 158
    E_CONSULT_NEW_MESSAGE_RECEIVED = 159

    SAMPLE_DYNAMIC_TEMPLATE_PREVIEW = 110
    SEND_LENSFIT_COUPON = 111

    PLUS_MEMBERSHIP_CONFIRMED = 180

    PARTNER_LAB_SAMPLE_EXTRACTION_PENDING = 200
    PARTNER_LAB_SAMPLE_SCAN_PENDING = 201
    PARTNER_LAB_SAMPLE_PICKUP_PENDING = 202
    PARTNER_LAB_SAMPLE_PICKED_UP = 203
    PARTNER_LAB_PARTIAL_REPORT_GENERATED = 204
    PARTNER_LAB_REPORT_GENERATED = 205
    PARTNER_LAB_REPORT_VIEWED = 206
    PARTNER_LAB_REQUEST_RECHECK = 207
    PARTNER_LAB_NEED_HELP = 208
    PARTNER_LAB_REPORT_UPLOADED = 209
    PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY = 210

    IPDIntimateEmailNotification = 301

    NOTIFICATION_TYPE_CHOICES = (
        (APPOINTMENT_ACCEPTED, "Appointment Accepted"),
        (APPOINTMENT_CANCELLED, "Appointment Cancelled"),
        (APPOINTMENT_RESCHEDULED_BY_PATIENT, "Appointment Rescheduled by Patient"),
        (APPOINTMENT_RESCHEDULED_BY_DOCTOR, "Appointment Rescheduled by Doctor"),
        (APPOINTMENT_BOOKED, "Appointment Booked"),


        (LAB_APPOINTMENT_ACCEPTED, "Lab Appointment Accepted"),
        (LAB_APPOINTMENT_CANCELLED, "Lab Appointment Cancelled"),
        (LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT, "Lab Appointment Rescheduled by Patient"),
        (LAB_APPOINTMENT_RESCHEDULED_BY_LAB, "Lab Appointment Rescheduled by Lab"),
        (LAB_APPOINTMENT_BOOKED, "Lab Appointment Booked"),
        (LAB_REPORT_UPLOADED, "Lab Report Uploaded"),
        (LAB_REPORT_SEND_VIA_CRM, "Send Lab Reports via CRM"),

        (OFFLINE_OPD_APPOINTMENT_BOOKED, "Offline OPD Appointment Booked"),
        (OFFLINE_OPD_APPOINTMENT_ACCEPTED, "Offline OPD Appointment Accepted"),
        (OFFLINE_OPD_APPOINTMENT_CANCELLED, "Offline OPD Appointment Cancelled"),
        (OFFLINE_OPD_APPOINTMENT_RESCHEDULED_DOCTOR, "Offline OPD Appointment Rescheduled by Doctor"),
        (OFFLINE_OPD_APPOINTMENT_NO_SHOW, "Offline OPD Appointment No Show"),
        (OFFLINE_OPD_APPOINTMENT_COMPLETED, "Offline OPD Appointment Completed"),
        (DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS, 'Docprime Appointment Reminder Provider SMS'),
        (OFFLINE_APPOINTMENT_REMINDER_PROVIDER_SMS, 'Offline Appointment Reminder Provider SMS'),

        (ECONSULTATION_BOOKED, 'EConsultation Booked'),
        (ECONSULTATION_ACCEPTED, 'EConsultation Accepted'),
        (ECONSULTATION_RESCHEDULED_DOCTOR, 'EConsultation Rescheduled Doctor'),
        (ECONSULTATION_RESCHEDULED_PATIENT, 'EConsultation Rescheduled Patient'),
        (ECONSULTATION_CANCELLED, 'EConsultation Cancelled'),
        (ECONSULTATION_COMPLETED, 'EConsultation Completed'),
        (ECONSULTATION_EXPIRED, 'EConsultation Expired'),
        (E_CONSULT_SHARE, 'E Consult Share'),
        (E_CONSULT_VIDEO_LINK_SHARE, 'E Consult Video Link Share'),
        (E_CONSULT_NEW_MESSAGE_RECEIVED, 'E Consult New Message Received'),

        (PRESCRIPTION_UPLOADED, "Prescription Uploaded"),
        (PAYMENT_PENDING, "Payment Pending"),
        (RECEIPT, "Receipt"),
        (DOCTOR_INVOICE, "Doctor Invoice"),
        (LAB_INVOICE, "Lab Invoice"),
        (OFFLINE_OPD_INVOICE, "Offline OPD Invoice"),

        (INSURANCE_CONFIRMED, "Insurance Confirmed"),
        (INSURANCE_ENDORSMENT_APPROVED, "Insurance endorsment completed."),
        (INSURANCE_ENDORSMENT_REJECTED, "Insurance endorsment rejected."),
        (INSURANCE_ENDORSMENT_PENDING, "Insurance endorsment received."),
        (CASHBACK_CREDITED, "Cashback Credited"),
        (REFUND_BREAKUP, 'Refund break up'),
        (REFUND_COMPLETED, 'Refund Completed'),
        (IPD_PROCEDURE_MAIL, 'IPD Procedure Mail'),
        (PRICING_ALERT_EMAIL, 'Pricing Change Mail'),
        (LAB_LOGO_CHANGE_MAIL, 'Lab Logo Change Mail'),
        (PROVIDER_MATRIX_LEAD_EMAIL, 'Provider Matrix Lead Email'),
        (DOCPRIME_APPOINTMENT_REMINDER_PROVIDER_SMS, 'Docprime Appointment Reminder Provider SMS'),
        (PROVIDER_ENCRYPTION_ENABLED, 'Provider Encryption Enabled'),
        (PROVIDER_ENCRYPTION_DISABLED, 'Provider Decryption Disabled'),
        (REQUEST_ENCRYPTION_KEY, 'Request Encryption Key'),
        (LOGIN_OTP, 'Login OTP'),
        (CHAT_NOTIFICATION, "Push Notification from chat"),
        (COD_TO_PREPAID, 'COD to Prepaid'),
        (COD_TO_PREPAID_REQUEST, 'COD To Prepaid Request'),
        (OPD_DAILY_SCHEDULE, 'OPD Daily Schedule'),

        (PARTNER_LAB_SAMPLE_EXTRACTION_PENDING, 'Partner Lab Sample Extraction Pending'),
        (PARTNER_LAB_SAMPLE_SCAN_PENDING, 'Partner Lab Sample Scan Pending'),
        (PARTNER_LAB_SAMPLE_PICKUP_PENDING, 'Partner Lab Sample Pickup Pending'),
        (PARTNER_LAB_SAMPLE_PICKED_UP, 'Partner Lab Sample Picked Up'),
        (PARTNER_LAB_PARTIAL_REPORT_GENERATED, 'Partner Lab Partial Report Generated'),
        (PARTNER_LAB_REPORT_GENERATED, 'Partner Lab Report Generated'),
        (PARTNER_LAB_REPORT_VIEWED, 'Partner Lab Report Viewed'),
        (PARTNER_LAB_REQUEST_RECHECK, 'Partner Lab Request Recheck'),
        (PARTNER_LAB_NEED_HELP, 'Partner Lab Need Help'),
        (PARTNER_LAB_REPORT_UPLOADED, 'Partner Lab Report Uploaded'),
        (PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY, 'Partner Lab Order Placed Successfully'),

        (IPDIntimateEmailNotification, 'IPD Intimate Email Notification Send Successfully'),
    )
    OPD_APPOINTMENT = "opd_appointment"
    LAB_APPOINTMENT = "lab_appoingment"
    OFFLINE_OPD_APPOINTMENT = "offline_opd_appointment"
    E_CONSULTATION = "e_consultation"
    PARTNER_LAB = "partner_lab"

    ACTION_TYPE_CHOICES = (
        (OPD_APPOINTMENT, 'Opd Appointment'),
        (LAB_APPOINTMENT, 'Lab Appointment'),
        (OFFLINE_OPD_APPOINTMENT, 'Offline Opd Appointment'),
        (E_CONSULTATION, 'E Consultation'),
        (PARTNER_LAB, 'partner_lab'),
    )

    APPOINTMENT = "appointment"
    E_CONSULT_CHAT_VIEW = "EConsultChatView"
    PARTNER_LAB_ORDER_DETAILS = "TestOrderDetails"          #PartnerLabOrderDetails
    SCREEN_TYPE_CHOICES = (
        (APPOINTMENT, 'appointment'),
        (E_CONSULT_CHAT_VIEW, 'e_consult_chat_view'),
        (PARTNER_LAB_ORDER_DETAILS, 'partner_lab_order_details'),
    )

    @classmethod
    def trigger(cls, instance, user, notification_type):
        from ondoc.doctor.models import OpdAppointment
        est = pytz.timezone(settings.TIME_ZONE)
        if notification_type != cls.INSURANCE_CONFIRMED:
            time_slot_start = instance.time_slot_start.astimezone(est)
        context = {}
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            procedures = instance.get_procedures()
            context = {
                "doctor_name": doctor_name,
                "patient_name": patient_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Confirmed",
                "body": "Appointment Confirmed for {} requested with Dr. {} at {}, {}.".format(
                    patient_name, doctor_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"), doctor_name
                ),
                "procedures": procedures,
                "coupon_discount": str(instance.discount) if instance.discount else None,
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Reschedule",
                "body": "Reschedule request received for the appointment with Dr. {}".format(doctor_name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Reschedule",
                "body": "Reschedule request received for the appointment with Dr. {}".format(doctor_name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Reschedule",
                "body": "Reschedule request received for the appointment from Dr. {}".format(doctor_name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            procedures = instance.get_procedures()
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "New Appointment",
                "body": "New Appointment for {} at {}, {} with Dr. {}. You will receive a confirmation as soon as it is accepted by the doctor.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"), doctor_name),
                "procedures": procedures,
                "coupon_discount": str(instance.discount) if instance.discount else None,
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.DOCTOR:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            procedures = instance.get_procedures()
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "New Appointment",
                "body": "New appointment for {} at {}, {}. Please confirm.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")),
                "procedures": procedures,
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.DOCTOR:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": "Appointment with {} at {}  {} has been cancelled.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            if instance.cancellation_type != instance.AUTO_CANCELLED:
                body = "Appointment with Dr. {} at {}, {} has been cancelled.".format(
                    doctor_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")
                )
            else:
                body = "Appointment with Dr. {} at {}, {} has been cancelled due to unavailability of doctor manager.".format(
                    doctor_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"))
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": body,
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.DOCTOR_INVOICE:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            procedures = instance.get_procedures()
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Invoice Generated",
                "procedures": procedures,
                "body": "Invoice for appointment ID-{} has been generated.".format(instance.id),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "payment_type": dict(OpdAppointment.PAY_CHOICES)[instance.payment_type],
                "image_url": ""
            }
            if user.user_type == User.CONSUMER:
                email = instance.profile.email

                # send notification to default profile also
                default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
                if default_user_profile and (
                        default_user_profile.id != instance.profile.id) and default_user_profile.email:
                    EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                        email=default_user_profile.email, context=context)
            else:
                email = user.email
            EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                email=email, context=context)

        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Prescription Uploaded",
                "body": "Prescription available for your appointment with Dr. {} on {}".format(
                    doctor_name, time_slot_start.strftime("%d/%m/%y")),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.INSURANCE_CONFIRMED:
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
                    'relation': member.relation,
                    'id': member.id,
                    'gender': member.gender.title(),
                    'age': int((datetime.datetime.now().date() - member.dob).days/365),
                }
                member_list.append(data)
                count = count + 1

            context = {
                'purchase_data': str(instance.purchase_date.date().strftime('%d-%m-%Y')),
                'expiry_date': str(instance.expiry_date.date().strftime('%d-%m-%Y')),
                'premium': instance.premium_amount,
                'proposer_name': proposer_name.title(),
                'current_date': datetime.datetime.now().date().strftime('%d-%m-%Y'),
                'policy_number': instance.policy_number,
                'total_member_covered': len(member_list),
                'plan': instance.insurance_plan.name,
                'insured_members': member_list,
                'insurer_logo': instance.insurance_plan.insurer.logo.url,
                'coi_url': instance.coi.url,
                'insurer_name': instance.insurance_plan.insurer.name
            }
            EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                context=context, email=proposer.email)


    @classmethod
    def trigger_all(cls, user, notification_type, context=None):
        if not context.get('instance'):
            return
        instance = context.get('instance')
        if user.user_type == User.CONSUMER:
            email = instance.profile.email
            phone_number = instance.profile.phone_number

            # send notification to default profile also
            default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
            if default_user_profile and (default_user_profile.id != instance.profile.id) and default_user_profile.email:
                EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                    email=default_user_profile.email, context=context)
            if default_user_profile and (default_user_profile.id != instance.profile.id) and default_user_profile.phone_number:
                SmsNotification.send_notification(user=user, phone_number=default_user_profile.phone_number,
                                                  notification_type=notification_type, context=context)
        else:
            email = user.email
            phone_number = user.phone_number
        if email:
            EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                email=email, context=context)
        if phone_number:
            SmsNotification.send_notification(user=user, phone_number=phone_number,
                                              notification_type=notification_type, context=context)
        AppNotification.send_notification(user=user, notification_type=notification_type,
                                          context=context)
        PushNotification.send_notification(user=user, notification_type=notification_type,
                                           context=context)
    @classmethod
    def trigger_push_and_inapp(cls, user, notification_type, context=None):
        AppNotification.send_notification(user=user, notification_type=notification_type,
                                          context=context)
        PushNotification.send_notification(user=user, notification_type=notification_type,
                                           context=context)


class EmailNotificationOpdMixin:

    @classmethod
    def get_email_template(cls, user, email, notification_type, context):
        html_body = ''
        email_subject = ''
        context = copy.deepcopy(context)
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            html_body = render_to_string("email/appointment_accepted/body.html", context=context)
            email_subject = render_to_string("email/appointment_accepted/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_booked_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_booked_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            html_body = render_to_string("email/appointment_booked_doctor/body.html", context=context)
            email_subject = render_to_string("email/appointment_booked_doctor/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_rescheduled_patient_initiated_to_patient/body.html",
                                         context=context)
            email_subject = render_to_string("email/appointment_rescheduled_patient_initiated_to_patient/subject.txt",
                                             context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            html_body = render_to_string("email/appointment_rescheduled_patient_initiated_to_doctor/body.html",
                                         context=context)
            email_subject = render_to_string("email/appointment_rescheduled_patient_initiated_to_doctor/subject.txt",
                                             context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_rescheduled_doctor_initiated_to_patient/body.html",
                                         context=context)
            email_subject = render_to_string("email/appointment_rescheduled_doctor_initiated_to_patient/subject.txt",
                                             context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            html_body = render_to_string("email/appointment_cancelled_doctor/body.html", context=context)
            email_subject = render_to_string("email/appointment_cancelled_doctor/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_cancelled_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_cancelled_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            html_body = render_to_string("email/prescription_uploaded/body.html", context=context)
            email_subject = render_to_string("email/prescription_uploaded/subject.txt", context=context)

        elif notification_type == NotificationAction.DOCTOR_INVOICE:
            invoice, created = account_model.Invoice.objects.get_or_create(reference_id=context.get("instance").id,
                                                                           product_id=account_model.Order.DOCTOR_PRODUCT_ID)
            context.update({"invoice": invoice})
            html_body = render_to_string("email/doctor_invoice/invoice_template.html", context=context)
            filename = "invoice_{}.pdf".format(str(timezone.now().timestamp()))
            try:
                pdf_file = HTML(string=html_body).write_pdf()
                invoice.file = SimpleUploadedFile(filename, pdf_file, content_type='application/pdf')
                invoice.save()
            except Exception as e:
                logger.error("Got error while creating pdf for opd invoice {}".format(e))
            context.update({"invoice_url": invoice.file.url})
            html_body = render_to_string("email/doctor_invoice/body.html", context=context)
            email_subject = render_to_string("email/doctor_invoice/subject.txt", context=context)

        elif notification_type == NotificationAction.INSURANCE_CONFIRMED:
            # html_body = render_to_string("email/insurance_confirmed/pdfbody.html", context=context)
            # instance = context.get('instance')
            # filename = "COI_{}.pdf".format(str(timezone.now().timestamp()))
            # try:
            #     from django.core.files.uploadedfile import TemporaryUploadedFile
            #     extra_args = {
            #         'virtual-time-budget': 6000
            #     }
            #     file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
            #     f = open(file.temporary_file_path())
            #     bytestring_to_pdf(html_body.encode(), f, **extra_args)
            #     f.seek(0)
            #     f.flush()
            #     f.content_type = 'application/pdf'
            #
            #     instance.coi = InMemoryUploadedFile(file, None, filename, 'application/pdf', file.tell(), None)
            #     instance.save()
            # except Exception as e:
            #     logger.error("Got error while creating pdf for opd invoice {}".format(e))
            html_body = render_to_string("email/insurance_confirmed/body.html", context=context)
            email_subject = render_to_string("email/insurance_confirmed/subject.txt", context=context)

        return html_body, email_subject


class EmailNotificationLabMixin:

    @classmethod
    def get_email_template(cls, user, email, notification_type, context):
        html_body = ''
        email_subject = ''
        context = copy.deepcopy(context)
        if notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
            html_body = render_to_string("email/lab/appointment_accepted/body.html", context=context)
            email_subject = render_to_string("email/lab/appointment_accepted/subject.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/lab/appointment_booked_patient/body.html", context=context)
            email_subject = render_to_string("email/lab/appointment_booked_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/lab/appointment_rescheduled_patient_initiated_to_patient/body.html",
                                         context=context)
            email_subject = render_to_string("email/lab/appointment_rescheduled_patient_initiated_to_patient/subject.txt",
                                             context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/lab/appointment_rescheduled_lab_initiated_to_patient/body.html",
                                         context=context)
            email_subject = render_to_string("email/lab/appointment_rescheduled_lab_initiated_to_patient/subject.txt",
                                             context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/lab/appointment_cancelled_patient/body.html", context=context)
            email_subject = render_to_string("email/lab/appointment_cancelled_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            html_body = render_to_string("email/lab/lab_report_uploaded/body.html", context=context)
            email_subject = render_to_string("email/lab/lab_report_uploaded/subject.txt", context=context)
        elif notification_type == NotificationAction.LAB_INVOICE:
            invoice, created = account_model.Invoice.objects.get_or_create(reference_id=context.get("instance").id,
                                                                           product_id=account_model.Order.LAB_PRODUCT_ID)
            context.update({"invoice": invoice})
            html_body = render_to_string("email/lab_invoice/invoice_template.html", context=context)
            filename = "invoice_{}.pdf".format(str(timezone.now().timestamp()))
            try:
                pdf_file = HTML(string=html_body).write_pdf()
                invoice.file = SimpleUploadedFile(filename, pdf_file, content_type='application/pdf')
                invoice.save()
            except Exception as e:
                logger.error("Got error while creating pdf for lab invoice {}".format(e))
            context.update({"invoice_url": invoice.file.url})
            html_body = render_to_string("email/lab_invoice/body.html", context=context)
            email_subject = render_to_string("email/lab_invoice/subject.txt", context=context)
        return html_body, email_subject


class EmailNotification(TimeStampedModel, EmailNotificationOpdMixin, EmailNotificationLabMixin):
    OPS_APPOINTMENT_NOTIFICATION = 1
    OPS_PAYMENT_NOTIFICATION = 2
    FOLLOWUP_APPOINTMENT = 3

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    email_subject = models.TextField(blank=True, null=True)
    email = models.EmailField(null=True)
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)
    cc = ArrayField(models.EmailField(), default=[], blank=[])
    bcc = ArrayField(models.EmailField(), default=[], blank=[])
    attachments = JSONField(default=[], blank=[])
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    # object_id = models.PositiveIntegerField(null=True)
    object_id = models.BigIntegerField(null=True)
    content_object = GenericForeignKey()

    class Meta:
        db_table = "email_notification"

    def __str__(self):
        return '{} -> {} ({})'.format(self.email_subject, self.email, self.user)

    @classmethod
    def send_notification(cls, user, email, notification_type, context):
        html_body, email_subject = EmailNotification.get_email_template(user, email, notification_type, context)
        if not html_body:
            html_body, email_subject = super(EmailNotificationOpdMixin, cls).get_email_template(user, email, notification_type, context)
        if email and user:
            email_noti = EmailNotification.objects.create(
                user=user,
                email=email,
                notification_type=notification_type,
                content=html_body,
                email_subject=email_subject
            )
            message = {
                "data": model_to_dict(email_noti),
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_to_manager(cls, email, notification_type, context):
        html_body = ''
        email_subject = ''
        context = copy.deepcopy(context)
        if notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED:
            html_body = render_to_string("email/lab/appointment_booked_lab/body.html", context=context)
            email_subject = render_to_string("email/lab/appointment_booked_lab/subject.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT:
            html_body = render_to_string("email/lab/appointment_rescheduled_patient_initiated_to_lab/body.html",
                                         context=context)
            email_subject = render_to_string(
                "email/lab/appointment_rescheduled_patient_initiated_to_lab/subject.txt",
                context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED:
            html_body = render_to_string("email/lab/appointment_cancelled_lab/body.html", context=context)
            email_subject = render_to_string("email/lab/appointment_cancelled_lab/subject.txt", context=context)
        if email:
            email_noti = EmailNotification.objects.create(
                email=email,
                notification_type=notification_type,
                content=html_body,
                email_subject=email_subject
            )
            message = {
                "data": model_to_dict(email_noti),
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def ops_notification_alert(cls, data_obj, email_list, product, alert_type):
        status_choices = readable_status_choices(product)

        html_body = None
        email_subject = None
        if alert_type == cls.OPS_APPOINTMENT_NOTIFICATION:
            if product == account_model.Order.DOCTOR_PRODUCT_ID:
                url = settings.ADMIN_BASE_URL + "/admin/doctor/opdappointment/" + str(data_obj.id) + "/change"
            elif product == account_model.Order.LAB_PRODUCT_ID:
                url = settings.ADMIN_BASE_URL + "/admin/diagnostic/labappointment/" + str(data_obj.id) + "/change"
            html_body = "status - {status}, user - {username}, url - {url}".format(
                status=status_choices[data_obj.status], username=data_obj.profile.name, url=url
            )
            email_subject = "Change in appointment of user - {username} and id - {id}".format(
                username=data_obj.profile.name, id=data_obj.id
            )
        elif alert_type == cls.OPS_PAYMENT_NOTIFICATION:
            email_subject = "Order created for user name - {user_name} and id - {user_id}".format(
                user_name=data_obj.get("profile_name"),
                user_id=data_obj.get("user_id")
            )
            if product == account_model.Order.DOCTOR_PRODUCT_ID:
                html_body = "Order created for user name - {user_name}, " \
                            "user id - {user_id} and phone number - {user_number} " \
                            "while booking appointment for doctor name -{doctor_name} , " \
                            "hospital name - {hospital_name} and appointment time - {time_of_appointment} " \
                            "with order id - {order_id} on transaction time - {transaction_time}".format(
                    user_name=data_obj.get("profile_name"), user_id=data_obj.get("user_id"),
                    user_number=data_obj.get("user_number"), doctor_name=data_obj.get("doctor_name"),
                    hospital_name=data_obj.get("hospital_name"), time_of_appointment=data_obj.get("time_of_appointment"),
                    order_id=data_obj.get("order_id"), transaction_time=data_obj.get("transaction_time"))
            elif product == account_model.Order.LAB_PRODUCT_ID:
                html_body = "Order created for user name - {user_name}, " \
                            "user id - {user_id} and phone number - {user_number} " \
                            "while booking appointment for lab name - {lab_name} , " \
                            "test names - ({test_names}) and appointment time - {time_of_appointment} " \
                            "with order id - {order_id} on transaction time - {transaction_time}".format(
                    user_name=data_obj.get("profile_name"), user_id=data_obj.get("user_id"),
                    user_number=data_obj.get("user_number"), lab_name=data_obj.get("lab_name"),
                    test_names=data_obj.get("test_names"), time_of_appointment=data_obj.get("time_of_appointment"),
                    order_id=data_obj.get("order_id"), transaction_time=data_obj.get("transaction_time"))
        elif alert_type == cls.FOLLOWUP_APPOINTMENT:
            url = settings.ADMIN_BASE_URL + "/admin/doctor/opdappointment/" + str(data_obj.id) + "/change"
            html_body = "Doctor Followup Appointment received for id   - {id}, You can change the appointment type with" \
                        "given url {url}".format(id=data_obj.id, url=url)
            email_subject = "Followup Appointment Received - {id}".format(id=data_obj.id)
        if email_list:
            for e_id in email_list:
                cls.publish_ops_email(e_id, html_body, email_subject)

    @classmethod
    def publish_ops_email(cls, email_list, html_body, email_subject):
        if email_list:
            email_notif = {
                "email": email_list,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_notif,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_token(cls, token, order_id, email):
        html_body = "".format()
        email_subject = "".format()
        if email:
            email_notif = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_notif,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_app_download_link(cls, email, context):
        email_body = render_to_string('email/doctor_onboarding/body.html', context=context)
        email_subject = render_to_string('email/doctor_onboarding/subject.txt', context=context)
        if email:
            email_notif = {
                "email": email,
                "content": email_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_notif,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_booking_url(cls, token, email):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        short_url = generate_short_url(booking_url)
        html_body = "Your booking url is - {} . Please pay to confirm".format(short_url)
        email_subject = "Booking Url"
        if email:
            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_insurance_booking_url(cls, token, email):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        booking_url = booking_url + "&callbackurl=insurance/insurance-user-details-review"
        short_url = generate_short_url(booking_url)
        html_body = "Your Insurance purchase url is - {} . Please pay to confirm".format(short_url)
        email_subject = "Insurance Purchase Url"
        if email:
            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_vip_booking_url(cls, token, email):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        booking_url = booking_url + "&callbackurl=vip-club-member-details"
        short_url = generate_short_url(booking_url)
        html_body = "Your VIP membership purchase url is - {} . Please pay to confirm".format(short_url)
        email_subject = "VIP Purchase Url"
        if email:
            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_endorsement_request_url(cls, token, email):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        booking_url = booking_url + "&callbackurl=insurance/insurance-user-details-review?is_endorsement=true"
        short_url = generate_short_url(booking_url)
        html_body = "Your Endorsement Request url is - {} . Please confirm to process".format(short_url)
        email_subject = "Insurance Endorsement Request"
        if email:
            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_insurance_float_alert_email(cls, email, html_body):
        email_subject = 'ALERT!!! Insurance Float amount is on the limit.'
        if email:
            email_obj = cls.objects.create(email=email, notification_type=NotificationAction.INSURANCE_FLOAT_LIMIT,
                                                          content=html_body,email_subject=email_subject, cc=[], bcc=[])
            email_obj.save()

            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_insurance_mis(cls, attachment):
        email_subject = 'Insurance MIS'
        html_body = 'Insurance MIS. Please find the attached MIS.'
        emails = settings.INSURANCE_MIS_EMAILS
        to_email = emails[0]
        cc_emails = emails[1:]
        email_obj = cls.objects.create(attachments=attachment, email=to_email, notification_type=NotificationAction.INSURANCE_MIS,
                                       content=html_body, email_subject=email_subject, cc=cc_emails, bcc=[])
        email_obj.save()

        message = {
            "data": model_to_dict(email_obj),
            "type": "email"
        }
        message = json.dumps(message)
        publish_message(message)

    @classmethod
    def send_contact_us_notification_email(cls, content_type, obj_id, email, html_body, mobile_number):
        email_subject = 'CONTACT US - A New Message Received ({})'.format(mobile_number)
        if email:
            email_obj = cls.objects.create(email=email, notification_type=NotificationAction.CONTACT_US_EMAIL,
                                           content=html_body, email_subject=email_subject, cc=[], bcc=[],
                                           content_type=content_type, object_id=obj_id)
            email_obj.save()

            email_noti = {
                "email": email,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_userprofile_email_update(cls, obj):
        from django.utils.safestring import mark_safe
        email = obj.new_email
        name = obj.profile.name

        profile_type = 'Insurance' if obj.profile.is_insured_profile else 'User'

        email_subject = 'Docprime : Profile Email update otp'
        html_body = mark_safe('<p>Dear  {name},</p><p>Please enter the OTP mentioned below to verify the new email ID for {profile_type} profile</p><p>OTP: {otp}</p><p>Thanks</p><p>Team Docprime </p>'.format(profile_type=profile_type, name=str(name.title()), otp=str(obj.otp)))
        # html_body = 'Please find the otp for email change. %s' % str(obj.otp)
        email_obj = cls.objects.create(email=email, notification_type=NotificationAction.USERPROFILE_EMAIL_UPDATE,
                                       content=html_body, email_subject=email_subject, cc=[], bcc=[])
        email_obj.save()

        message = {
            "data": model_to_dict(email_obj),
            "type": "email"
        }
        message = json.dumps(message)
        publish_message(message)

    @classmethod
    def send_dynamic_template_notification(cls, recipient_obj, html_body, email_subject, notification_type, *args, **kwargs):
        if recipient_obj and recipient_obj.to:
            obj = None
            content_type = None
            if kwargs.get('ipd_email_obj'):
                obj = kwargs.get('ipd_email_obj')
                content_type = ContentType.objects.get_for_model(obj)

            if kwargs.get('is_preview', False):
                email_obj = cls.objects.create(email=recipient_obj.to, notification_type=notification_type,
                                               content=html_body, email_subject=email_subject, cc=[], bcc=[], object_id=obj.id, content_type= content_type)

            else:
                email_obj = cls.objects.create(email=recipient_obj.to, notification_type=notification_type,
                                               content=html_body, email_subject=email_subject, cc=recipient_obj.cc, bcc=recipient_obj.bcc, object_id=obj.id, content_type= content_type)
                # object_id = models.BigIntegerField(null=True)
                # content_object = GenericForeignKey()

            email_obj.save()

            email_noti = {
                "email": recipient_obj.to,
                "content": html_body,
                "email_subject": email_subject
            }
            message = {
                "data": email_noti,
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)


class SmsNotificationOpdMixin:

    @classmethod
    def get_message_body(cls, user, phone_number, notification_type, context):
        html_body = ''
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            html_body = render_to_string("sms/appointment_accepted.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_booked_patient.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            html_body = render_to_string("sms/appointment_booked_doctor.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_rescheduled_patient_initiated_to_patient.txt",
                                         context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            html_body = render_to_string("sms/appointment_rescheduled_patient_initiated_to_doctor.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_rescheduled_doctor_initiated_to_patient.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            html_body = render_to_string("sms/appointment_cancelled_doctor.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_cancelled_patient.txt", context=context)
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            html_body = render_to_string("sms/prescription_uploaded.txt", context=context)
        return html_body


class SmsNotificationLabMixin:

    @classmethod
    def get_message_body(cls, user, phone_number, notification_type, context):
        html_body = ''
        if notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
            html_body = render_to_string("sms/lab/appointment_accepted.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/lab/appointment_booked_patient.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/lab/appointment_rescheduled_patient_initiated_to_patient.txt",
                                         context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/lab/appointment_rescheduled_lab_initiated_to_patient.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/lab/appointment_cancelled_patient.txt", context=context)
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            html_body = render_to_string("sms/lab/lab_report_uploaded.txt", context=context)
        return html_body


class SmsNotification(TimeStampedModel, SmsNotificationOpdMixin, SmsNotificationLabMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    content = models.TextField()
    phone_number = models.BigIntegerField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "sms_notification"

    def __str__(self):
        return '{} -> {} ({})'.format(self.content, self.phone_number, self.user)

    @classmethod
    def send_dynamic_template_notification(cls, phone_number, body, notification_type, *args, **kwargs):
        user = kwargs.get('user')
        obj = cls.objects.create(
            user=user,
            phone_number=phone_number,
            notification_type=notification_type,
            content=body
        )

        if phone_number:
            message = {
                "data": model_to_dict(obj),
                "type": "sms"
            }
            message = json.dumps(message)
            if phone_number not in settings.OTP_BYPASS_NUMBERS:
                publish_message(message)


    @classmethod
    def send_notification(cls, user, phone_number, notification_type, context):
        html_body = super().get_message_body(user, phone_number, notification_type, context)
        if not html_body:
            html_body = super(SmsNotificationOpdMixin, cls).get_message_body(user, phone_number, notification_type, context)

        if phone_number and user:
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

    @classmethod
    def send_to_manager(cls, phone_number, notification_type, context):
        html_body = ''
        if notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED:
            html_body = render_to_string("sms/lab/appointment_booked_lab.txt", context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT:
            html_body = render_to_string("sms/lab/appointment_rescheduled_patient_initiated_to_lab.txt",
                                         context=context)
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED:
            html_body = render_to_string("sms/lab/appointment_cancelled_lab.txt", context=context)
        if phone_number:
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

    @classmethod
    def send_booking_url(cls, token, phone_number, name):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        short_url = generate_short_url(booking_url)
        html_body = "Dear {}, \n" \
                    "Please click on the link to review your appointment details and make an online payment.\n" \
                    "{}\n"\
                    "Thanks,\n" \
                    "Team Docprime".format(name, short_url)
        if phone_number:
            sms_noti = {
                "phone_number": phone_number,
                "content": html_body,
            }
            message = {
                "data": sms_noti,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_insurance_booking_url(cls, token, phone_number):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        booking_url = booking_url + "&callbackurl=insurance/insurance-user-details-review"
        short_url = generate_short_url(booking_url)
        html_body = "Your Insurance purchase url is - {} . Please pay to confirm".format(short_url)
        if phone_number:
            sms_notification = {
                "phone_number": phone_number,
                "content": html_body,
            }
            message = {
                "data": sms_notification,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_vip_booking_url(cls, token, phone_number, *args, **kwargs):
        utm_source = kwargs.get('utm_source', '')
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        if utm_source:
            booking_url = booking_url + "&callbackurl=vip-club-member-details?utm_source={utm_source}&is_agent=false".format(utm_source=utm_source)
        else:
            booking_url = booking_url + "&callbackurl=vip-club-member-details?is_agent=false"

        short_url = generate_short_url(booking_url)
        print(short_url)

        sms_body = "Hi,\nPlease click on the link to view your Docprime VIP- Health Package details and make an online payment.\n{link} \nThanks\nTeam Docprime".format(link=short_url)
        if phone_number:
            sms_notification = {
                "phone_number": phone_number,
                "content": sms_body,
            }
            message = {
                "data": sms_notification,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_endorsement_request_url(cls, token, phone_number):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        booking_url = booking_url + "&callbackurl=insurance/insurance-user-details-review?is_endorsement=true"
        short_url = generate_short_url(booking_url)
        html_body = "Your Insurance Endorsement request url is - {} . Please confirm to process".format(short_url)
        if phone_number:
            sms_notification = {
                "phone_number": phone_number,
                "content": html_body,
            }
            message = {
                "data": sms_notification,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        return booking_url

    @classmethod
    def send_cart_url(cls, token, phone_number, utm):
        callback_url = "cart"
        payment_page_url = "{}/agent/booking?token={}&agent=false&callbackurl={}&{}".format(settings.CONSUMER_APP_DOMAIN,
                                                                                         token, callback_url, utm)
        short_url = generate_short_url(payment_page_url)
        html_body = "Your booking url is - {} . Please pay to confirm".format(short_url)
        if phone_number:
            sms_noti = {
                "phone_number": phone_number,
                "content": html_body,
            }
            message = {
                "data": sms_noti,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)
        return short_url

    @classmethod
    def send_app_download_link(cls, phone_number, context):
        sms_body = render_to_string('sms/doctor_onboarding.txt', context=context)
        if phone_number:
            sms_noti = {
                "phone_number": phone_number,
                "content": sms_body,
            }
            message = {
                "data": sms_noti,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)

    @classmethod
    def send_rating_link(cls, data):
        if data:
            sms_noti = {
                "phone_number": data['phone_number'],
                "content": data['text'],
            }
            message = {
                "data": sms_noti,
                "type": "sms"
            }
            message = json.dumps(message)
            publish_message(message)


class WhtsappNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    phone_number = models.BigIntegerField()
    viewed_at = models.DateTimeField(blank=True, null=True, default=None)
    read_at = models.DateTimeField(blank=True, null=True, default=None)
    template_name = models.CharField(max_length=100, null=False, blank=False)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)
    payload = JSONField(null=False, blank=False, default={})
    extras = JSONField(null=False, blank=False, default={})

    @classmethod
    def send_login_otp(cls, phone_number, request_source, **kwargs):

        from ondoc.sms.backends.backend import create_otp
        via_sms = kwargs.get('via_sms')
        via_whatsapp = kwargs.get('via_whatsapp')
        otp = create_otp(phone_number, "{}", call_source=request_source, return_otp=True, via_sms=via_sms, via_whatsapp=via_whatsapp)

        template_name = 'docprime_otp_web'
        if request_source == 'docprimechat':
            template_name = 'docprime_otp_verification'

        whatsapp_message = {"media": {},
                            "message": "",
                            "template": {
                                "name": template_name,
                                "params": [otp]
                            },
                            "message_type": "HSM",
                            "phone_number": phone_number
                            }

        extra = {'call_source': request_source}
        whatsapp_noti = WhtsappNotification.objects.create(
            phone_number=phone_number,
            notification_type=NotificationAction.LOGIN_OTP,
            template_name='docprime_otp_verification',
            payload=whatsapp_message,
            extras=extra
        )

        whatsapp_payload = {
                "data": whatsapp_noti.payload,
                "type": "social_message"
            }

        publish_message(json.dumps(whatsapp_payload))

    class Meta:
        db_table = "whtsapp_notification"

    def __str__(self):
        return '{} -> {} ({})'.format(self.notification_type, self.phone_number, self.user)


class AppNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "app_notification"

    def __str__(self):
        return '{} -> ({})'.format(self.content, self.user)

    @classmethod
    def send_notification(cls, user, notification_type, context):
        context.pop("instance", None)
        app_noti = AppNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content={key: val for key, val in context.items() if key != 'instance'}
        )
        message = {
            "data": model_to_dict(app_noti),
            "type": "app"
        }
        message = json.dumps(message)
        publish_message(message)


class PushNotification(TimeStampedModel):
    TARGET_APP_CHOICES = User.USER_TYPE_CHOICES
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    target_app = models.PositiveSmallIntegerField(choices=TARGET_APP_CHOICES, blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "push_notification"

    def __str__(self):
        return '{} -> ({})'.format(self.content, self.user)

    @classmethod
    def send_notification(cls, user, notification_type, context):
        context.pop("instance", None)
        target_app = user.user_type
        push_noti = PushNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content={key: val for key, val in context.items() if key != 'instance'},
            target_app=target_app
        )
        tokens = [token.token for token in NotificationEndpoint.objects.filter(user=user)]
        data = model_to_dict(push_noti)
        data["tokens"] = tokens
        message = {
            "data": data,
            "type": "push"
        }
        message = json.dumps(message)
        publish_message(message)


class RecipientSMS(object):
    def __init__(self, to):
        self.to = to


class RecipientEmail(object):
    def __init__(self, to, cc=[], bcc=[]):
        self.to = to
        self.cc = cc if cc else []
        self.bcc = bcc if bcc else []

    def add_cc(self, email):
        if email.__class__.__name__ == 'list':
            self.cc.extend(email)
        elif email.__class__.__name__ == 'str':
            self.cc.append(email)

        return self

    def add_bcc(self, email):
        if email.__class__.__name__ == 'list':
            self.bcc.extend(email)
        elif email.__class__.__name__ == 'str':
            self.bcc.append(email)

        return self


class DynamicTemplates(TimeStampedModel):
    class TemplateType(Choices):
        SMS = 'SMS'
        EMAIL = 'EMAIL'

    class Content:
        def __init__(self, content):
            self.content = content

    template_name = models.CharField(max_length=100, null=False, blank=False, help_text="Give name without extension")
    template_type = models.CharField(max_length=100, choices=TemplateType.as_choices(), null=False, blank=False)
    content = models.TextField(blank=False, null=False)
    virtual_content = models.TextField(null=True)
    approved = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=False, limit_choices_to={'user_type': 1}, on_delete=models.DO_NOTHING)
    sample_parameters = JSONField(default=dict, null=True, blank=True)
    subject = models.CharField(max_length=256, null=True, blank=True)
    recipient = models.CharField(max_length=100, null=True, blank=True)
    cc = models.CharField(max_length=512, null=True, blank=True)
    bcc = models.CharField(max_length=512, null=True, blank=True)

    def __str__(self):
        return str(self.template_name)

    def get_parameter_json(self):
        return self.sample_parameters

    def get_cc(self):
        if not self.cc:
            return []
        cc_emails = self.cc.split(',')
        return cc_emails

    def get_bcc(self):
        if not self.bcc:
            return []
        bcc_emails = self.bcc.split(',')
        return bcc_emails

    def send_notification(self, context, recipient_obj, notification_type, *args, **kwargs):
        rendered_content = self.render_template(context)
        if rendered_content is None:
            logger.error("Could not generate content. Dynamic temlplate id %s" % str(self.id))
            return None

        if self.template_type == self.TemplateType.EMAIL:
            if recipient_obj.__class__.__name__ != 'RecipientEmail':
                raise Exception('Recipient object is not defined.')

            recipient_obj.add_cc(self.get_cc())
            recipient_obj.add_bcc(self.get_bcc())

            EmailNotification.send_dynamic_template_notification(recipient_obj, rendered_content, self.subject, notification_type, *args, **kwargs)
        elif self.template_type == self.TemplateType.SMS:
            SmsNotification.send_dynamic_template_notification(recipient_obj, rendered_content, notification_type, *args, **kwargs)

        return

    def render_template(self, context):
        rendered_data = None

        try:
            file_content = self.content
            t = Template(file_content)
            c = Context(context)
            rendered_data = t.render(c)
        except Exception as e:
            logger.error(str(e))

        return rendered_data

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def preview_url(self):
        return mark_safe("<a href='/api/v1/notification/preview/{template_name}?send=False' target='_blank'>Preview</a> "
                         "| <a href='/api/v1/notification/preview/{template_name}?send=True' target='_blank'>Send Preview</a>"
                         .format(template_name=self.template_name))

    class Meta:
        db_table = 'dynamic_template'
        unique_together = (('template_name', 'template_type'), )

    # def evaluate_loop(self, content_obj):
    #     content = content_obj.content.replace('\r','').replace('\n', '')
    #     loops = re.findall(r'\{LOOP.*?ENDLOOP\}', content, re.MULTILINE)
    #     if not loops:
    #         return
    #     loops_dict = dict()
    #     for loop in loops:
    #         # get loop name
    #         loop_tag = re.findall(r'\{.*?\}', loop, re.MULTILINE)[0]
    #         loop_tag = loop_tag[1:len(loop_tag)-1]
    #         loop_name = loop_tag.split(" ")[1]
    #         counter = 0
    #         for e in loop:
    #             counter = counter + 1
    #             if e is not '}':
    #                 pass
    #             else:
    #                 break
    #         loop_script = loop[counter:len(loop) - len("{ENDLOOP}")]
    #         parameter_list = re.findall(r'\{.*?\}', loop_script, re.MULTILINE)
    #         p_dict = dict()
    #         for p in parameter_list:
    #             p_dict[p[1:len(p)-1]] = 'SAMPLE_VALUE'
    #
    #         loops_dict[loop_name] = [p_dict]
    #
    #         starting_offset = content.find(loop)
    #         ending_offset = starting_offset + len(loop)
    #         content = content[0:starting_offset] + content[ending_offset:]
    #
    #     content_obj.content = content
    #
    #     return loops_dict
    #
    # def evaluate_if(self, content):
    #     return
    #
    # @classmethod
    # def get_random_id(cls):
    #     return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    #
    # def generate_virutal_content(self):
    #     print("Generating virtual content.")
    #     virtual_content = copy.deepcopy(self.content)
    #     virtual_content = virtual_content.replace('\r','').replace('\n', '')
    #
    #     loops = re.findall(r'\{LOOP.*?ENDLOOP\}', virtual_content, re.MULTILINE)
    #
    #     for k, v in self.sample_parameters.items():
    #         if v.__class__.__name__ == 'list':
    #             if not loops:
    #                 return
    #             for loop in loops:
    #                 loop_tag = re.findall(r'\{.*?\}', loop, re.MULTILINE)[0]
    #                 loop_tag = loop_tag[1:len(loop_tag) - 1]
    #                 loop_name = loop_tag.split(" ")[1]
    #
    #                 if k != loop_name:
    #                     continue
    #
    #                 loop_identifier = DynamicTemplates.get_random_id()
    #                 starting_offset = virtual_content.find(loop)
    #                 ending_offset = starting_offset + len(loop)
    #
    #                 starting_loop_defination = "{%% for %s in %s %%}" % (str(loop_identifier), str(k))
    #                 counter = 0
    #                 for e in loop:
    #                     counter = counter + 1
    #                     if e is not '}':
    #                         pass
    #                     else:
    #                         break
    #                 loop = loop[counter:len(loop) - len("{ENDLOOP}")]
    #                 parameter_list = re.findall(r'\{.*?\}', loop, re.MULTILINE)
    #                 for v_para in parameter_list:
    #                     updated_value = "{{%s.%s}}" % (str(loop_identifier), v_para[1:len(v_para)-1])
    #                     loop = loop.replace(v_para, updated_value)
    #
    #                 ending_loop_defination = '{% endfor %}'
    #
    #                 final_parsed_template_loop = '%s%s%s' %(starting_loop_defination, loop, ending_loop_defination)
    #                 virtual_content = virtual_content[0:starting_offset] + final_parsed_template_loop + virtual_content[ending_offset:]
    #         else:
    #             virtual_content = virtual_content.replace('{%s}' % str(k), '{{%s}}' % str(k))
    #
    #     self.virtual_content = virtual_content

    # def parse_and_genearate_sample_json(self):
    #     parameter_dict = OrderedDict()
    #     content = copy.deepcopy(self.content)
    #     content_obj = self.Content(content)
    #     loop_dict = self.evaluate_loop(content_obj)
    #     if loop_dict:
    #         parameter_dict.update(loop_dict)
    #     parameter_list = re.findall(r'\{.*?\}', content_obj.content, re.MULTILINE)
    #
    #     for p in parameter_list:
    #         parameter_dict[p[1:len(p)-1]] = 'SAMPLE_VALUE'
    #
    #     return parameter_dict


class IPDIntimateEmailNotification(TimeStampedModel):

    MALE = 'm'
    FEMALE = 'f'
    GENDER_TYPE_CHOICES = (
        (MALE, 'male'),
        (FEMALE, 'female')
    )

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=False)
    doctor = models.ForeignKey('doctor.Doctor', on_delete=models.DO_NOTHING, null=False)
    hospital = models.ForeignKey('doctor.Hospital', on_delete=models.DO_NOTHING, null=False)
    phone_number = models.BigIntegerField(null=False)
    preferred_date = models.DateField(null=True, blank=True)
    time_slot = models.TimeField(blank=True, null=True)
    gender = models.CharField(max_length=100,choices=GENDER_TYPE_CHOICES, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    email_notifications = JSONField(null=True, blank=True)

    class Meta:
        db_table = "ipd_intimate_email_notification"