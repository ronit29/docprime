from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage
from django.conf import settings


class Command(BaseCommand):
    help = 'Crop doctor images'

    def handle(self, *args, **options):
        for di in DoctorImage.objects.all():
            if di.cropped_image == '':
                try:
                    di.crop_image()
                except Exception as e:
                    print(str(e))
