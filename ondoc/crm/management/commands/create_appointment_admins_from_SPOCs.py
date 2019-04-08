from django.core.management.base import BaseCommand
from ondoc.doctor.models import SPOCDetails
from ondoc.diagnostic.models import LabAppointment, Hospital
from ondoc.authentication.models import GenericAdmin
from ondoc.matrix.tasks import create_or_update_lead_on_matrix
from django.db.models import Q


class Command(BaseCommand):
    help = 'Create matrix leads for provider signup data in database without matrix lead id'

    def handle(self, *args, **options):

        for spoc in SPOCDetails.objects.all():
            try:
                if not GenericAdmin.objects.filter(Q(phone_number=str(spoc.number), hospital=spoc.content_object),
                                               Q(write_permission=True, permission_type=GenericAdmin.APPOINTMENT) | Q(
                                                       super_user_permission=True)):
                    generic_admin = GenericAdmin(phone_number=str(spoc.number), hospital=spoc.content_object,
                                                 write_permission=True, permission_type=GenericAdmin.APPOINTMENT)
                    generic_admin.save()
            except Exception as e:
                print("Some error occured for SPOC with ID-{}. ERROR :: {}".format(spoc.id, str(e)))
