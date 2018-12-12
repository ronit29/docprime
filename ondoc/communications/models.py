import json
from itertools import groupby

from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
from ondoc.authentication.models import UserProfile, GenericAdmin, NotificationEndpoint
from ondoc.doctor.models import OpdAppointment
from ondoc.notification.models import NotificationAction, SmsNotification, EmailNotification, AppNotification, \
    PushNotification
from ondoc.notification.rabbitmq_client import publish_message

User = get_user_model()
logger = logging.getLogger(__name__)


def unique(list_):
    """Function accepts list of dictionaries and returns list of unique dictionaries"""
    temp_list = [tuple(item.items()) for item in list_]
    final_list = list(set(temp_list))
    final_list = [dict(item) for item in final_list]
    return final_list


class Notification:
    SMS = 1
    EMAIL = 2
    PUSH = 3
    IN_APP = 4
    OPD_NOTIFICATION_TYPE_MAPPING = \
        {OpdAppointment.ACCEPTED: NotificationAction.APPOINTMENT_ACCEPTED,
         OpdAppointment.RESCHEDULED_PATIENT: NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
         OpdAppointment.RESCHEDULED_DOCTOR: NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
         OpdAppointment.BOOKED: NotificationAction.APPOINTMENT_BOOKED,
         OpdAppointment.CANCELLED: NotificationAction.APPOINTMENT_CANCELLED,
         OpdAppointment.COMPLETED: NotificationAction.DOCTOR_INVOICE
         }


class SMSNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = context

    def get_template(self, user):
        notification_type = self.notification_type
        body_template = ''
        if notification_type == NotificationAction.APPOINTMENT_ACCEPTED:
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
        return body_template

    # def get_receivers(self):
    #     instance = self.appointment
    #     receivers = []
    #     notification_type = self.notification_type
    #     if not instance or not instance.user:
    #         return receivers
    #     doctor_admins = GenericAdmin.get_appointment_admins(instance)
    #     if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
    #                              NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
    #                              NotificationAction.PRESCRIPTION_UPLOADED]:
    #         receivers.append(instance.user)
    #     elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
    #                                NotificationAction.APPOINTMENT_BOOKED,
    #                                NotificationAction.APPOINTMENT_CANCELLED]:
    #         receivers.extend(doctor_admins)
    #         receivers.append(instance.user)
    #     phone_numbers = []
    #     for user in receivers:
    #         if user.user_type == User.CONSUMER:
    #             phone_number = instance.profile.phone_number
    #             # send notification to default profile also
    #             default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
    #             if default_user_profile and (
    #                     default_user_profile.id != instance.profile.id) and default_user_profile.phone_number:
    #                 phone_numbers.append(
    #                     {'user': user, 'phone_number': default_user_profile.phone_number})
    #         else:
    #             phone_number = user.phone_number
    #         phone_numbers.append({'user': user, 'phone_number': phone_number})
    #     phone_numbers = unique(phone_numbers)
    #     return phone_numbers

    def trigger(self, receiver, template, context):
        user = receiver.get('user')
        phone_number = receiver.get('phone_number')
        html_body = render_to_string(template, context=context)

        if phone_number and user:
            sms_noti = SmsNotification.objects.create(
                user=user,
                phone_number=phone_number,
                notification_type=self.notification_type,
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
            self.trigger(receiver, template, context)


class EMAILNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = context

    def get_template(self, user):
        notification_type = self.notification_type
        body_template = 'email/'
        subject_template = 'email/'
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

    # def get_receivers(self):
    #     instance = self.appointment
    #     receivers = []
    #     notification_type = self.notification_type
    #     if not instance or not instance.user:
    #         return receivers
    #     doctor_admins = GenericAdmin.get_appointment_admins(instance)
    #     if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
    #                              NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
    #                              NotificationAction.DOCTOR_INVOICE,
    #                              NotificationAction.PRESCRIPTION_UPLOADED]:
    #         receivers.append(instance.user)
    #     elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
    #                                NotificationAction.APPOINTMENT_BOOKED,
    #                                NotificationAction.APPOINTMENT_CANCELLED]:
    #         receivers.extend(doctor_admins)
    #         receivers.append(instance.user)
    #     emails = []
    #     for user in receivers:
    #         if user.user_type == User.CONSUMER:
    #             email = instance.profile.email
    #             # send notification to default profile also
    #             default_user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
    #             if default_user_profile and (
    #                     default_user_profile.id != instance.profile.id) and default_user_profile.email:
    #                 emails.append({'user': user, 'email': default_user_profile.email})
    #         else:
    #             email = user.email
    #         emails.append({'user': user, 'email': email})
    #     emails = unique(emails)
    #     return emails

    def trigger(self, receiver, template, context):
        user = receiver.get('user')
        email = receiver.get('email')
        email_subject = render_to_string(template[0], context=context)
        html_body = render_to_string(template[1], context=context)
        if email and user:
            email_noti = EmailNotification.objects.create(
                user=user,
                email=email,
                notification_type=self.notification_type,
                content=html_body,
                email_subject=email_subject
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
            self.trigger(receiver, template, context)


class APPNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = context

    def get_template(self, user):
        pass

    # def get_receivers(self):
    #     instance = self.appointment
    #     receivers = []
    #     notification_type = self.notification_type
    #     if not instance or not instance.user:
    #         return receivers
    #     doctor_admins = GenericAdmin.get_appointment_admins(instance)
    #     if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
    #                              NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
    #                              NotificationAction.PRESCRIPTION_UPLOADED]:
    #         receivers.append(instance.user)
    #     elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
    #                                NotificationAction.APPOINTMENT_BOOKED,
    #                                NotificationAction.APPOINTMENT_CANCELLED]:
    #         receivers.extend(doctor_admins)
    #         receivers.append(instance.user)
    #     return list(set(receivers))

    def trigger(self, receiver, context):
        user = receiver
        context.pop("instance", None)
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
            self.trigger(receiver, context)


class PUSHNotification:

    def __init__(self, notification_type, context=None):
        self.notification_type = notification_type
        self.context = context

    # def get_receivers(self):
    #     instance = self.appointment
    #     receivers = []
    #     notification_type = self.notification_type
    #     if not instance or not instance.user:
    #         return receivers
    #     doctor_admins = GenericAdmin.get_appointment_admins(instance)
    #     if notification_type in [NotificationAction.APPOINTMENT_ACCEPTED,
    #                              NotificationAction.APPOINTMENT_RESCHEDULED_BY_DOCTOR,
    #                              NotificationAction.PRESCRIPTION_UPLOADED]:
    #         receivers.append(instance.user)
    #     elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
    #                                NotificationAction.APPOINTMENT_BOOKED,
    #                                NotificationAction.APPOINTMENT_CANCELLED]:
    #         receivers.extend(doctor_admins)
    #         receivers.append(instance.user)
    #
    #     tokens = [{'user': token.user, 'token': token.token} for token in
    #               NotificationEndpoint.objects.filter(user__in=receivers)]
    #     tokens.sort(key=lambda x: x['user'])
    #     final_tokens = []
    #     for user, user_token_group in groupby(tokens, key=lambda x: x['user']):
    #         final_tokens.append({'user': user, 'tokens': [t['token'] for t in user_token_group]})
    #     # final_tokens = [for token in final_tokens]
    #     # tokens = unique(tokens)
    #     return final_tokens

    def trigger(self, receiver, context):
        user = receiver.get('user')
        tokens = receiver.get('tokens')
        context.pop("instance", None)
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
            self.trigger(receiver, context)


class OpdNotification(Notification):
    template_path = ''

    def __init__(self, appointment, notification_type=None):
        self.appointment = appointment
        if notification_type:
            self.notification_type = notification_type
        else:
            self.notification_type = Notification.OPD_NOTIFICATION_TYPE_MAPPING[appointment.status]

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
            "payment_type": dict(OpdAppointment.PAY_CHOICES)[self.appointment.payment_type],
            "image_url": ""
        }
        return context

    def send(self):
        context = self.get_context()
        notification_type = self.notification_type
        all_receivers = self.get_receivers()

        if notification_type == NotificationAction.DOCTOR_INVOICE:
            email_notification = EMAILNotification(notification_type, context)
            email_notification.send(all_receivers.get('email_receivers', []))
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
                                 NotificationAction.DOCTOR_INVOICE]:
            receivers.append(instance.user)
        elif notification_type in [NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT,
                                   NotificationAction.APPOINTMENT_BOOKED,
                                   NotificationAction.APPOINTMENT_CANCELLED]:
            receivers.extend(doctor_admins)
            receivers.append(instance.user)
        user_and_phone_number = []
        user_and_email = []
        app_receivers = receivers
        user_and_tokens = []

        user_and_token = [{'user': token.user, 'token': token.token} for token in
                          NotificationEndpoint.objects.filter(user__in=receivers).order_by('user')]
        # user_and_token.sort(key=lambda x: x['user'])
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
            user_and_phone_number.append({'user': user, 'phone_number': phone_number})
            user_and_email.append({'user': user, 'email': email})
        user_and_phone_number = unique(user_and_phone_number)
        user_and_email = unique(user_and_email)

        all_receivers['sms_receivers'] = user_and_phone_number
        all_receivers['email_receivers'] = user_and_email
        all_receivers['app_receivers'] = app_receivers
        all_receivers['push_receivers'] = user_and_tokens

        return all_receivers
