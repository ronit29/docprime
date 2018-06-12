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
    APPOINTMENT_REJECTED = 2
    APPOINTMENT_RESCHEDULED_BY_PATIENT = 3
    APPOINTMENT_RESCHEDULED_BY_DOCTOR = 4
    APPOINTMENT_BOOKED = 5
    NOTIFICATION_TYPE_CHOICES = (
        (APPOINTMENT_ACCEPTED, "Appointment Accepted"),
        (APPOINTMENT_REJECTED, "Appointment Rejected"),
        (APPOINTMENT_RESCHEDULED_BY_PATIENT, "Appointment Rescheduled by Patient"),
        (APPOINTMENT_RESCHEDULED_BY_DOCTOR, "Appointment Rescheduled by Doctor"),
        (APPOINTMENT_BOOKED, "Appointment Booked"),
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
            context = {
                "doctor_name": instance.doctor.name,
                "id": instance.id,
                "title": "Appointment Accepted",
                "body": "Your appointment with Dr. {} has been accepted.".format(instance.doctor.name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT:
            context = {
                "patient_name": instance.profile.name,
                "id": instance.id,
                "title": "Appointment Rescheduled",
                "body": "Patient {} has rescheduled the appointment.".format(instance.profile.name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            AppNotification.send_notification(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            context = {
                "patient_name": instance.profile.name,
                "doctor_name": instance.doctor.name,
                "title": "Appointment booked",
                "body": "Your appointment with Dr. {} has been booked.".format(instance.doctor.name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            context = {
                "patient_name": instance.profile.name,
                "doctor_name": instance.doctor.name,
                "title": "Notification Accepted",
                "body": "Patient {} has booked an appointment with you".format(instance.doctor.name),
                "url": "/opd/appointment/{}".format(instance.id),
                "action_type": NotificationAction.OPD_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_push_and_inapp(user=user, notification_type=notification_type, context=context)

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
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED:
            html_body = render_to_string("email/appointment_booked_patient/body.html", context=context)
            email_subject = render_to_string("email/appointment_booked_patient/subject.txt", context=context)
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
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED:
            html_body = render_to_string("sms/appointment_booked_patient.txt", context=context)
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
