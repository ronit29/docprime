from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage
from ondoc.diagnostic.models import LabDocument


class Command(BaseCommand):
    help = 'Generate thumbnails'

    def handle(self, *args, **options):
        count=0
        for di in DoctorImage.objects.exclude(cropped_image__isnull=True).exclude(cropped_image__exact='').order_by('id'):
                try:
                    count+=1
                    print(count)
                    di.save()
                except Exception as e:
                    print(str(e))

        count=0            
        for ld in LabDocument.objects.filter(document_type=LabDocument.LOGO).order_by('id'):
                try:
                    count+=1
                    print(count)
                    ld.save()
                except Exception as e:
                    print(str(e))
