from .models import NotificationAction, EmailNotification
from django.contrib.auth import get_user_model
from django.conf import settings
import pytz

User = get_user_model()


class LabNotificationAction(NotificationAction):

    @classmethod
    def trigger(cls, instance, user, notification_type):
        context = {}
        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = instance.time_slot_start.astimezone(est)
        if notification_type == NotificationAction.LAB_APPOINTMENT_ACCEPTED:
            patient_name = instance.profile.name.title() if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "lab_name": lab_name,
                "patient_name": patient_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Confirmed",
                "body": "Appointment Confirmed for {} requested with Lab - {} at {}, {}.".format(
                    patient_name, lab_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"), lab_name
                ),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": notification_type,
                "action_id": instance.id,
                "image_url": ""
            }
            super().trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Reschedule",
                "body": "Reschedule request received for the appointment with Lab - {}".format(lab_name),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": notification_type,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "id": instance.id,
                "instance": instance,
                "title": "Appointment Reschedule",
                "body": "Reschedule request received for the appointment from Lab - {}".format(lab_name),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": notification_type,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Appointment Confirmed",
                "body": "Appointment confirmed for {} at {}, {} with Lab - {}.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"), lab_name
                ),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": notification_type,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": "Appointment with Lab - {} at {}, {} has been cancelled as per your request..".format(
                    lab_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": notification_type,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        elif notification_type == NotificationAction.LAB_INVOICE:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Invoice Generated",
                "body": "Invoice for appointment ID-{} has been generated.".format(instance.id),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            EmailNotification.send_notification(user=user, notification_type=notification_type,
                                                email=user.email, context=context)