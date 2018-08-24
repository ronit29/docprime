from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage
from ondoc.diagnostic.models import LabDocument


class Command(BaseCommand):
    help = 'Generate thumbnails'

    def handle(self, *args, **options):
        for di in DoctorImage.objects.filter(cropped_image__isnull=False):
                try:
                    di.save()
                except Exception as e:
                    print(str(e))
        for ld in LabDocument.objects.filter(document_type=LabDocument.LOGO):
                try:
                    ld.save()
                except Exception as e:
                    print(str(e))
