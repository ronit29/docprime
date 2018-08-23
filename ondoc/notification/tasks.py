from __future__ import absolute_import, unicode_literals
from .labnotificationaction import LabNotificationAction
from . import models as notification_models
from celery import task
import logging

logger = logging.getLogger(__name__)


@task
def send_lab_notifications(appointment_id):
    from ondoc.diagnostic import models as lab_models
    instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
    if not instance:
        return
    if not instance.user:
        return
    # lab_managers = lab_models.LabManager.objects.filter(lab=instance.lab)
    lab_managers = instance.get_lab_admins()
    if instance.status == lab_models.LabAppointment.COMPLETED:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_INVOICE,
        )
        return
    if instance.status == lab_models.LabAppointment.ACCEPTED:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_ACCEPTED,
        )
        return
    if instance.status == lab_models.LabAppointment.RESCHEDULED_PATIENT:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT)
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_PATIENT,
        )
        return
    if instance.status == lab_models.LabAppointment.RESCHEDULED_LAB:
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_RESCHEDULED_BY_LAB,
        )
        return
    if instance.status == lab_models.LabAppointment.CANCELLED:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_CANCELLED)
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_CANCELLED,
        )
        return
    if instance.status == lab_models.LabAppointment.BOOKED:
        for lab_manager in lab_managers:
            LabNotificationAction.send_to_lab_managers(
                instance, lab_manager, notification_models.NotificationAction.LAB_APPOINTMENT_BOOKED)

@task
def send_opd_notifications(appointment_id):
    from ondoc.authentication.models import GenericAdmin
    from ondoc.doctor.models import OpdAppointment
    instance = OpdAppointment.objects.filter(id=appointment_id).first()
    if not instance:
        return
    if not instance.user:
        return
    doctor_admins = GenericAdmin.get_appointment_admins(instance)
    if instance.user and instance.status == OpdAppointment.ACCEPTED:
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_ACCEPTED,
        )
    elif instance.status == OpdAppointment.RESCHEDULED_PATIENT:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT)
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT)
    elif instance.status == OpdAppointment.RESCHEDULED_DOCTOR:
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR)
    elif instance.status == OpdAppointment.BOOKED:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_BOOKED)
    elif instance.status == OpdAppointment.CANCELLED:
        for admin in doctor_admins:
            notification_models.NotificationAction.trigger(
                instance=instance,
                user=admin,
                notification_type=notification_models.NotificationAction.APPOINTMENT_CANCELLED)
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.APPOINTMENT_CANCELLED)
    elif instance.status == OpdAppointment.COMPLETED:
        if not instance.user:
            return
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.DOCTOR_INVOICE,
        )
