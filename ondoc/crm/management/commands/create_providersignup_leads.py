from django.core.management.base import BaseCommand
from ondoc.doctor.models import ProviderSignupLead
from ondoc.diagnostic.models import LabAppointment, Hospital
from ondoc.matrix.tasks import create_or_update_lead_on_matrix


class Command(BaseCommand):
    help = 'Create matrix leads for provider signup data in database without matrix lead id'

    def handle(self, *args, **options):

        for p in ProviderSignupLead.objects.filter(is_docprime=True, matrix_lead_id=None).order_by('-id'):
            try:
                create_or_update_lead_on_matrix.apply_async(({'obj_type': p.__class__.__name__, 'obj_id': p.id}
                                                             ,), countdown=5)
            except Exception as e:
                print("Some error occured for ProviderSignupLead with ID-{}. ERROR :: {}".format(p.id, str(e)))

        for h in Hospital.objects.filter(is_listed_on_docprime=True, source_type=Hospital.PROVIDER).order_by('-id'):
            try:
                create_or_update_lead_on_matrix.apply_async(({'obj_type': h.__class__.__name__, 'obj_id': h.id}
                                                             ,), countdown=5)
            except Exception as e:
                print("Some error occured for Hospital with ID-{}. ERROR :: {}".format(h.id, str(e)))
