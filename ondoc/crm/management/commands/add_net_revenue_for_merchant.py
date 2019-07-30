from django.core.management.base import BaseCommand
import datetime
from ondoc.authentication.models import MerchantNetRevenue
from django.db import transaction


def add_net_revenue_for_merchant():
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    opd_appointments_count = OpdAppointment.objects.count()
    opd_appointments = OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED)[0:opd_appointments_count]
    appointment_wise_revenue(opd_appointments)
    print('Opd Appointment Done')

    lab_appointments_count = LabAppointment.objects.count()
    lab_appointments = LabAppointment.objects.filter(status=LabAppointment.COMPLETED)[0:lab_appointments_count]
    appointment_wise_revenue(lab_appointments)
    print('Lab Appointment Done')


def appointment_wise_revenue(all_appointments):
    with transaction.atomic():
        for appointment in all_appointments.iterator(chunk_size=100):
            created_at = datetime.datetime.strptime(appointment.created_at.strftime("%Y-%m-%d"), "%Y-%m-%d")
            financial_year_end = datetime.datetime.strptime('2019-03-31', "%Y-%m-%d")

            if created_at <= financial_year_end:
                financial_year = "2018-2019"
            else:
                financial_year = '2019-2020'

            # Create net revenue
            booking_net_revenue = appointment.get_booking_revenue()
            merchant = appointment.get_merchant
            if merchant:
                print(booking_net_revenue)
                net_revenue_obj = MerchantNetRevenue.objects.filter(merchant=merchant, financial_year=financial_year).first()
                if net_revenue_obj:
                    net_revenue_obj.total_revenue += booking_net_revenue
                    net_revenue_obj.save()
                else:
                    MerchantNetRevenue.objects.create(merchant=merchant, total_revenue=booking_net_revenue,
                                                      financial_year=financial_year)


class Command(BaseCommand):

    def handle(self, **options):
        add_net_revenue_for_merchant()

