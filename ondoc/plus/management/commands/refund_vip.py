from django.core.management.base import BaseCommand
from django.db import transaction

from ondoc.diagnostic.models import LabAppointment
from ondoc.plus.models import PlusUser
from ondoc.subscription_plan.models import UserPlanMapping
from ondoc.doctor.models import OpdAppointment
from django.conf import settings


def refund_vip_payments():
    lab_appointments = LabAppointment.objects.filter(status=LabAppointment.CANCELLED, payment_type=OpdAppointment.VIP)
    for lab_appointment in lab_appointments:
        lab_appointment.action_refund()

    opd_appointments = OpdAppointment.objects.filter(status=OpdAppointment.CANCELLED, payment_type=OpdAppointment.VIP)
    for opd_appointment in opd_appointments:
        opd_appointment.action_refund()


class Command(BaseCommand):

    def handle(self, **options):
        refund_vip_payments()
