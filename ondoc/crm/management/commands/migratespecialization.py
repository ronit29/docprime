from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorQualification, DoctorSpecialization, Specialization, GeneralSpecialization

class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'

    def handle(self, *args, **options):
        for sp in Specialization.objects.all():
            ex = GeneralSpecialization.objects.filter(name=sp.name)
            if len(ex)==0:
                GeneralSpecialization.objects.create(name=sp.name)

        for dq in DoctorQualification.objects.filter(specialization__isnull=False):
            gp = GeneralSpecialization.objects.filter(name=dq.specialization.name)


            if len(gp) > 0:
                ds = DoctorSpecialization.objects.filter(doctor=dq.doctor, specialization=gp[0])
                if len(ds)==0:
                    DoctorSpecialization.objects.create(doctor=dq.doctor, specialization=gp[0])
