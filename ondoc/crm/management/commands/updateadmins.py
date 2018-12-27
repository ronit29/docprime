from django.core.management.base import BaseCommand
import datetime
from ondoc.authentication import models as auth_models
from django.db import transaction


class Command(BaseCommand):

    help = 'Update Admin Permissions'

    @transaction.atomic
    def handle(self, *args, **options):
        date = datetime.datetime.strptime('17/12/18', '%d/%m/%y')
        admin_query = auth_models.GenericAdmin.objects.filter(updated_at__gte=date, entity_type=auth_models.GenericAdmin.OTHER)
        if admin_query.exists():
            admin_query.update(entity_type=auth_models.GenericAdmin.HOSPITAL)
            self.stdout.write('Successfully Updated Admin Permissions')
        else:
            self.stdout.write('No Permissions Found')


