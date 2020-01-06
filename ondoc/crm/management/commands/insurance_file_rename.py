from django.core.management.base import BaseCommand

from ondoc.insurance.models import UserInsurance
from django.db import transaction
import uuid

class Command(BaseCommand):

    help = 'Rename Insurance COI files!'

    @transaction.atomic
    def handle(self, *args, **options):
        queryset = UserInsurance.objects.all()
        for data in queryset:
            if data.coi:
                file_name = data.coi.url

