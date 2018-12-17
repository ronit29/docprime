from __future__ import absolute_import, unicode_literals

import json

from ondoc.notification.labnotificationaction import LabNotificationAction
from ondoc.notification import models as notification_models
from celery import task
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


@task
def send_lab_notifications_refactored(appointment_id):
    from ondoc.diagnostic import models as lab_models
    from ondoc.communications.models import LabNotification
    instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
    if not instance or not instance.user:
        return
    try:
        instance = lab_models.LabAppointment.objects.filter(id=appointment_id).first()
        if not instance or not instance.user:
            return
        opd_notification = LabNotification(instance)
        opd_notification.send()
    except Exception as e:
        logger.error(str(e))


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
        LabNotificationAction.trigger(
            instance=instance,
            user=instance.user,
            notification_type=notification_models.NotificationAction.LAB_APPOINTMENT_BOOKED,
        )
        return


@task()
def send_opd_notifications_refactored(appointment_id):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.communications.models import OpdNotification
    try:
        instance = OpdAppointment.objects.filter(id=appointment_id).first()
        if not instance or not instance.user:
            return

        opd_notification = OpdNotification(instance)
        opd_notification.send()
    except Exception as e:
        logger.error(str(e))


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
        notification_models.NotificationAction.trigger(
            instance=instance,
            user=instance.user,
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

@task
def send_opd_rating_message(appointment_id, type):
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    from django.conf import settings
    from django.utils.safestring import mark_safe

    data = {}
    name = ''
    if type == 'opd':
        appointment = OpdAppointment.objects.filter(id=appointment_id, is_rated=False, status=OpdAppointment.COMPLETED).first()
        name = appointment.doctor.name if appointment else None
    else:
        appointment = LabAppointment.objects.filter(id=appointment_id, is_rated=False, status=LabAppointment.COMPLETED).first()
        name = appointment.lab.name if appointment else None
    if appointment:
        number = appointment.user.phone_number
        data['phone_number'] = number
        app_url = settings.CONSUMER_APP_DOMAIN
        text_url = str(app_url)+ "/" + str(type) + "/appointment/" + str(appointment_id)
        text = '''You have successfully completed your appointment with %s . Rate your experience %s''' % (name, text_url)
        data['text'] = mark_safe(text)
        notification_models.SmsNotification.send_rating_link(data)


@task(bind=True, max_retries=5)
def set_order_dummy_transaction(self, order_id, user_id):
    from ondoc.account.models import Order, DummyTransactions
    from ondoc.account.models import User
    try:
        order_row = Order.objects.filter(id=order_id).first()
        user = User.objects.filter(id=user_id).first()

        if order_row and user and order_row.reference_id:
            if order_row.getTransactions():
                print("dummy Transaction already set")
                return

            appointment = order_row.getAppointment()
            if not appointment:
                raise Exception("No Appointment found.")

            token = settings.PG_DUMMY_TRANSACTION_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_DUMMY_TRANSACTION_URL

            req_data = {
                "customerId": user_id,
                "mobile": user.phone_number,
                "email": user.email or "dummyemail@docprime.com",
                "productId": order_row.product_id,
                "orderId": order_id,
                "name": appointment.profile.name,
                "txAmount": str(appointment.effective_price),
                "couponCode": "",
                "couponAmt": 0,
                "paymentMode": "DC",
                "AppointmentId": order_row.reference_id,
                "buCallbackSuccessUrl": "",
                "buCallbackFailureUrl": ""
            }

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                if resp_data.get("ok") is not None and resp_data.get("ok") == 1:
                    tx_data = {}
                    tx_data['user'] = user
                    tx_data['product_id'] = order_row.product_id
                    tx_data['order_no'] = resp_data.get('orderNo')
                    tx_data['order_id'] = order_row.id
                    tx_data['reference_id'] = order_row.reference_id
                    tx_data['type'] = DummyTransactions.CREDIT
                    tx_data['amount'] = 0
                    tx_data['payment_mode'] = "DC"

                    # tx_data['transaction_id'] = resp_data.get('orderNo')
                    # tx_data['response_code'] = response.get('responseCode')
                    # tx_data['bank_id'] = response.get('bankTxId')
                    # transaction_time = parse(response.get("txDate"))
                    # tx_data['transaction_date'] = transaction_time
                    # tx_data['bank_name'] = response.get('bankName')
                    # tx_data['currency'] = response.get('currency')
                    # tx_data['status_code'] = response.get('statusCode')
                    # tx_data['pg_name'] = response.get('pgGatewayName')
                    # tx_data['status_type'] = response.get('txStatus')
                    # tx_data['pb_gateway_name'] = response.get('pbGatewayName')

                    DummyTransactions.objects.create(**tx_data)
                    print("SAVED DUMMY TRANSACTION")
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))

    except Exception as e:
        logger.error("Error in Setting Dummy Transaction of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
        self.retry([order_id, user_id], countdown=300)
