from django.core.management.base import BaseCommand
from django.db import transaction

from ondoc.diagnostic.models import LabAppointment
from ondoc.plus.models import PlusUser
from ondoc.subscription_plan.models import UserPlanMapping
from ondoc.doctor.models import OpdAppointment
from django.conf import settings


def refund_vip_payments():
    lab_appointments = LabAppointment.objects.filter(id__in=[2000033008, 2000033002, 2000032994, 2000032911, 2000032883, 2000032842, 2000032841, 2000032834, 2000032786, 2000032592, 2000032646, 2000031547, 2000031550, 2000031549, 2000031548, 2000031095, 2000031094, 2000031093, 2000032232, 2000032175, 2000032051, 2000032044, 2000031980, 2000032673, 2000032422, 2000031546, 2000031545, 2000031561, 2000031560])
    for lab_appointment in lab_appointments:
        print(lab_appointment.id)
        lab_appointment.action_refund()

    opd_appointments = OpdAppointment.objects.filter(id__in=[1000044244,1000044069,1000044092,1000044106,1000043948,1000044006,1000043944,1000043861,1000043934,1000043855,1000043872,1000043892,1000043810,1000043838,1000043879,1000043751,1000043650,1000043770,1000043745,1000043772,1000043754,1000043750,1000043785,1000043573,1000043512,1000043313,1000043327,1000043271,1000043179,1000042893,1000042609,1000042504,1000042483,1000042389,1000042413])
    for opd_appointment in opd_appointments:
        print(opd_appointment.id)
        opd_appointment.action_refund()


class Command(BaseCommand):

    def handle(self, **options):
        refund_vip_payments()
