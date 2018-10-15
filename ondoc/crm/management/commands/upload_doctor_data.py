from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Upload doctors via Excel'

    def handle(self, *args, **options):
        pass