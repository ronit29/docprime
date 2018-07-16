import json
from django.db import models
from django.contrib.postgres.fields import JSONField
from django.forms.models import model_to_dict
from ondoc.authentication.models import TimeStampedModel
from ondoc.authentication.models import NotificationEndpoint
from .rabbitmq_client import publish_message
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

User = get_user_model()


class NotificationAction:
    APPOINTMENT_ACCEPTED = 1
    APPOINTMENT_CANCELLED = 2
    APPOINTMENT_RESCHEDULED_BY_PATIENT = 3
    APPOINTMENT_RESCHEDULED_BY_DOCTOR = 4
    APPOINTMENT_BOOKED = 5

    PRESCRIPTION_UPLOADED = 6
    PAYMENT_PENDING = 7
    RECEIPT = 8
    NOTIFICATION_TYPE_CHOICES = (
        (APPOINTMENT_ACCEPTED, "Appointment Accepted"),
        (APPOINTMENT_CANCELLED, "Appointment Cancelled"),
        (APPOINTMENT_RESCHEDULED_BY_PATIENT, "Appointment Rescheduled by Patient"),
        (APPOINTMENT_RESCHEDULED_BY_DOCTOR, "Appointment Rescheduled by Doctor"),
        (APPOINTMENT_BOOKED, "Appointment Booked"),
        (PRESCRIPTION_UPLOADED, "Prescription Uploaded"),
        (PAYMENT_PENDING, "Payment Pending"),
        (RECEIPT, "Receipt")
    )

    OPD_APPOINTMENT = "opd_appointment"
    LAB_APPOINTMENT = "lab_appoingment"

    ACTION_TYPE_CHOICES = (
        (OPD_APPOINTMENT, 'Opd Appointment'),
        (LAB_APPOINTMENT, 'Lab Appointment'),
    )

    @classmethod
    def trigger(cls, instance, user, notification_type):
        context = {}
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "doctor_name": doctor_name,
                "id": instance.id,
                "title": "Appointment Accepted",
                "body": "Your appointment with Dr. {} has been accepted.".format(doctor_name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT:
            patient_name = instance.profile.name if instance.profile.name else ""
            context = {
                "patient_name": patient_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Rescheduled",
                "body": "Reschedule request received for the appointment with Mr. {}".format(patient_name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Appointment Confirmed",
                "body": "Appointment confirmed for Mr. {} at {}, {} with Dr. {}.".format(
                    patient_name, instance.time_slot_start.strftime("%I:%M %P"),
                    instance.time_slot_start.strftime("%d/%m/%y"), doctor_name
                ),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user and user.user_type == User.DOCTOR:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Appointment Confirmed",
                "body": "New appointment for Mr. {} at {}, {}. Please confirm.".format(
                    patient_name, instance.time_slot_start.strftime("%I:%M %P"),
                    instance.time_slot_start.strftime("%d/%m/%y")),
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
                "body": "Appointment with Mr. {} at {}  {} has been cancelled.".format(
                    patient_name, instance.time_slot_start.strftime("%I:%M %P"),
                    instance.time_slot_start.strftime("%d/%m/%y")),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            doctor_name = instance.doctor.name if instance.doctor.name else ""
            context = {
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": "Appointment with Dr. {} at {} {} has been cancelled as per your request.".format(
                    doctor_name, instance.time_slot_start.strftime("%I:%M %P"),
                    instance.time_slot_start.strftime("%d/%m/%y")),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)


    @classmethod
    def trigger_all(cls, user, notification_type, context=None):
        EmailNotification.send_notification(user=user, notification_type=notification_type,
                                            email=user.email, context=context)
        SmsNotification.send_notification(user=user, phone_number=user.phone_number,
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


class EmailNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    email_subject = models.TextField(blank=True, null=True)
    email = models.EmailField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "email_notification"

    @classmethod
    def send_notification(cls, user, email, notification_type, context):
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            html_body = render_to_string("email/appointment_accepted/body.html", context=context)
            email_subject = render_to_string("email/appointment_accepted/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_booked_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_booked_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            html_body = render_to_string("email/appointment_booked_doctor/body.html", context=context)
            email_subject = render_to_string("email/appointment_booked_doctor/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT:
            html_body = render_to_string("email/appointment_rescheduled_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_rescheduled_patient/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            html_body = render_to_string("email/appointment_cancelled_doctor/body.html", context=context)
            email_subject = render_to_string("email/appointment_cancelled_doctor/subject.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("email/appointment_cancelled_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_cancelled_patient/subject.txt", context=context)

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



class SmsNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    phone_number = models.BigIntegerField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "sms_notification"

    @classmethod
    def send_notification(cls, user, phone_number, notification_type, context):
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            html_body = render_to_string("sms/appointment_accepted.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_booked_patient.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            html_body = render_to_string("sms/appointment_booked_doctor.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT:
            html_body = render_to_string("sms/appointment_rescheduled_patient.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            html_body = render_to_string("sms/appointment_cancelled_doctor.txt", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            html_body = render_to_string("sms/appointment_cancelled_patient.txt", context=context)

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
            publish_message(message)


class AppNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "app_notification"

    @classmethod
    def send_notification(cls, user, notification_type, context):
        context.pop("instance", None)
        app_noti = AppNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content=context
        )
        message = {
            "data": model_to_dict(app_noti),
            "type": "app"
        }
        message = json.dumps(message)
        publish_message(message)


class PushNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "push_notification"

    @classmethod
    def send_notification(cls, user, notification_type, context):
        context.pop("instance", None)
        push_noti = PushNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content=context
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
