from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from ondoc.doctor.models import SPOCDetails
from ondoc.diagnostic.models import LabAppointment, Hospital
from ondoc.authentication.models import GenericAdmin
from ondoc.matrix.tasks import create_or_update_lead_on_matrix
from django.db.models import Q


class Command(BaseCommand):
    help = 'create appointment admins, if not present, for existing SPOCs'

    def handle(self, *args, **options):

        for spoc in SPOCDetails.objects.all():
            try:
                if spoc.content_type == ContentType.objects.get_for_model(Hospital) and not GenericAdmin.objects.filter(
                        Q(phone_number=str(spoc.number), hospital=spoc.content_object),
                        Q(permission_type=GenericAdmin.APPOINTMENT) | Q(
                            super_user_permission=True)):
                    generic_admin = GenericAdmin(phone_number=str(spoc.number), hospital=spoc.content_object,
                                                 permission_type=GenericAdmin.APPOINTMENT, auto_created_from_SPOCs=True)
                    generic_admin.save()
            except Exception as e:
                print("Some error occured for SPOC with ID-{}. ERROR :: {}".format(spoc.id, str(e)))
