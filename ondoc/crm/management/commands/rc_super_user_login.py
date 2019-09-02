from django.core.management.base import BaseCommand
from ondoc.api.v1.utils import rc_superuser_login
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'create rocket chat super user token and user id in database'

    def handle(self, *args, **options):
        try:
            rc_superuser_login()
        except Exception as e:
            logger.error('Error in e-consultation create - ' + str(e))
        return