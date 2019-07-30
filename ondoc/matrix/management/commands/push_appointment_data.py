from django.core.management import BaseCommand
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from ondoc.matrix.tasks import push_appointment_to_matrix
import logging

logger = logging.getLogger(__name__)


def push_appointment_data():
    lab_appointments = LabAppointment.objects.all()
    for l_appointment in lab_appointments:
        try:
            push_appointment_to_matrix.apply_async(
                ({'type': 'LAB_APPOINTMENT', 'appointment_id': l_appointment.id, 'product_id': 5,
                  'sub_product_id': 2},), countdown=5)
            print("Lab Appointment id "+ str(l_appointment.id) + " done")
        except Exception as e:
            print("Lab Appointment id " + str(l_appointment.id) + " has error")
            logger.error(str(e))

    opd_appointments = OpdAppointment.objects.all()
    for o_appointment in opd_appointments:
        try:
            push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': o_appointment.id,
                                                     'product_id': 5, 'sub_product_id': 2},), countdown=5)
            print("Opd Appointment id " + str(o_appointment.id) + " done")
        except Exception as e:
            print("Opd Appointment id " + str(o_appointment.id) + " has error")
            logger.error(str(e))


class Command(BaseCommand):
    def handle(self, **options):
        push_appointment_data()
