from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor, Hospital, MedicalCondition, PracticeSpecialization
from ondoc.diagnostic.models import Lab, LabTest


class Command(BaseCommand):
    help = 'Update search key'

    def handle(self, *args, **options):

        for sp in PracticeSpecialization.objects.all():
            sp.save()
        for mc in MedicalCondition.objects.all():
            mc.save()
        for hospital in Hospital.objects.all():
            hospital.save()
        for doctor in Doctor.objects.all():
            doctor.save()
        for lab in Lab.objects.all():
            lab.save()
        for lab_test in LabTest.objects.all():
            lab_test.save()
