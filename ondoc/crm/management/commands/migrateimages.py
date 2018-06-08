from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage, DoctorDocument

class Command(BaseCommand):
    help = 'Migrate Images to S3'

    def handle(self, *args, **options):
        for di in DoctorImage.objects.all():
            try:
                di.save()
            except:
                print('error in image')
                pass

        for di in DoctorDocument.objects.all():
            try:
                di.save()
            except:
                print('error in documents')
                pass
