from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage, DoctorDocument, HospitalImage, HospitalDocument
from ondoc.diagnostic.models import LabImage, LabDocument

class Command(BaseCommand):
    help = 'Fix existing image sizes'

    def handle(self, *args, **options):
        total = DoctorImage.objects.count()
        print('total doctor images'+str(total))
        counter = 0
        for di in DoctorImage.objects.all():
            counter+=1
            print('doctor images processed'+str(counter))
            try:
                di.save()
            except Exception as e:
                print(e)
                pass

        total = DoctorDocument.objects.count()
        print('total doctor documents'+str(total))
        counter = 0
        for di in DoctorDocument.objects.all():
            counter+=1
            print('doctor documents processed'+str(counter))
            try:
                di.save()
            except Exception as e:
                print(e)
                pass

        total = LabImage.objects.count()
        print('total lab images'+str(total))
        counter = 0
        for li in LabImage.objects.all():
            counter+=1
            print('lab images processed'+str(counter))
            try:
                li.save()
            except Exception as e:
                print(e)
                pass

        total = LabDocument.objects.count()
        print('total lab document'+str(total))
        counter = 0
        for ld in LabDocument.objects.all():
            counter+=1
            print('lab document processed'+str(counter))
            try:
                ld.save()
            except Exception as e:
                print(e)
                pass

        total = HospitalImage.objects.count()
        print('total hospital images'+str(total))
        counter = 0
        for hi in HospitalImage.objects.all():
            counter+=1
            print('hospital images processed'+str(counter))
            try:
                hi.save()
            except Exception as e:
                print(e)
                pass

        total = HospitalDocument.objects.count()
        print('total hospital documents'+str(total))
        counter = 0
        for hd in HospitalDocument.objects.all():
            counter+=1
            print('hospital documents processed'+str(counter))
            try:
                hd.save()
            except Exception as e:
                print(e)
                pass
