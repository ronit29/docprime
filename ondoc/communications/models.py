import copy
from django.db import models
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
import logging

from ondoc.authentication.models import UserProfile, GenericAdmin
from ondoc.doctor.models import OpdAppointment
from ondoc.notification.models import NotificationAction, SmsNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class Notification:
    SMS = 1
    EMAIL = 2
    PUSH = 3
    IN_APP = 4

    def get_context(self):
        pass

    def get_email_template(self):
        pass

    def get_senders_list(self):
        pass

    def trigger(self):
        pass


class SMSNotification:
    def get_sms_template(self):
        pass

    def get_receivers_numbers(self):
        pass


class EmailNotification:

    def get_template(self):
        pass

    def get_receivers(self):
        pass

    def send(self, receiver, template, context):
        email_subject = render_to_string(template[0], context=context)
        html_body = render_to_string(template[1], context=context)



class TemplateLoader:

    def get_template(self, notification_type, user):
        body_template = 'email/'
        subject_template = 'email/'
        # context = copy.deepcopy(context)
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
            body_template += "appointment_accepted/body.html"
            subject_template += "appointment_accepted/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.CONSUMER:
            body_template += "appointment_booked_patient/body.html"
            subject_template += "appointment_booked_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_BOOKED and user.user_type == User.DOCTOR:
            body_template += "appointment_booked_doctor/body.html"
            subject_template += "appointment_booked_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.CONSUMER:
            body_template += "appointment_rescheduled_patient_initiated_to_patient/body.html"
            subject_template += "appointment_rescheduled_patient_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT and user.user_type == User.DOCTOR:
            body_template += "appointment_rescheduled_patient_initiated_to_doctor/body.html"
            subject_template += "appointment_rescheduled_patient_initiated_to_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR and user.user_type == User.CONSUMER:
            body_template += "appointment_rescheduled_doctor_initiated_to_patient/body.html"
            subject_template += "appointment_rescheduled_doctor_initiated_to_patient/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.DOCTOR:
            body_template += "appointment_cancelled_doctor/body.html"
            subject_template += "appointment_cancelled_doctor/subject.txt"
        elif notification_type == NotificationAction.APPOINTMENT_CANCELLED and user.user_type == User.CONSUMER:
            body_template += "appointment_cancelled_patient/body.html"
            subject_template += "appointment_cancelled_patient/subject.txt"
        elif notification_type == NotificationAction.PRESCRIPTION_UPLOADED:
            body_template += "prescription_uploaded/body.html"
            subject_template += "prescription_uploaded/subject.txt"
        elif notification_type == NotificationAction.DOCTOR_INVOICE:
            body_template += "doctor_invoice/body.html"
            subject_template += "doctor_invoice/subject.txt"
        return subject_template, body_template


class OpdNotification(Notification, TemplateLoader):
    template_path = ''

    def __init__(self, appointment):
        self.appointment = appointment

    def get_context(self):
        patient_name = self.appointment.profile.name if self.appointment.profile.name else ""
        doctor_name = self.appointment.doctor.name if self.appointment.doctor.name else ""
        procedures = self.appointment.get_procedures()
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
            "image_url": ""
        }
        return context

    def send(self, event, notification_type):
        pass

    def get_receivers(self, event, notification_type):
        instance = self.appointment
        receivers = []
        # doctor_admins = GenericAdmin.get_appointment_admins(instance)
        # for admin in doctor_admins:
        #     user = admin
        if not instance:
            return
        if not instance.user:
            return
        doctor_admins = GenericAdmin.get_appointment_admins(instance)
        if instance.status in [OpdAppointment.ACCEPTED, OpdAppointment.RESCHEDULED_DOCTOR,
                               OpdAppointment.COMPLETED]:
            receivers.append(instance.user)
        elif instance.status in [OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.BOOKED, OpdAppointment.CANCELLED]:
            receivers.extend(doctor_admins)
            receivers.append(instance.user)

        # emails = []
        # phone_numbers = []
        #
        # for user in receivers:
        #     if user.user_type == User.CONSUMER:
        #         email = instance.profile.email
        #         phone_number = instance.profile.phone_number
        #         # send notification to default profile also
        #         default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
        #         if default_user_profile and (
        #                 default_user_profile.id != instance.profile.id) and default_user_profile.email:
        #             emails.append({'email': default_user_profile.email, 'user_type': user.user_type})
        #         if default_user_profile and (
        #                 default_user_profile.id != instance.profile.id) and default_user_profile.phone_number:
        #             phone_numbers.append(
        #                 {'phone_number': default_user_profile.phone_number, 'user_type': user.user_type})
        #     else:
        #         email = user.email
        #         phone_number = user.phone_number
        #     emails.append({'email': email, 'user_type': user.user_type})
        #     phone_numbers.append({'phone_number': phone_number, 'user_type': user.user_type})
        return receivers

    def send_email(self, event, notification_type):
        receivers = self.get_receivers(event, notification_type)
        context = self.get_context()
        for receiver in receivers:
            template = self.get_template(notification_type, receiver)
            EmailNotification.send(receiver, template, context)
        pass
