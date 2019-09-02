from django.core.management.base import BaseCommand
from ondoc.provider.models import RocketChatSuperUser
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'create rocket chat super user token and user id in database'

    def handle(self, *args, **options):
        try:
            RocketChatSuperUser.update_rc_super_user()
        except Exception as e:
            logger.error('Error in e-consultation create - ' + str(e))
        return