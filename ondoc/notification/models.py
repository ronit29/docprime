import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.forms.models import model_to_dict
from ondoc.authentication.models import TimeStampedModel
from ondoc.authentication.models import NotificationEndpoint
from ondoc.authentication.models import UserProfile
from ondoc.account import models as account_model
from ondoc.api.v1.utils import readable_status_choices
from ondoc.notification.rabbitmq_client import publish_message
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
from django.conf import settings
import pytz
import logging
from django.contrib.postgres.fields import ArrayField

import copy

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationAction:
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

    OPD_OTP_BEFORE_APPOINTMENT = 30
    LAB_OTP_BEFORE_APPOINTMENT = 31

    CASHBACK_CREDITED = 55

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

        (PRESCRIPTION_UPLOADED, "Prescription Uploaded"),
        (PAYMENT_PENDING, "Payment Pending"),
        (RECEIPT, "Receipt"),
        (DOCTOR_INVOICE, "Doctor Invoice"),
        (LAB_INVOICE, "Lab Invoice"),
        (CASHBACK_CREDITED, "Cashback Credited")
    )

    OPD_APPOINTMENT = "opd_appointment"
    LAB_APPOINTMENT = "lab_appoingment"

    ACTION_TYPE_CHOICES = (
        (OPD_APPOINTMENT, 'Opd Appointment'),
        (LAB_APPOINTMENT, 'Lab Appointment'),
    )

    @classmethod
    def trigger(cls, instance, user, notification_type):
        from ondoc.doctor.models import OpdAppointment
        est = pytz.timezone(settings.TIME_ZONE)
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
                body = "Appointment with Dr. {} at {}, {} has been cancelled as per your request.".format(
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

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    email_subject = models.TextField(blank=True, null=True)
    email = models.EmailField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)
    cc = ArrayField(models.EmailField(), default=[], blank=[])
    bcc = ArrayField(models.EmailField(), default=[], blank=[])
    attachments = JSONField(default=[], blank=[])
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
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
        html_body = "Your booking url is - {} . Please pay to confirm".format(booking_url)
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
    def send_booking_url(cls, token, phone_number):
        booking_url = "{}/agent/booking?token={}".format(settings.CONSUMER_APP_DOMAIN, token)
        html_body = "Your booking url is - {} . Please pay to confirm".format(booking_url)
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
