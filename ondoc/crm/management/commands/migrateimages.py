from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage, DoctorDocument, HospitalImage, HospitalDocument
from ondoc.diagnostic.models import LabImage, LabDocument

class Command(BaseCommand):
    help = 'Migrate Images to S3'

    def handle(self, *args, **options):
        for di in DoctorImage.objects.all():
            try:
                di.save()
            except Exception:
                print('error in image')
                pass

        for di in DoctorDocument.objects.all():
            try:
                di.save()
            except Exception:
                print('error in documents')
                pass

        for li in LabImage.objects.all():
            try:
                li.save()
            except Exception:
                print('error in lab image')

        for ld in LabDocument.objects.all():
            try:
                ld.save()
            except Exception:
                print("error in lab document")

        for hi in HospitalImage.objects.all():
            try:
                hi.save()
            except Exception:
                print("error in hospital image")

        for hd in HospitalDocument.objects.all():
            try:
                hd.save()
            except Exception:
                print("error in hospital document")
