from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from ondoc.doctor.models import SPOCDetails
from ondoc.diagnostic.models import LabAppointment, Hospital
from ondoc.authentication.models import GenericAdmin
from ondoc.matrix.tasks import create_or_update_lead_on_matrix
from django.db.models import Q, F, IntegerField, ExpressionWrapper, CharField
from django.db.models.functions import Cast
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'create appointment admins, if not present, for existing SPOCs'

    def handle(self, *args, **options):

        all_spocs = SPOCDetails.objects
        all_spocs_hospitals = all_spocs.filter(content_type=ContentType.objects.get_for_model(Hospital))
        spocs_with_admins = SPOCDetails.objects.prefetch_related('content_object', 'content_object__manageable_hospitals').annotate(
            chr_number=Cast('number', CharField())).filter(content_type=ContentType.objects.get_for_model(Hospital),
                                                           hospital_spocs__manageable_hospitals__phone_number=F(
                                                               'chr_number')).filter(
            Q(hospital_spocs__manageable_hospitals__permission_type=GenericAdmin.APPOINTMENT) | Q(
                hospital_spocs__manageable_hospitals__super_user_permission=True))
        spocs_without_admins = all_spocs_hospitals.exclude(
            Q(id__in=spocs_with_admins) | Q(number__isnull=True) | Q(number__lt=1000000000) | Q(number__gt=9999999999)).values('name', 'number',
                                                                                                    'hospital_spocs')
        admins_to_be_created = list()
        for spoc in spocs_without_admins:
            if len(spoc['name']) > 100:
                continue
            admins_to_be_created.append(
                GenericAdmin(name=spoc['name'], phone_number=str(spoc['number']), hospital_id=spoc['hospital_spocs'],
                             permission_type=GenericAdmin.APPOINTMENT, auto_created_from_SPOCs=True))
        try:
            GenericAdmin.objects.bulk_create(admins_to_be_created)
        except Exception as e:
            logger.error(str(e))
            print("Error while bulk creating SPOCs. ERROR :: {}".format(str(e)))
