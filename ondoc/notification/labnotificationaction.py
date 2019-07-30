from .models import NotificationAction, EmailNotification, SmsNotification, AppNotification, PushNotification
from ondoc.authentication.models import UserProfile
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
                "action_type": NotificationAction.LAB_APPOINTMENT,
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
                "action_type": NotificationAction.LAB_APPOINTMENT,
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
                "action_type": NotificationAction.LAB_APPOINTMENT,
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
                "title": "New Appointment",
                "body": "New Appointment for {} at {}, {} with Lab - {}. You will receive a confirmation as soon as it is accepted by the lab".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y"), lab_name
                ),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED and user and user.user_type == User.CONSUMER:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            if instance.cancellation_type != instance.AUTO_CANCELLED:
                body = "Appointment with Lab - {} at {}, {} has been cancelled.".format(
                        lab_name, time_slot_start.strftime("%I:%M %P"),
                        time_slot_start.strftime("%d/%m/%y")
                )
            else:
                body = "Appointment with Lab - {} at {}, {} has cancelled due to unavailability of lab manager.".format(
                        lab_name, time_slot_start.strftime("%I:%M %P"),
                        time_slot_start.strftime("%d/%m/%y"))
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": body,
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)
            return
        if notification_type == NotificationAction.LAB_INVOICE:
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
            return
        if notification_type == NotificationAction.LAB_REPORT_UPLOADED:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Report Uploaded",
                "body": "Report available for your appointment with Lab - {} on {}".format(
                    lab_name, time_slot_start.strftime("%d/%m/%y")),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            NotificationAction.trigger_all(user=user, notification_type=notification_type, context=context)

    @classmethod
    def send_to_lab_managers(cls, instance, lab_manager, notification_type):
        est = pytz.timezone(settings.TIME_ZONE)
        time_slot_start = instance.time_slot_start.astimezone(est)
        if notification_type == NotificationAction.LAB_APPOINTMENT_BOOKED:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "New Appointment",
                "body": "New appointment for {} at {}, {}. Please confirm.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            EmailNotification.send_to_manager(email=lab_manager.email, notification_type=notification_type,
                                              context=context)
            SmsNotification.send_to_manager(phone_number=lab_manager.phone_number, notification_type=notification_type,
                                            context=context)
            AppNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                              context=context)
            PushNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                               context=context)
        if notification_type == NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT:
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
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            EmailNotification.send_to_manager(email=lab_manager.email, notification_type=notification_type,
                                              context=context)
            SmsNotification.send_to_manager(phone_number=lab_manager.phone_number, notification_type=notification_type,
                                            context=context)
            AppNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                              context=context)
            PushNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                               context=context)
            return

        if notification_type == NotificationAction.LAB_APPOINTMENT_CANCELLED:
            patient_name = instance.profile.name if instance.profile.name else ""
            lab_name = instance.lab.name.title() if instance.lab.name else ""
            context = {
                "patient_name": patient_name,
                "lab_name": lab_name,
                "instance": instance,
                "title": "Appointment Cancelled",
                "body": "Appointment with {} at {}  {} has been cancelled.".format(
                    patient_name, time_slot_start.strftime("%I:%M %P"),
                    time_slot_start.strftime("%d/%m/%y")),
                "url": "/lab/appointment/{}".format(instance.id),
                "action_type": NotificationAction.LAB_APPOINTMENT,
                "action_id": instance.id,
                "image_url": ""
            }
            EmailNotification.send_to_manager(email=lab_manager.email, notification_type=notification_type,
                                              context=context)
            SmsNotification.send_to_manager(phone_number=lab_manager.phone_number, notification_type=notification_type,
                                            context=context)
            AppNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                              context=context)
            PushNotification.send_notification(user=lab_manager, notification_type=notification_type,
                                               context=context)

