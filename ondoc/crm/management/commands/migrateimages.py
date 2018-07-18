from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage, DoctorDocument, HospitalImage, HospitalDocument
from ondoc.diagnostic.models import LabImage, LabDocument

class Command(BaseCommand):
    help = 'Fix existing image sizes'

    def handle(self, *args, **options):
        for di in DoctorImage.objects.all():
            try:
                di.save()
            except Exception as e:
                print(e)
                pass

        for di in DoctorDocument.objects.all():
            try:
                di.save()
            except Exception as e:
                print(e)
                pass

        for li in LabImage.objects.all():
            try:
                li.save()
            except Exception as e:
                print(e)
                pass

        for ld in LabDocument.objects.all():
            try:
                ld.save()
            except Exception as e:
                print(e)
                pass

        for hi in HospitalImage.objects.all():
            try:
                hi.save()
            except Exception as e:
                print(e)
                pass

        for hd in HospitalDocument.objects.all():
            try:
                hd.save()
            except Exception as e:
                print(e)
                pass
