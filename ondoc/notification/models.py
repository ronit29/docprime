from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.authentication.models import TimeStampedModel
from django.contrib.auth import get_user_model


User = get_user_model()


class NotificationConstants:
    APPOINTMENT_ACCEPTED = 1
    APPOINTMENT_REJECTED = 2
    NOTIFICATION_TYPE_CHOICES = (
        (APPOINTMENT_ACCEPTED, "Appointment Accepted"),
        (APPOINTMENT_REJECTED, "Appointment Rejected"),
    )


class EmailNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    email = models.EmailField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationConstants.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "email_notification"


class SmsNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    phone_number = models.BigIntegerField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationConstants.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "sms_notification"


class AppNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationConstants.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "app_notification"


class PushNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = JSONField()
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    notification_type = models.PositiveIntegerField(choices=NotificationConstants.NOTIFICATION_TYPE_CHOICES)

    class Meta:
        db_table = "push_notification"