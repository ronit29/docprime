from django.core.management.base import BaseCommand

from ondoc.account.models import MerchantPayout, Order
from django.db import transaction

from ondoc.diagnostic.models import LabAppointment
from ondoc.doctor.models import OpdAppointment


class Command(BaseCommand):

    help = 'Create payouts for appointments'

    @transaction.atomic
    def handle(self, *args, **options):
        opd_appointments = OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED, merchant_payout__isnull=True)
        lab_appointments = LabAppointment.objects.filter(status=LabAppointment.COMPLETED, merchant_payout__isnull=True)

        if opd_appointments:
            for appointment in opd_appointments:
                print(str(appointment.id))
                appointment.save_merchant_payout()

        if lab_appointments:
            for appointment in lab_appointments:
                print(str(appointment.id))
                appointment.save_merchant_payout()
