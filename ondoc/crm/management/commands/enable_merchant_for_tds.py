import datetime

from django.core.management.base import BaseCommand
from ondoc.account.models import Merchant
# from ondoc.common.models import TdsDeductionMixin


class Command(BaseCommand):

    def enable_merchant_for_tds(self):
        pan_card_characters = ['C', 'F', 'A', 'T', 'B', 'L', 'J', 'G']
        merchants = Merchant.objects.all()
        for merchant in merchants:
            pan_number = merchant.pan_number
            if pan_number:
                pan_character = list(pan_number)[3]
                if pan_character in pan_card_characters:
                    merchant.enable_for_tds_deductions = True
                    merchant.save()

    def add_net_revenue_for_merchant(self):
        from ondoc.doctor.models import OpdAppointment
        all_appointments = OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED)

        for appointment in all_appointments:
            net_revenue = appointment.get_booking_revenue()
            created_at = datetime.datetime.strptime(appointment.created_at.strftime("%Y-%m-%d"), "%Y-%m-%d")
            financial_year_end = datetime.datetime.strptime('2019-03-31', "%Y-%m-%d")

            if created_at <= financial_year_end:
                financial_year = "2018-2019"
            else:
                financial_year = '2019-2020'

            # Create net revenue





