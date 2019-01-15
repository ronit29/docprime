import copy
import json
import random
from collections import defaultdict
from itertools import groupby

import pytz
from django.db.models import F
# from hardcopy import bytestring_to_pdf

from ondoc.api.v1.utils import util_absolute_url, util_file_name
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile, InMemoryUploadedFile
from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from django.utils import timezone
from weasyprint import HTML

from ondoc.account.models import Invoice, Order
from ondoc.authentication.models import UserProfile, GenericAdmin, NotificationEndpoint

from ondoc.notification.models import NotificationAction, SmsNotification, EmailNotification, AppNotification, \
    PushNotification
# from ondoc.notification.sqs_client import publish_message
from ondoc.notification.rabbitmq_client import publish_message

User = get_user_model()
logger = logging.getLogger(__name__)


def unique_emails(list_):
    """Function accepts list of dictionaries and returns list of unique dictionaries"""
    temp = set()

    for item in list_:
        if item.get('email', None) and item.get('user', None):
            temp.add((item.get('user'), item.get('email').strip().lower()))

    return [{'user': item[0], 'email': item[1]} for item in temp]


def unique_phone_numbers(list_):
    """Function accepts list of dictionaries and returns list of unique dictionaries"""
    temp = set()

    for item in list_:
        if item.get('phone_number', None) and item.get('user', None):
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
        body = "Appointment Confirmed for {} requested with Dr. {} at {}, {}.".format(
            patient_name, doctor_name, time_slot_start.strftime("%I:%M %P"),
            time_slot_start.strftime("%d/%m/%y"), doctor_name)
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
        body = "New Appointment for {} at {}, {} with Dr. {}. You will receive a confirmation as soon as it is accepted by the doctor.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"), doctor_name)
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
            body = "Appointment with Dr. {} at {}, {} has been cancelled as per your request.".format(
                doctor_name, time_slot_start.strftime("%I:%M %P"),
                time_slot_start.strftime("%d/%m/%y")
            )
        else:
            body = "Appointment with Dr. {} at {}, {} has been cancelled due to unavailability of doctor manager.".format(
                doctor_name, time_slot_start.strftime("%I:%M %P"),
                time_slot_start.strftime("%d/%m/%y"))
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
        body = "Appointment Confirmed for {} requested with Lab - {} at {}, {}.".format(
            patient_name, lab_name, time_slot_start.strftime("%I:%M %P"),
            time_slot_start.strftime("%d/%m/%y"), lab_name)
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
        body = "New Appointment for {} at {}, {} with Lab - {}. You will receive a confirmation as soon as it is accepted by the lab".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"), lab_name)
    elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.DOCTOR:
        title = "New Appointment"
        body = "New appointment for {} at {}, {}. Please confirm.".format(
            patient_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
    elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
        if instance.cancellation_type != instance.AUTO_CANCELLED:
            body = "Appointment with Lab - {} at {}, {} has been cancelled as per your request.".format(
                lab_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
        else:
            body = "Appointment with Lab - {} at {}, {} has cancelled due to unavailability of lab manager.".format(
                lab_name, time_slot_start.strftime("%I:%M %P"), time_slot_start.strftime("%d/%m/%y"))
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
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_booked_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            body_template = "sms/appointment_booked_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_rescheduled_patient_initiated_to_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            body_template = "sms/appointment_rescheduled_patient_initiated_to_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_rescheduled_doctor_initiated_to_patient.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            body_template = "sms/appointment_cancelled_doctor.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            body_template = "sms/appointment_cancelled_patient.txt"
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template = "sms/prescription_uploaded.txt"

        elif notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED or \
                notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:
            body_template = "sms/lab/appointment_accepted.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_booked_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            body_template = "sms/lab/appointment_booked_lab.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_rescheduled_patient_initiated_to_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            body_template = "sms/lab/appointment_rescheduled_patient_initiated_to_lab.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_rescheduled_lab_initiated_to_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            body_template = "sms/lab/appointment_cancelled_patient.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            body_template = "sms/lab/appointment_cancelled_lab.txt"
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            body_template = "sms/lab/lab_report_uploaded.txt"
        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            body_template = "sms/lab/lab_report_send_crm.txt"
        return body_template

    def trigger(self, receiver, template, context):
        user = receiver.get('user')
        phone_number = receiver.get('phone_number')
        notification_type = self.notification_type
        context = copy.deepcopy(context)
        html_body = render_to_string(template, context=context)
        if phone_number and user.user_type == User.DOCTOR and notification_type in [
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
        elif phone_number and user:
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

    def send(self, receivers):
        context = self.context
        if not context:
            return
        for receiver in receivers:
            template = self.get_template(receiver.get('user'))
            if template:
                self.trigger(receiver, template, context)


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
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            body_template = "email/appointment_booked_patient/body.html"
            subject_template = "email/appointment_booked_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            body_template = "email/appointment_booked_doctor/body.html"
            subject_template = "email/appointment_booked_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            body_template = "email/appointment_rescheduled_patient_initiated_to_patient/body.html"
            subject_template = "email/appointment_rescheduled_patient_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            body_template = "email/appointment_rescheduled_patient_initiated_to_doctor/body.html"
            subject_template = "email/appointment_rescheduled_patient_initiated_to_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            body_template = "email/appointment_rescheduled_doctor_initiated_to_patient/body.html"
            subject_template = "email/appointment_rescheduled_doctor_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            body_template = "email/appointment_cancelled_doctor/body.html"
            subject_template = "email/appointment_cancelled_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            body_template = "email/appointment_cancelled_patient/body.html"
            subject_template = "email/appointment_cancelled_patient/subject.txt"
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template = "email/prescription_uploaded/body.html"
            subject_template = "email/prescription_uploaded/subject.txt"
        elif notification_type == NotificationAction.DOCTOR_INVOICE:

            invoice, created = Invoice.objects.get_or_create(reference_id=context.get("instance").id,
                                                             product_id=Order.DOCTOR_PRODUCT_ID)
            context.update({"invoice": invoice})
            html_body = render_to_string("email/doctor_invoice/invoice_template.html", context=context)
            filename = "invoice_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
                                                  random.randint(1111111111, 9999999999))
            try:
                extra_args = {
                    'virtual-time-budget': 6000
                }
                temp_pdf_file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
                file = open(temp_pdf_file.temporary_file_path())
                bytestring_to_pdf(html_body.encode(), file, **extra_args)
                file.seek(0)
                file.flush()
                file.content_type = 'application/pdf'
                invoice.file = InMemoryUploadedFile(temp_pdf_file, None, filename, 'application/pdf',
                                                    temp_pdf_file.tell(), None)
                invoice.save()
            except Exception as e:
                logger.error("Got error while creating pdf for opd invoice {}".format(e))
            context.update({"invoice_url": invoice.file.url})
            context.update(
                {"attachments": [
                    {"filename": util_file_name(invoice.file.url), "path": util_absolute_url(invoice.file.url)}]})
            body_template = "email/doctor_invoice/body.html"
            subject_template = "email/doctor_invoice/subject.txt"

        if notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
            body_template = "email/lab/appointment_accepted/body.html"
            subject_template = "email/lab/appointment_accepted/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_booked_patient/body.html"
            subject_template = "email/lab/appointment_booked_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            body_template = "email/lab/appointment_booked_lab/body.html"
            subject_template = "email/lab/appointment_booked_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_rescheduled_patient_initiated_to_patient/body.html"
            subject_template = "email/lab/appointment_rescheduled_patient_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            body_template = "email/lab/appointment_rescheduled_patient_initiated_to_lab/body.html"
            subject_template = "email/lab/appointment_rescheduled_patient_initiated_to_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_rescheduled_lab_initiated_to_patient/body.html"
            subject_template = "email/lab/appointment_rescheduled_lab_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            body_template = "email/lab/appointment_cancelled_patient/body.html"
            subject_template = "email/lab/appointment_cancelled_patient/subject.txt"
        elif notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            body_template = "email/lab/appointment_cancelled_lab/body.html"
            subject_template = "email/lab/appointment_cancelled_lab/subject.txt"
        elif notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            body_template = "email/lab/lab_report_uploaded/body.html"
            subject_template = "email/lab/lab_report_uploaded/subject.txt"
        elif notification_type == NotificationAction.LAB_INVOICE:
            invoice, created = Invoice.objects.get_or_create(reference_id=context.get("instance").id,
                                                             product_id=Order.LAB_PRODUCT_ID)
            context.update({"invoice": invoice})
            html_body = render_to_string("email/lab_invoice/invoice_template.html", context=context)
            filename = "invoice_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
                                                  random.randint(1111111111, 9999999999))
            try:
                extra_args = {
                    'virtual-time-budget': 6000
                }
                temp_pdf_file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
                file = open(temp_pdf_file.temporary_file_path())
                bytestring_to_pdf(html_body.encode(), file, **extra_args)
                file.seek(0)
                file.flush()
                file.content_type = 'application/pdf'
                invoice.file = InMemoryUploadedFile(temp_pdf_file, None, filename, 'application/pdf',
                                                    temp_pdf_file.tell(), None)
                invoice.save()
            except Exception as e:
                logger.error("Got error while creating pdf for opd invoice {}".format(e))
            context.update({"invoice_url": invoice.file.url})
            context.update(
                {"attachments": [{"filename": util_file_name(invoice.file.url), "path": util_absolute_url(invoice.file.url)}]})
            body_template = "email/lab_invoice/body.html"
            subject_template = "email/lab_invoice/subject.txt"

        elif notification_type == NotificationAction.LAB_REPORT_SEND_VIA_CRM:
            attachments = []
            for report_link in context.get('reports', []):
                attachments.append({"filename": util_file_name(report_link), "path": util_absolute_url(report_link)})
            context.update({'attachments': attachments})
            body_template = "email/lab/lab_report_send_crm/body.html"
            subject_template = "email/lab/lab_report_send_crm/subject.txt"

        return subject_template, body_template

    def trigger(self, receiver, template, context):
        cc = []
        bcc = [settings.PROVIDER_EMAIL]
        attachments = context.get('attachments', [])
        user = receiver.get('user')
        email = receiver.get('email')
        notification_type = self.notification_type
        context = copy.deepcopy(context)
        email_subject = render_to_string(template[0], context=context)
        html_body = render_to_string(template[1], context=context)
        if email and user.user_type == User.DOCTOR and notification_type in [
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
                attachments=attachments
            )
            message = {
                "data": model_to_dict(email_noti),
                "type": "email"
            }
            message = json.dumps(message)
            publish_message(message)
        elif email and user:
            email_noti = EmailNotification.objects.create(
                user=user,
                email=email,
                notification_type=notification_type,
                content=html_body,
                email_subject=email_subject,
                cc=cc,
                bcc=bcc,
                attachments=attachments
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
        context = {
            "doctor_name": doctor_name,
            "patient_name": patient_name,
            "id": self.appointment.id,
            "instance": self.appointment,
            "procedures": procedures,
            "coupon_discount": str(self.appointment.discount) if self.appointment.discount else None,
            "url": "/opd/appointment/{}".format(self.appointment.id),
            "action_type": NotificationAction.OPD_APPOINTMENT,
            "action_id": self.appointment.id,
            "payment_type": dict(OpdAppointment.PAY_CHOICES)[self.appointment.payment_type],
            "image_url": "",
            "time_slot_start": time_slot_start,
            "attachments": {}  # Updated later
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.DOCTOR_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
        elif notification_type == NotificationAction.OPD_OTP_BEFORE_APPOINTMENT:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
        else:
            email_notification = EMAILNotification(notification_type, context)
            sms_notification = SMSNotification(notification_type, context)
            app_notification = APPNotification(notification_type, context)
            push_notification = PUSHNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers
        doctor_admins = GenericAdmin.get_appointment_admins(instance)
        if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
                                 NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
                                 NotificationAction.PRESCRIPTION_UPLOADED,
                                 NotificationAction.DOCTOR_INVOICE,
                                 NotificationAction.OPD_OTP_BEFORE_APPOINTMENT]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.APPOINTMENT_BOOKED,
                                   NotificationAction.APPOINTMENT_CANCELLED]:
            receivers.extend(doctor_admins)
            receivers.append(instance.user)
        receivers = list(set(receivers))
        user_and_phone_number = []
        user_and_email = []
        app_receivers = receivers
        user_and_tokens = []

        user_and_token = [{'user': token.user, 'token': token.token} for token in
                          NotificationEndpoint.objects.filter(user__in=receivers).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append({'user': user, 'tokens': [t['token'] for t in user_token_group]})

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
        user_and_email = unique_emails(user_and_email)
        user_and_phone_number = unique_phone_numbers(user_and_phone_number)
        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['app_receivers'] = app_receivers
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
        reports = instance.reports.all()
        report_file_links = set()
        for report in reports:
            report_file_links = report_file_links.union(
                set([report_file.name.url for report_file in report.files.all()]))
        report_file_links = [util_absolute_url(report_file_link) for report_file_link in report_file_links]
        for test in tests:
            test['mrp'] = str(test['mrp'])
            test['deal_price'] = str(test['deal_price'])
            test['discount'] = str(test['discount'])
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
            "attachments": {}  # Updated later
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.LAB_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
        elif notification_type == NotificationAction.LAB_OTP_BEFORE_APPOINTMENT:
            sms_notification = SMSNotification(notification_type, context)
            sms_notification.send(all_receivers.get('sms_receivers', []))
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
            email_notification.send(all_receivers.get('email_receivers', []))
            sms_notification.send(all_receivers.get('sms_receivers', []))
            app_notification.send(all_receivers.get('app_receivers', []))
            push_notification.send(all_receivers.get('push_receivers', []))

    def get_receivers(self):
        all_receivers = {}
        instance = self.appointment
        receivers = []
        notification_type = self.notification_type
        if not instance or not instance.user:
            return receivers
        lab_managers = instance.get_lab_admins()
        if notification_type in [NotificationAction.LAB_APPOINTMENT_ACCEPTED,
                                 NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
                                 NotificationAction.LAB_REPORT_UPLOADED,
                                 NotificationAction.LAB_INVOICE,
                                 NotificationAction.LAB_OTP_BEFORE_APPOINTMENT,
                                 NotificationAction.LAB_REPORT_SEND_VIA_CRM]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.LAB_APPOINTMENT_BOOKED,
                                   NotificationAction.LAB_APPOINTMENT_CANCELLED]:
            receivers.extend(lab_managers)
            receivers.append(instance.user)
        receivers = list(set(receivers))
        user_and_phone_number = []
        user_and_email = []
        app_receivers = receivers
        user_and_tokens = []

        user_and_token = [{'user': token.user, 'token': token.token} for token in
                          NotificationEndpoint.objects.filter(user__in=receivers).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append({'user': user, 'tokens': [t['token'] for t in user_token_group]})

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

        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['app_receivers'] = app_receivers
        all_receivers['push_receivers'] = user_and_tokens

        return all_receivers
