from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel
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

    @classmethod
    def trigger(cls, instance, user, notification_type):
        context = {}
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            context = {
                "doctor_name": instance.doctor.name,
                "id": instance.id,
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT:
            context = {
                "patient_name": instance.profile.name,
                "id": instance.id
            }
            AppNotification.send_notification(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            context = {
                "patient_name": instance.profile.name,
                "doctor_name": instance.doctor.name,
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            context = {
                "patient_name": instance.profile.name,
                "doctor_name": instance.doctor.name,
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
    email = models.EmailField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "email_notification"

    @classmethod
    def send_notification(cls, user, email, notification_type, context):
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            html_body = render_to_string("email/appointment_accepted.html", context=context)
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED:
            html_body = render_to_string("email/appointment_booked_patient.html", context=context)
        EmailNotification.objects.create(
            user=user,
            email=email,
            notification_type=notification_type,
            content=html_body
        )


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
        SmsNotification.objects.create(
            user=user,
            phone_number=phone_number,
            notification_type=notification_type,
            content=html_body
        )


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
        AppNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content=context
        )


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
        PushNotification.objects.create(
            user=user,
            notification_type=notification_type,
            content=context
        )
