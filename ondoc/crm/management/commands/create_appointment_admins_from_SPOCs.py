from django.core.management.base import BaseCommand
from ondoc.doctor.models import SPOCDetails
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'create appointment admins, if not present, for existing SPOCs'

    def handle(self, *args, **options):
        SPOCDetails.create_appointment_admins_from_spocs()
