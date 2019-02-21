from django.core.management.base import BaseCommand
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment


class Command(BaseCommand):
    help = 'Send a test mail using email send api'

    def handle(self, *args, **options):

        for o in OpdAppointment.objects.filter(status=7).order_by('-id'):
            try:
                o.generate_invoice()
            except Exception as e:
                print("Some error occured for OPD appointment with ID-{}. ERROR :: {}".format(o.id, str(e)))

        for l in LabAppointment.objects.filter(status=7).order_by('-id'):
            try:
                l.generate_invoice()
            except Exception as e:
                print("Some error occured for LAB appointment with ID-{}. ERROR :: {}".format(l.id, str(e)))
